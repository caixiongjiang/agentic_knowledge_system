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
from typing import Dict, List, Optional

from loguru import logger

from src.client.reranker import RerankerClient, RerankResult, create_reranker_client
from src.retrieve.pipeline.types import FusedCandidate
from src.retrieve.types.result import ChunkItem


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

        # 确保所有候选都有文本内容
        await self._ensure_texts(candidates)

        # 提取文本用于 rerank
        documents = [c.text or "" for c in candidates]
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
        """对缺少文本内容的候选，从 MongoDB 批量获取"""
        missing_ids = [
            c.chunk_id for c in candidates
            if not c.text and not c.chunk_id.startswith(("section:", "qa:", "summary:"))
        ]

        if not missing_ids:
            return

        try:
            from src.db.mongodb.repositories.chunk_data_repository import (
                ChunkDataRepository,
            )
            repo = ChunkDataRepository()
            chunk_data_list = await repo.get_by_ids(missing_ids)

            text_map: Dict[str, str] = {}
            for cd in chunk_data_list:
                text_map[str(cd.id)] = cd.text or ""

            for c in candidates:
                if not c.text and c.chunk_id in text_map:
                    c.text = text_map[c.chunk_id]

        except Exception as e:
            logger.warning(f"批量获取 Chunk 文本失败: {e}")

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
