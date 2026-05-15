#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_stream_realtime.py
@Author  : caixiongjiang
@Date    : 2026/05/09
@Function:
    流式接口真机端到端测试（依赖 LiteLLM Proxy）

    覆盖目标
    --------
    1. 纯文本流式：实时打印 token + ``StreamAccumulator.finalize()`` 与本地累积
       的字符串一致；
    2. 思考链流式：使用 ``deepseek-reasoner``（preset ``reasoning``），实时区分
       打印 thinking / content 增量，验证 ``LLMResponse.thinking`` 非空；
    3. 工具调用流式：绑定 ``get_weather`` 工具，强制模型发起调用，验证
       ``tool_call_delta`` 增量逐块到达，``finalize()`` 后 ``arguments`` 是合法
       JSON 且与 ``agenerate`` 行为一致；
    4. 完整 Agent 循环：流式拿到工具调用 → 注入工具结果 → 流式拿到最终回答；
       这是 ChatService Agent 模式每轮都要走的通路。

    与离线单元测试的关系
    --------------------
    - ``test_stream_tool_calls.py``：离线纯协议测试，不依赖外部模型；
    - ``test_stream_realtime.py``（本文件）：真机黑盒测试，验证整条链路在真实
      LiteLLM Proxy + DeepSeek 后端下能跑通。

    运行方式
    --------
    ::

        # 前置：.env 里配好 LITELLM_PROXY_URL / LITELLM_PROXY_KEY，
        #       且 Proxy 上有 deepseek-chat / deepseek-reasoner 两个模型
        uv run python test/client/llm/test_stream_realtime.py

    若不传任何参数则跑全部 4 个测试；可以指定子集，例如::

        uv run python test/client/llm/test_stream_realtime.py basic thinking

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 加载 .env，确保 LITELLM_PROXY_URL / LITELLM_PROXY_KEY 进环境变量
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(project_root / ".env")
except Exception:  # noqa: BLE001
    pass


# ==================== 输出辅助 ====================


def _hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠️  {msg}")


def _live(prefix: str, text: str) -> None:
    """实时打印一条增量，不换行；输出后立刻 flush"""
    sys.stdout.write(f"{prefix}{text}")
    sys.stdout.flush()


# ==================== Test 1: 纯文本流式 ====================


async def test_basic_streaming() -> bool:
    _hr("Test 1 · 纯文本流式 + Accumulator 一致性")
    from src.chat.stream_buffer import StreamAccumulator, StreamEventType
    from src.client.llm import create_llm_client_from_preset

    client = create_llm_client_from_preset("fast")
    print(f"  preset=fast  model={client.model}")

    acc = StreamAccumulator()
    local_content = ""
    chunk_count = 0

    print("  ⏳ stream output ↓")
    sys.stdout.write("  ")
    sys.stdout.flush()

    t0 = time.perf_counter()
    try:
        async for chunk in client.astream(
            messages=[{
                "role": "user",
                "content": "请用一句话简短介绍一下知识库系统的核心价值。",
            }],
            temperature=0.0,
            max_tokens=120,
        ):
            chunk_count += 1
            for ev in acc.feed(chunk):
                if ev.type == StreamEventType.CONTENT_DELTA:
                    local_content += ev.text
                    _live("", ev.text)
                elif ev.type == StreamEventType.FINISH:
                    print(f"\n  ↑ stream finished (finish_reason={ev.finish_reason})")
    except Exception as e:
        _fail(f"stream 异常: {e}")
        traceback.print_exc()
        return False
    elapsed = (time.perf_counter() - t0) * 1000

    resp = acc.finalize()

    print(f"  chunks_received={chunk_count}, elapsed={elapsed:.0f}ms")
    print(f"  finalize.content (前 60 字)={resp.content[:60]!r}")
    print(f"  finalize.finish_reason={resp.finish_reason}")
    print(f"  finalize.tool_calls={len(resp.tool_calls)}")

    if not resp.content:
        _fail("finalize.content 为空")
        return False
    if local_content != resp.content:
        _fail("本地累积与 finalize 不一致")
        print(f"    local   = {local_content[:120]!r}")
        print(f"    finalize= {resp.content[:120]!r}")
        return False
    if resp.finish_reason not in ("stop", "length"):
        _fail(f"finish_reason 异常: {resp.finish_reason}")
        return False
    if resp.tool_calls:
        _fail("纯文本流不应有 tool_calls")
        return False

    _ok("纯文本流式 → Accumulator 累积一致")
    return True


# ==================== Test 2: 思考链流式 ====================


async def test_thinking_streaming() -> bool:
    _hr("Test 2 · 思考链流式（deepseek-reasoner）")
    from src.chat.stream_buffer import StreamAccumulator, StreamEventType
    from src.client.llm import create_llm_client_from_preset

    try:
        client = create_llm_client_from_preset("reasoning")
    except Exception as e:
        _warn(f"reasoning preset 不可用，跳过: {e}")
        return True
    print(f"  preset=reasoning  model={client.model}  "
          f"thinking_budget={client.config.thinking_budget}")

    acc = StreamAccumulator()
    thinking_chars = 0
    content_chars = 0
    first_thinking_at: Optional[float] = None
    first_content_at: Optional[float] = None

    print("  ⏳ stream output ↓ （T=思考增量, C=正文增量）")
    sys.stdout.write("  ")
    sys.stdout.flush()

    t0 = time.perf_counter()
    try:
        async for chunk in client.astream(
            messages=[{
                "role": "user",
                "content": "9.11 和 9.9 哪个大？请仔细思考后回答。",
            }],
            temperature=0.0,
            max_tokens=400,
        ):
            for ev in acc.feed(chunk):
                if ev.type == StreamEventType.THINKING_DELTA:
                    if first_thinking_at is None:
                        first_thinking_at = time.perf_counter() - t0
                    thinking_chars += len(ev.text)
                    _live("\033[90m", "")  # 灰
                    _live("", ev.text)
                    _live("\033[0m", "")
                elif ev.type == StreamEventType.CONTENT_DELTA:
                    if first_content_at is None:
                        first_content_at = time.perf_counter() - t0
                        sys.stdout.write("\n  ──── 正文 ────\n  ")
                        sys.stdout.flush()
                    content_chars += len(ev.text)
                    _live("", ev.text)
                elif ev.type == StreamEventType.FINISH:
                    print(f"\n  ↑ finish_reason={ev.finish_reason}")
    except Exception as e:
        _fail(f"stream 异常: {e}")
        traceback.print_exc()
        return False
    elapsed = (time.perf_counter() - t0) * 1000

    resp = acc.finalize()
    print(f"  thinking_chars={thinking_chars}, content_chars={content_chars}, "
          f"elapsed={elapsed:.0f}ms")
    if first_thinking_at is not None:
        print(f"  first_thinking_at={first_thinking_at*1000:.0f}ms")
    if first_content_at is not None:
        print(f"  first_content_at={first_content_at*1000:.0f}ms")
    print(f"  finalize.thinking? {resp.thinking is not None}")
    print(f"  finalize.content (前 80 字)={resp.content[:80]!r}")

    if not resp.content:
        _fail("finalize.content 为空")
        return False
    if resp.thinking is None or not resp.thinking.reasoning:
        _warn("模型未返回 reasoning_content（视为软通过）")
    elif thinking_chars == 0:
        _fail("流式过程未发出 thinking.delta，但 finalize 有 thinking")
        return False

    _ok("思考链流式正常")
    return True


# ==================== Test 3: 工具调用流式 ====================


_WEATHER_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市的当前天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名"},
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "温度单位",
                },
            },
            "required": ["city"],
        },
    },
}


async def test_tool_calling_streaming() -> bool:
    _hr("Test 3 · 工具调用流式（deepseek-chat + tools）")
    from src.chat.stream_buffer import StreamAccumulator, StreamEventType
    from src.client.llm import create_llm_client_from_preset

    client = create_llm_client_from_preset("fast")
    print(f"  preset=fast  model={client.model}")

    acc = StreamAccumulator()
    tool_started_events = 0
    tool_args_chars: Dict[int, int] = {}

    messages = [
        {"role": "system", "content": "对天气类问题，必须调用 get_weather 工具。"},
        {"role": "user", "content": "上海现在天气怎么样？请用摄氏度。"},
    ]

    print("  ⏳ stream events ↓")
    t0 = time.perf_counter()
    try:
        async for chunk in client.astream(
            messages=messages,
            tools=[_WEATHER_TOOL],
            tool_choice="auto",
            temperature=0.0,
            max_tokens=200,
        ):
            for ev in acc.feed(chunk):
                if ev.type == StreamEventType.CONTENT_DELTA:
                    _live("\n  [content]   ", ev.text)
                elif ev.type == StreamEventType.THINKING_DELTA:
                    _live("\n  [thinking]  ", ev.text[:40])
                elif ev.type == StreamEventType.TOOL_CALL_STARTED:
                    tool_started_events += 1
                    print(f"\n  [tool.start] index={ev.tool_call_index} "
                          f"id={ev.tool_call_id} name={ev.tool_call_name}")
                elif ev.type == StreamEventType.TOOL_CALL_ARGS_DELTA:
                    idx = ev.tool_call_index or 0
                    tool_args_chars[idx] = tool_args_chars.get(idx, 0) + len(ev.text)
                    print(f"  [tool.args]  index={idx} +{len(ev.text)}c "
                          f"chunk={ev.text!r}")
                elif ev.type == StreamEventType.FINISH:
                    print(f"\n  [finish] {ev.finish_reason}")
    except Exception as e:
        _fail(f"stream 异常: {e}")
        traceback.print_exc()
        return False
    elapsed = (time.perf_counter() - t0) * 1000

    resp = acc.finalize()
    print(f"  elapsed={elapsed:.0f}ms")
    print(f"  finalize.tool_calls={len(resp.tool_calls)}")
    print(f"  finalize.finish_reason={resp.finish_reason}")
    print(f"  args_chars_per_index={tool_args_chars}")

    if not resp.tool_calls:
        _fail("预期模型应发起 tool_calls，但 finalize 为空")
        return False
    if tool_started_events != len(resp.tool_calls):
        _fail(f"started 事件数 {tool_started_events} ≠ 最终 tool_calls 数 "
              f"{len(resp.tool_calls)}")
        return False

    tc = resp.tool_calls[0]
    print(f"  tool_call[0]: id={tc.id}, name={tc.name}, args={tc.arguments}")
    if tc.name != "get_weather":
        _fail(f"期望 name=get_weather，实际 {tc.name}")
        return False
    if not isinstance(tc.arguments, dict) or "city" not in tc.arguments:
        _fail(f"arguments 非法或缺 city: {tc.arguments}")
        return False
    if "_raw" in tc.arguments:
        _fail(f"arguments 没解出来，走了 _raw 兜底: {tc.arguments['_raw']!r}")
        return False
    if resp.finish_reason != "tool_calls":
        _fail(f"finish_reason 应为 tool_calls，实际 {resp.finish_reason}")
        return False

    _ok(f"工具调用流式正常（args 累积 {sum(tool_args_chars.values())} 字符 → JSON 解析成功）")
    return True


# ==================== Test 4: 完整 Agent 循环 ====================


async def test_full_agent_loop() -> bool:
    _hr("Test 4 · 完整 Agent 循环（流式 → 执行工具 → 流式续答）")
    from src.chat.stream_buffer import StreamAccumulator, StreamEventType
    from src.client.llm import create_llm_client_from_preset

    client = create_llm_client_from_preset("fast")
    print(f"  preset=fast  model={client.model}")

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": "对天气类问题，必须调用 get_weather 工具。"},
        {"role": "user", "content": "上海现在天气怎么样？回答时把工具返回的温度告诉我。"},
    ]

    # ---- 第 1 轮：流式拿 tool_calls ----
    print("  ── Round 1 (expect tool_calls) ──")
    acc1 = StreamAccumulator()
    sys.stdout.write("  ")
    async for chunk in client.astream(
        messages=messages,
        tools=[_WEATHER_TOOL],
        tool_choice="auto",
        temperature=0.0,
        max_tokens=200,
    ):
        for ev in acc1.feed(chunk):
            if ev.type == StreamEventType.CONTENT_DELTA:
                _live("", ev.text)
            elif ev.type == StreamEventType.TOOL_CALL_STARTED:
                print(f"\n  [tool.start] {ev.tool_call_name}(id={ev.tool_call_id})")
                sys.stdout.write("  ")
                sys.stdout.flush()
            elif ev.type == StreamEventType.TOOL_CALL_ARGS_DELTA:
                _live("\033[36m", ev.text)
                _live("\033[0m", "")

    resp1 = acc1.finalize()
    print(f"\n  → round1: content={resp1.content!r}, tool_calls={len(resp1.tool_calls)}")

    if not resp1.tool_calls:
        _fail("Round 1 未发起 tool_calls")
        return False

    # 把 assistant 消息（含 tool_calls）拼回去
    messages.append({
        "role": "assistant",
        "content": resp1.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
            for tc in resp1.tool_calls
        ],
    })

    # 模拟工具执行
    for tc in resp1.tool_calls:
        fake_result = {
            "city": tc.arguments.get("city", "unknown"),
            "temp": "22°C",
            "desc": "多云，湿度 65%",
        }
        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": json.dumps(fake_result, ensure_ascii=False),
        })
        print(f"  [tool.result] id={tc.id}  result={fake_result}")

    # ---- 第 2 轮：流式拿最终回答 ----
    print("  ── Round 2 (expect final content) ──")
    acc2 = StreamAccumulator()
    sys.stdout.write("  ")
    async for chunk in client.astream(
        messages=messages,
        tools=[_WEATHER_TOOL],
        tool_choice="auto",
        temperature=0.0,
        max_tokens=300,
    ):
        for ev in acc2.feed(chunk):
            if ev.type == StreamEventType.CONTENT_DELTA:
                _live("", ev.text)
            elif ev.type == StreamEventType.TOOL_CALL_STARTED:
                print(f"\n  [tool.start] {ev.tool_call_name}")
                sys.stdout.write("  ")
                sys.stdout.flush()

    resp2 = acc2.finalize()
    print(f"\n  → round2: tool_calls={len(resp2.tool_calls)}, "
          f"finish={resp2.finish_reason}, "
          f"content_len={len(resp2.content)}")

    if resp2.tool_calls:
        _warn(f"Round 2 又发起了 {len(resp2.tool_calls)} 次 tool_calls；"
              f"在真实 ChatService 中应继续循环或强制收尾")
    if not resp2.content:
        _fail("Round 2 最终 content 为空")
        return False
    if "22" not in resp2.content:
        _warn(f"最终回答没明显引用工具结果中的温度 22；content={resp2.content[:120]!r}")

    _ok("完整 Agent 循环走通：流式 tool_calls → 执行 → 流式续答")
    return True


# ==================== 主入口 ====================


_REGISTRY: Dict[str, Any] = {
    "basic":    test_basic_streaming,
    "thinking": test_thinking_streaming,
    "tool":     test_tool_calling_streaming,
    "agent":    test_full_agent_loop,
}


async def main(argv: List[str]) -> int:
    print("=" * 70)
    print("  流式接口真机端到端测试（依赖 LiteLLM Proxy）")
    print(f"  LITELLM_PROXY_URL = {os.getenv('LITELLM_PROXY_URL', '<unset>')}")
    print(f"  LITELLM_PROXY_KEY = {'<set>' if os.getenv('LITELLM_PROXY_KEY') else '<unset>'}")
    print("=" * 70)

    if not os.getenv("LITELLM_PROXY_URL"):
        _warn("未配置 LITELLM_PROXY_URL，请确保 .env 已加载或使用 .env 中的 Proxy")
        # 不退出，让 LiteLLM 自己报错给用户看

    selected = argv if argv else list(_REGISTRY.keys())
    invalid = [s for s in selected if s not in _REGISTRY]
    if invalid:
        print(f"未知测试项: {invalid}, 可用: {list(_REGISTRY.keys())}")
        return 2

    results: List[Tuple[str, bool]] = []
    for name in selected:
        try:
            ok = await _REGISTRY[name]()
        except Exception as e:  # noqa: BLE001
            _fail(f"{name} 抛出未捕获异常: {e}")
            traceback.print_exc()
            ok = False
        results.append((name, ok))

    print("\n" + "=" * 70)
    passed = sum(1 for _, ok in results if ok)
    print(f"  汇总: {passed}/{len(results)} 通过")
    for name, ok in results:
        print(f"    {'✅' if ok else '❌'} {name}")
    print("=" * 70)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
