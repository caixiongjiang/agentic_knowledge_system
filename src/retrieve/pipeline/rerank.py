#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : rerank.py
@Author  : caixiongjiang
@Date    : 2026/04/03
@Function: 
    Phase 5: Reranker 精排封装
    调用 Cross-Encoder 对融合候选做精排
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from src.client.reranker import RerankerClient, RerankResult, create_reranker_client
from src.retrieve.pipeline.types import FusedCandidate
from src.retrieve.types.result import ChunkItem
from src.types.utils.chunk_search_text import resolve_chunk_display_text


class RerankStage:
    """Reranker 精排阶段

    从 MongoDB 获取 Chunk 文本内容，调用 Cross-Encoder 对候选精排。
    """

    def __init__(
        self,
        reranker_client: Optional[RerankerClient] = None,
    ) -> None:
        self._client = reranker_client

    def _get_client(self) -> RerankerClient:
        if self._client is None:
            self._client = create_reranker_client()
        return self._client

    async def rerank(
        self,
        query: str,
        candidates: List[FusedCandidate],
        top_k: int = 10,
    ) -> List[ChunkItem]:
        """精排候选集

        Args:
            query: 原始查询文本
            candidates: RRF 融合后的候选
            top_k: 最终返回数量

        Returns:
            精排后的 ChunkItem 列表
        """
        if not candidates:
            return []

        start = time.perf_counter()

        # 补全展示文本与检索文本
        await self._ensure_texts(candidates)

        # Rerank 使用 search_text（去包装），不用展示 text
        documents = [
            (c.metadata or {}).get("_search_text") or c.text or ""
            for c in candidates
        ]
        non_empty_indices = [i for i, d in enumerate(documents) if d.strip()]

        if not non_empty_indices:
            logger.warning("所有候选文本为空，跳过 Rerank")
            return self._candidates_to_items(candidates[:top_k])

        non_empty_docs = [documents[i] for i in non_empty_indices]
        non_empty_candidates = [candidates[i] for i in non_empty_indices]

        client = self._get_client()
        rerank_results: List[RerankResult] = await client.arerank(
            query=query,
            documents=non_empty_docs,
            top_k=min(top_k, len(non_empty_docs)),
        )

        # 按 rerank 分数构建最终结果
        items: List[ChunkItem] = []
        for rr in rerank_results:
            if rr.index < len(non_empty_candidates):
                c = non_empty_candidates[rr.index]
                items.append(ChunkItem(
                    chunk_id=c.chunk_id,
                    score=rr.score,
                    document_id=c.document_id,
                    section_id=c.section_id,
                    knowledge_base_id=c.knowledge_base_id,
                    text=c.text,
                    metadata={
                        **c.metadata,
                        "_rrf_score": c.rrf_score,
                        "_source_routes": c.source_routes,
                    },
                ))

        elapsed = (time.perf_counter() - start) * 1000
        logger.debug(
            f"Rerank 完成: {len(candidates)} 候选 → {len(items)} 结果, "
            f"耗时 {elapsed:.1f}ms"
        )
        return items

    async def _ensure_texts(self, candidates: List[FusedCandidate]) -> None:
        """从 MongoDB 批量补全展示文本与检索文本。"""
        chunk_ids = [
            c.chunk_id for c in candidates
            if not c.chunk_id.startswith(("section:", "qa:", "summary:"))
        ]
        if not chunk_ids:
            return

        try:
            from src.db.mongodb.repositories.chunk_data_repository import (
                ChunkDataRepository,
            )
            repo = ChunkDataRepository()
            chunk_data_list = await repo.get_by_ids(chunk_ids)

            display_map: Dict[str, str] = {}
            search_map: Dict[str, str] = {}
            meta_map: Dict[str, Dict[str, Any]] = {}
            for cd in chunk_data_list:
                cid = str(cd.id)
                # 展示文本：从 text_meta 拼接
                display_map[cid] = resolve_chunk_display_text(cd)
                # 检索文本：直接使用 MongoDB 中的 search_text 字段
                if cd.search_text and cd.search_text.strip():
                    search_map[cid] = cd.search_text.strip()
                extra: Dict[str, Any] = {}
                if cd.chunk_type:
                    extra["chunk_type"] = cd.chunk_type
                # 从 text_meta 提取元数据用于 format_chunks_for_llm 展示
                text_meta = cd.text_meta or {}
                if text_meta.get("image_caption"):
                    extra["image_caption"] = text_meta["image_caption"]
                if text_meta.get("image_footnote"):
                    extra["image_footnote"] = text_meta["image_footnote"]
                if text_meta.get("table_caption"):
                    extra["table_caption"] = text_meta["table_caption"]
                if text_meta.get("table_footnote"):
                    extra["table_footnote"] = text_meta["table_footnote"]
                if extra:
                    meta_map[cid] = extra

            for c in candidates:
                cid = c.chunk_id
                if cid in display_map:
                    c.text = display_map[cid]
                if cid in search_map:
                    c.metadata["_search_text"] = search_map[cid]
                else:
                    c.metadata["_search_text"] = c.text or ""
                if cid in meta_map:
                    c.metadata.update(meta_map[cid])

        except Exception as e:
            logger.warning(f"批量获取 Chunk 文本失败: {e}")
            for c in candidates:
                c.metadata["_search_text"] = c.text or ""

    @staticmethod
    def _candidates_to_items(candidates: List[FusedCandidate]) -> List[ChunkItem]:
        return [
            ChunkItem(
                chunk_id=c.chunk_id,
                score=c.rrf_score,
                document_id=c.document_id,
                section_id=c.section_id,
                knowledge_base_id=c.knowledge_base_id,
                text=c.text,
                metadata=c.metadata,
            )
            for c in candidates
        ]
