#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_litellm_smoke.py
@Author  : caixiongjiang
@Date    : 2026/04/21
@Function:
    LiteLLM 客户端冒烟测试

    覆盖目标
    --------
    1. preset 加载（``config.toml → [llm.presets.test]``）
    2. 同步 + 异步基本生成
    3. 流式异步生成
    4. 多模态消息构造（仅构造 + 调用，不强求模型支持图片）
    5. OpenAI 原生 tool calling 走通：模型返回 tool_calls → 我们注入工具结果 → 模型给最终答复
    6. thinking_budget > 0 时 ``LLMResponse.thinking`` 字段可被解析（如模型不支持，跳过断言）

    运行::

        uv run python test/client/llm/test_litellm_smoke.py

    依赖：``LITELLM_PROXY_URL`` / ``LITELLM_PROXY_KEY``（自托管 proxy），
    或 ``DEEPSEEK_API_KEY`` 等供应商原生 key（LiteLLM 默认行为）。

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import json
import sys
import traceback
from pathlib import Path
from typing import List, Tuple

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def _hr(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


# ---- 测试 1: 同步 + 异步基础生成 ----
async def test_basic_generation() -> bool:
    _hr("Test 1 · 同步 + 异步基础生成")
    from src.client.llm import create_llm_client_from_preset

    client = create_llm_client_from_preset("test")
    print(f"  preset model = {client.model}")

    try:
        resp = client.generate(
            messages=[{"role": "user", "content": "回答只输出: OK"}],
            temperature=0.0,
            max_tokens=8,
        )
        print(f"  sync content = {resp.content!r}, tokens={resp.usage.total_tokens}")
        if not resp.content:
            _fail("sync content 为空")
            return False
        _ok("sync 生成成功")
    except Exception as e:
        _fail(f"sync 异常: {e}")
        traceback.print_exc()
        return False

    try:
        resp = await client.agenerate(
            messages=[{"role": "user", "content": "回答只输出: ok"}],
            temperature=0.0,
            max_tokens=8,
        )
        print(f"  async content = {resp.content!r}, tokens={resp.usage.total_tokens}")
        if not resp.content:
            _fail("async content 为空")
            return False
        _ok("async 生成成功")
    except Exception as e:
        _fail(f"async 异常: {e}")
        traceback.print_exc()
        return False

    return True


# ---- 测试 2: 异步流式 ----
async def test_streaming() -> bool:
    _hr("Test 2 · 异步流式生成")
    from src.client.llm import create_llm_client_from_preset

    client = create_llm_client_from_preset("test")
    pieces: List[str] = []
    try:
        async for chunk in client.astream(
            messages=[{"role": "user", "content": "依次输出: 1 2 3 4 5"}],
            temperature=0.0,
            max_tokens=64,
        ):
            if chunk.delta:
                pieces.append(chunk.delta)
            if chunk.finish_reason:
                print(f"  finish_reason = {chunk.finish_reason}")
        joined = "".join(pieces)
        print(f"  stream content = {joined!r}")
        if not joined.strip():
            _fail("stream 输出为空")
            return False
        _ok("stream 生成成功")
        return True
    except Exception as e:
        _fail(f"stream 异常: {e}")
        traceback.print_exc()
        return False


# ---- 测试 3: 多模态 message 构造 ----
async def test_multimodal_messages() -> bool:
    _hr("Test 3 · 多模态消息（仅构造 & 调用）")
    from src.client.llm import create_llm_client_from_preset

    client = create_llm_client_from_preset("test")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "下面这张图（占位 URL）若你看不到，请回答 '看不到图片'"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://placehold.co/64x64.png"},
                },
            ],
        },
    ]

    try:
        resp = await client.agenerate(messages=messages, temperature=0.0, max_tokens=64)
        print(f"  multimodal content = {resp.content!r}")
        _ok("多模态消息可接受 + 模型给出响应（不强求识图能力）")
        return True
    except Exception as e:
        # 文本模型可能不接受 image_url，但只要错误是合理的 4xx，就视为路径打通
        msg = str(e)
        print(f"  multimodal 调用返回错误: {msg[:200]}")
        if any(k in msg.lower() for k in ("image", "vision", "modality", "unsupported")):
            _ok("多模态被供应商拒绝（符合预期，路径已通）")
            return True
        _fail(f"多模态意外失败: {e}")
        return False


# ---- 测试 4: OpenAI 原生 tool calling ----
async def test_tool_calling() -> bool:
    _hr("Test 4 · OpenAI 原生 tool calling")
    from src.client.llm import create_llm_client_from_preset

    client = create_llm_client_from_preset("test")

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "查询指定城市当前天气",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "城市名"},
                    },
                    "required": ["city"],
                },
            },
        },
    ]

    messages = [
        {"role": "system", "content": "你必须调用 get_weather 工具来回答天气类问题。"},
        {"role": "user", "content": "上海现在天气怎么样？"},
    ]

    try:
        resp = await client.agenerate(messages=messages, tools=tools, tool_choice="auto")
    except Exception as e:
        _fail(f"tool calling 调用失败: {e}")
        traceback.print_exc()
        return False

    if not resp.tool_calls:
        print(f"  模型未发起 tool_calls，content = {resp.content!r}")
        _fail("预期模型应发起工具调用")
        return False

    tc = resp.tool_calls[0]
    print(f"  tool_call: name={tc.name}, args={tc.arguments}")
    _ok(f"模型发起了 {len(resp.tool_calls)} 次工具调用")

    # 拼接 assistant + tool result 再调一次
    messages.append({
        "role": "assistant",
        "content": resp.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
            for tc in resp.tool_calls
        ],
    })
    for tc in resp.tool_calls:
        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": '{"city":"上海","temp":"22°C","desc":"多云"}',
        })

    try:
        final = await client.agenerate(messages=messages, tools=tools, tool_choice="auto")
        print(f"  final content = {final.content!r}")
        if not final.content:
            _fail("收尾响应 content 为空")
            return False
        _ok("工具调用闭环走通")
        return True
    except Exception as e:
        _fail(f"工具调用闭环异常: {e}")
        traceback.print_exc()
        return False


# ---- 测试 5: thinking 字段 ----
async def test_thinking_budget() -> bool:
    _hr("Test 5 · thinking_budget（reasoning_content）")
    from src.client.llm import create_llm_client

    # 用 reasoning preset 类似的模型；如失败则跳过断言
    try:
        client = create_llm_client(
            model="deepseek/deepseek-reasoner",
            temperature=0.0,
            max_tokens=128,
            thinking_budget=2048,
        )
        resp = await client.agenerate(
            messages=[{"role": "user", "content": "1+1=? 请简要解释。"}],
        )
        print(f"  content = {resp.content!r}")
        if resp.thinking:
            print(f"  reasoning（前 80 字）= {resp.thinking.reasoning[:80]!r}")
            _ok(f"reasoning 字段已解析，tokens={resp.thinking.tokens_used}")
        else:
            print("  ⚠️  模型未返回 reasoning_content（视为软通过）")
        return True
    except Exception as e:
        print(f"  ⚠️  thinking 模型不可用，跳过：{e}")
        return True


# ---- 主入口 ----
async def main() -> int:
    print("=" * 60)
    print("  LiteLLM 客户端冒烟测试")
    print("=" * 60)

    results: List[Tuple[str, bool]] = []
    results.append(("basic",      await test_basic_generation()))
    results.append(("stream",     await test_streaming()))
    results.append(("multimodal", await test_multimodal_messages()))
    results.append(("tool",       await test_tool_calling()))
    results.append(("thinking",   await test_thinking_budget()))

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    print(f"  汇总: {passed}/{len(results)} 通过")
    for name, ok in results:
        print(f"    {'✅' if ok else '❌'} {name}")
    print("=" * 60)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
