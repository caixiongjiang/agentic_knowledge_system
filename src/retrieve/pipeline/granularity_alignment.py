#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : granularity_alignment.py
@Author  : caixiongjiang
@Date    : 2026/04/03
@Function: 
    Phase 3: 跨粒度对齐
    将 Section/QA/Summary 级别的召回结果下钻对齐到 Chunk 粒度
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from src.retrieve.pipeline.types import RecallResult
from src.retrieve.types.result import ChunkItem


# Section/Document 级别下钻时每个范围保留的最大 Chunk 数
_DEFAULT_DRILLDOWN_TOP_N = 5

# 不同粒度下钻时的分数衰减系数
_SCORE_DECAY = {
    "section": 0.9,
    "qa": 1.0,
    "summary": 0.7,
}


class GranularityAligner:
    """跨粒度对齐器

    将各路召回结果统一对齐到 Chunk 粒度。
    - Chunk 级别结果: 直接透传
    - Section 级别结果: 查询该 Section 下所有 Chunk，用 query 向量二次精排
    - QA 级别结果: 通过 QA 元数据溯源到 chunk_id
    - Summary 级别结果: Document → Section → Chunk 逐级下钻
    """

    def __init__(
        self,
        drilldown_top_n: int = _DEFAULT_DRILLDOWN_TOP_N,
    ) -> None:
        self._drilldown_top_n = drilldown_top_n

    async def align(
        self,
        recall_results: List[RecallResult],
        query_vector: Optional[List[float]] = None,
    ) -> List[RecallResult]:
        """对所有召回结果执行跨粒度对齐

        Args:
            recall_results: 各路召回结果
            query_vector: 查询向量（用于非 Chunk 粒度结果的 in-memory 二次精排）

        Returns:
            对齐后的 RecallResult 列表，所有 items 均为真实 Chunk 粒度
        """
        start = time.perf_counter()
        aligned_results: List[RecallResult] = []

        for rr in recall_results:
            needs_alignment = any(
                item.metadata.get("_original_type") in ("section", "qa", "summary")
                for item in rr.items
            )
            if not needs_alignment:
                aligned_results.append(rr)
                continue

            aligned_items = await self._align_single_route(rr, query_vector)
            aligned_results.append(RecallResult(
                route=rr.route,
                items=aligned_items,
                total_count=len(aligned_items),
                execution_time_ms=rr.execution_time_ms,
            ))

        elapsed = (time.perf_counter() - start) * 1000
        logger.debug(f"跨粒度对齐完成: 耗时 {elapsed:.1f}ms")
        return aligned_results

    async def _align_single_route(
        self,
        rr: RecallResult,
        query_vector: Optional[List[float]],
    ) -> List[ChunkItem]:
        """对单路结果中的非 Chunk 项执行下钻"""
        aligned: List[ChunkItem] = []

        for item in rr.items:
            original_type = item.metadata.get("_original_type")

            if original_type == "section":
                section_id = item.metadata.get("_section_id")
                if section_id:
                    drilled = await self._drilldown_section(
                        section_id, item.score, query_vector,
                    )
                    aligned.extend(drilled)
                continue

            if original_type == "qa":
                qa_chunks = await self._resolve_qa_to_chunk(item)
                aligned.extend(qa_chunks)
                continue

            if original_type == "summary":
                summary_chunks = await self._drilldown_summary(
                    item, query_vector,
                )
                aligned.extend(summary_chunks)
                continue

            # Already chunk-level
            aligned.append(item)

        return aligned

    async def _drilldown_section(
        self,
        section_id: str,
        parent_score: float,
        query_vector: Optional[List[float]],
    ) -> List[ChunkItem]:
        """Section → Chunk 下钻"""
        try:
            from src.db.mysql.repositories.base.chunk_section_document_repo import (
                ChunkSectionDocumentRepository,
            )
            from src.db.mysql.connection.factory import get_mysql_manager

            manager = get_mysql_manager()
            repo = ChunkSectionDocumentRepository()

            with manager.get_session() as session:
                rels = repo.get_by_section_id(session, section_id)

            if not rels:
                return []

            chunk_ids = [r.chunk_id for r in rels]

            # 如果有 query_vector，做 in-memory 二次精排
            if query_vector and len(chunk_ids) > self._drilldown_top_n:
                chunk_ids = await self._inmemory_rerank_chunks(
                    chunk_ids, query_vector, self._drilldown_top_n,
                )

            decay = _SCORE_DECAY.get("section", 0.9)
            items: List[ChunkItem] = []
            for cid in chunk_ids[: self._drilldown_top_n]:
                items.append(ChunkItem(
                    chunk_id=cid,
                    score=parent_score * decay,
                    metadata={
                        "_source_route": "section_drilldown",
                        "_section_id": section_id,
                    },
                ))
            return items

        except Exception as e:
            logger.error(f"Section 下钻失败 (section_id={section_id}): {e}")
            return []

    async def _resolve_qa_to_chunk(self, item: ChunkItem) -> List[ChunkItem]:
        """QA → Chunk 溯源（v1.1：按 source_chunk_ids 展开）

        v1.1 TextAnalyzer 的 QA 在 section 级抽取，可横跨多 chunk，溯源信息
        在 metadata["source_chunk_ids"]（由 QAVectorSearch Mongo 下钻回填）。
        本方法把 QA 展开为它所依据的若干真实 ChunkItem，注入候选池参与融合，
        保留 answer / qa_id 在 metadata 供后续 rerank / tool 渲染。
        """
        decay = _SCORE_DECAY.get("qa", 1.0)
        qa_id = item.metadata.get("_qa_id")
        answer = item.metadata.get("answer")
        source_chunk_ids = item.metadata.get("source_chunk_ids") or []

        # 优先走 v1.1 多 chunk 溯源
        if source_chunk_ids:
            items: List[ChunkItem] = []
            for cid in list(source_chunk_ids)[: self._drilldown_top_n]:
                if not cid:
                    continue
                items.append(ChunkItem(
                    chunk_id=cid,
                    score=item.score * decay,
                    document_id=item.document_id,
                    knowledge_base_id=item.knowledge_base_id,
                    metadata={
                        "_source_route": "qa_traceback",
                        "_qa_id": qa_id,
                        "answer": answer,
                    },
                ))
            if items:
                return items
            # source_chunk_ids 全空 → 落到下方兜底

        # 兼容旧路径：metadata 单 chunk_id（v1.0 chunk 级 QA 遗留）
        chunk_id = item.metadata.get("chunk_id")
        if chunk_id:
            return [ChunkItem(
                chunk_id=chunk_id,
                score=item.score * decay,
                document_id=item.document_id,
                knowledge_base_id=item.knowledge_base_id,
                metadata={
                    "_source_route": "qa_traceback",
                    "_qa_id": qa_id,
                    "answer": answer,
                },
            )]

        # 无任何溯源信息：保留 QA 项本身（question 作为 text 参与 rerank）
        return [item]

    async def _drilldown_summary(
        self,
        item: ChunkItem,
        query_vector: Optional[List[float]],
    ) -> List[ChunkItem]:
        """Summary (Document) → Section → Chunk 逐级下钻"""
        document_id = item.document_id
        if not document_id:
            return [item]

        try:
            from src.db.mysql.repositories.base.section_document_repo import (
                SectionDocumentRepository,
            )
            from src.db.mysql.repositories.base.chunk_section_document_repo import (
                ChunkSectionDocumentRepository,
            )
            from src.db.mysql.connection.factory import get_mysql_manager

            manager = get_mysql_manager()
            sec_repo = SectionDocumentRepository()
            chunk_repo = ChunkSectionDocumentRepository()

            with manager.get_session() as session:
                sections = sec_repo.get_by_document_id(session, document_id)
                if not sections:
                    return []

                all_chunk_ids: List[str] = []
                for sec in sections[:5]:
                    rels = chunk_repo.get_by_section_id(session, sec.section_id)
                    all_chunk_ids.extend(r.chunk_id for r in rels)

            if not all_chunk_ids:
                return []

            if query_vector and len(all_chunk_ids) > self._drilldown_top_n:
                all_chunk_ids = await self._inmemory_rerank_chunks(
                    all_chunk_ids, query_vector, self._drilldown_top_n,
                )

            decay = _SCORE_DECAY.get("summary", 0.7)
            items: List[ChunkItem] = []
            for cid in all_chunk_ids[: self._drilldown_top_n]:
                items.append(ChunkItem(
                    chunk_id=cid,
                    score=item.score * decay,
                    document_id=document_id,
                    metadata={
                        "_source_route": "summary_drilldown",
                    },
                ))
            return items

        except Exception as e:
            logger.error(f"Summary 下钻失败 (document_id={document_id}): {e}")
            return [item]

    async def _inmemory_rerank_chunks(
        self,
        chunk_ids: List[str],
        query_vector: List[float],
        top_n: int,
    ) -> List[str]:
        """用 query 向量对一批 chunk 做 in-memory cosine similarity 精排

        从 Milvus 获取 chunk 向量，在内存中计算 cosine similarity 排序。
        """
        try:
            from src.db.milvus.repositories.base.chunk_repository import ChunkRepository

            repo = ChunkRepository()
            entities = repo.query_by_ids(chunk_ids, output_fields=["vector"])

            if not entities:
                return chunk_ids[:top_n]

            id_to_vec: Dict[str, List[float]] = {}
            for ent in entities:
                eid = str(ent.get("id", ""))
                vec = ent.get("vector")
                if eid and vec:
                    id_to_vec[eid] = vec

            q = np.array(query_vector, dtype=np.float32)
            q_norm = np.linalg.norm(q)
            if q_norm == 0:
                return chunk_ids[:top_n]

            scored: List[Tuple[str, float]] = []
            for cid in chunk_ids:
                vec = id_to_vec.get(cid)
                if vec is None:
                    scored.append((cid, 0.0))
                    continue
                v = np.array(vec, dtype=np.float32)
                v_norm = np.linalg.norm(v)
                if v_norm == 0:
                    scored.append((cid, 0.0))
                    continue
                sim = float(np.dot(q, v) / (q_norm * v_norm))
                scored.append((cid, sim))

            scored.sort(key=lambda x: x[1], reverse=True)
            return [cid for cid, _ in scored[:top_n]]

        except Exception as e:
            logger.warning(f"in-memory rerank 失败，回退截断: {e}")
            return chunk_ids[:top_n]
