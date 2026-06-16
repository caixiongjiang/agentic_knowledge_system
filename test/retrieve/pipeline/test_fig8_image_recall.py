#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
诊断：Fig.8 图片 chunk 多路召回失败原因

复现用户提供的 route_plan 参数，逐路检查：
  - MongoDB 是否存在含 Fig.8 的 image chunk
  - exact_match / chunk_dense / bm25_sparse 各路独立召回
  - 完整 Pipeline（RRF + Rerank）
  - match_mode EXACT vs fuzzy 差异
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

KB_ID = "kb-dc3910bf-5e4a-4b8e-8b42-8fe4fa249fe8"
QUERY_TEXT = "Fig.8 图片"
TOP_K = 10

USER_ROUTE_PLAN = [
    {
        "route": "exact_match",
        "top_k": 10,
        "params": {
            "keywords": ["Fig.8"],
            "match_mode": "EXACT",
            "filters": {"kb_id": KB_ID},
        },
    },
    {
        "route": "chunk_dense",
        "top_k": 20,
        "params": {
            "query_text": "Fig.8 图片",
            "filters": {"kb_id": KB_ID},
        },
    },
    {
        "route": "bm25_sparse",
        "top_k": 20,
        "params": {
            "query_text": "Fig.8 图片",
            "filters": {"kb_id": KB_ID},
        },
    },
]


def _hr(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")


def _print_items(label: str, items: List[Any], limit: int = 8) -> None:
    print(f"\n  [{label}] 命中 {len(items)} 条")
    for i, item in enumerate(items[:limit]):
        text = (getattr(item, "text", None) or "")[:160].replace("\n", " ")
        meta = getattr(item, "metadata", {}) or {}
        chunk_type = meta.get("chunk_type", "?")
        score = getattr(item, "score", None)
        print(
            f"    {i + 1}. score={score} type={chunk_type} "
            f"id={getattr(item, 'chunk_id', '?')[:40]} "
            f"text={text!r}",
        )


async def init_mongodb() -> None:
    from src.db.mongodb.mongodb_manager import MongoDBManager
    await MongoDBManager.get_instance()


async def diagnose_mongodb_chunks(kb_id: str) -> Dict[str, Any]:
    """在 Mongo / MySQL 中查找 Fig.8 相关 image chunk。"""
    _hr("Step 1 · 数据层诊断（MongoDB + MySQL）")
    info: Dict[str, Any] = {
        "kb_image_chunks": 0,
        "fig8_in_text": [],
        "fig8_in_caption": [],
        "sample_image_texts": [],
    }

    try:
        await init_mongodb()
        from src.db.mongodb.models.chunk_data import ChunkData
        from src.db.mysql.connection.factory import get_mysql_manager
        from src.db.mysql.models.base.chunk_meta_info import ChunkMetaInfo
        from src.db.mysql.models.base.chunk_section_document import (
            ChunkSectionDocument,
        )

        manager = get_mysql_manager()
        with manager.get_session() as session:
            image_rows = (
                session.query(ChunkSectionDocument.chunk_id)
                .join(
                    ChunkMetaInfo,
                    ChunkSectionDocument.chunk_id == ChunkMetaInfo.chunk_id,
                )
                .filter(
                    ChunkSectionDocument.knowledge_base_id == kb_id,
                    ChunkMetaInfo.chunk_type == "image",
                    ChunkSectionDocument.deleted == 0,
                    ChunkMetaInfo.deleted == 0,
                )
                .all()
            )
        image_ids = [r[0] for r in image_rows if r and r[0]]
        info["kb_image_chunks"] = len(image_ids)
        print(f"  知识库 {kb_id} 下 image chunk 数量: {len(image_ids)}")

        if not image_ids:
            print("  ⚠️  该知识库没有任何 image 类型 chunk")
            return info

        docs = await ChunkData.find(
            {"_id": {"$in": image_ids}, "deleted": 0},
        ).to_list()

        for doc in docs:
            text_meta = doc.text_meta or {}
            text = text_meta.get("text", "") or ""
            caption = text_meta.get("image_caption", "") or ""
            if "Fig.8" in text or "fig.8" in text.lower():
                info["fig8_in_text"].append(str(doc.id))
            if "Fig.8" in caption or "fig.8" in caption.lower():
                info["fig8_in_caption"].append(str(doc.id))

        print(f"  text 字段含 Fig.8: {len(info['fig8_in_text'])} 条")
        print(f"  image_caption 含 Fig.8: {len(info['fig8_in_caption'])} 条")

        for doc in docs[:3]:
            text_meta = doc.text_meta or {}
            info["sample_image_texts"].append({
                "id": str(doc.id),
                "text": text_meta.get("text", "")[:300],
                "caption": text_meta.get("image_caption", "")[:200],
            })
            print(f"\n  样例 image chunk: {doc.id}")
            print(f"    text    = {(text_meta.get('text', ''))[:200]!r}")
            print(f"    caption = {(text_meta.get('image_caption', ''))[:200]!r}")

        # 全库扫描（不限 KB）看 Fig.8 是否在别的库
        fig8_any = await ChunkData.find(
            {
                "deleted": 0,
                "$or": [
                    {"text_meta.text": {"$regex": "Fig\\.8", "$options": "i"}},
                    {"text_meta.image_caption": {"$regex": "Fig\\.8", "$options": "i"}},
                ],
            },
        ).limit(5).to_list()
        print(f"\n  全库含 Fig.8 的 chunk（最多 5 条）: {len(fig8_any)}")
        for doc in fig8_any:
            text_meta = doc.text_meta or {}
            print(f"    - {doc.id} type={doc.chunk_type} caption={text_meta.get('image_caption', '')[:80]!r}")

    except Exception as e:
        print(f"  ❌ 数据层诊断失败: {e}")
        traceback.print_exc()

    return info


async def run_per_route_recall(kb_id: str) -> None:
    """逐路独立召回 + 完整 Pipeline。"""
    await init_mongodb()
    from src.retrieve.pipeline.parallel_recall import (
        ParallelRecallExecutor,
        build_query_for_route,
    )
    from src.retrieve.pipeline.route_registry import RouteRegistry
    from src.retrieve.pipeline.types import (
        FusionStrategy,
        RouteConfig,
        RoutePlan,
    )
    from src.retrieve.types.enums import MatchMode
    from src.retrieve.types.query import LexicalQuery, MetadataFilter
    from src.service.knowledge.retrieve_service import RetrieveService

    filters = MetadataFilter(knowledge_base_id=kb_id)
    routes = [RouteConfig(**r) for r in USER_ROUTE_PLAN]

    _hr("Step 2 · 逐路独立召回（使用请求级 knowledge_base_id 过滤）")
    executor = ParallelRecallExecutor(RouteRegistry())

    for route_cfg in routes:
        print(f"\n  --- 路由: {route_cfg.route} ---")
        print(f"  params = {json.dumps(route_cfg.params, ensure_ascii=False)}")
        try:
            results = await executor.execute(
                routes=[route_cfg],
                query_text=QUERY_TEXT,
                filters=filters,
            )
            if not results:
                print("  结果: 0 条")
                continue
            _print_items(route_cfg.route, results[0].items)
            image_hits = [
                it for it in results[0].items
                if (it.metadata or {}).get("chunk_type") == "image"
            ]
            print(f"  其中 image 类型: {len(image_hits)} 条")
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            traceback.print_exc()

    _hr("Step 3 · exact_match match_mode 对比（EXACT vs fuzzy）")
    from src.retrieve.capabilities.lexical.exact_match import ExactMatch

    for mode_label, mode in [("EXACT(错误值EXACT→回退fuzzy)", "EXACT"), ("fuzzy", "fuzzy"), ("exact小写", "exact")]:
        q = LexicalQuery(
            keywords=["Fig.8"],
            match_mode=MatchMode.FUZZY,  # placeholder
            top_k=10,
            filters=filters,
        )
        # 模拟 build_query_for_route 的 match_mode 解析
        try:
            q.match_mode = MatchMode(mode)
        except ValueError:
            q.match_mode = MatchMode.FUZZY
        print(f"\n  match_mode 输入={mode!r} → 实际={q.match_mode.value}")
        try:
            result = await ExactMatch().execute(query=q)
            _print_items(mode_label, result.items)
        except Exception as e:
            print(f"  ❌ {e}")

    _hr("Step 4a · RRF 融合排名（Rerank 之前）")
    from src.retrieve.pipeline.fusion import create_fusion
    from src.retrieve.pipeline.granularity_alignment import GranularityAligner

    aligner = GranularityAligner()
    recall_all = await executor.execute(
        routes=routes,
        query_text=QUERY_TEXT,
        filters=filters,
    )
    aligned = await aligner.align(recall_all)
    fused = create_fusion(strategy=FusionStrategy.RRF).fuse(
        aligned, top_n=50,
    )
    fig8_ids = {
        "chunk-7743203f-801b-423e-b9e5-eba9982c6d93",  # text
        "chunk-d9d2b61d-77a9-4312-9122-207bc890fefb",  # image
    }
    print(f"  RRF 候选总数: {len(fused)}")
    for rank, c in enumerate(fused, 1):
        if c.chunk_id in fig8_ids:
            ctype = (c.metadata or {}).get("chunk_type", "?")
            print(
                f"    RRF #{rank}: {c.chunk_id[:40]} type={ctype} "
                f"rrf={c.rrf_score:.6f} routes={c.source_routes} "
                f"text={(c.text or '')[:80]!r}",
            )

    _hr("Step 4 · 完整 Pipeline（retrieve_custom + RRF + Rerank）")
    service = RetrieveService()
    try:
        resp = await service.retrieve_custom(
            routes=routes,
            query_text=QUERY_TEXT,
            filters=filters,
            top_k=TOP_K,
            enable_rerank=True,
        )
        _print_items("pipeline_final", resp.items)
        image_hits = [
            it for it in resp.items
            if (it.metadata or {}).get("chunk_type") == "image"
        ]
        print(f"\n  最终 Top-{TOP_K} 中 image 类型: {len(image_hits)} 条")
        if resp.phase_timings:
            t = resp.phase_timings
            print(
                f"  耗时: recall={t.recall_ms:.0f}ms "
                f"align={t.alignment_ms:.0f}ms "
                f"fusion={t.fusion_ms:.0f}ms "
                f"rerank={t.rerank_ms:.0f}ms",
            )
    except Exception as e:
        print(f"  ❌ Pipeline 失败: {e}")
        traceback.print_exc()

    _hr("Step 5 · route_plan.params.filters 是否被使用？")
    print("  当前 build_query_for_route 只使用请求级 MetadataFilter，")
    print("  不会读取 route_plan[].params.filters（其中 kb_id 字段也不会生效）。")
    print("  实际过滤字段应为 knowledge_base_id（由 search_knowledge_base 工具注入）。")
    sample = build_query_for_route(routes[0], QUERY_TEXT, filters)
    print(f"  exact_match 实际 filters.knowledge_base_id = {sample.filters.knowledge_base_id}")


async def main() -> int:
    print("Fig.8 图片多路召回诊断测试")
    print(f"KB_ID={KB_ID}")
    print(f"QUERY={QUERY_TEXT!r}")

    await diagnose_mongodb_chunks(KB_ID)
    await run_per_route_recall(KB_ID)

    _hr("结论提示")
    print("  若 Step1 显示 image_caption 含 Fig.8 但 text 不含 → exact_match 只搜 text 字段会漏检")
    print("  若 Step1 显示该 KB 无 image chunk → 索引/入库问题，与召回无关")
    print("  若各路有 image 但 Pipeline 最终无 image → Rerank 把图片挤出 Top-K")
    print("  match_mode=EXACT 要求整段 text 完全等于关键词，对图片 chunk 几乎永远失败")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
