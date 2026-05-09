#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : llm_quickstart.py
@Author  : caixiongjiang
@Date    : 2026/04/21
@Function:
    LiteLLM 客户端快速开始示例（重写后）

    覆盖：
        1) 同步基础生成
        2) 异步并发
        3) 推理模型 + thinking_budget（DeepSeek-Reasoner）
        4) 多 provider 切换 —— 只改 model 字符串
        5) OpenAI 原生 tool calling 简化示例
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.client.llm import create_llm_client  # noqa: E402


def example_basic() -> None:
    print("=" * 60)
    print("示例 1: 基础同步生成（DeepSeek-Chat）")
    print("=" * 60)

    client = create_llm_client(
        model="deepseek/deepseek-chat",
        temperature=0.0,
        max_tokens=100,
    )
    resp = client.generate(
        messages=[{"role": "user", "content": "什么是 Python？用一句话回答。"}],
    )
    print(f"回答: {resp.content}")
    print(f"Token: {resp.usage.total_tokens}, model={resp.model}")
    print()


async def example_async_concurrent() -> None:
    print("=" * 60)
    print("示例 2: 异步并发")
    print("=" * 60)

    questions = [
        "什么是 Python？",
        "什么是机器学习？",
        "什么是深度学习？",
        "什么是 RAG？",
    ]
    client = create_llm_client(model="deepseek/deepseek-chat", max_tokens=80)
    tasks = [
        client.agenerate(messages=[{"role": "user", "content": q}])
        for q in questions
    ]
    resps = await asyncio.gather(*tasks)
    for q, r in zip(questions, resps):
        print(f"- {q} → {r.content[:80]}")
    print()


def example_thinking() -> None:
    print("=" * 60)
    print("示例 3: 推理模型 + thinking_budget")
    print("=" * 60)

    client = create_llm_client(
        model="deepseek/deepseek-reasoner",
        temperature=0.0,
        max_tokens=400,
        thinking_budget=2048,
    )
    resp = client.generate(
        messages=[{"role": "user", "content": "分析快速排序的时间复杂度"}],
    )
    print(f"回答: {resp.content[:120]}...")
    if resp.thinking:
        print(f"\n推理（前 200 字）: {resp.thinking.reasoning[:200]}...")
        print(f"推理 Token: {resp.thinking.tokens_used}")
    print()


def example_multi_provider() -> None:
    print("=" * 60)
    print("示例 4: 多 provider 切换（只改 model 字符串）")
    print("=" * 60)

    candidates = [
        "deepseek/deepseek-chat",
        # "openai/gpt-4o-mini",
        # "gemini/gemini-1.5-flash",
        # "anthropic/claude-3-5-sonnet-20241022",
    ]
    question = "什么是人工智能？一句话回答。"
    for model in candidates:
        try:
            client = create_llm_client(model=model, max_tokens=60)
            resp = client.generate(messages=[{"role": "user", "content": question}])
            print(f"  {model} → {resp.content}")
        except Exception as e:
            print(f"  {model} 失败: {e}")
    print()


def example_tool_calling() -> None:
    print("=" * 60)
    print("示例 5: OpenAI 原生 tool calling")
    print("=" * 60)

    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询城市当前天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }]

    client = create_llm_client(model="deepseek/deepseek-chat", max_tokens=200)
    messages = [
        {"role": "system", "content": "天气问题必须调用 get_weather。"},
        {"role": "user", "content": "北京现在天气怎么样？"},
    ]
    resp = client.generate(messages=messages, tools=tools, tool_choice="auto")

    if not resp.tool_calls:
        print(f"  模型直接回答：{resp.content}")
        return

    tc = resp.tool_calls[0]
    print(f"  → 工具调用 {tc.name}({tc.arguments})")

    messages.append({
        "role": "assistant",
        "content": resp.content or "",
        "tool_calls": [{
            "id": tc.id, "type": "function",
            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
        }],
    })
    messages.append({
        "role": "tool",
        "tool_call_id": tc.id,
        "content": '{"city":"北京","temp":"18°C","desc":"晴"}',
    })
    final = client.generate(messages=messages)
    print(f"  最终回答: {final.content}")


if __name__ == "__main__":
    for fn in (example_basic, example_thinking, example_multi_provider, example_tool_calling):
        try:
            fn()
        except Exception as e:
            print(f"{fn.__name__} 失败: {e}\n")

    try:
        asyncio.run(example_async_concurrent())
    except Exception as e:
        print(f"example_async_concurrent 失败: {e}\n")

    print("所有示例运行完成！")
