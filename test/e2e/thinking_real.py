#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""真实模型端到端：deepseek-v4-flash 思考强度 4 档对比。"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.client.llm import create_llm_client_from_model
from src.client.llm.registry import (
    get_litellm_registry,
    get_supported_thinking_levels,
)


MODEL = "litellm_proxy/deepseek-v4-flash"
TEMPLATE_PRESET = "fast"
LEVELS = ["off", "low", "medium", "high", "max"]
PROMPT = "一个长方形泳池，长比宽多 3 米，周长 26 米。求面积。请给出推导过程。"


BARE_MODEL = "deepseek-v4-flash"


async def run_one(level: str) -> dict:
    reg = get_litellm_registry()
    effort = reg.resolve_reasoning_effort(MODEL, level)
    clamped = reg.clamp_thinking_level(MODEL, level)
    spec = reg.peek_thinking_spec(BARE_MODEL)
    supported = get_supported_thinking_levels(spec)

    client = create_llm_client_from_model(
        model=MODEL, chat_template_preset=TEMPLATE_PRESET,
    )

    t0 = time.perf_counter()
    full_text = ""
    thinking_text = ""
    has_thinking_stream = False
    async for chunk in client.astream(
        [{"role": "user", "content": PROMPT}],
        reasoning_effort=effort,
        max_tokens=2048,
    ):
        if not chunk.delta:
            continue
        if chunk.is_thought:
            has_thinking_stream = True
            thinking_text += chunk.delta
        else:
            full_text += chunk.delta
    elapsed = time.perf_counter() - t0

    return {
        "level": level,
        "clamped": clamped,
        "supported": supported,
        "reasoning_effort_sent": effort,
        "has_thinking_stream": has_thinking_stream,
        "thinking_len": len(thinking_text),
        "answer_len": len(full_text),
        "elapsed_s": round(elapsed, 2),
        "thinking_head": (thinking_text[:200] + "...") if thinking_text else "",
    }


async def main() -> int:
    print("=" * 78)
    print(f"  真实模型思考强度端到端: {MODEL}")
    print("=" * 78)
    reg = get_litellm_registry()
    spec = reg.peek_thinking_spec("deepseek-v4-flash")
    print(f"  模型支持档位: {get_supported_thinking_levels(spec)}")
    print(f"  默认档位   : {spec.default if spec else None}")
    print()

    results = []
    for lv in LEVELS:
        print(f"  --- 思考档位: {lv} ---")
        try:
            r = await run_one(lv)
        except Exception as e:  # noqa: BLE001
            print(f"    [ERROR] {type(e).__name__}: {e}")
            results.append({"level": lv, "error": str(e)})
            continue
        results.append(r)
        print(f"    resolve_reasoning_effort({lv!r}) = {r['reasoning_effort_sent']!r}")
        print(f"    clamp({lv!r})                   = {r['clamped']!r}")
        print(f"    流式 thinking 事件             = {r['has_thinking_stream']}")
        print(f"    thinking 长度                   = {r['thinking_len']} 字符")
        print(f"    answer 长度                     = {r['answer_len']} 字符")
        print(f"    耗时                            = {r['elapsed_s']} s")
        if r["thinking_head"]:
            print(f"    thinking 片段                   = {r['thinking_head']}")
        print()

    print("=" * 78)
    print("  断言")
    print("=" * 78)
    ok = True
    by_level = {r["level"]: r for r in results if "error" not in r}

    if "off" in by_level:
        r = by_level["off"]
        # 配置写了 "off":"none" → 透传 "none" 显式关思考；DeepSeek 等默认思考模型
        # 需要此值才能真正关闭思考链（thinking 长度应为 0）
        if r["reasoning_effort_sent"] != "none":
            print(f"  [FAIL] off 应 resolve 为 'none'，实际 {r['reasoning_effort_sent']!r}")
            ok = False
        elif r["thinking_len"] != 0:
            print(f"  [FAIL] off 应无 thinking 内容，实际长度 {r['thinking_len']}")
            ok = False
        else:
            print(f"  [PASS] off → reasoning_effort='none'，thinking=0（思考链已关闭）")
    else:
        print("  [SKIP] off 档出错"); ok = False

    if "high" in by_level:
        r = by_level["high"]
        if not isinstance(r["reasoning_effort_sent"], str):
            print(f"  [FAIL] high 应 resolve 为字符串，实际 {r['reasoning_effort_sent']!r}")
            ok = False
        elif r["thinking_len"] == 0:
            print(f"  [FAIL] high 应产生 thinking 内容，实际长度 0")
            ok = False
        else:
            print(f"  [PASS] high → reasoning_effort={r['reasoning_effort_sent']!r}, "
                  f"thinking={r['thinking_len']} 字符")
    else:
        print("  [SKIP] high 档出错"); ok = False

    avail = [lv for lv in LEVELS if lv in by_level]
    if len(avail) >= 3:
        lens = [by_level[lv]["thinking_len"] for lv in avail]
        if lens[0] <= lens[-1] and lens[0] == 0:
            print(f"  [PASS] thinking 长度单调（off 最短=0）: {dict(zip(avail, lens))}")
        else:
            print(f"  [WARN] thinking 长度未严格单调: {dict(zip(avail, lens))}")

    print()
    print("  结果汇总:")
    for r in results:
        if "error" in r:
            print(f"    {r['level']:8s} ERROR: {r['error']}")
        else:
            print(f"    {r['level']:8s} effort={r['reasoning_effort_sent']!r:12} "
                  f"thinking={r['thinking_len']:6d}  answer={r['answer_len']:6d}  "
                  f"{r['elapsed_s']}s")
    print()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
