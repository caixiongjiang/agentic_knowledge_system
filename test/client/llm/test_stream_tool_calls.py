#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_stream_tool_calls.py
@Author  : caixiongjiang
@Date    : 2026/05/09
@Function:
    流式工具调用累积单元测试（Phase 0 验收用例）

    覆盖目标
    --------
    1. ``_yield_stream_chunks`` 能正确把 LiteLLM 风格 ``delta.tool_calls``
       拆成 ``StreamChunk(tool_call_delta=...)``；
    2. ``StreamAccumulator`` 按 ``index`` 聚合 OpenAI / Anthropic 两种风格的
       工具调用增量，``finalize()`` 输出的 ``LLMResponse`` 与
       ``LLMClient.agenerate`` 行为一致；
    3. 正文 / 思考 / 工具混合流的事件序列符合预期；
    4. ``arguments`` 增量跨多块拼接后能正确 JSON 解析；非法 JSON 走 ``_raw`` 兜底；
    5. 单回复并行多工具（``index=0`` 与 ``index=1`` 增量交错）能正确归位；
    6. ``finish_reason`` 缺失但累积到 ``tool_calls`` 时自动归一化为 ``tool_calls``。

    运行::

        uv run python test/client/llm/test_stream_tool_calls.py
        # 或
        uv run pytest test/client/llm/test_stream_tool_calls.py -v

    设计说明
    --------
    本测试**不依赖外部 LiteLLM Proxy / 模型供应商**，全部用构造的
    ``MockLiteLLMChunk`` 喂入 ``_yield_stream_chunks``，纯单元测试，
    可在离线 CI 中运行。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.chat.stream_buffer import (
    StreamAccumulator,
    StreamEvent,
    StreamEventType,
)
from src.client.llm.client import _yield_stream_chunks
from src.client.llm.types import StreamChunk


# ==================== 辅助：构造 LiteLLM 风格 chunk ====================


class MockLiteLLMChunk:
    """模拟 LiteLLM 流式响应的单个 chunk

    LiteLLM 真实对象有 ``model_dump()`` 方法，``_yield_stream_chunks`` 优先调用它。
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data

    def model_dump(self) -> Dict[str, Any]:
        return self._data


def _make_chunk(
    *,
    content: Optional[str] = None,
    reasoning: Optional[str] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    finish_reason: Optional[str] = None,
    model: str = "openai/gpt-4o-mini",
) -> MockLiteLLMChunk:
    """构造单个 LiteLLM 风格的 chunk dict"""
    delta: Dict[str, Any] = {}
    if content is not None:
        delta["content"] = content
    if reasoning is not None:
        delta["reasoning_content"] = reasoning
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    return MockLiteLLMChunk({
        "model": model,
        "choices": [
            {
                "delta": delta,
                "finish_reason": finish_reason,
            },
        ],
    })


def _expand(chunks: List[MockLiteLLMChunk]) -> List[StreamChunk]:
    """把若干 LiteLLM chunk 顺序展开为 StreamChunk 列表"""
    out: List[StreamChunk] = []
    for c in chunks:
        out.extend(_yield_stream_chunks(c))
    return out


def _feed_all(acc: StreamAccumulator, chunks: List[MockLiteLLMChunk]) -> List[StreamEvent]:
    """喂入所有 chunk，返回累积器透出的所有事件"""
    events: List[StreamEvent] = []
    for c in chunks:
        for sc in _yield_stream_chunks(c):
            events.extend(acc.feed(sc))
    return events


# ==================== 输出辅助 ====================


def _hr(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


# ==================== Test 1: 纯文本流 ====================


def test_pure_text_stream() -> bool:
    _hr("Test 1 · 纯文本流（无工具）")
    chunks = [
        _make_chunk(content="Hello"),
        _make_chunk(content=", "),
        _make_chunk(content="world"),
        _make_chunk(content="!", finish_reason="stop"),
    ]
    sc_list = _expand(chunks)
    # 4 个 content + 1 个 finish
    if len(sc_list) != 5:
        _fail(f"期望 5 个 StreamChunk，实际 {len(sc_list)}")
        return False
    if not all(c.tool_call_delta is None for c in sc_list):
        _fail("纯文本流不应出现 tool_call_delta")
        return False

    acc = StreamAccumulator()
    events = _feed_all(acc, chunks)
    if acc.content != "Hello, world!":
        _fail(f"content 累积错误：{acc.content!r}")
        return False
    if acc.has_tool_calls:
        _fail("不应有 tool_calls")
        return False
    if acc.finish_reason != "stop":
        _fail(f"finish_reason 错误：{acc.finish_reason}")
        return False
    content_events = [e for e in events if e.type == StreamEventType.CONTENT_DELTA]
    if len(content_events) != 4:
        _fail(f"期望 4 个 content.delta，实际 {len(content_events)}")
        return False

    resp = acc.finalize()
    if resp.content != "Hello, world!" or resp.tool_calls:
        _fail(f"LLMResponse 不一致: {resp}")
        return False
    if resp.finish_reason != "stop":
        _fail(f"LLMResponse.finish_reason: {resp.finish_reason}")
        return False
    _ok("纯文本流累积正确")
    return True


# ==================== Test 2: 思考 + 正文 ====================


def test_thinking_and_content() -> bool:
    _hr("Test 2 · 思考链 + 正文混合流")
    chunks = [
        _make_chunk(reasoning="先想想"),
        _make_chunk(reasoning="..."),
        _make_chunk(content="答案是"),
        _make_chunk(content=" 42", finish_reason="stop"),
    ]
    acc = StreamAccumulator()
    events = _feed_all(acc, chunks)

    if acc.thinking_text != "先想想...":
        _fail(f"thinking 累积错误: {acc.thinking_text!r}")
        return False
    if acc.content != "答案是 42":
        _fail(f"content 累积错误: {acc.content!r}")
        return False

    th_events = [e for e in events if e.type == StreamEventType.THINKING_DELTA]
    ct_events = [e for e in events if e.type == StreamEventType.CONTENT_DELTA]
    if len(th_events) != 2 or len(ct_events) != 2:
        _fail(f"事件数错误: thinking={len(th_events)}, content={len(ct_events)}")
        return False

    resp = acc.finalize()
    if resp.thinking is None or resp.thinking.reasoning != "先想想...":
        _fail("LLMResponse.thinking 缺失")
        return False
    _ok("思考 + 正文混合流累积正确")
    return True


# ==================== Test 3: OpenAI 风格单工具调用（多块增量） ====================


def test_openai_style_single_tool_call() -> bool:
    _hr("Test 3 · OpenAI 风格：单工具调用，arguments 跨块增量")
    # 首块带 id 和 function.name，后续块只带 arguments 增量
    chunks = [
        _make_chunk(tool_calls=[{
            "index": 0,
            "id": "call_abc",
            "type": "function",
            "function": {"name": "get_weather", "arguments": ""},
        }]),
        _make_chunk(tool_calls=[{
            "index": 0,
            "function": {"arguments": '{"city":"'},
        }]),
        _make_chunk(tool_calls=[{
            "index": 0,
            "function": {"arguments": "上海"},
        }]),
        _make_chunk(tool_calls=[{
            "index": 0,
            "function": {"arguments": '"}'},
        }]),
        _make_chunk(finish_reason="tool_calls"),
    ]

    sc_list = _expand(chunks)
    tcd_chunks = [c for c in sc_list if c.tool_call_delta is not None]
    if not tcd_chunks:
        _fail("未产生 tool_call_delta StreamChunk")
        return False

    acc = StreamAccumulator()
    events = _feed_all(acc, chunks)

    started = [e for e in events if e.type == StreamEventType.TOOL_CALL_STARTED]
    args_delta = [e for e in events if e.type == StreamEventType.TOOL_CALL_ARGS_DELTA]

    if len(started) != 1:
        _fail(f"期望 1 次 tool_call.started，实际 {len(started)}")
        return False
    if started[0].tool_call_id != "call_abc" or started[0].tool_call_name != "get_weather":
        _fail(f"started 字段错误: id={started[0].tool_call_id}, name={started[0].tool_call_name}")
        return False

    if len(args_delta) != 3:
        _fail(f"期望 3 次 args_delta（首块 arguments=''被忽略），实际 {len(args_delta)}")
        return False

    resp = acc.finalize()
    if len(resp.tool_calls) != 1:
        _fail(f"期望 1 个 tool_call，实际 {len(resp.tool_calls)}")
        return False
    tc = resp.tool_calls[0]
    if tc.id != "call_abc" or tc.name != "get_weather":
        _fail(f"tool_call 字段错误: {tc}")
        return False
    if tc.arguments != {"city": "上海"}:
        _fail(f"arguments 解析错误: {tc.arguments}")
        return False
    if resp.finish_reason != "tool_calls":
        _fail(f"finish_reason 应为 tool_calls，实际 {resp.finish_reason}")
        return False

    _ok("OpenAI 风格单工具调用流式累积正确")
    return True


# ==================== Test 4: OpenAI 风格并行多工具 ====================


def test_openai_style_parallel_tool_calls() -> bool:
    _hr("Test 4 · OpenAI 风格：单回复并行多工具，index 交错")
    # index=0 与 index=1 的增量交错出现
    chunks = [
        _make_chunk(tool_calls=[{
            "index": 0, "id": "c0", "type": "function",
            "function": {"name": "f_a", "arguments": ""},
        }]),
        _make_chunk(tool_calls=[{
            "index": 1, "id": "c1", "type": "function",
            "function": {"name": "f_b", "arguments": ""},
        }]),
        _make_chunk(tool_calls=[{
            "index": 0, "function": {"arguments": '{"x":1}'},
        }]),
        _make_chunk(tool_calls=[{
            "index": 1, "function": {"arguments": '{"y":'},
        }]),
        _make_chunk(tool_calls=[{
            "index": 1, "function": {"arguments": '2}'},
        }]),
        _make_chunk(finish_reason="tool_calls"),
    ]

    acc = StreamAccumulator()
    events = _feed_all(acc, chunks)

    started_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_STARTED]
    if len(started_events) != 2:
        _fail(f"期望 2 次 tool_call.started，实际 {len(started_events)}")
        return False

    started_indices = sorted(e.tool_call_index for e in started_events)
    if started_indices != [0, 1]:
        _fail(f"started index 错误: {started_indices}")
        return False

    resp = acc.finalize()
    if len(resp.tool_calls) != 2:
        _fail(f"期望 2 个 tool_call，实际 {len(resp.tool_calls)}")
        return False

    by_id = {tc.id: tc for tc in resp.tool_calls}
    if by_id["c0"].arguments != {"x": 1}:
        _fail(f"c0 arguments 错误: {by_id['c0'].arguments}")
        return False
    if by_id["c1"].arguments != {"y": 2}:
        _fail(f"c1 arguments 错误: {by_id['c1'].arguments}")
        return False
    _ok("并行多工具 index 交错累积正确")
    return True


# ==================== Test 5: Anthropic 风格（一次性给完整 tool_call） ====================


def test_anthropic_style_complete_tool_call() -> bool:
    _hr("Test 5 · Anthropic 风格：一次性完整 tool_call")
    chunks = [
        _make_chunk(tool_calls=[{
            "index": 0,
            "id": "toolu_01",
            "type": "function",
            "function": {
                "name": "search",
                "arguments": '{"query":"foo","top_k":5}',
            },
        }]),
        _make_chunk(finish_reason="tool_use"),
    ]

    acc = StreamAccumulator()
    _feed_all(acc, chunks)

    resp = acc.finalize()
    if len(resp.tool_calls) != 1:
        _fail(f"期望 1 个 tool_call，实际 {len(resp.tool_calls)}")
        return False
    tc = resp.tool_calls[0]
    if tc.id != "toolu_01" or tc.name != "search":
        _fail(f"tool_call 字段错误: {tc}")
        return False
    if tc.arguments != {"query": "foo", "top_k": 5}:
        _fail(f"arguments 解析错误: {tc.arguments}")
        return False
    if resp.finish_reason != "tool_calls":
        _fail(f"finish_reason 应归一化为 tool_calls，实际 {resp.finish_reason}")
        return False
    _ok("Anthropic 风格完整 tool_call 归一化正确")
    return True


# ==================== Test 6: 非法 JSON 兜底 ====================


def test_invalid_json_arguments_fallback() -> bool:
    _hr("Test 6 · arguments 非法 JSON 走 _raw 兜底")
    chunks = [
        _make_chunk(tool_calls=[{
            "index": 0, "id": "c0", "type": "function",
            "function": {"name": "f", "arguments": "{not json"},
        }]),
        _make_chunk(finish_reason="tool_calls"),
    ]
    acc = StreamAccumulator()
    _feed_all(acc, chunks)
    resp = acc.finalize()

    if len(resp.tool_calls) != 1:
        _fail(f"期望 1 个 tool_call，实际 {len(resp.tool_calls)}")
        return False
    args = resp.tool_calls[0].arguments
    if "_raw" not in args or args["_raw"] != "{not json":
        _fail(f"_raw 兜底失败: {args}")
        return False
    _ok("非法 JSON 走 _raw 兜底正确")
    return True


# ==================== Test 7: 缺失 finish_reason 但有 tool_calls ====================


def test_missing_finish_reason_with_tool_calls() -> bool:
    _hr("Test 7 · 缺失 finish_reason，自动归一化为 tool_calls")
    chunks = [
        _make_chunk(tool_calls=[{
            "index": 0, "id": "c0", "type": "function",
            "function": {"name": "f", "arguments": "{}"},
        }]),
        # 没有 finish_reason 的 chunk
    ]
    acc = StreamAccumulator()
    _feed_all(acc, chunks)
    resp = acc.finalize()
    if resp.finish_reason != "tool_calls":
        _fail(f"应自动归一化为 tool_calls，实际 {resp.finish_reason}")
        return False
    _ok("缺失 finish_reason 时自动归一化为 tool_calls")
    return True


# ==================== Test 8: 正文 + 工具混合（边说边调） ====================


def test_content_then_tool_call() -> bool:
    _hr("Test 8 · 正文 + 工具混合（边解释边调用）")
    chunks = [
        _make_chunk(content="我先查一下："),
        _make_chunk(tool_calls=[{
            "index": 0, "id": "c0", "type": "function",
            "function": {"name": "search", "arguments": '{"q":"x"}'},
        }]),
        _make_chunk(finish_reason="tool_calls"),
    ]
    acc = StreamAccumulator()
    events = _feed_all(acc, chunks)

    if acc.content != "我先查一下：":
        _fail(f"content 累积错误: {acc.content!r}")
        return False
    if not acc.has_tool_calls:
        _fail("应有 tool_calls")
        return False

    seq = [e.type for e in events]
    expected_prefix = [
        StreamEventType.CONTENT_DELTA,
        StreamEventType.TOOL_CALL_STARTED,
        StreamEventType.TOOL_CALL_ARGS_DELTA,
        StreamEventType.FINISH,
    ]
    if seq != expected_prefix:
        _fail(f"事件顺序错误: {seq}")
        return False
    _ok("正文 + 工具混合事件顺序正确")
    return True


# ==================== 主入口 ====================


def main() -> int:
    print("=" * 60)
    print("  流式工具调用累积单元测试（Phase 0）")
    print("=" * 60)

    results: List[tuple] = [
        ("pure_text",          test_pure_text_stream()),
        ("thinking",           test_thinking_and_content()),
        ("openai_single",      test_openai_style_single_tool_call()),
        ("openai_parallel",    test_openai_style_parallel_tool_calls()),
        ("anthropic",          test_anthropic_style_complete_tool_call()),
        ("invalid_json",       test_invalid_json_arguments_fallback()),
        ("missing_finish",     test_missing_finish_reason_with_tool_calls()),
        ("content_then_tool",  test_content_then_tool_call()),
    ]

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    print(f"  汇总: {passed}/{len(results)} 通过")
    for name, ok in results:
        print(f"    {'✅' if ok else '❌'} {name}")
    print("=" * 60)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
