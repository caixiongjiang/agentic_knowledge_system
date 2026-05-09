#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_reranker_client.py
@Author  : caixiongjiang
@Date    : 2026/04/03
@Function: 
    RerankerClient 测试（真实 API 调用，无 Mock）
    前置条件: Reranker 服务已部署在 config.toml 配置的地址上
@Modify History:
    2026/04/07 - 移除 Mock，全部改为真实 API 调用
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import asyncio
import time
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.client.reranker import (
    RerankerClient,
    RerankResult,
    create_reranker_client,
)


# ==================== 1. RerankResult 模型 ====================


def test_rerank_result_model():
    """测试 RerankResult Pydantic 模型"""
    print("=" * 80)
    print("测试1: RerankResult 模型创建与序列化")
    print("=" * 80)

    result = RerankResult(index=0, score=0.95, text="测试文档")
    assert result.index == 0
    assert result.score == 0.95
    assert result.text == "测试文档"
    print(f"  创建: index={result.index}, score={result.score}, text='{result.text}' ✓")

    result2 = RerankResult(index=1, score=0.5)
    assert result2.text == ""
    print(f"  默认text: '{result2.text}' ✓")

    dumped = result.model_dump()
    restored = RerankResult.model_validate(dumped)
    assert restored == result
    print(f"  JSON 往返一致 ✓")

    print()


# ==================== 2. 配置加载与校验 ====================


def test_config_loading():
    """测试从 config.toml 加载配置（LiteLLM 版）"""
    print("=" * 80)
    print("测试2: 从 config.toml 加载真实配置")
    print("=" * 80)

    client = create_reranker_client()
    config = client.get_config()
    print(f"  配置: {config}")

    # LiteLLM 版 get_config() 返回字段：model / api_base / batch_size / top_k / timeout
    assert "model" in config and isinstance(config["model"], str) and config["model"]
    assert "/" in config["model"], f"model 字符串应为 'provider/model' 形式: {config['model']}"
    assert "reranker" in config["model"].lower() or "qwen" in config["model"].lower()
    # api_base 允许为 None（由 LiteLLM 走 provider 默认 endpoint），但走 Proxy 时会有值
    assert config["api_base"] is None or config["api_base"] != ""
    assert config["timeout"] > 0
    assert config["batch_size"] > 0
    assert config["top_k"] > 0
    print(
        f"  model={config['model']}, api_base={config['api_base']}, "
        f"batch_size={config['batch_size']}, top_k={config['top_k']} ✓"
    )

    print()


def test_config_validation_missing_fields():
    """测试缺少必需字段时的校验（LiteLLM 版只校验 model 字段）"""
    print("=" * 80)
    print("测试3: 配置缺少必需字段时抛异常")
    print("=" * 80)

    # LiteLLM 时代只对 'model' 强校验（api_base/api_key 可由 [proxy] + .env 兜底）
    try:
        create_reranker_client(custom_config={"model": ""})
        print(f"  ✗ 缺少 model 应该抛异常")
    except ValueError as e:
        print(f"  ✓ 缺少 model: {e}")

    print()


def test_custom_config_override():
    """测试 custom_config 覆盖"""
    print("=" * 80)
    print("测试4: custom_config 覆盖默认配置")
    print("=" * 80)

    client = create_reranker_client(custom_config={"batch_size": 32, "top_k": 20})
    assert client.batch_size == 32
    assert client.default_top_k == 20
    print(f"  batch_size={client.batch_size}, top_k={client.default_top_k} ✓")

    print()


# ==================== 3. 输入校验 ====================


def test_empty_query_raises():
    """测试空查询文本"""
    print("=" * 80)
    print("测试5: 空查询文本抛 ValueError")
    print("=" * 80)

    client = create_reranker_client()

    for empty_q in ["", "   ", None]:
        label = repr(empty_q)
        try:
            client.rerank(empty_q, ["doc1"])
            print(f"  ✗ query={label} 应该抛异常")
        except (ValueError, TypeError) as e:
            print(f"  ✓ query={label}: {e}")

    print()


def test_empty_documents_raises():
    """测试空文档列表"""
    print("=" * 80)
    print("测试6: 空文档列表抛 ValueError")
    print("=" * 80)

    client = create_reranker_client()

    try:
        client.rerank("查询", [])
        print("  ✗ 应该抛异常")
    except ValueError as e:
        print(f"  ✓ 空列表: {e}")

    print()


async def test_async_empty_input():
    """测试异步方法的空输入校验"""
    print("=" * 80)
    print("测试7: 异步方法空输入校验")
    print("=" * 80)

    client = create_reranker_client()

    try:
        await client.arerank("", ["doc"])
        print("  ✗ 空 query 应该抛异常")
    except ValueError as e:
        print(f"  ✓ 异步空query: {e}")

    try:
        await client.arerank("查询", [])
        print("  ✗ 空 documents 应该抛异常")
    except ValueError as e:
        print(f"  ✓ 异步空documents: {e}")

    print()


# ==================== 4. 同步 rerank — 真实 API ====================


def test_sync_rerank_basic():
    """测试同步 rerank 基本调用"""
    print("=" * 80)
    print("测试8: 同步 rerank 基本调用 (真实 API)")
    print("=" * 80)

    with create_reranker_client() as client:
        query = "苹果怎么吃？"
        docs = [
            "苹果可以直接洗净生吃。",
            "苹果公司发布了新手机。",
            "做成苹果派也很美味。",
        ]

        start = time.time()
        results = client.rerank(query, docs, top_k=3)
        elapsed = time.time() - start

        print(f"  查询: {query}")
        print(f"  文档数: {len(docs)}, top_k=3")
        print(f"  耗时: {elapsed:.3f}s")

        assert len(results) > 0, "应该返回至少1条结果"
        assert len(results) <= 3, "不应超过 top_k"
        print(f"  返回 {len(results)} 条结果:")

        for r in results:
            assert isinstance(r, RerankResult)
            assert 0 <= r.index < len(docs)
            assert r.score > 0
            assert r.text == docs[r.index]
            print(f"    index={r.index}, score={r.score:.4f}, text='{r.text}'")

        # 结果应按 score 降序
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), "结果未按 score 降序排列"
        print(f"  分数降序排列 ✓")

        # "苹果可以直接洗净生吃" 应该排在 "苹果公司发布了新手机" 之前
        food_score = next(r.score for r in results if r.index == 0)
        company_score = next(r.score for r in results if r.index == 1)
        assert food_score > company_score, "语义排序不正确"
        print(f"  语义排序正确: 水果({food_score:.4f}) > 公司({company_score:.4f}) ✓")

    print()


def test_sync_rerank_top_k_truncation():
    """测试 top_k 截断"""
    print("=" * 80)
    print("测试9: top_k 截断 (真实 API)")
    print("=" * 80)

    with create_reranker_client() as client:
        docs = [
            "机器学习是人工智能的分支",
            "深度学习在图像识别中表现突出",
            "自然语言处理是NLP的核心",
            "向量数据库用于高维检索",
            "知识图谱表示实体关系",
        ]

        results = client.rerank("什么是机器学习？", docs, top_k=2)
        assert len(results) == 2
        print(f"  5 个文档, top_k=2 → 返回 {len(results)} 条 ✓")

        results_all = client.rerank("什么是机器学习？", docs, top_k=10)
        assert len(results_all) == 5
        print(f"  5 个文档, top_k=10 → 返回 {len(results_all)} 条 (不超过文档数) ✓")

    print()


def test_sync_rerank_batch_split():
    """测试同步 rerank 自动分片 (batch_size=3, docs=7)"""
    print("=" * 80)
    print("测试10: 同步 rerank 自动分片 (真实 API)")
    print("=" * 80)

    client = create_reranker_client(custom_config={"batch_size": 3})

    docs = [
        "苹果是一种常见的水果",
        "Python是一门编程语言",
        "太阳是太阳系的中心恒星",
        "地球是我们居住的星球",
        "月亮绕着地球公转",
        "量子计算是新兴技术",
        "区块链用于去中心化存储",
    ]

    with client:
        start = time.time()
        results = client.rerank("天文学知识", docs, top_k=3)
        elapsed = time.time() - start

    print(f"  文档数: {len(docs)}, batch_size: 3 → 3 批次 (3+3+1)")
    print(f"  耗时: {elapsed:.3f}s")
    assert len(results) == 3
    print(f"  返回 {len(results)} 条结果:")

    for r in results:
        assert 0 <= r.index < len(docs)
        print(f"    index={r.index}, score={r.score:.4f}, text='{r.text}'")

    # 结果按 score 降序
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    print(f"  跨批次全局排序正确 ✓")

    # "太阳/地球/月亮" 应该排在前面
    top_indices = {r.index for r in results}
    astronomy_indices = {2, 3, 4}
    overlap = top_indices & astronomy_indices
    assert len(overlap) >= 2, "天文相关文档应排在前列"
    print(f"  语义: 天文相关文档 {overlap} 排在前列 ✓")

    print()


# ==================== 5. 异步 rerank — 真实 API ====================


async def test_async_rerank_basic():
    """测试异步 arerank 基本调用"""
    print("=" * 80)
    print("测试11: 异步 arerank 基本调用 (真实 API)")
    print("=" * 80)

    async with create_reranker_client() as client:
        query = "什么是量子计算？"
        docs = [
            "量子计算利用量子力学原理进行计算",
            "经典计算机使用二进制位",
            "量子比特可以同时处于0和1的叠加态",
        ]

        start = time.time()
        results = await client.arerank(query, docs, top_k=2)
        elapsed = time.time() - start

        print(f"  查询: {query}")
        print(f"  耗时: {elapsed:.3f}s")
        assert len(results) == 2
        print(f"  返回 {len(results)} 条结果:")
        for r in results:
            assert r.score > 0
            print(f"    index={r.index}, score={r.score:.4f}, text='{r.text}'")

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
        print(f"  分数降序 ✓")

    print()


async def test_async_rerank_batch():
    """测试异步 arerank 自动分片"""
    print("=" * 80)
    print("测试12: 异步 arerank 自动分片 (真实 API)")
    print("=" * 80)

    async with create_reranker_client(custom_config={"batch_size": 2}) as client:
        docs = [
            "深度学习是机器学习的子领域",
            "卷积神经网络擅长图像处理",
            "循环神经网络处理序列数据",
            "Transformer架构改变了NLP领域",
            "BERT是预训练语言模型的代表",
        ]

        results = await client.arerank("深度学习模型有哪些？", docs, top_k=5)

        print(f"  文档数: {len(docs)}, batch_size: 2 → 3 批次 (2+2+1)")
        assert len(results) == 5
        print(f"  返回全部 {len(results)} 条结果 ✓")

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
        print(f"  跨批次全局排序正确 ✓")

        for r in results:
            print(f"    index={r.index}, score={r.score:.4f}, text='{r.text}'")

    print()


# ==================== 6. 上下文管理器 ====================


def test_sync_context_manager():
    """测试同步上下文管理器（LiteLLM 版为 no-op，连接池由 LiteLLM 维护）"""
    print("=" * 80)
    print("测试13: 同步上下文管理器 — 接口保留（no-op）")
    print("=" * 80)

    client = create_reranker_client()
    docs = ["苹果是水果", "香蕉是水果"]

    # 上下文管理器接口仍然可用（向后兼容），只是不再持有 httpx 客户端
    with client as ctx_client:
        assert ctx_client is client, "__enter__ 应返回 self"
        r1 = client.rerank("水果", docs, top_k=2)
        r2 = client.rerank("食物", docs, top_k=2)
        assert len(r1) > 0 and len(r2) > 0
        print(f"  with-block 内连续调用通过: r1={len(r1)} 条, r2={len(r2)} 条 ✓")

    # close() 也是 no-op，不应抛异常
    client.close()
    client.close()
    print(f"  退出 with + 重复 close() 不抛异常 ✓")

    print()


async def test_async_context_manager():
    """测试异步上下文管理器（LiteLLM 版为 no-op）"""
    print("=" * 80)
    print("测试14: 异步上下文管理器 — 接口保留（no-op）")
    print("=" * 80)

    client = create_reranker_client()
    docs = ["Python是语言", "Java是语言"]

    async with client as ctx_client:
        assert ctx_client is client, "__aenter__ 应返回 self"
        r1 = await client.arerank("编程语言", docs, top_k=2)
        r2 = await client.arerank("技术", docs, top_k=2)
        assert len(r1) > 0 and len(r2) > 0
        print(f"  async-with-block 内连续调用通过: r1={len(r1)} 条, r2={len(r2)} 条 ✓")

    await client.aclose()
    await client.aclose()
    print(f"  退出 async-with + 重复 aclose() 不抛异常 ✓")

    print()


# ==================== 7. 健康检查 — 真实 API ====================


def test_health_check():
    """测试同步健康检查"""
    print("=" * 80)
    print("测试15: 同步健康检查 (真实 API)")
    print("=" * 80)

    with create_reranker_client() as client:
        is_healthy = client.health_check()
        assert is_healthy is True
        print(f"  结果: {'✓ 健康' if is_healthy else '✗ 不健康'}")

    print()


async def test_async_health_check():
    """测试异步健康检查"""
    print("=" * 80)
    print("测试16: 异步健康检查 (真实 API)")
    print("=" * 80)

    async with create_reranker_client() as client:
        is_healthy = await client.ahealth_check()
        assert is_healthy is True
        print(f"  结果: {'✓ 健康' if is_healthy else '✗ 不健康'}")

    print()


# ==================== 8. 边界场景 ====================


def test_single_document():
    """测试单个文档"""
    print("=" * 80)
    print("测试17: 单个文档 (真实 API)")
    print("=" * 80)

    with create_reranker_client() as client:
        results = client.rerank("测试", ["唯一的文档"], top_k=5)
        assert len(results) == 1
        assert results[0].index == 0
        assert results[0].text == "唯一的文档"
        print(f"  1 个文档 → 返回 {len(results)} 条, index={results[0].index}, score={results[0].score:.4f} ✓")

    print()


def test_long_documents():
    """测试长文档"""
    print("=" * 80)
    print("测试18: 长文档 (真实 API)")
    print("=" * 80)

    with create_reranker_client() as client:
        long_doc = "人工智能是计算机科学的一个分支。" * 50
        docs = [long_doc, "这是短文档"]

        results = client.rerank("人工智能", docs, top_k=2)
        assert len(results) == 2
        print(f"  长文档({len(long_doc)}字) + 短文档 → 返回 {len(results)} 条 ✓")
        for r in results:
            text_preview = r.text[:50] + "..." if len(r.text) > 50 else r.text
            print(f"    index={r.index}, score={r.score:.4f}, text='{text_preview}'")

    print()


def test_chinese_and_english_mixed():
    """测试中英文混合"""
    print("=" * 80)
    print("测试19: 中英文混合 (真实 API)")
    print("=" * 80)

    with create_reranker_client() as client:
        query = "What is deep learning?"
        docs = [
            "Deep learning is a subset of machine learning.",
            "深度学习是机器学习的子集。",
            "今天天气不错。",
        ]

        results = client.rerank(query, docs, top_k=3)
        assert len(results) == 3
        print(f"  查询: {query}")
        for r in results:
            print(f"    index={r.index}, score={r.score:.4f}, text='{r.text}'")

        # 前两条应该比"今天天气不错"分数高
        weather_score = next(r.score for r in results if r.index == 2)
        best_score = results[0].score
        assert best_score > weather_score, "相关文档应排在不相关文档之前"
        print(f"  相关文档分数({best_score:.4f}) > 不相关文档分数({weather_score:.4f}) ✓")

    print()


# ==================== 9. 性能 ====================


def test_latency():
    """测试延迟"""
    print("=" * 80)
    print("测试20: 延迟测量 (真实 API)")
    print("=" * 80)

    with create_reranker_client() as client:
        docs = [f"测试文档 {i}: 人工智能和机器学习相关内容" for i in range(10)]

        times = []
        for trial in range(3):
            start = time.time()
            results = client.rerank("人工智能", docs, top_k=5)
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"  第{trial+1}次: {elapsed:.3f}s, 返回 {len(results)} 条")

        avg = sum(times) / len(times)
        print(f"  平均延迟: {avg:.3f}s")
        assert avg < 5.0, f"平均延迟 {avg:.3f}s 超过 5s 上限"
        print(f"  延迟在可接受范围内 (<5s) ✓")

    print()


# ==================== 10. close / aclose ====================


def test_close():
    """测试手动 close（LiteLLM 版为 no-op，调用后仍可继续使用）"""
    print("=" * 80)
    print("测试21: 手动 close()")
    print("=" * 80)

    client = create_reranker_client()
    docs = ["唯一文档"]

    client.close()
    print(f"  首次 close() 不抛异常 ✓")
    client.close()
    print(f"  重复 close() 不抛异常 ✓")

    # close 后调用 rerank 仍应可用（无状态）
    results = client.rerank("查询", docs, top_k=1)
    assert len(results) == 1
    print(f"  close 后仍可继续 rerank: 返回 {len(results)} 条 ✓")

    print()


async def test_aclose():
    """测试手动 aclose（LiteLLM 版为 no-op）"""
    print("=" * 80)
    print("测试22: 手动 aclose()")
    print("=" * 80)

    client = create_reranker_client()
    docs = ["唯一文档"]

    await client.aclose()
    print(f"  首次 aclose() 不抛异常 ✓")
    await client.aclose()
    print(f"  重复 aclose() 不抛异常 ✓")

    results = await client.arerank("查询", docs, top_k=1)
    assert len(results) == 1
    print(f"  aclose 后仍可继续 arerank: 返回 {len(results)} 条 ✓")

    print()


# ==================== 运行器 ====================


def run_all_sync_tests():
    """运行所有同步测试"""
    print("\n" + "=" * 80)
    print(" RerankerClient 测试套件 — 同步测试 (真实 API)")
    print("=" * 80 + "\n")

    tests = [
        test_rerank_result_model,
        test_config_loading,
        test_config_validation_missing_fields,
        test_custom_config_override,
        test_empty_query_raises,
        test_empty_documents_raises,
        test_sync_rerank_basic,
        test_sync_rerank_top_k_truncation,
        test_sync_rerank_batch_split,
        test_sync_context_manager,
        test_health_check,
        test_single_document,
        test_long_documents,
        test_chinese_and_english_mixed,
        test_latency,
        test_close,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {test_fn.__name__} 失败: {e}")
            import traceback
            traceback.print_exc()
            print()

    print("=" * 80)
    print(f" 同步测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 项")
    print("=" * 80)
    return failed


async def run_all_async_tests():
    """运行所有异步测试"""
    print("\n" + "=" * 80)
    print(" RerankerClient 测试套件 — 异步测试 (真实 API)")
    print("=" * 80 + "\n")

    tests = [
        test_async_empty_input,
        test_async_rerank_basic,
        test_async_rerank_batch,
        test_async_context_manager,
        test_async_health_check,
        test_aclose,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            await test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {test_fn.__name__} 失败: {e}")
            import traceback
            traceback.print_exc()
            print()

    print("=" * 80)
    print(f" 异步测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 项")
    print("=" * 80)
    return failed


if __name__ == "__main__":
    sync_failures = run_all_sync_tests()
    print("\n\n")
    async_failures = asyncio.run(run_all_async_tests())

    total_failures = sync_failures + async_failures
    print("\n" + "=" * 80)
    if total_failures == 0:
        print(" ✓ 所有测试通过！")
    else:
        print(f" ✗ {total_failures} 项测试失败")
    print("=" * 80)
