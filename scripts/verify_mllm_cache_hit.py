#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
验证脚本：对比「单轮（不跨轮持久化）」与「跨轮持久化」下 MLLM 的 prompt 缓存命中。

背景
----
read_image_chunks（return_image_url=true）把图片以 ``image_url: <url>`` 文本行写进
role=tool 消息。OpenAI 多模态协议要求图片以结构化 image_url 内容块传入，因此
chat_service._run_loop_real 与 context_builder.rebuild_messages_from_history 会在
tool 消息后追加一条带 image_url 块的 user 消息（两者共用 build_image_followup_message，
输出逐字节一致）。本脚本直接复用该构造函数，构造一个带图片块的固定前缀，连续打两次
模型，对比第二次的 cache 命中情况，并对比「去掉图片块」的基线（模拟旧的不跨轮持久化）。

用法
----
    # 默认：用合成图表图（data URL，无需联网取图），模型走 LiteLLM Proxy
    uv run python scripts/verify_mllm_cache_hit.py --model deepseek-v4-flash

    # 用真实公网图片 URL（验证 image_url URL 形式的缓存）
    uv run python scripts/verify_mllm_cache_hit.py \
        --model deepseek-v4-flash \
        --image "https://api.hijarson.com/api/knowledge/chunk/<cid>/raw-image?token=<uid>&max_long_edge=512"

    # 用本地图片文件（自动转 data URL）
    uv run python scripts/verify_mllm_cache_hit.py --model deepseek-v4-flash --image ./chart.png

输出
----
三次调用的对比表：
  Call 1 (cold)              —— 首次发完整前缀，灌入缓存（应 miss）
  Call 2 (cross-turn 持久化) —— 同前缀 + 新一轮，前缀应命中缓存（hit>0）
  Call 3 (baseline 不持久化) —— 去掉图片块的前缀，前缀变化 → miss，且模型看不到图
"""

import argparse
import asyncio
import base64
import io
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# 让脚本在项目根目录可直接运行
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.prompts.chat.image_injection import build_image_followup_message, extract_image_urls
from src.client.llm.client import create_llm_client


# ==================== 图片准备 ====================


def _synth_chart_png() -> bytes:
    """生成一张简单的折线图 PNG，供默认自测（无需外部图片）。"""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (480, 320), "white")
    draw = ImageDraw.Draw(img)
    # 坐标轴
    draw.line([(40, 280), (460, 280)], fill="black", width=2)  # x
    draw.line([(40, 280), (40, 40)], fill="black", width=2)   # y
    # 两条折线
    pts_a = [(60, 220), (140, 160), (220, 120), (300, 90), (380, 70), (460, 60)]
    pts_b = [(60, 250), (140, 230), (220, 200), (300, 170), (380, 150), (460, 130)]
    for pts, color in ((pts_a, "red"), (pts_b, "blue")):
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=color, width=3)
        for p in pts:
            draw.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], fill=color)
    # 图例
    draw.text((50, 20), "red=A  blue=B", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _file_to_data_url(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _resolve_image_url(image_arg: Optional[str]) -> str:
    """解析 --image 参数为可放进 image_url 块的 URL/data URL。"""
    if not image_arg:
        b64 = base64.b64encode(_synth_chart_png()).decode("ascii")
        return "data:image/png;base64," + b64
    if image_arg.startswith("http://") or image_arg.startswith("https://"):
        return image_arg
    if os.path.isfile(image_arg):
        return _file_to_data_url(image_arg)
    raise SystemExit(f"--image 既不是 URL，也不是存在的本地文件: {image_arg}")


# ==================== 缓存统计抽取 ====================


def _extract_cache_stats(raw_usage: Dict[str, Any]) -> Dict[str, int]:
    """从 LiteLLM 原始 usage dict 抽取各厂商的缓存命中字段，统一成 hit/miss。"""
    def _int(v: Any) -> int:
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0

    # DeepSeek
    hit = _int(raw_usage.get("prompt_cache_hit_tokens"))
    miss = _int(raw_usage.get("prompt_cache_miss_tokens"))
    if hit or miss:
        return {"hit": hit, "miss": miss, "vendor": "deepseek"}

    # Anthropic
    cache_read = _int(raw_usage.get("cache_read_input_tokens"))
    cache_create = _int(raw_usage.get("cache_creation_input_tokens"))
    if cache_read or cache_create:
        return {"hit": cache_read, "miss": cache_create, "vendor": "anthropic"}

    # OpenAI
    details = raw_usage.get("prompt_tokens_details") or {}
    cached = _int(details.get("cached_tokens"))
    prompt = _int(raw_usage.get("prompt_tokens"))
    if cached or prompt:
        return {"hit": cached, "miss": max(0, prompt - cached), "vendor": "openai"}

    return {"hit": 0, "miss": _int(raw_usage.get("prompt_tokens")), "vendor": "unknown"}


# ==================== 消息构造 ====================


SYSTEM_PROMPT = "你是一个能看图的知识问答助手。回答尽量简短。"
TOOL_RESULT_TEXT_TEMPLATE = (
    "--- chunk_id=chunk-test-0001, page=1 ---\n"
    "mode: direct_image\n"
    "image_url: {image_url}\n"
    "caption: 示例折线图\n"
    "footnote: 无\n"
    "note: image_url 为公网直读 URL，已作为 image_url 内容块附在下一条 user 消息中。"
)
QUESTION_T1 = "请描述这张图里有哪些线，分别是什么颜色。"
QUESTION_T2 = "红色线 A 的最高点大约在图的最右侧还是最左侧？"


def _build_prefix(image_url: str) -> List[Dict[str, Any]]:
    """构造带图片块的固定前缀（模拟 chat_service 注入后的历史）。"""
    tool_content = TOOL_RESULT_TEXT_TEMPLATE.format(image_url=image_url)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": QUESTION_T1},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_test_1",
                "type": "function",
                "function": {
                    "name": "read_image_chunks",
                    "arguments": '{"chunk_ids": ["chunk-test-0001"], "return_image_url": true}',
                },
            }],
        },
        {"role": "tool", "tool_call_id": "call_test_1", "content": tool_content},
        # 与 chat_service._run_loop_real / context_builder.rebuild 共用同一构造函数
        build_image_followup_message(extract_image_urls(tool_content)),
    ]


def _build_prefix_no_image(image_url: str) -> List[Dict[str, Any]]:
    """基线前缀：模拟旧的不跨轮持久化——既不追加 image_url 块，也去掉 tool 文本
    里的 ``image_url:`` 行（生产环境该行是短公网 URL，token 很少；真正占 token 的
    图片内容只来自 followup 块）。data URL 测试时若保留该行会因 base64 巨大而误命中。
    """
    tool_content = TOOL_RESULT_TEXT_TEMPLATE.format(image_url=image_url)
    # 去掉 image_url 行，避免 data URL 场景下 tool 文本本身携带巨大 base64 干扰对比
    import re as _re
    tool_content = _re.sub(r"^image_url:\s*\S+\s*$", "image_url: (unavailable)", tool_content, flags=_re.MULTILINE)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": QUESTION_T1},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_test_1",
                "type": "function",
                "function": {
                    "name": "read_image_chunks",
                    "arguments": '{"chunk_ids": ["chunk-test-0001"], "return_image_url": true}',
                },
            }],
        },
        {"role": "tool", "tool_call_id": "call_test_1", "content": tool_content},
        # 注意：这里不再追加 image_url 块
    ]


# ==================== 主流程 ====================


async def _call(client: Any, messages: List[Dict[str, Any]], label: str) -> Tuple[Dict[str, int], str, float]:
    t0 = time.perf_counter()
    try:
        resp = await client.agenerate(messages, max_tokens=256)
    except Exception as e:  # noqa: BLE001
        print(f"\n[{label}] 调用失败: {e}")
        return {"hit": 0, "miss": 0, "vendor": "error"}, "", 0.0
    elapsed = (time.perf_counter() - t0) * 1000
    stats = _extract_cache_stats(resp.raw.get("usage") or {})
    answer = (resp.content or "").strip().replace("\n", " ")
    return stats, answer, elapsed


async def main() -> int:
    parser = argparse.ArgumentParser(description="对比 MLLM 单轮/跨轮 prompt 缓存命中")
    parser.add_argument("--model", default="deepseek-v4-flash",
                        help="LiteLLM 模型字符串（裸名会自动补 litellm_proxy/ 前缀），默认 deepseek-v4-flash")
    parser.add_argument("--image", default=None,
                        help="图片 URL / 本地文件路径；省略则合成一张图表图（data URL）")
    parser.add_argument("--gap", type=float, default=2.0,
                        help="两次调用之间的间隔秒数（默认 2.0），便于厂商缓存落盘")
    args = parser.parse_args()

    image_url = _resolve_image_url(args.image)
    print(f"模型: {args.model}")
    print(f"图片形式: {'URL' if image_url.startswith('http') else 'data URL (合成/本地)'}")
    print(f"图片块前缀长度: {len(image_url)} 字符")
    print("=" * 78)

    client = create_llm_client(model=args.model)

    # ---- Call 1: cold，灌入缓存 ----
    prefix = _build_prefix(image_url)
    msgs1 = prefix + [{"role": "user", "content": QUESTION_T2}]
    s1, a1, e1 = await _call(client, msgs1, "Call 1 cold")
    print(f"[Call 1 cold]            hit={s1['hit']:>6}  miss={s1['miss']:>6}  "
          f"({s1['vendor']})  {e1:.0f}ms")
    print(f"  答: {a1[:200]}")

    await asyncio.sleep(args.gap)

    # ---- Call 2: 跨轮持久化（同前缀 + 新一轮）----
    msgs2 = prefix + [{"role": "user", "content": QUESTION_T2}]
    s2, a2, e2 = await _call(client, msgs2, "Call 2 persisted")
    print(f"[Call 2 cross-turn 持久] hit={s2['hit']:>6}  miss={s2['miss']:>6}  "
          f"({s2['vendor']})  {e2:.0f}ms")
    print(f"  答: {a2[:200]}")

    await asyncio.sleep(args.gap)

    # ---- Call 3: 基线（不持久化，前缀去掉图片块）----
    prefix_no = _build_prefix_no_image(image_url)
    msgs3 = prefix_no + [{"role": "user", "content": QUESTION_T2}]
    s3, a3, e3 = await _call(client, msgs3, "Call 3 baseline")
    print(f"[Call 3 baseline 不持久] hit={s3['hit']:>6}  miss={s3['miss']:>6}  "
          f"({s3['vendor']})  {e3:.0f}ms")
    print(f"  答: {a3[:200]}")

    print("=" * 78)
    print("判定：")
    if s2["hit"] > 0:
        print(f"  ✓ 跨轮持久化命中厂商缓存（hit={s2['hit']}），命中段按缓存价计费。")
    else:
        print(f"  ✗ 跨轮持久化未命中缓存（hit=0）。可能原因：厂商未缓存图片 token / "
              f"前缀仍存在差异 / 缓存 TTL 过期 / 该 provider 不支持。")
    if s3["hit"] == 0:
        print(f"  ✓ 基线（去掉图片块）未命中缓存，符合预期——前缀变化导致 miss。")
    else:
        print(f"  ? 基线竟命中缓存（hit={s3['hit']}），可能是厂商按 system 段单独缓存。")
    print("  另外对比 Call 2 与 Call 3 的回答：Call 2 应能描述图片细节，Call 3 看不到图。")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
