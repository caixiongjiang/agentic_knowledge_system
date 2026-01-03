#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_embedding_client.py
@Author  : caixiongjiang
@Date    : 2026/01/04
@Function: 
    Embedding客户端测试和使用示例
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import asyncio
import time

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.client.embedding import EmbeddingClient, create_embedding_client


def test_sync_embedding():
    """测试同步embedding"""
    print("=" * 80)
    print("测试1: 同步单条文本embedding（上下文管理器）")
    print("=" * 80)
    
    # 使用上下文管理器自动管理资源
    with create_embedding_client() as client:
        # 打印配置
        print(f"配置信息: {client.get_config()}")
        print()
        
        # 单条文本embedding
        text = "这是一个测试文本"
        print(f"文本: {text}")
        
        start_time = time.time()
        embedding = client.embed(text)
        elapsed = time.time() - start_time
        
        print(f"Embedding维度: {len(embedding)}")
        print(f"耗时: {elapsed:.3f}秒")
        print(f"前10个值: {embedding[:10]}")
        print()
    # 退出上下文后自动释放资源


def test_sync_batch_embedding():
    """测试同步批量embedding"""
    print("=" * 80)
    print("测试2: 同步批量文本embedding（上下文管理器）")
    print("=" * 80)
    
    with create_embedding_client() as client:
        # 批量文本
        texts = [
            "机器学习是人工智能的一个重要分支",
            "深度学习在图像识别领域取得了巨大成功",
            "自然语言处理技术正在快速发展",
            "向量数据库用于存储和检索高维向量",
            "知识图谱可以表示实体之间的关系",
        ]
        
        print(f"文本数量: {len(texts)}")
        print(f"批处理大小: {client.batch_size}")
        print()
        
        start_time = time.time()
        embeddings = client.embed_batch(texts)
        elapsed = time.time() - start_time
        
        print(f"成功获取 {len(embeddings)} 个embedding")
        print(f"总耗时: {elapsed:.3f}秒")
        print(f"平均耗时: {elapsed / len(texts):.3f}秒/条")
        print()


async def test_async_embedding():
    """测试异步embedding"""
    print("=" * 80)
    print("测试3: 异步单条文本embedding（异步上下文管理器）")
    print("=" * 80)
    
    async with create_embedding_client() as client:
        text = "异步处理可以提高并发性能"
        print(f"文本: {text}")
        
        start_time = time.time()
        embedding = await client.aembed(text)
        elapsed = time.time() - start_time
        
        print(f"Embedding维度: {len(embedding)}")
        print(f"耗时: {elapsed:.3f}秒")
        print()


async def test_async_batch_embedding():
    """测试异步批量embedding"""
    print("=" * 80)
    print("测试4: 异步批量文本embedding（异步上下文管理器）")
    print("=" * 80)
    
    async with create_embedding_client() as client:
        texts = [
            f"这是第 {i} 个测试文本，用于测试异步批量处理能力"
            for i in range(1, 11)
        ]
        
        print(f"文本数量: {len(texts)}")
        
        start_time = time.time()
        embeddings = await client.aembed_batch(texts)
        elapsed = time.time() - start_time
        
        print(f"成功获取 {len(embeddings)} 个embedding")
        print(f"总耗时: {elapsed:.3f}秒")
        print(f"平均耗时: {elapsed / len(texts):.3f}秒/条")
        print()


async def test_concurrent_embedding():
    """测试并发异步embedding"""
    print("=" * 80)
    print("测试5: 并发异步批量embedding（大规模）")
    print("=" * 80)
    
    async with create_embedding_client() as client:
        # 生成大量文本
        texts = [
            f"测试文本 {i}: 人工智能、机器学习、深度学习、自然语言处理"
            for i in range(1, 101)
        ]
        
        print(f"文本数量: {len(texts)}")
        print(f"最大并发: 5")
        
        start_time = time.time()
        embeddings = await client.aembed_concurrent(texts, max_concurrent=5)
        elapsed = time.time() - start_time
        
        print(f"成功获取 {len(embeddings)} 个embedding")
        print(f"总耗时: {elapsed:.3f}秒")
        print(f"平均耗时: {elapsed / len(texts):.3f}秒/条")
        print(f"理论加速比: {(len(texts) * 0.1) / elapsed:.2f}x (假设单次0.1秒)")
        print()


def test_retry_mechanism():
    """测试重试机制"""
    print("=" * 80)
    print("测试6: 测试重试机制（需要配置enable_retry=true）")
    print("=" * 80)
    
    # 创建启用重试的客户端，使用上下文管理器确保资源释放
    with create_embedding_client(custom_config={
        "enable_retry": True,
        "max_retries": 3,
        "retry_strategy": "exponential"
    }) as client:
        print(f"重试配置:")
        print(f"  - 启用重试: {client.enable_retry}")
        print(f"  - 最大重试次数: {client.max_retries}")
        print(f"  - 重试策略: {client.retry_strategy}")
        print()
        
        # 如果API正常，这个测试会直接成功
        # 如果API失败，会自动重试
        try:
            text = "测试重试机制"
            embedding = client.embed(text)
            print(f"成功获取embedding (维度: {len(embedding)})")
        except Exception as e:
            print(f"重试后仍然失败: {e}")
        print()


def test_timeout():
    """测试超时机制"""
    print("=" * 80)
    print("测试7: 测试超时机制（设置极短超时）")
    print("=" * 80)
    
    # 创建超时很短的客户端，使用临时模式即可（每次请求自动创建和关闭连接）
    try:
        client = create_embedding_client(custom_config={
            "timeout": 0.001  # 1毫秒，几乎肯定超时
        })
        
        text = "这个请求会超时"
        embedding = client.embed(text)
        print("意外成功（网络极快）")
    
    except TimeoutError as e:
        print(f"✓ 正确触发超时: {e}")
    
    except Exception as e:
        print(f"其他错误: {e}")
    
    print()


def test_health_check():
    """测试健康检查"""
    print("=" * 80)
    print("测试8: 健康检查")
    print("=" * 80)
    
    with create_embedding_client() as client:
        # 同步健康检查
        print("执行同步健康检查...")
        is_healthy = client.health_check()
        print(f"结果: {'✓ 健康' if is_healthy else '✗ 不健康'}")
        print()


async def test_async_health_check():
    """测试异步健康检查"""
    print("执行异步健康检查...")
    async with create_embedding_client() as client:
        is_healthy = await client.ahealth_check()
        print(f"结果: {'✓ 健康' if is_healthy else '✗ 不健康'}")
        print()


def test_error_handling():
    """测试错误处理"""
    print("=" * 80)
    print("测试9: 错误处理")
    print("=" * 80)
    
    with create_embedding_client() as client:
        # 测试空文本
        print("1. 测试空文本...")
        try:
            client.embed("")
            print("  ✗ 应该抛出异常")
        except ValueError as e:
            print(f"  ✓ 正确捕获: {e}")
        
        # 测试空列表
        print("2. 测试空列表...")
        try:
            client.embed_batch([])
            print("  ✗ 应该抛出异常")
        except ValueError as e:
            print(f"  ✓ 正确捕获: {e}")
        
        # 测试包含空文本的列表
        print("3. 测试包含空文本的列表...")
        try:
            embeddings = client.embed_batch(["有效文本", "", "  ", "另一个有效文本"])
            print(f"  ✓ 自动过滤空文本，获得 {len(embeddings)} 个embedding")
        except Exception as e:
            print(f"  错误: {e}")
        
        print()


def test_custom_config():
    """测试自定义配置"""
    print("=" * 80)
    print("测试10: 自定义配置")
    print("=" * 80)
    
    # 使用自定义配置创建客户端（临时使用模式，查看配置即可）
    custom_config = {
        "batch_size": 16,
        "timeout": 30.0,
        "enable_retry": True,
        "max_retries": 5,
    }
    
    client = create_embedding_client(custom_config=custom_config)
    
    config = client.get_config()
    print("自定义配置:")
    for key, value in config.items():
        print(f"  - {key}: {value}")
    print()


def run_all_sync_tests():
    """运行所有同步测试"""
    print("\n" + "=" * 80)
    print(" Embedding客户端测试套件 - 同步测试")
    print("=" * 80 + "\n")
    
    try:
        test_sync_embedding()
        test_sync_batch_embedding()
        test_retry_mechanism()
        test_timeout()
        test_health_check()
        test_error_handling()
        test_custom_config()
        
        print("=" * 80)
        print("✓ 所有同步测试完成")
        print("=" * 80)
    
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def run_all_async_tests():
    """运行所有异步测试"""
    print("\n" + "=" * 80)
    print(" Embedding客户端测试套件 - 异步测试")
    print("=" * 80 + "\n")
    
    try:
        await test_async_embedding()
        await test_async_batch_embedding()
        await test_concurrent_embedding()
        await test_async_health_check()
        
        print("=" * 80)
        print("✓ 所有异步测试完成")
        print("=" * 80)
    
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 运行同步测试
    run_all_sync_tests()
    
    # 运行异步测试
    print("\n\n")
    asyncio.run(run_all_async_tests())
    
    print("\n" + "=" * 80)
    print(" 所有测试完成！")
    print("=" * 80)
