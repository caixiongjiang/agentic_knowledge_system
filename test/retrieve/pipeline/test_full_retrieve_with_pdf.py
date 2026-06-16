#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_full_retrieve_with_pdf.py
@Author  : caixiongjiang
@Date    : 2026/04/17
@Function:
    全流程检索集成测试 — 基于真实 PDF 案例 ``tmp_files/pdf/FRT075-33F.pdf``

    被测对象 (RetrieveService.retrieve):
        Phase 1: LLM₁ RoutePlanner          ← @traceable 上报 LangSmith
        Phase 2: ParallelRecallExecutor     ← 修复后：路由名/索引不再错位
        Phase 3: GranularityAligner
        Phase 4: 融合（RRF / WeightedSum）  ← 修复后：可按策略切换
        Phase 5: RerankStage

    用例覆盖（按 3.3 节修复点对应验证）:
        T1  HYBRID + RRF + 完整 Pipeline
        T2  SEARCH_MODE=SEMANTIC （仅保留语义路由）
        T3  SEARCH_MODE=LEXICAL  （仅保留字面路由 + 字面 filter 透传）
        T4  FusionStrategy.WEIGHTED_SUM （加权融合，enhanced 上权重）
        T5  ExactMatch + MetadataFilter(document_id=FRT075) 字面过滤透传
        T6  retrieve_custom 含 section_dense（间接验证 ParallelRecall 跳过 / 索引修复）

    LangSmith:
        - 在 .env 设置 LANGSMITH_API_KEY 即自动启用追踪
        - 顶层 trace 名 = 用例名（便于在 UI 中按用例聚合）

    运行:
        uv run python test/retrieve/pipeline/test_full_retrieve_with_pdf.py

    前提:
        - Milvus / MySQL / MongoDB / Embedding / Sparse Embedding / Reranker / LLM 服务可达
        - tmp_files/pdf/FRT075-33F.pdf 已经走过索引流水线，即在 chunk_store /
          chunk_data / chunk_section_document 中存在；若未索引，本脚本会 EARLY-EXIT
          并给出明确提示

@Modify History:
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import os
import sys
import time
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(project_root / ".env", override=False)


# ---------------------------------------------------------------------------
# 测试常量（围绕 FRT075-33F 真实内容设计）
# ---------------------------------------------------------------------------

PDF_PATH = "tmp_files/pdf/FRT075-33F.pdf"

# 全测试集只用一个能确定文档命中的 query，后面会按需 override
PRIMARY_QUERY = "FRT075-33F 的保持电流、触发电流和最大电压分别是多少？"

QUERIES = {
    "T1_HYBRID":    PRIMARY_QUERY,
    "T2_SEMANTIC":  "FRT 系列可恢复保险丝适用于哪些应用场景？工作温度范围是多少？",
    "T3_LEXICAL":   "FRT075-33F 的额定电压 36VDC 与最大故障电流 40A 是怎么标注的？",
    "T4_WEIGHTED":  "FRT075-33F 的物理尺寸是多少？引脚线径是多少 AWG？",
    "T5_FILTER":    "FRT075-33F 的引脚材料与绝缘涂层规格",
    "T6_RECUSTOM":  "FRT 系列保险丝符合哪些机构认证（UL / C-UL / TÜV）？",
}

# 这些关键 token 必须在该用例的最终结果里至少命中其中一个，
# 用来弱断言"召回相关性"，而不是只校验数量。
EXPECTED_TOKENS: Dict[str, List[str]] = {
    "T1_HYBRID":    ["FRT075", "0.75", "1.50", "36"],
    "T2_SEMANTIC":  ["IEEE", "FireWire", "Applications", "Temperature"],
    "T3_LEXICAL":   ["36VDC", "VMAX", "IMAX", "40"],
    "T4_WEIGHTED":  ["7.4", "12.2", "AWG", "24"],
    "T5_FILTER":    ["Tin", "epoxy", "UL-94"],
    "T6_RECUSTOM":  ["UL", "TÜV", "E211981"],
}

RECALL_TOP_K = 20
FINAL_TOP_K = 5


# ---------------------------------------------------------------------------
# 通用打印
# ---------------------------------------------------------------------------


def _indent(text: str, prefix: str = "    ") -> str:
    if not text or not text.strip():
        return prefix + "(空)\n"
    return "".join(f"{prefix}{line}\n" for line in text.rstrip().splitlines())


def print_header(title: str, query: str, **extra: Any) -> None:
    print(f"\n{'='*72}")
    print(f"  {title}")
    print(f"{'='*72}")
    print(f"  Query: {query}")
    for k, v in extra.items():
        print(f"  {k}: {v}")
    print()


def print_items(items, label: str, max_items: int = 3) -> None:
    print(f"  ── {label} (共 {len(items)} 条) ──")
    for i, item in enumerate(items[:max_items]):
        text_preview = (item.text or "")[:80].replace("\n", " ")
        score = item.score if item.score is not None else 0.0
        print(
            f"    #{i+1} [score={score:.4f}] "
            f"chunk_id={item.chunk_id[:24]}  doc={item.document_id or 'N/A'}"
        )
        print(f"        {text_preview}")
    if len(items) > max_items:
        print(f"    ... 其余 {len(items) - max_items} 条省略")


def print_phase_timings(response) -> None:
    t = response.phase_timings
    print(
        f"  ── 阶段耗时 ── total={response.execution_time_ms:.0f}ms "
        f"| plan={t.planning_ms:.0f} recall={t.recall_ms:.0f} "
        f"align={t.alignment_ms:.0f} fuse={t.fusion_ms:.0f} "
        f"rerank={t.rerank_ms:.0f}"
    )


def print_route_plan(plan) -> None:
    if plan is None:
        print("  ── RoutePlan ── (None)")
        return
    intent = getattr(plan.query_analysis, "intent", "n/a")
    routes = [(r.route, r.top_k) for r in plan.route_plan]
    print(
        f"  ── RoutePlan ── intent={intent}, fusion={plan.fusion_strategy.value}, "
        f"weights={plan.fusion_weights or '{}'}, rerank_top_n={plan.rerank_top_n}"
    )
    print(f"    routes: {routes}")


# ---------------------------------------------------------------------------
# 基础设施 + 数据可用性检查
# ---------------------------------------------------------------------------


async def check_infrastructure() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "milvus_ok": False,
        "mysql_ok": False,
        "mongodb_ok": False,
        "embedding_ok": False,
        "sparse_embedding_ok": False,
        "reranker_ok": False,
        "llm_ok": False,
    }

    try:
        from src.db.milvus import get_milvus_manager, reset_manager
        reset_manager()
        m = get_milvus_manager()
        info["milvus_ok"] = m.check_connection()
        print(f"  {'OK' if info['milvus_ok'] else 'FAIL'} Milvus")
    except Exception as e:
        print(f"  FAIL Milvus: {e}")

    try:
        from sqlalchemy import text
        from src.db.mysql.connection.factory import get_mysql_manager
        with get_mysql_manager().get_session() as session:
            session.execute(text("SELECT 1")).fetchone()
        info["mysql_ok"] = True
        print("  OK   MySQL")
    except Exception as e:
        print(f"  FAIL MySQL: {e}")

    try:
        from src.db.mongodb.mongodb_manager import MongoDBManager
        await MongoDBManager.get_instance()
        from src.db.mongodb.models.chunk_data import ChunkData
        await ChunkData.find({"deleted": 0}).limit(1).count()
        info["mongodb_ok"] = True
        print("  OK   MongoDB")
    except Exception as e:
        print(f"  FAIL MongoDB: {e}")

    try:
        from src.client.embedding import create_embedding_client
        async with create_embedding_client() as c:
            info["embedding_ok"] = await c.ahealth_check()
        print(f"  {'OK' if info['embedding_ok'] else 'FAIL'} Embedding")
    except Exception as e:
        print(f"  FAIL Embedding: {e}")

    try:
        from src.client.embedding import create_sparse_embedding_client
        v = await create_sparse_embedding_client().aembed_sparse("ping")
        info["sparse_embedding_ok"] = bool(v)
        print(f"  {'OK' if info['sparse_embedding_ok'] else 'FAIL'} Sparse Embedding")
    except Exception as e:
        print(f"  FAIL Sparse Embedding: {e}")

    try:
        from src.client.reranker import create_reranker_client
        r = await create_reranker_client().arerank(
            query="ping", documents=["pong"], top_k=1,
        )
        info["reranker_ok"] = len(r) > 0
        print(f"  {'OK' if info['reranker_ok'] else 'FAIL'} Reranker")
    except Exception as e:
        print(f"  FAIL Reranker: {e}")

    try:
        from src.client.llm import create_llm_client_from_preset
        c = create_llm_client_from_preset("test")
        info["llm_ok"] = bool(c.api_base) and bool(c.model_name)
        print(
            f"  OK   LLM preset=test provider={c.provider} model={c.model_name}"
            if info["llm_ok"] else "  FAIL LLM"
        )
    except Exception as e:
        print(f"  FAIL LLM: {e}")

    return info


async def locate_frt075_document() -> Optional[Tuple[str, Optional[str]]]:
    """通过 MongoDB 字面查询定位 FRT075-33F 在哪个文档/知识库

    Returns:
        (document_id, knowledge_base_id) 或 None
    """
    try:
        from sqlalchemy import text
        from src.db.mongodb.models.chunk_data import ChunkData
        from src.db.mysql.connection.factory import get_mysql_manager
    except Exception as e:
        print(f"  无法定位 FRT075 文档（依赖加载失败）: {e}")
        return None

    rows = await ChunkData.find(
        {
            "deleted": 0,
            "text_meta.text": {"$regex": "FRT075-33F", "$options": "i"},
        },
    ).limit(20).to_list()
    if not rows:
        return None

    chunk_ids = [str(r.id) for r in rows]
    placeholders = ",".join([":id" + str(i) for i in range(len(chunk_ids))])
    params = {f"id{i}": cid for i, cid in enumerate(chunk_ids)}

    with get_mysql_manager().get_session() as session:
        result = session.execute(
            text(
                f"SELECT chunk_id, document_id, knowledge_base_id "
                f"FROM chunk_section_document "
                f"WHERE deleted=0 AND chunk_id IN ({placeholders})"
            ),
            params,
        ).fetchall()

    if not result:
        return None

    doc_counter: Counter[str] = Counter()
    kb_for_doc: Dict[str, Optional[str]] = {}
    for _cid, doc_id, kb_id in result:
        if not doc_id:
            continue
        doc_counter[doc_id] += 1
        kb_for_doc.setdefault(doc_id, kb_id)

    if not doc_counter:
        return None

    most_common_doc = doc_counter.most_common(1)[0][0]
    return most_common_doc, kb_for_doc.get(most_common_doc)


# ---------------------------------------------------------------------------
# 用例断言辅助
# ---------------------------------------------------------------------------


def assert_basic_response(response, label: str) -> List[str]:
    failures: List[str] = []
    if response is None:
        return [f"{label}: response 为 None"]
    if not response.items:
        failures.append(f"{label}: items 为空")
        return failures
    for i, item in enumerate(response.items):
        if not item.chunk_id:
            failures.append(f"{label}: items[{i}].chunk_id 为空")
        if item.score is None:
            failures.append(f"{label}: items[{i}].score 为 None")
        if item.chunk_id.startswith(("section:", "qa:", "summary:")):
            failures.append(f"{label}: 残留合成 ID {item.chunk_id}")
    scores = [it.score for it in response.items]
    for i in range(len(scores) - 1):
        if scores[i] < scores[i + 1] - 1e-6:
            failures.append(
                f"{label}: score 非降序 (#{i}={scores[i]:.4f} < #{i+1}={scores[i+1]:.4f})"
            )
            break
    return failures


def assert_token_hit(response, label: str, expected_tokens: List[str]) -> List[str]:
    """至少命中一个期望 token，避免误判 LLM 召回偏题"""
    hay = " ".join((it.text or "") for it in response.items)
    if not any(tok.lower() in hay.lower() for tok in expected_tokens):
        return [
            f"{label}: 期望 token {expected_tokens} 在结果中均未出现 "
            f"(可能召回偏题)"
        ]
    return []


def assert_routes_filtered(plan, allowed_predicate, label: str) -> List[str]:
    if plan is None:
        return [f"{label}: route_plan 为 None"]
    bad = [r.route for r in plan.route_plan if not allowed_predicate(r.route)]
    if bad:
        return [f"{label}: route_plan 中残留不符合模式的路由 {bad}"]
    return []


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


async def t1_hybrid_full(service, kb_id: Optional[str], doc_id: str) -> bool:
    label = "T1 HYBRID 完整 Pipeline"
    query = QUERIES["T1_HYBRID"]
    print_header(label, query, knowledge_base_id=kb_id, document_id=doc_id)

    from src.retrieve.pipeline.types import RetrieveRequest
    from src.retrieve.types.enums import SearchMode
    from src.retrieve.types.query import MetadataFilter

    req = RetrieveRequest(
        query_text=query,
        filters=MetadataFilter(knowledge_base_id=kb_id) if kb_id else MetadataFilter(),
        top_k=FINAL_TOP_K,
        search_mode=SearchMode.HYBRID,
        enable_rerank=True,
    )

    try:
        resp = await service.retrieve(req)
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        traceback.print_exc()
        return False

    print_route_plan(resp.route_plan)
    print_phase_timings(resp)
    print_items(resp.items, "Final Items")

    failures = assert_basic_response(resp, label)
    failures += assert_token_hit(resp, label, EXPECTED_TOKENS["T1_HYBRID"])
    return _emit(label, failures)


async def t2_semantic_mode(service, kb_id: Optional[str], doc_id: str) -> bool:
    label = "T2 SearchMode=SEMANTIC (仅语义路由)"
    query = QUERIES["T2_SEMANTIC"]
    print_header(label, query, knowledge_base_id=kb_id)

    from src.retrieve.pipeline.parallel_recall import is_semantic_route
    from src.retrieve.pipeline.types import RetrieveRequest
    from src.retrieve.types.enums import SearchMode
    from src.retrieve.types.query import MetadataFilter

    req = RetrieveRequest(
        query_text=query,
        filters=MetadataFilter(knowledge_base_id=kb_id) if kb_id else MetadataFilter(),
        top_k=FINAL_TOP_K,
        search_mode=SearchMode.SEMANTIC,
        enable_rerank=True,
    )

    try:
        resp = await service.retrieve(req)
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        traceback.print_exc()
        return False

    print_route_plan(resp.route_plan)
    print_phase_timings(resp)
    print_items(resp.items, "Final Items")

    failures = assert_basic_response(resp, label)
    failures += assert_routes_filtered(resp.route_plan, is_semantic_route, label)
    failures += assert_token_hit(resp, label, EXPECTED_TOKENS["T2_SEMANTIC"])
    return _emit(label, failures)


async def t3_lexical_mode(service, kb_id: Optional[str], doc_id: str) -> bool:
    label = "T3 SearchMode=LEXICAL (仅字面路由 + filter 透传)"
    query = QUERIES["T3_LEXICAL"]
    print_header(label, query, knowledge_base_id=kb_id, document_id=doc_id)

    from src.retrieve.pipeline.parallel_recall import is_lexical_route
    from src.retrieve.pipeline.types import RetrieveRequest
    from src.retrieve.types.enums import SearchMode
    from src.retrieve.types.query import MetadataFilter

    req = RetrieveRequest(
        query_text=query,
        filters=MetadataFilter(
            knowledge_base_id=kb_id,
            document_id=doc_id,
        ),
        top_k=FINAL_TOP_K,
        search_mode=SearchMode.LEXICAL,
        enable_rerank=True,
    )

    try:
        resp = await service.retrieve(req)
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        traceback.print_exc()
        return False

    print_route_plan(resp.route_plan)
    print_phase_timings(resp)
    print_items(resp.items, "Final Items")

    failures = assert_basic_response(resp, label)
    failures += assert_routes_filtered(resp.route_plan, is_lexical_route, label)
    failures += assert_token_hit(resp, label, EXPECTED_TOKENS["T3_LEXICAL"])
    return _emit(label, failures)


async def t4_weighted_sum_fusion(service, kb_id: Optional[str], doc_id: str) -> bool:
    label = "T4 FusionStrategy=WEIGHTED_SUM (加权融合)"
    query = QUERIES["T4_WEIGHTED"]
    print_header(label, query, knowledge_base_id=kb_id)

    from src.retrieve.pipeline.fusion import create_fusion
    from src.retrieve.pipeline.parallel_recall import ParallelRecallExecutor
    from src.retrieve.pipeline.rerank import RerankStage
    from src.retrieve.pipeline.types import (
        FusionStrategy,
        RouteConfig,
        RoutePlan,
    )
    from src.retrieve.types.query import MetadataFilter

    # 直接用工厂在用例里跑一次，避免依赖 LLM₁ 是否会主动返回 weighted_sum
    executor = ParallelRecallExecutor(service._registry)  # noqa: SLF001
    rerank_stage = RerankStage()

    plan = RoutePlan(
        route_plan=[
            RouteConfig(route="chunk_dense", top_k=RECALL_TOP_K),
            RouteConfig(route="enhanced_chunk_dense", top_k=RECALL_TOP_K),
            RouteConfig(route="bm25_sparse", top_k=RECALL_TOP_K),
        ],
        fusion_strategy=FusionStrategy.WEIGHTED_SUM,
        fusion_weights={
            "enhanced_chunk_dense": 1.5,
            "chunk_dense": 1.0,
            "bm25_sparse": 0.7,
        },
        rerank_top_n=40,
    )
    filters = MetadataFilter(knowledge_base_id=kb_id) if kb_id else MetadataFilter()

    try:
        recall = await executor.execute(plan.route_plan, query, filters)
        fusion = create_fusion(plan.fusion_strategy, weights=plan.fusion_weights)
        fused = fusion.fuse(recall, top_n=plan.rerank_top_n)
        items = await rerank_stage.rerank(query=query, candidates=fused, top_k=FINAL_TOP_K)
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        traceback.print_exc()
        return False

    print(
        f"  ── 召回 ── 各路命中: "
        f"{[(rr.route, rr.total_count) for rr in recall]}; "
        f"融合 → {len(fused)} 候选；最终 {len(items)} 条"
    )
    print_items(items, "Final Items")

    failures: List[str] = []
    if not items:
        failures.append(f"{label}: items 为空")
    if items:
        hay = " ".join((it.text or "") for it in items)
        if not any(t.lower() in hay.lower() for t in EXPECTED_TOKENS["T4_WEIGHTED"]):
            failures.append(
                f"{label}: 期望 token {EXPECTED_TOKENS['T4_WEIGHTED']} 均未命中"
            )
    return _emit(label, failures)


async def t5_lexical_filter_pushdown(service, kb_id: Optional[str], doc_id: str) -> bool:
    label = "T5 ExactMatch + MetadataFilter 透传 (修复 lexical filter)"
    query = QUERIES["T5_FILTER"]
    print_header(label, query, knowledge_base_id=kb_id, document_id=doc_id)

    from src.retrieve.pipeline.types import RouteConfig
    from src.retrieve.types.query import MetadataFilter

    routes = [
        RouteConfig(
            route="exact_match",
            top_k=20,
            params={"keywords": ["FRT075-33F", "epoxy"], "match_mode": "fuzzy"},
        ),
    ]
    filters = MetadataFilter(knowledge_base_id=kb_id, document_id=doc_id)

    try:
        resp = await service.retrieve_custom(
            routes=routes,
            query_text=query,
            filters=filters,
            top_k=FINAL_TOP_K,
            enable_rerank=False,
        )
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        traceback.print_exc()
        return False

    print_phase_timings(resp)
    print_items(resp.items, "Final Items")

    failures: List[str] = []
    if not resp.items:
        failures.append(f"{label}: items 为空（filter 透传可能裁掉了所有结果，请校验）")

    # 强约束：所有命中的 chunk 必须属于这个 document_id
    if resp.items and doc_id:
        from sqlalchemy import text
        from src.db.mysql.connection.factory import get_mysql_manager

        cids = [it.chunk_id for it in resp.items]
        placeholders = ",".join([":id" + str(i) for i in range(len(cids))])
        params = {f"id{i}": c for i, c in enumerate(cids)}
        with get_mysql_manager().get_session() as session:
            mapping = session.execute(
                text(
                    f"SELECT chunk_id, document_id FROM chunk_section_document "
                    f"WHERE deleted=0 AND chunk_id IN ({placeholders})"
                ),
                params,
            ).fetchall()
        bad = [(c, d) for c, d in mapping if d != doc_id]
        if bad:
            failures.append(
                f"{label}: filter 未生效，存在跨文档 chunk: {bad[:3]}..."
            )
        else:
            print(f"  filter 透传校验: 全部 {len(cids)} 条均属于 doc={doc_id} ✓")

    return _emit(label, failures)


async def t6_custom_with_section(service, kb_id: Optional[str], doc_id: str) -> bool:
    label = "T6 retrieve_custom 含 section_dense (验证索引修复 + 跨粒度)"
    query = QUERIES["T6_RECUSTOM"]
    print_header(label, query, knowledge_base_id=kb_id)

    from src.retrieve.pipeline.types import RouteConfig
    from src.retrieve.types.query import MetadataFilter

    # 故意混入一个不存在的路由名，验证 ParallelRecall 修复后的索引不会错位
    routes = [
        RouteConfig(route="chunk_dense", top_k=RECALL_TOP_K),
        RouteConfig(route="__not_a_route__", top_k=10),
        RouteConfig(route="bm25_sparse", top_k=RECALL_TOP_K),
        RouteConfig(route="section_dense", top_k=10),
    ]
    filters = MetadataFilter(knowledge_base_id=kb_id) if kb_id else MetadataFilter()

    try:
        resp = await service.retrieve_custom(
            routes=routes,
            query_text=query,
            filters=filters,
            top_k=FINAL_TOP_K,
            enable_rerank=True,
        )
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        traceback.print_exc()
        return False

    print_phase_timings(resp)
    print_items(resp.items, "Final Items")

    failures = assert_basic_response(resp, label)
    failures += assert_token_hit(resp, label, EXPECTED_TOKENS["T6_RECUSTOM"])
    return _emit(label, failures)


# ---------------------------------------------------------------------------
# 结果汇总 + 报告
# ---------------------------------------------------------------------------


def _emit(label: str, failures: List[str]) -> bool:
    if not failures:
        print(f"\n  PASS  {label}\n")
        return True
    print(f"\n  FAIL  {label}")
    for f in failures:
        print(f"        - {f}")
    print()
    return False


def write_report(
    results: List[Tuple[str, bool]],
    total_s: float,
    output_path: Path,
    *,
    document_id: Optional[str],
    knowledge_base_id: Optional[str],
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    lines = [
        "# 全流程检索集成测试 — 报告 (FRT075-33F.pdf)",
        "",
        f"- 执行时间: {now}",
        f"- 测试脚本: `test/retrieve/pipeline/test_full_retrieve_with_pdf.py`",
        f"- 观测: LiteLLM Proxy → PostgreSQL",
        f"- 定位文档: document_id=`{document_id}`, knowledge_base_id=`{knowledge_base_id}`",
        f"- 总耗时: {total_s:.1f}s",
        f"- 结果: {passed}/{total} 通过",
        "",
        "## 用例明细",
        "",
        "| 用例 | 状态 |",
        "|------|------|",
    ]
    for name, ok in results:
        lines.append(f"| {name} | {'PASS' if ok else 'FAIL'} |")
    lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告已生成: {output_path}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


async def run_all_tests() -> int:
    print("=" * 72)
    print("  全流程检索集成测试 — FRT075-33F.pdf")
    print("=" * 72)
    print(f"  项目根: {project_root}")
    print(f"  PDF: {project_root / PDF_PATH}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # ---- 观测：调用日志由自托管 LiteLLM Proxy 落到 PostgreSQL ----
    print("  观测: LiteLLM Proxy → PostgreSQL")
    print()

    # ---- Step 1: infra ----
    print("─" * 40)
    print(" Step 1: 基础设施检查")
    print("─" * 40)
    infra = await check_infrastructure()
    if not (infra["milvus_ok"] and infra["mongodb_ok"]
            and infra["mysql_ok"] and infra["embedding_ok"]):
        print("\n核心基础设施不可用，测试终止")
        return 1
    if not infra["llm_ok"]:
        print("\nLLM preset=test 不可用 → T1 用例会失败但其它用例仍会跑")

    # ---- Step 2: 定位 FRT075 文档 ----
    print("\n" + "─" * 40)
    print(" Step 2: 在知识库中定位 FRT075-33F")
    print("─" * 40)
    located = await locate_frt075_document()
    if not located:
        print(
            "\n  FAIL  未在 chunk_data 中找到 'FRT075-33F' 关键字。\n"
            f"        请先把 {PDF_PATH} 走一次索引流水线后再跑本测试。\n"
        )
        return 1
    doc_id, kb_id = located
    print(f"  OK   document_id   = {doc_id}")
    print(f"  OK   knowledge_base_id = {kb_id}")

    # ---- Step 3: 初始化 Service ----
    from src.service.knowledge.retrieve_service import RetrieveService
    service = RetrieveService()
    print("\n  RetrieveService 初始化完成")

    # ---- Step 4: 执行用例 ----
    print("\n" + "─" * 40)
    print(" Step 3: 执行测试用例")
    print("─" * 40)

    total_start = time.perf_counter()
    results: List[Tuple[str, bool]] = []

    cases = [
        ("T1 HYBRID 全 Pipeline",                   t1_hybrid_full),
        ("T2 SearchMode=SEMANTIC",                  t2_semantic_mode),
        ("T3 SearchMode=LEXICAL + filter 透传",     t3_lexical_mode),
        ("T4 FusionStrategy.WEIGHTED_SUM",          t4_weighted_sum_fusion),
        ("T5 ExactMatch + MetadataFilter 透传",     t5_lexical_filter_pushdown),
        ("T6 retrieve_custom + section_dense",      t6_custom_with_section),
    ]

    for name, fn in cases:
        try:
            ok = await fn(service, kb_id, doc_id)
        except Exception as e:
            print(f"  EXCEPTION in {name}: {e}")
            traceback.print_exc()
            ok = False
        results.append((name, ok))

    total_s = time.perf_counter() - total_start

    # ---- 汇总 ----
    print("\n" + "=" * 72)
    print(" 测试结果汇总")
    print("=" * 72)
    passed = 0
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if ok:
            passed += 1
    print(f"\n  {passed}/{len(results)} 通过, 总耗时 {total_s:.1f}s")

    write_report(
        results,
        total_s,
        project_root / "test" / "retrieve" / "pipeline"
            / "full_retrieve_with_pdf_report.md",
        document_id=doc_id,
        knowledge_base_id=kb_id,
    )

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

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run_all_tests()))
