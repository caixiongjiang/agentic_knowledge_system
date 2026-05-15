#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_deterministic_pipeline.py
@Author  : caixiongjiang
@Date    : 2026/04/08
@Function: 
    测试 1: Phase 2-5 确定性 Pipeline 联调
    
    验证从 ParallelRecall → GranularityAlignment → RRFFusion → Rerank
    的完整确定性管道在真实基础设施上端到端跑通。

    调用方式: RetrieveService.retrieve_custom(enable_validation=False)
    不依赖 LLM，这是最优先要跑通的测试。

    测试用例:
      1.1  双路基础联调:       chunk_dense + bm25_sparse
      1.2  三路 + 非 Chunk 粒度: chunk_dense + bm25_sparse + section_dense
      1.3  含 exact_match 路由:  chunk_dense + exact_match(keywords=[...])
      1.4  跳过 Rerank:         chunk_dense + bm25_sparse, enable_rerank=False
      1.5  MetadataFilter 过滤: chunk_dense, 指定 knowledge_base_id
      1.6  chunk + enhanced_chunk 混合召回: chunk_dense + enhanced_chunk_dense

    前提条件:
      - Milvus / MySQL / MongoDB / Embedding / Reranker 服务可达
      - chunk_store / enhanced_chunk_store / section_store 中有已索引数据
      - MongoDB chunk_data 中有文本数据
      - MySQL chunk_section_document 中有关系数据

@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import asyncio
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


# ======================================================================
#  常量 & 配置
# ======================================================================

TEST_QUERY = "深度学习是什么？它的核心方法有哪些？"
TEST_EXACT_KEYWORDS = ["深度学习", "神经网络"]
RECALL_TOP_K = 20
FINAL_TOP_K = 10


# ======================================================================
#  基础设施检查
# ======================================================================


async def check_infrastructure() -> Dict[str, Any]:
    """检查所有基础设施是否可达，返回可用信息"""
    info: Dict[str, Any] = {
        "milvus_ok": False,
        "mysql_ok": False,
        "mongodb_ok": False,
        "embedding_ok": False,
        "sparse_embedding_ok": False,
        "reranker_ok": False,
        "knowledge_base_id": None,
        "available_collections": [],
    }

    # 1. Milvus
    try:
        from src.db.milvus import get_milvus_manager, reset_manager
        reset_manager()
        manager = get_milvus_manager()
        if manager.check_connection():
            info["milvus_ok"] = True
            collections = manager.list_collections()
            info["available_collections"] = collections
            print(f"  ✅ Milvus: 连接成功, {len(collections)} 个 Collection")
        else:
            print("  ❌ Milvus: 连接失败")
    except Exception as e:
        print(f"  ❌ Milvus: {e}")

    # 2. MySQL — 查询一个有数据的知识库
    try:
        from src.db.mysql.connection.factory import get_mysql_manager
        from src.db.mysql.repositories.base.chunk_section_document_repo import (
            ChunkSectionDocumentRepository,
        )
        mysql_mgr = get_mysql_manager()
        repo = ChunkSectionDocumentRepository()
        with mysql_mgr.get_session() as session:
            from sqlalchemy import text
            row = session.execute(
                text("SELECT knowledge_base_id FROM chunk_section_document "
                     "WHERE deleted=0 LIMIT 1")
            ).fetchone()
            if row:
                info["mysql_ok"] = True
                info["knowledge_base_id"] = row[0]
                print(f"  ✅ MySQL: 连接成功, 发现知识库 {row[0][:20]}...")
            else:
                info["mysql_ok"] = True
                print("  ⚠️  MySQL: 连接成功, 但无可用数据")
    except Exception as e:
        print(f"  ❌ MySQL: {e}")

    # 3. MongoDB
    try:
        from src.db.mongodb.mongodb_manager import MongoDBManager
        await MongoDBManager.get_instance()
        from src.db.mongodb.models.chunk_data import ChunkData
        count = await ChunkData.find({"deleted": 0}).limit(1).count()
        info["mongodb_ok"] = count > 0
        if info["mongodb_ok"]:
            print(f"  ✅ MongoDB: 连接成功, chunk_data 有数据")
        else:
            print("  ⚠️  MongoDB: 连接成功, 但 chunk_data 无数据")
    except Exception as e:
        print(f"  ❌ MongoDB: {e}")

    # 4. Embedding 服务
    try:
        from src.client.embedding import create_embedding_client
        async with create_embedding_client() as client:
            healthy = await client.ahealth_check()
            info["embedding_ok"] = healthy
            print(f"  ✅ Embedding: 服务可用" if healthy
                  else "  ❌ Embedding: 健康检查失败")
    except Exception as e:
        print(f"  ❌ Embedding: {e}")

    # 5. Sparse Embedding 服务
    try:
        from src.client.embedding import create_sparse_embedding_client
        sparse_client = create_sparse_embedding_client()
        test_vec = await sparse_client.aembed_sparse("测试")
        info["sparse_embedding_ok"] = test_vec is not None and len(test_vec) > 0
        print(f"  ✅ Sparse Embedding: 服务可用" if info["sparse_embedding_ok"]
              else "  ❌ Sparse Embedding: 返回为空")
    except Exception as e:
        print(f"  ❌ Sparse Embedding: {e}")

    # 6. Reranker 服务
    try:
        from src.client.reranker import create_reranker_client
        reranker = create_reranker_client()
        results = await reranker.arerank(
            query="测试", documents=["测试文档"], top_k=1,
        )
        info["reranker_ok"] = len(results) > 0
        print(f"  ✅ Reranker: 服务可用" if info["reranker_ok"]
              else "  ❌ Reranker: 返回为空")
    except Exception as e:
        print(f"  ❌ Reranker: {e}")

    return info


def check_collection_available(collections: List[str], target: str) -> bool:
    """检查目标 Collection 是否存在"""
    return any(target in c for c in collections)


# ======================================================================
#  通用验证辅助
# ======================================================================


def validate_response_basic(
    response,
    test_name: str,
    expect_rerank: bool = True,
) -> List[str]:
    """对 RetrieveResponse 执行基本验证，返回失败项列表"""
    failures: List[str] = []

    # 返回 RetrieveResponse 不为空
    if response is None:
        failures.append("response 为 None")
        return failures

    # items 不为空
    if not response.items:
        failures.append("response.items 为空")
        return failures

    # 每个 ChunkItem 有 chunk_id, score
    for i, item in enumerate(response.items):
        if not item.chunk_id:
            failures.append(f"items[{i}].chunk_id 为空")
        if item.score is None:
            failures.append(f"items[{i}].score 为 None")

    # 按 score 降序排列
    scores = [item.score for item in response.items]
    for i in range(len(scores) - 1):
        if scores[i] < scores[i + 1]:
            failures.append(
                f"score 非降序: items[{i}].score={scores[i]:.4f} "
                f"< items[{i+1}].score={scores[i+1]:.4f}"
            )
            break

    # phase_timings 各阶段耗时 > 0
    t = response.phase_timings
    if t.recall_ms <= 0:
        failures.append(f"recall_ms={t.recall_ms} 应 > 0")
    if t.fusion_ms <= 0:
        failures.append(f"fusion_ms={t.fusion_ms} 应 > 0")
    if expect_rerank and t.rerank_ms <= 0:
        failures.append(f"rerank_ms={t.rerank_ms} 应 > 0")

    # total_count >= 1
    if response.total_count < 1:
        failures.append(f"total_count={response.total_count} 应 >= 1")

    # 无重复 chunk_id
    chunk_ids = [item.chunk_id for item in response.items]
    unique_ids = set(chunk_ids)
    if len(unique_ids) < len(chunk_ids):
        duplicates = [cid for cid in chunk_ids if chunk_ids.count(cid) > 1]
        failures.append(f"存在重复 chunk_id: {set(duplicates)}")

    # 不残留合成 ID（section:xxx / qa:xxx / summary:xxx）
    synthetic_ids = [
        cid for cid in chunk_ids
        if cid.startswith(("section:", "qa:", "summary:"))
    ]
    if synthetic_ids:
        failures.append(f"存在未对齐残留合成 ID: {synthetic_ids}")

    return failures


# ======================================================================
#  格式化输出辅助
# ======================================================================


def print_test_header(test_name: str, query: str, kb_id: Optional[str] = None):
    print(f"\n{'='*60}")
    print(f"  Pipeline 真实链路测试 — {test_name}")
    print(f"{'='*60}")
    if kb_id:
        print(f"  知识库: {kb_id}")
    print(f"  Query: {query}")
    print()


def print_phase_details(response, routes_desc: str):
    """打印各阶段详情"""
    t = response.phase_timings
    total_recall_items = response.total_count

    print(f"  [Phase 2] 并行召回: {routes_desc}, 耗时 {t.recall_ms:.0f}ms")
    if t.alignment_ms > 0:
        print(f"  [Phase 3] 跨粒度对齐: 耗时 {t.alignment_ms:.0f}ms")
    else:
        print(f"  [Phase 3] 跨粒度对齐: 无需对齐 (0ms)")
    print(f"  [Phase 4] RRF 融合: → {total_recall_items} 候选, 耗时 {t.fusion_ms:.0f}ms")
    if t.rerank_ms > 0:
        print(f"  [Phase 5] Rerank: → {len(response.items)} 结果, 耗时 {t.rerank_ms:.0f}ms")
    else:
        print(f"  [Phase 5] Rerank: 已跳过")
    print(f"\n  总耗时: {response.execution_time_ms:.0f}ms")

    # Top-3 结果
    print(f"\n  结果 Top-{min(3, len(response.items))}:")
    for i, item in enumerate(response.items[:3]):
        text_preview = (item.text or "")[:40].replace("\n", " ")
        print(f'    #{i+1} [score={item.score:.4f}] chunk_id={item.chunk_id[:16]}  "{text_preview}..."')


def print_test_result(test_name: str, failures: List[str]) -> bool:
    if not failures:
        print(f"\n  ✅ {test_name} 通过")
        return True
    else:
        print(f"\n  ❌ {test_name} 失败:")
        for f in failures:
            print(f"     - {f}")
        return False


# ======================================================================
#  测试用例
# ======================================================================


async def test_1_1_dual_route(service, kb_id: Optional[str]) -> bool:
    """用例 1.1: 双路基础联调 — chunk_dense + bm25_sparse"""
    test_name = "1.1 双路基础联调 (chunk_dense + bm25_sparse)"
    print_test_header(test_name, TEST_QUERY, kb_id)

    from src.retrieve.pipeline.types import RouteConfig
    from src.retrieve.types.query import MetadataFilter

    routes = [
        RouteConfig(route="chunk_dense", top_k=RECALL_TOP_K),
        RouteConfig(route="bm25_sparse", top_k=RECALL_TOP_K),
    ]
    filters = MetadataFilter(knowledge_base_id=kb_id) if kb_id else MetadataFilter()

    try:
        response = await service.retrieve_custom(
            routes=routes,
            query_text=TEST_QUERY,
            filters=filters,
            top_k=FINAL_TOP_K,
            enable_rerank=True,
            enable_validation=False,
        )
    except Exception as e:
        print(f"  ❌ 执行异常: {e}")
        traceback.print_exc()
        return False

    print_phase_details(response, "2 路 (chunk_dense, bm25_sparse)")
    failures = validate_response_basic(response, test_name, expect_rerank=True)

    # Phase 5 Rerank 专项验证
    if response.items:
        # Reranker 返回的 score 范围合理（0~1 之间）
        for i, item in enumerate(response.items):
            if not (0.0 <= item.score <= 1.0):
                failures.append(
                    f"Rerank score 超出 [0,1] 范围: items[{i}].score={item.score}"
                )

    return print_test_result(test_name, failures)


async def test_1_2_three_route_with_section(
    service, kb_id: Optional[str], has_section_data: bool,
) -> bool:
    """用例 1.2: 三路 + 非 Chunk 粒度 — chunk_dense + bm25_sparse + section_dense"""
    test_name = "1.2 三路 + Section 粒度 (chunk_dense + bm25_sparse + section_dense)"

    if not has_section_data:
        print(f"\n  ⏭️  跳过 {test_name}: section_store 无数据")
        return True

    print_test_header(test_name, TEST_QUERY, kb_id)

    from src.retrieve.pipeline.types import RouteConfig
    from src.retrieve.types.query import MetadataFilter

    routes = [
        RouteConfig(route="chunk_dense", top_k=RECALL_TOP_K),
        RouteConfig(route="bm25_sparse", top_k=RECALL_TOP_K),
        RouteConfig(route="section_dense", top_k=10),
    ]
    filters = MetadataFilter(knowledge_base_id=kb_id) if kb_id else MetadataFilter()

    try:
        response = await service.retrieve_custom(
            routes=routes,
            query_text=TEST_QUERY,
            filters=filters,
            top_k=FINAL_TOP_K,
            enable_rerank=True,
            enable_validation=False,
        )
    except Exception as e:
        print(f"  ❌ 执行异常: {e}")
        traceback.print_exc()
        return False

    print_phase_details(response, "3 路 (chunk_dense, bm25_sparse, section_dense)")
    failures = validate_response_basic(response, test_name, expect_rerank=True)

    # Phase 3 跨粒度对齐专项验证
    if response.phase_timings.alignment_ms <= 0:
        failures.append("含 section_dense 路由但 alignment_ms 为 0，对齐可能未执行")

    # 最终结果中不应残留 section:xxx 合成项
    for item in response.items:
        if item.chunk_id.startswith("section:"):
            failures.append(
                f"对齐后仍残留合成 section ID: {item.chunk_id}"
            )

    return print_test_result(test_name, failures)


async def test_1_3_with_exact_match(service, kb_id: Optional[str]) -> bool:
    """用例 1.3: 含 exact_match 路由 — chunk_dense + exact_match(keywords=[...])"""
    test_name = "1.3 含 exact_match (chunk_dense + exact_match)"
    print_test_header(test_name, TEST_QUERY, kb_id)

    from src.retrieve.pipeline.types import RouteConfig
    from src.retrieve.types.query import MetadataFilter

    routes = [
        RouteConfig(route="chunk_dense", top_k=RECALL_TOP_K),
        RouteConfig(
            route="exact_match",
            top_k=RECALL_TOP_K,
            params={"keywords": TEST_EXACT_KEYWORDS, "match_mode": "fuzzy"},
        ),
    ]
    filters = MetadataFilter(knowledge_base_id=kb_id) if kb_id else MetadataFilter()

    try:
        response = await service.retrieve_custom(
            routes=routes,
            query_text=TEST_QUERY,
            filters=filters,
            top_k=FINAL_TOP_K,
            enable_rerank=True,
            enable_validation=False,
        )
    except Exception as e:
        print(f"  ❌ 执行异常: {e}")
        traceback.print_exc()
        return False

    print_phase_details(response, "2 路 (chunk_dense, exact_match)")
    failures = validate_response_basic(response, test_name, expect_rerank=True)

    # exact_match 参数透传验证: 如果有结果，说明参数正确传递了
    if not response.items:
        failures.append("exact_match 路由未召回任何结果，参数透传可能有问题")

    return print_test_result(test_name, failures)


async def test_1_4_skip_rerank(service, kb_id: Optional[str]) -> bool:
    """用例 1.4: 跳过 Rerank — chunk_dense + bm25_sparse, enable_rerank=False"""
    test_name = "1.4 跳过 Rerank (enable_rerank=False)"
    print_test_header(test_name, TEST_QUERY, kb_id)

    from src.retrieve.pipeline.types import RouteConfig
    from src.retrieve.types.query import MetadataFilter

    routes = [
        RouteConfig(route="chunk_dense", top_k=RECALL_TOP_K),
        RouteConfig(route="bm25_sparse", top_k=RECALL_TOP_K),
    ]
    filters = MetadataFilter(knowledge_base_id=kb_id) if kb_id else MetadataFilter()

    try:
        response = await service.retrieve_custom(
            routes=routes,
            query_text=TEST_QUERY,
            filters=filters,
            top_k=FINAL_TOP_K,
            enable_rerank=False,
            enable_validation=False,
        )
    except Exception as e:
        print(f"  ❌ 执行异常: {e}")
        traceback.print_exc()
        return False

    print_phase_details(response, "2 路 (chunk_dense, bm25_sparse), Rerank=OFF")

    # 跳过 Rerank 时不检查 rerank_ms > 0
    failures = validate_response_basic(response, test_name, expect_rerank=False)

    # 验证 rerank_ms 应为 0
    if response.phase_timings.rerank_ms > 0:
        failures.append(
            f"enable_rerank=False 但 rerank_ms={response.phase_timings.rerank_ms:.1f} > 0"
        )

    # 跳过 Rerank 时，score 应该是 RRF 分数（通常远 < 1）
    if response.items:
        max_score = max(item.score for item in response.items)
        if max_score > 0.5:
            failures.append(
                f"跳过 Rerank 时 max_score={max_score:.4f} 异常高，"
                f"可能仍在使用 Reranker 分数"
            )

    return print_test_result(test_name, failures)


async def test_1_5_metadata_filter(service, kb_id: Optional[str]) -> bool:
    """用例 1.5: MetadataFilter 过滤 — chunk_dense, 指定 knowledge_base_id"""
    test_name = "1.5 MetadataFilter 过滤 (knowledge_base_id)"

    if not kb_id:
        print(f"\n  ⏭️  跳过 {test_name}: 未找到可用的 knowledge_base_id")
        return True

    print_test_header(test_name, TEST_QUERY, kb_id)

    from src.retrieve.pipeline.types import RouteConfig
    from src.retrieve.types.query import MetadataFilter

    routes = [
        RouteConfig(route="chunk_dense", top_k=RECALL_TOP_K),
    ]
    filters = MetadataFilter(knowledge_base_id=kb_id)

    try:
        response = await service.retrieve_custom(
            routes=routes,
            query_text=TEST_QUERY,
            filters=filters,
            top_k=FINAL_TOP_K,
            enable_rerank=True,
            enable_validation=False,
        )
    except Exception as e:
        print(f"  ❌ 执行异常: {e}")
        traceback.print_exc()
        return False

    print_phase_details(response, "1 路 (chunk_dense), MetadataFilter=ON")
    failures = validate_response_basic(response, test_name, expect_rerank=True)

    # 验证结果中的 knowledge_base_id 与过滤条件一致
    for i, item in enumerate(response.items):
        if item.knowledge_base_id and item.knowledge_base_id != kb_id:
            failures.append(
                f"items[{i}].knowledge_base_id={item.knowledge_base_id} "
                f"!= 过滤条件 {kb_id}"
            )

    return print_test_result(test_name, failures)


async def test_1_6_chunk_enhanced_mixed(
    service, kb_id: Optional[str], has_enhanced_data: bool,
) -> bool:
    """用例 1.6: chunk + enhanced_chunk 混合召回"""
    test_name = "1.6 混合召回 (chunk_dense + enhanced_chunk_dense)"

    if not has_enhanced_data:
        print(f"\n  ⏭️  跳过 {test_name}: enhanced_chunk_store 无数据")
        return True

    print_test_header(test_name, TEST_QUERY, kb_id)

    from src.retrieve.pipeline.types import RouteConfig
    from src.retrieve.types.query import MetadataFilter

    routes = [
        RouteConfig(route="chunk_dense", top_k=RECALL_TOP_K),
        RouteConfig(route="enhanced_chunk_dense", top_k=RECALL_TOP_K),
    ]
    filters = MetadataFilter(knowledge_base_id=kb_id) if kb_id else MetadataFilter()

    try:
        response = await service.retrieve_custom(
            routes=routes,
            query_text=TEST_QUERY,
            filters=filters,
            top_k=FINAL_TOP_K,
            enable_rerank=True,
            enable_validation=False,
        )
    except Exception as e:
        print(f"  ❌ 执行异常: {e}")
        traceback.print_exc()
        return False

    print_phase_details(response, "2 路 (chunk_dense, enhanced_chunk_dense)")
    failures = validate_response_basic(response, test_name, expect_rerank=True)

    # 混合召回专项验证
    if response.items:
        # 检查是否有来自多个路由的结果被融合
        multi_route_items = [
            item for item in response.items
            if len(item.metadata.get("_source_routes", [])) > 1
        ]
        if multi_route_items:
            print(f"\n  [混合召回] {len(multi_route_items)} 个 chunk 被两路同时命中 (RRF 融合生效)")
        else:
            print(f"\n  [混合召回] 未发现两路同时命中的 chunk (可能两路返回了不同的 chunk)")

    return print_test_result(test_name, failures)


# ======================================================================
#  测试报告生成
# ======================================================================


def generate_report(
    results: List[Tuple[str, bool]],
    total_time_s: float,
    output_path: Path,
):
    """生成 Markdown 测试报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    lines = [
        "# Pipeline 确定性管道 — 测试报告",
        "",
        f"- **执行时间**: {now}",
        f"- **测试文件**: `test/retrieve/pipeline/test_deterministic_pipeline.py`",
        f"- **测试范围**: Phase 2-5 (ParallelRecall → Alignment → Fusion → Rerank)",
        f"- **总耗时**: {total_time_s:.1f}s",
        f"- **结果**: {passed}/{total} 通过",
        "",
        "## 用例明细",
        "",
        "| 用例 | 状态 |",
        "|------|------|",
    ]
    for name, ok in results:
        status = "✅ 通过" if ok else "❌ 失败"
        lines.append(f"| {name} | {status} |")

    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n📄 测试报告已生成: {output_path}")


# ======================================================================
#  主入口
# ======================================================================


async def run_all_tests() -> int:
    print("=" * 60)
    print("  Pipeline 真实链路测试 — 测试 1: Phase 2-5 确定性 Pipeline")
    print("=" * 60)
    print(f"  项目根目录: {project_root}")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # ---- Step 0: 前提检查 ----
    print("─" * 40)
    print(" Step 1: 基础设施检查")
    print("─" * 40)
    infra = await check_infrastructure()

    # 最低要求: Milvus + Embedding
    if not infra["milvus_ok"]:
        print("\n❌ Milvus 不可用，终止测试")
        return 1
    if not infra["embedding_ok"]:
        print("\n❌ Embedding 服务不可用，终止测试")
        return 1

    kb_id = infra["knowledge_base_id"]
    collections = infra["available_collections"]

    has_section = check_collection_available(collections, "section_store")
    has_enhanced = check_collection_available(collections, "enhanced_chunk_store")

    print(f"\n  Collection 可用性:")
    print(f"    chunk_store:          {'✅' if check_collection_available(collections, 'chunk_store') else '❌'}")
    print(f"    enhanced_chunk_store: {'✅' if has_enhanced else '❌'}")
    print(f"    section_store:        {'✅' if has_section else '❌'}")

    # ---- 初始化 RetrieveService ----
    print("\n  初始化 RetrieveService...")
    from src.service.knowledge.retrieve_service import RetrieveService
    service = RetrieveService()
    print("  ✅ RetrieveService 初始化完成")

    # ---- Step 2: 执行测试用例 ----
    print("\n" + "─" * 40)
    print(" Step 2: 执行测试用例")
    print("─" * 40)

    total_start = time.perf_counter()
    results: List[Tuple[str, bool]] = []

    # 1.1 双路基础联调
    ok = await test_1_1_dual_route(service, kb_id)
    results.append(("1.1 双路基础联调 (chunk_dense + bm25_sparse)", ok))

    # 1.2 三路 + Section 粒度
    ok = await test_1_2_three_route_with_section(service, kb_id, has_section)
    results.append(("1.2 三路 + Section 粒度对齐", ok))

    # 1.3 含 exact_match
    ok = await test_1_3_with_exact_match(service, kb_id)
    results.append(("1.3 含 exact_match 参数透传", ok))

    # 1.4 跳过 Rerank
    ok = await test_1_4_skip_rerank(service, kb_id)
    results.append(("1.4 跳过 Rerank", ok))

    # 1.5 MetadataFilter
    ok = await test_1_5_metadata_filter(service, kb_id)
    results.append(("1.5 MetadataFilter 过滤", ok))

    # 1.6 chunk + enhanced_chunk 混合召回
    ok = await test_1_6_chunk_enhanced_mixed(service, kb_id, has_enhanced)
    results.append(("1.6 chunk + enhanced_chunk 混合召回", ok))

    total_time = time.perf_counter() - total_start

    # ---- 汇总 ----
    print("\n" + "=" * 60)
    print(" 测试结果汇总")
    print("=" * 60)

    passed = 0
    for name, ok in results:
        status = "✅ 通过" if ok else "❌ 失败"
        print(f"  {status}: {name}")
        if ok:
            passed += 1

    total = len(results)
    print(f"\n  总计: {passed}/{total} 测试通过, 总耗时 {total_time:.1f}s")

    if passed == total:
        print("\n  🎉 所有测试通过!")
    else:
        print(f"\n  ⚠️  有 {total - passed} 个测试失败")

    # 生成报告
    report_path = project_root / "test" / "retrieve" / "pipeline" / "pipeline_test_report.md"
    generate_report(results, total_time, report_path)

    # 清理
    try:
        from src.db.mongodb.mongodb_manager import MongoDBManager
        mgr = await MongoDBManager.get_instance()
        await mgr.disconnect()
    except Exception:
        pass
    try:
        from src.db.milvus import reset_manager
        reset_manager()
    except Exception:
        pass

    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
