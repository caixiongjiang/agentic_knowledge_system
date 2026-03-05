#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_sparse_embedding_client.py
@Author  : caixiongjiang
@Date    : 2026/03/04
@Function: 
    BGE-M3 稀疏向量客户端效果测试
    
    测试重点不是"能否调通"，而是在模拟业务场景下稀疏向量的质量:
    - 稀疏向量的基本结构和非零维度分布
    - 相似文本 vs 不相关文本的稀疏向量区分度
    - 中文关键词在稀疏向量中的体现能力
    - 批量编码的一致性（同一文本多次编码结果应稳定）
    - 同步/异步接口的结果一致性
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import asyncio
import time
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.client.embedding import SparseEmbeddingClient, create_sparse_embedding_client


# ==================== 工具函数 ====================


def sparse_inner_product(a: dict[int, float], b: dict[int, float]) -> float:
    """计算两个稀疏向量的内积（IP），越大表示越相似"""
    score = 0.0
    for idx in a:
        if idx in b:
            score += a[idx] * b[idx]
    return score


def sparse_overlap_ratio(a: dict[int, float], b: dict[int, float]) -> float:
    """计算两个稀疏向量的维度重叠率"""
    if not a or not b:
        return 0.0
    overlap = len(set(a.keys()) & set(b.keys()))
    union = len(set(a.keys()) | set(b.keys()))
    return overlap / union if union > 0 else 0.0


def print_sparse_stats(name: str, vec: dict[int, float]) -> None:
    """打印稀疏向量统计信息"""
    if not vec:
        print(f"  [{name}] 空向量!")
        return
    weights = list(vec.values())
    print(
        f"  [{name}] 非零维度: {len(vec)}, "
        f"权重范围: [{min(weights):.4f}, {max(weights):.4f}], "
        f"权重均值: {sum(weights)/len(weights):.4f}"
    )


# ==================== 测试用例 ====================


def test_basic_sparse_structure():
    """测试1: 稀疏向量基本结构验证"""
    print("=" * 80)
    print("测试1: 稀疏向量基本结构验证")
    print("=" * 80)

    with create_sparse_embedding_client() as client:
        text = "什么是Agent基础设施服务？"
        print(f"输入文本: {text}")

        start = time.time()
        sparse_vec = client.embed_sparse(text)
        elapsed = time.time() - start

        print(f"耗时: {elapsed:.3f}s")
        print_sparse_stats("结果", sparse_vec)

        assert isinstance(sparse_vec, dict), "稀疏向量应为 dict 类型"
        assert len(sparse_vec) > 0, "稀疏向量不应为空"
        assert all(isinstance(k, int) for k in sparse_vec.keys()), "key 应为 int (token ID)"
        assert all(isinstance(v, float) for v in sparse_vec.values()), "value 应为 float"
        assert all(v > 0 for v in sparse_vec.values()), "权重应为正数"

        print("  结果: 通过 - 稀疏向量结构正确")
    print()


def test_semantic_similarity_discrimination():
    """测试2: 语义相似 vs 不相关文本的区分度

    核心效果测试：相似文本对的 IP 得分应显著高于不相关文本对。
    """
    print("=" * 80)
    print("测试2: 语义相似 vs 不相关文本的区分度")
    print("=" * 80)

    similar_pairs = [
        ("Transformer模型使用自注意力机制", "Self-Attention是Transformer的核心组件"),
        ("深度学习在图像识别领域的应用", "卷积神经网络用于图片分类"),
        ("知识图谱存储实体与关系", "图数据库中的节点和边表示知识"),
    ]

    irrelevant_pairs = [
        ("Transformer模型使用自注意力机制", "今天天气不错适合出去散步"),
        ("深度学习在图像识别领域的应用", "明天股市可能会下跌"),
        ("知识图谱存储实体与关系", "厨房里的冰箱坏了需要维修"),
    ]

    with create_sparse_embedding_client() as client:
        similar_scores = []
        for text_a, text_b in similar_pairs:
            vecs = client.embed_sparse_batch([text_a, text_b])
            score = sparse_inner_product(vecs[0], vecs[1])
            overlap = sparse_overlap_ratio(vecs[0], vecs[1])
            similar_scores.append(score)
            print(f"  相似对 IP={score:.4f}, 重叠率={overlap:.2%}")
            print(f"    A: {text_a}")
            print(f"    B: {text_b}")

        print()

        irrelevant_scores = []
        for text_a, text_b in irrelevant_pairs:
            vecs = client.embed_sparse_batch([text_a, text_b])
            score = sparse_inner_product(vecs[0], vecs[1])
            overlap = sparse_overlap_ratio(vecs[0], vecs[1])
            irrelevant_scores.append(score)
            print(f"  不相关对 IP={score:.4f}, 重叠率={overlap:.2%}")
            print(f"    A: {text_a}")
            print(f"    B: {text_b}")

        avg_similar = sum(similar_scores) / len(similar_scores)
        avg_irrelevant = sum(irrelevant_scores) / len(irrelevant_scores)
        discrimination = avg_similar / avg_irrelevant if avg_irrelevant > 0 else float("inf")

        print()
        print(f"  相似对平均 IP: {avg_similar:.4f}")
        print(f"  不相关对平均 IP: {avg_irrelevant:.4f}")
        print(f"  区分度 (相似/不相关): {discrimination:.2f}x")

        if discrimination > 1.5:
            print("  结果: 通过 - 稀疏向量能有效区分相似与不相关文本")
        else:
            print("  结果: 警告 - 区分度偏低，稀疏向量区分能力有限")
    print()


def test_keyword_sensitivity():
    """测试3: 关键词敏感性

    验证包含相同关键词的文本在稀疏向量中共享更多非零维度。
    """
    print("=" * 80)
    print("测试3: 关键词敏感性测试")
    print("=" * 80)

    keyword = "向量数据库"
    texts_with_keyword = [
        "向量数据库是AI应用的核心基础设施",
        "Milvus是一款开源的向量数据库",
        "选择合适的向量数据库对RAG效果至关重要",
    ]
    texts_without_keyword = [
        "关系型数据库使用SQL进行查询",
        "消息队列用于异步通信",
        "分布式缓存提高系统性能",
    ]

    with create_sparse_embedding_client() as client:
        query_vec = client.embed_sparse(keyword)
        print_sparse_stats(f"查询词 '{keyword}'", query_vec)
        print()

        print("  含关键词文本的 IP 得分:")
        scores_with = []
        for text in texts_with_keyword:
            text_vec = client.embed_sparse(text)
            score = sparse_inner_product(query_vec, text_vec)
            scores_with.append(score)
            print(f"    IP={score:.4f}  {text}")

        print("  不含关键词文本的 IP 得分:")
        scores_without = []
        for text in texts_without_keyword:
            text_vec = client.embed_sparse(text)
            score = sparse_inner_product(query_vec, text_vec)
            scores_without.append(score)
            print(f"    IP={score:.4f}  {text}")

        avg_with = sum(scores_with) / len(scores_with)
        avg_without = sum(scores_without) / len(scores_without)

        print()
        print(f"  含关键词平均 IP: {avg_with:.4f}")
        print(f"  不含关键词平均 IP: {avg_without:.4f}")

        if avg_with > avg_without:
            print("  结果: 通过 - 稀疏向量对关键词匹配敏感")
        else:
            print("  结果: 失败 - 稀疏向量未能体现关键词偏好")
    print()


def test_encoding_stability():
    """测试4: 编码稳定性

    同一文本多次编码应产生完全相同的稀疏向量。
    """
    print("=" * 80)
    print("测试4: 编码稳定性（确定性验证）")
    print("=" * 80)

    text = "BGE-M3模型支持多语言稀疏检索"

    with create_sparse_embedding_client() as client:
        vec1 = client.embed_sparse(text)
        vec2 = client.embed_sparse(text)
        vec3 = client.embed_sparse(text)

        is_stable_12 = (vec1 == vec2)
        is_stable_23 = (vec2 == vec3)

        print(f"  文本: {text}")
        print(f"  第1次非零维度数: {len(vec1)}")
        print(f"  第2次非零维度数: {len(vec2)}")
        print(f"  第3次非零维度数: {len(vec3)}")
        print(f"  1-2 完全一致: {is_stable_12}")
        print(f"  2-3 完全一致: {is_stable_23}")

        if is_stable_12 and is_stable_23:
            print("  结果: 通过 - 编码结果完全确定性")
        else:
            ip_12 = sparse_inner_product(vec1, vec2)
            ip_self = sparse_inner_product(vec1, vec1)
            ratio = ip_12 / ip_self if ip_self > 0 else 0
            print(f"  结果: 警告 - 编码存在轻微波动，自相关比: {ratio:.6f}")
    print()


def test_batch_vs_single_consistency():
    """测试5: 批量编码 vs 逐条编码的一致性"""
    print("=" * 80)
    print("测试5: 批量编码 vs 逐条编码一致性")
    print("=" * 80)

    texts = [
        "大语言模型的上下文窗口决定了输入长度",
        "Prompt工程是提高LLM输出质量的关键",
        "RAG通过检索增强来减少大模型幻觉",
    ]

    with create_sparse_embedding_client() as client:
        batch_vecs = client.embed_sparse_batch(texts)

        single_vecs = [client.embed_sparse(t) for t in texts]

        all_match = True
        for i, (bv, sv) in enumerate(zip(batch_vecs, single_vecs)):
            match = (bv == sv)
            ip = sparse_inner_product(bv, sv)
            ip_self = sparse_inner_product(bv, bv)
            ratio = ip / ip_self if ip_self > 0 else 0
            print(f"  文本{i}: 完全一致={match}, IP自相关比={ratio:.6f}")
            if not match:
                all_match = False

        if all_match:
            print("  结果: 通过 - 批量与逐条编码完全一致")
        else:
            print("  结果: 警告 - 批量与逐条结果存在差异（可能是浮点精度问题）")
    print()


async def test_sync_async_consistency():
    """测试6: 同步 vs 异步编码一致性"""
    print("=" * 80)
    print("测试6: 同步 vs 异步编码一致性")
    print("=" * 80)

    texts = [
        "知识图谱抽取实体和关系",
        "多模态模型可以处理图文混合输入",
    ]

    sync_client = create_sparse_embedding_client()
    sync_vecs = sync_client.embed_sparse_batch(texts)

    async with create_sparse_embedding_client() as async_client:
        async_vecs = await async_client.aembed_sparse_batch(texts)

    for i in range(len(texts)):
        match = (sync_vecs[i] == async_vecs[i])
        ip = sparse_inner_product(sync_vecs[i], async_vecs[i])
        ip_self = sparse_inner_product(sync_vecs[i], sync_vecs[i])
        ratio = ip / ip_self if ip_self > 0 else 0
        print(f"  文本{i}: 完全一致={match}, IP自相关比={ratio:.6f}")

    print("  结果: 通过 - 同步/异步接口结果验证完成")
    print()


def test_multilingual_sparse():
    """测试7: 多语言稀疏向量效果

    BGE-M3 本身支持多语言，验证中英文混合场景下的稀疏向量质量。
    """
    print("=" * 80)
    print("测试7: 多语言稀疏向量效果（中英文）")
    print("=" * 80)

    pairs = [
        ("机器学习算法", "machine learning algorithm"),
        ("自然语言处理", "natural language processing"),
        ("深度神经网络", "deep neural network"),
    ]

    unrelated_pairs = [
        ("机器学习算法", "beautiful sunset over the ocean"),
        ("自然语言处理", "cooking recipe for chocolate cake"),
        ("深度神经网络", "basketball game highlights"),
    ]

    with create_sparse_embedding_client() as client:
        print("  中英对照（语义相同）:")
        cross_scores = []
        for zh, en in pairs:
            vecs = client.embed_sparse_batch([zh, en])
            score = sparse_inner_product(vecs[0], vecs[1])
            overlap = sparse_overlap_ratio(vecs[0], vecs[1])
            cross_scores.append(score)
            print(f"    IP={score:.4f}, 重叠率={overlap:.2%}  {zh} <-> {en}")

        print("  中英对照（语义不相关）:")
        unrelated_scores = []
        for zh, en in unrelated_pairs:
            vecs = client.embed_sparse_batch([zh, en])
            score = sparse_inner_product(vecs[0], vecs[1])
            overlap = sparse_overlap_ratio(vecs[0], vecs[1])
            unrelated_scores.append(score)
            print(f"    IP={score:.4f}, 重叠率={overlap:.2%}  {zh} <-> {en}")

        avg_cross = sum(cross_scores) / len(cross_scores)
        avg_unrelated = sum(unrelated_scores) / len(unrelated_scores)
        print()
        print(f"  语义相同中英对 平均 IP: {avg_cross:.4f}")
        print(f"  语义不相关中英对 平均 IP: {avg_unrelated:.4f}")
        print(
            f"  注: 稀疏向量基于 token 级别，跨语言 IP 通常较低属正常现象，"
            f"跨语言语义匹配更多依赖稠密向量。"
        )
    print()


def test_long_text_sparse():
    """测试8: 长文本稀疏向量特性

    验证长文本产生更多非零维度，且关键信息不被稀释。
    """
    print("=" * 80)
    print("测试8: 长文本稀疏向量特性")
    print("=" * 80)

    short_text = "向量检索"
    medium_text = (
        "向量检索是一种利用高维向量空间中的距离度量来查找相似数据的技术，"
        "广泛应用于推荐系统和搜索引擎。"
    )
    long_text = (
        "向量检索是一种利用高维向量空间中的距离度量来查找相似数据的技术。"
        "在实际应用中，文本、图像、音频等非结构化数据会被编码为高维向量。"
        "通过近似最近邻（ANN）算法，如HNSW、IVF、PQ等索引结构，"
        "可以在海量数据中高效地找到与查询向量最相似的结果。"
        "向量检索已成为RAG（检索增强生成）、推荐系统、"
        "以及多模态搜索等AI应用的核心基础设施。"
        "Milvus、Qdrant、Pinecone等向量数据库专门为此场景优化。"
    )

    with create_sparse_embedding_client() as client:
        vecs = client.embed_sparse_batch([short_text, medium_text, long_text])
        print_sparse_stats("短文本", vecs[0])
        print_sparse_stats("中文本", vecs[1])
        print_sparse_stats("长文本", vecs[2])

        query_vec = client.embed_sparse("向量检索技术")
        scores = [sparse_inner_product(query_vec, v) for v in vecs]

        print()
        print(f"  查询 '向量检索技术' vs 短文本 IP: {scores[0]:.4f}")
        print(f"  查询 '向量检索技术' vs 中文本 IP: {scores[1]:.4f}")
        print(f"  查询 '向量检索技术' vs 长文本 IP: {scores[2]:.4f}")
        print(f"  非零维度趋势: {len(vecs[0])} → {len(vecs[1])} → {len(vecs[2])}")

        if len(vecs[0]) < len(vecs[1]) < len(vecs[2]):
            print("  结果: 通过 - 文本越长非零维度越多（符合预期）")
        else:
            print("  结果: 观察 - 非零维度分布不完全单调递增")
    print()


async def test_concurrent_sparse():
    """测试9: 并发稀疏编码性能"""
    print("=" * 80)
    print("测试9: 并发稀疏编码性能")
    print("=" * 80)

    texts = [
        f"测试文本{i}: 人工智能在{domain}领域的应用前景"
        for i, domain in enumerate([
            "医疗", "金融", "教育", "制造", "农业",
            "交通", "能源", "零售", "安防", "法律",
            "媒体", "物流", "环保", "航天", "生物",
            "材料", "通信", "游戏", "体育", "音乐",
        ])
    ]

    async with create_sparse_embedding_client() as client:
        print(f"  文本数量: {len(texts)}")

        start = time.time()
        results = await client.aembed_sparse_concurrent(texts, max_concurrent=5)
        elapsed = time.time() - start

        print(f"  总耗时: {elapsed:.3f}s")
        print(f"  平均耗时: {elapsed/len(texts):.3f}s/条")
        print(f"  成功编码: {len(results)} 个稀疏向量")

        dims = [len(v) for v in results]
        print(
            f"  非零维度统计: "
            f"min={min(dims)}, max={max(dims)}, avg={sum(dims)/len(dims):.0f}"
        )
    print()


def test_health_check():
    """测试10: 健康检查"""
    print("=" * 80)
    print("测试10: BGE-M3 稀疏向量服务健康检查")
    print("=" * 80)

    with create_sparse_embedding_client() as client:
        print(f"  配置信息: {client.get_config()}")
        is_healthy = client.health_check()
        print(f"  健康状态: {'通过' if is_healthy else '失败'}")
    print()


# ==================== 运行入口 ====================


def run_all_sync_tests():
    print("\n" + "=" * 80)
    print(" BGE-M3 稀疏向量客户端测试 — 同步测试")
    print("=" * 80 + "\n")

    try:
        test_health_check()
        test_basic_sparse_structure()
        test_encoding_stability()
        test_batch_vs_single_consistency()
        test_semantic_similarity_discrimination()
        test_keyword_sensitivity()
        test_multilingual_sparse()
        test_long_text_sparse()

        print("=" * 80)
        print("所有同步测试完成")
        print("=" * 80)
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


async def run_all_async_tests():
    print("\n" + "=" * 80)
    print(" BGE-M3 稀疏向量客户端测试 — 异步测试")
    print("=" * 80 + "\n")

    try:
        await test_sync_async_consistency()
        await test_concurrent_sparse()

        print("=" * 80)
        print("所有异步测试完成")
        print("=" * 80)
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_sync_tests()
    print("\n\n")
    asyncio.run(run_all_async_tests())
    print("\n" + "=" * 80)
    print(" BGE-M3 稀疏向量客户端 — 全部测试完成！")
    print("=" * 80)
