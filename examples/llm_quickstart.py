#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : llm_quickstart.py
@Author  : caixiongjiang
@Date    : 2026/1/5
@Function: 
    LLM Client 快速开始示例
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from src.client.llm import create_llm_client


def example_basic():
    """基础使用示例"""
    print("=" * 60)
    print("示例1: 基础使用（DeepSeek-V3.2 非思考模式）")
    print("=" * 60)
    
    # 创建客户端（需要在环境变量中设置 DEEPSEEK_API_KEY）
    # deepseek-chat: DeepSeek-V3.2 非思考模式，快速响应
    client = create_llm_client(
        provider="deepseek",
        model_name="deepseek-chat",
        temperature=0.0,
        max_tokens=100
    )
    
    # 发送请求
    response = client.generate(
        messages=[
            {"role": "user", "content": "什么是Python？用一句话回答。"}
        ]
    )
    
    # 输出结果
    print(f"回答: {response.content}")
    print(f"Token使用: {response.usage.total_tokens}")
    print(f"模型: {response.model}")
    print()


def example_with_context_manager():
    """上下文管理器示例（推荐）"""
    print("=" * 60)
    print("示例2: 上下文管理器（批量处理）")
    print("=" * 60)
    
    # 使用上下文管理器，复用连接池
    with create_llm_client("deepseek", "deepseek-chat") as client:
        questions = [
            "什么是Python？",
            "什么是机器学习？",
            "什么是深度学习？"
        ]
        
        for i, question in enumerate(questions, 1):
            response = client.generate(
                messages=[{"role": "user", "content": question}],
                max_tokens=50
            )
            print(f"{i}. {question}")
            print(f"   回答: {response.content[:100]}...")
            print(f"   Token: {response.usage.total_tokens}")
            print()


async def example_async_concurrent():
    """异步并发示例"""
    print("=" * 60)
    print("示例3: 异步并发处理")
    print("=" * 60)
    
    questions = [
        "什么是Python？",
        "什么是机器学习？",
        "什么是深度学习？",
        "什么是自然语言处理？",
        "什么是计算机视觉？"
    ]
    
    # 使用异步上下文管理器
    async with create_llm_client("deepseek", "deepseek-chat") as client:
        # 创建并发任务
        tasks = [
            client.agenerate(
                messages=[{"role": "user", "content": q}],
                max_tokens=50
            )
            for q in questions
        ]
        
        # 并发执行
        responses = await asyncio.gather(*tasks)
        
        # 输出结果
        for i, (q, resp) in enumerate(zip(questions, responses), 1):
            print(f"{i}. {q}")
            print(f"   回答: {resp.content[:100]}...")
            print(f"   Token: {resp.usage.total_tokens}")
            print()


def example_deepseek_thinking():
    """DeepSeek 推理模式示例"""
    print("=" * 60)
    print("示例4: DeepSeek-V3.2 思考模式")
    print("=" * 60)
    
    # 方式1: 使用 deepseek-reasoner（推荐）
    # deepseek-reasoner: DeepSeek-V3.2 思考模式，自动启用推理
    client = create_llm_client(
        provider="deepseek",
        model_name="deepseek-reasoner",
        temperature=0.0,
        max_tokens=500
    )
    
    # 方式2: 使用 deepseek-chat + enable_thinking（等价）
    # client = create_llm_client(
    #     provider="deepseek",
    #     model_name="deepseek-chat",
    #     temperature=0.0,
    #     max_tokens=500,
    #     enable_thinking=True
    # )
    
    response = client.generate(
        messages=[
            {"role": "user", "content": "分析一下快速排序算法的时间复杂度"}
        ]
    )
    
    print(f"回答: {response.content}")
    
    if response.thinking:
        print(f"\n推理过程:")
        print(response.thinking.reasoning[:200] + "...")
        print(f"推理Token: {response.thinking.tokens_used}")
    
    print(f"\n总Token使用: {response.usage.total_tokens}")
    print()


def example_different_providers():
    """不同provider示例"""
    print("=" * 60)
    print("示例5: 使用不同的Provider")
    print("=" * 60)
    
    providers = [
        ("deepseek", "deepseek-chat"),
        # ("openai", "gpt-4o"),  # 需要 OPENAI_API_KEY
        # ("gemini", "gemini-1.5-pro"),  # 需要 GEMINI_API_KEY
        # ("anthropic", "claude-3-5-sonnet-20241022"),  # 需要 ANTHROPIC_API_KEY
    ]
    
    question = "什么是人工智能？用一句话回答。"
    
    for provider, model in providers:
        try:
            client = create_llm_client(
                provider=provider,
                model_name=model,
                max_tokens=50
            )
            
            response = client.generate(
                messages=[{"role": "user", "content": question}]
            )
            
            print(f"{provider.upper()} ({model}):")
            print(f"  回答: {response.content}")
            print(f"  Token: {response.usage.total_tokens}")
            print()
            
        except Exception as e:
            print(f"{provider.upper()}: 跳过（{e}）")
            print()


if __name__ == "__main__":
    # 同步示例
    try:
        example_basic()
    except Exception as e:
        print(f"示例1失败: {e}\n")
    
    try:
        example_with_context_manager()
    except Exception as e:
        print(f"示例2失败: {e}\n")
    
    try:
        example_deepseek_thinking()
    except Exception as e:
        print(f"示例4失败: {e}\n")
    
    try:
        example_different_providers()
    except Exception as e:
        print(f"示例5失败: {e}\n")
    
    # 异步示例
    print("运行异步示例...")
    try:
        asyncio.run(example_async_concurrent())
    except Exception as e:
        print(f"示例3失败: {e}\n")
    
    print("所有示例运行完成！")
