#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_semantic_search.py
@Author  : caixiongjiang
@Date    : 2026/03/02
@Function: 
    语义向量检索能力 端到端测试
    - 连接真实 Milvus（Server 模式，从 config.toml + .env 读取）
    - 连接真实 Embedding 服务
    - 对 5 种 Collection（chunk/section/enhanced_chunk/atomic_qa/summary）
      执行：插入测试数据 → 语义检索 → 验证结果 → 清理数据
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import os
import asyncio
import time
import uuid
import random
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


VECTOR_DIM = 1024
TEST_PREFIX = f"semantic_test_{uuid.uuid4().hex[:6]}"
TEST_TEXTS = [
    "深度学习是机器学习的一个分支，通过多层神经网络自动学习数据的特征表示",
    "自然语言处理技术可以帮助计算机理解和生成人类语言",
    "向量数据库使用近似最近邻搜索算法来高效检索相似向量",
    "知识图谱通过实体和关系的结构化表示来组织领域知识",
    "检索增强生成（RAG）结合了信息检索和大语言模型的优势",
]
TEST_QUERY = "什么是深度学习和神经网络？"


def generate_test_record(
    record_id: str,
    vector: List[float],
    doc_id: str,
) -> Dict[str, Any]:
    """生成通用测试记录（适用于所有 Collection）"""
    now = int(time.time())
    return {
        "id": record_id,
        "vector": vector,
        "user_id": f"{TEST_PREFIX}_user",
        "knowledge_base_id": f"{TEST_PREFIX}_kb",
        "knowledge_base_name": "语义检索测试知识库",
        "parent_knowledge_base_id": "",
        "parent_knowledge_base_name": "",
        "agent_ids": {"session_id": 1, "task_id": 1, "agent_id": TEST_PREFIX},
        "type": "text",
        "role": "user",
        "knowledge_type": "test",
        "document_id": doc_id,
        "label_id": "test_label",
        "timestamp": now,
        "create_time": now,
        "update_time": now,
    }


async def embed_texts(embedding_client, texts: List[str]) -> List[List[float]]:
    """异步批量向量化"""
    return await embedding_client.aembed_batch(texts)


async def run_single_search_test(
    name: str,
    search_capability,
    repository,
    embedding_client,
    target,
) -> bool:
    """对单个 Search 能力执行端到端测试

    流程：生成向量 → 插入数据 → 执行检索 → 验证结果 → 清理
    """
    from src.retrieve.types.query import SemanticQuery, MetadataFilter

    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")

    record_ids: List[str] = []
    try:
        # 1. 向量化测试文本
        print("  [1/5] 向量化测试文本...")
        vectors = await embed_texts(embedding_client, TEST_TEXTS)
        print(f"        生成 {len(vectors)} 个向量，维度 {len(vectors[0])}")

        # 2. 构造并插入测试数据
        print("  [2/5] 插入测试数据...")
        records = []
        for i, (text, vec) in enumerate(zip(TEST_TEXTS, vectors)):
            rid = f"{TEST_PREFIX}_{name}_{i}"
            record_ids.append(rid)
            records.append(generate_test_record(
                record_id=rid,
                vector=vec,
                doc_id=f"{TEST_PREFIX}_doc_{i}",
            ))

        inserted_ids = repository.insert(records)
        print(f"        插入 {len(inserted_ids)} 条记录")

        time.sleep(1)

        # 3. 使用 query_text 执行检索（走 EmbeddingClient 自动向量化）
        print("  [3/5] 使用 query_text 执行语义检索...")
        query = SemanticQuery(
            target=target,
            query_text=TEST_QUERY,
            top_k=5,
            filters=MetadataFilter(
                knowledge_base_id=f"{TEST_PREFIX}_kb",
            ),
        )
        result = await search_capability.execute(query=query)
        print(f"        返回 {result.total_count} 条结果，耗时 {result.execution_time_ms:.1f}ms")

        if result.total_count == 0:
            print("  ✗ 检索结果为空")
            return False

        for i, item in enumerate(result.items[:3]):
            score = item.score
            item_id = getattr(item, "chunk_id", None) or \
                      getattr(item, "section_id", None) or \
                      getattr(item, "qa_id", None) or \
                      getattr(item, "summary_id", None)
            print(f"        Top-{i+1}: id={item_id}, score={score:.4f}")

        # 4. 使用 query_vector 执行检索（直接传入向量）
        print("  [4/5] 使用 query_vector 执行语义检索...")
        query_vec = await embedding_client.aembed(TEST_QUERY)
        query2 = SemanticQuery(
            target=target,
            query_vector=query_vec,
            top_k=3,
        )
        result2 = await search_capability.execute(query=query2)
        print(f"        返回 {result2.total_count} 条结果，耗时 {result2.execution_time_ms:.1f}ms")

        if result2.total_count == 0:
            print("  ✗ query_vector 检索结果为空")
            return False

        # 5. 验证
        print("  [5/5] 验证检索结果...")
        assert result.source_capability != "", "source_capability 不应为空"
        assert result.execution_time_ms > 0, "execution_time_ms 应 > 0"
        first_score = result.items[0].score
        assert first_score > 0, f"score 应 > 0, 实际 {first_score}"

        print(f"\n  ✅ {name} 端到端测试通过!")
        return True

    except Exception as e:
        print(f"\n  ✗ {name} 测试失败: {e}")
        traceback.print_exc()
        return False
    finally:
        if record_ids:
            try:
                ids_str = ", ".join(f"'{r}'" for r in record_ids)
                repository.delete(f"id in [{ids_str}]")
                print(f"  🧹 已清理 {len(record_ids)} 条测试数据")
            except Exception as e:
                print(f"  ⚠️  清理失败: {e}")


async def run_all_tests() -> int:
    """运行所有语义检索端到端测试"""
    print("="*60)
    print("语义向量检索能力 — 端到端测试")
    print("="*60)
    print(f"项目根目录: {project_root}")
    print(f"测试前缀: {TEST_PREFIX}")

    os.environ["MILVUS_AUTO_CREATE_COLLECTION"] = "true"

    try:
        from src.db.milvus import get_milvus_manager, reset_manager
        from src.client.embedding import create_embedding_client
        from src.retrieve.capabilities.semantic.chunk_vector_search import ChunkVectorSearch
        from src.retrieve.capabilities.semantic.section_vector_search import SectionVectorSearch
        from src.retrieve.capabilities.semantic.enhanced_chunk_vector_search import EnhancedChunkVectorSearch
        from src.retrieve.capabilities.semantic.qa_vector_search import QAVectorSearch
        from src.retrieve.capabilities.semantic.section_summary_vector_search import SectionSummaryVectorSearch
        from src.retrieve.capabilities.semantic.file_summary_vector_search import FileSummaryVectorSearch
        from src.retrieve.types.enums import SemanticTarget

        # 初始化基础设施
        reset_manager()
        manager = get_milvus_manager()
        print(f"Milvus 连接: {type(manager).__name__}")

        if not manager.check_connection():
            print("✗ Milvus 连接失败，终止测试")
            return 1

        print(f"Milvus 集合列表: {manager.list_collections()}")

        async with create_embedding_client() as emb_client:
            healthy = await emb_client.ahealth_check()
            if not healthy:
                print("✗ Embedding 服务健康检查失败，终止测试")
                return 1
            print(f"Embedding 服务: {emb_client.embeddings_url} (维度 {emb_client.dimension})")

            test_cases: List[Tuple[str, Any, Any, SemanticTarget]] = []

            # Chunk
            chunk_search = ChunkVectorSearch(embedding_client=emb_client, milvus_manager=manager)
            test_cases.append((
                "ChunkVectorSearch",
                chunk_search,
                chunk_search._repository,
                SemanticTarget.CHUNK,
            ))

            # Section
            section_search = SectionVectorSearch(embedding_client=emb_client, milvus_manager=manager)
            test_cases.append((
                "SectionVectorSearch",
                section_search,
                section_search._repository,
                SemanticTarget.SECTION,
            ))

            # Enhanced Chunk
            enhanced_search = EnhancedChunkVectorSearch(embedding_client=emb_client, milvus_manager=manager)
            test_cases.append((
                "EnhancedChunkVectorSearch",
                enhanced_search,
                enhanced_search._repository,
                SemanticTarget.ENHANCED,
            ))

            # QA
            qa_search = QAVectorSearch(embedding_client=emb_client, milvus_manager=manager)
            test_cases.append((
                "QAVectorSearch",
                qa_search,
                qa_search._repository,
                SemanticTarget.ATOMIC_QA,
            ))

            # Section Summary
            section_summary_search = SectionSummaryVectorSearch(embedding_client=emb_client, milvus_manager=manager)
            test_cases.append((
                "SectionSummaryVectorSearch",
                section_summary_search,
                section_summary_search._repository,
                SemanticTarget.SECTION_SUMMARY,
            ))

            # File Summary
            file_summary_search = FileSummaryVectorSearch(embedding_client=emb_client, milvus_manager=manager)
            test_cases.append((
                "FileSummaryVectorSearch",
                file_summary_search,
                file_summary_search._repository,
                SemanticTarget.FILE_SUMMARY,
            ))

            results = []
            for name, capability, repo, target in test_cases:
                ok = await run_single_search_test(name, capability, repo, emb_client, target)
                results.append((name, ok))

        # 汇总
        print("\n" + "="*60)
        print("测试结果汇总")
        print("="*60)
        passed = 0
        for name, ok in results:
            status = "✅ 通过" if ok else "❌ 失败"
            print(f"  {status}: {name}")
            if ok:
                passed += 1

        total = len(results)
        print(f"\n总计: {passed}/{total} 测试通过")

        if passed == total:
            print("\n🎉 所有端到端测试通过!")
            return 0
        else:
            print(f"\n⚠️  有 {total - passed} 个测试失败")
            return 1

    except Exception as e:
        print(f"\n✗ 测试初始化失败: {e}")
        traceback.print_exc()
        return 1
    finally:
        try:
            from src.db.milvus import reset_manager
            reset_manager()
        except Exception:
            pass
        os.environ.pop("MILVUS_AUTO_CREATE_COLLECTION", None)


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
