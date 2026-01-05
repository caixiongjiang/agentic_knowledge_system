#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : embedding_quickstart.py
@Author  : caixiongjiang
@Date    : 2026/01/04
@Function: 
    Embedding客户端快速入门示例
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from src.client.embedding import create_embedding_client, EmbeddingClient


def example_1_basic_sync():
    """示例1: 基础同步调用（上下文管理器）"""
    print("\n" + "=" * 60)
    print("示例1: 基础同步调用（上下文管理器）")
    print("=" * 60)
    
    # 使用上下文管理器自动管理资源
    with create_embedding_client() as client:
        # 单条文本
        text = "人工智能正在改变世界"
        embedding = client.embed(text)
        print(f"✓ 文本: {text}")
        print(f"✓ Embedding维度: {len(embedding)}")
        print(f"✓ 前5个值: {embedding[:5]}")


def example_2_batch_sync():
    """示例2: 批量同步调用（上下文管理器）"""
    print("\n" + "=" * 60)
    print("示例2: 批量同步调用（上下文管理器）")
    print("=" * 60)
    
    with create_embedding_client() as client:
        # 批量文本
        texts = [
            "深度学习是机器学习的一个分支",
            "自然语言处理技术正在快速发展",
            "向量数据库用于高效检索",
        ]
        
        embeddings = client.embed_batch(texts)
        print(f"✓ 输入文本数: {len(texts)}")
        print(f"✓ 获得embedding数: {len(embeddings)}")
        print(f"✓ 每个维度: {len(embeddings[0])}")


async def example_3_basic_async():
    """示例3: 基础异步调用（异步上下文管理器）"""
    print("\n" + "=" * 60)
    print("示例3: 基础异步调用（异步上下文管理器）")
    print("=" * 60)
    
    async with create_embedding_client() as client:
        # 异步单条
        text = "异步处理提高并发性能"
        embedding = await client.aembed(text)
        print(f"✓ 文本: {text}")
        print(f"✓ Embedding维度: {len(embedding)}")


async def example_4_concurrent():
    """示例4: 并发处理大量文本（异步上下文管理器）"""
    print("\n" + "=" * 60)
    print("示例4: 并发处理（高性能）")
    print("=" * 60)
    
    async with create_embedding_client() as client:
        # 生成100个文本
        texts = [f"测试文本编号 {i}" for i in range(1, 101)]
        
        print(f"处理 {len(texts)} 个文本...")
        embeddings = await client.aembed_concurrent(
            texts,
            max_concurrent=5  # 5个批次并发
        )
        
        print(f"✓ 成功获取 {len(embeddings)} 个embedding")
        print(f"✓ 使用并发处理，速度显著提升")


def example_5_with_retry():
    """示例5: 启用重试机制（上下文管理器）"""
    print("\n" + "=" * 60)
    print("示例5: 启用重试机制")
    print("=" * 60)
    
    # 创建启用重试的客户端，使用上下文管理器
    with create_embedding_client(custom_config={
        "enable_retry": True,
        "max_retries": 3,
        "retry_strategy": "exponential"
    }) as client:
        print(f"重试配置:")
        print(f"  - 最大重试: {client.max_retries}次")
        print(f"  - 重试策略: {client.retry_strategy}")
        
        text = "带重试保护的请求"
        embedding = client.embed(text)
        print(f"✓ 成功获取embedding (维度: {len(embedding)})")


def example_6_error_handling():
    """示例6: 错误处理"""
    print("\n" + "=" * 60)
    print("示例6: 错误处理")
    print("=" * 60)
    
    with create_embedding_client() as client:
        # 测试1: 空文本
        try:
            client.embed("")
        except ValueError as e:
            print(f"✓ 正确捕获空文本错误: {e}")
        
        # 测试2: 包含空文本的列表（会自动过滤）
        texts = ["有效文本1", "", "有效文本2", "   "]
        embeddings = client.embed_batch(texts)
        print(f"✓ 自动过滤空文本，获得 {len(embeddings)} 个embedding")


def example_7_health_check():
    """示例7: 健康检查"""
    print("\n" + "=" * 60)
    print("示例7: 健康检查")
    print("=" * 60)
    
    with create_embedding_client() as client:
        print("执行健康检查...")
        is_healthy = client.health_check()
        
        if is_healthy:
            print("✓ Embedding服务正常运行")
        else:
            print("✗ Embedding服务异常，请检查配置")


def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print(" Embedding客户端快速入门")
    print("=" * 60)
    
    print("\n提示: 请确保以下配置正确:")
    print("1. config/config.toml 中的 [embedding] 配置")
    print("2. 本地Embedding服务已启动")
    print("3. 如需认证，在 .env 中设置 EMBEDDING_API_KEY")
    print("\n资源管理说明:")
    print("- 所有示例都使用上下文管理器（with/async with）")
    print("- 退出上下文时自动释放连接资源，无内存泄漏")
    print("- 这是推荐的最佳实践！")
    
    try:
        # 同步示例
        example_1_basic_sync()
        example_2_batch_sync()
        example_5_with_retry()
        example_6_error_handling()
        example_7_health_check()
        
        # 异步示例
        print("\n" + "-" * 60)
        print(" 异步示例")
        print("-" * 60)
        asyncio.run(example_3_basic_async())
        asyncio.run(example_4_concurrent())
        
        print("\n" + "=" * 60)
        print("✓ 所有示例执行完成!")
        print("=" * 60)
        print("\n更多用法请参考:")
        print("- 详细文档: src/client/README.md")
        print("- 资源管理指南: docs/embedding_client_resource_management.md")
        
    except Exception as e:
        print(f"\n✗ 执行失败: {e}")
        print("\n请检查:")
        print("1. Embedding服务是否正常运行")
        print("2. config/config.toml 配置是否正确")
        print("3. 网络连接是否正常")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
