#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : bm25_search.py
@Author  : caixiongjiang
@Date    : 2026/03/02
@Function: 
    稀疏向量全文检索原子能力
    
    核心流程:
      query_text → SparseEmbeddingClient(BGE-M3) → 稀疏向量
      → Milvus ChunkRepository.search_sparse() → RetrieveResult[ChunkItem]
    
    依赖:
      - BGE-M3 稀疏向量服务（通过 SparseEmbeddingClient 调用）
      - Milvus ChunkRepository（稀疏向量 ANN 检索）
@Modify History:
    2026/03/04 - 将编码器从 pymilvus BM25EmbeddingFunction 替换为 SparseEmbeddingClient（BGE-M3）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List, Optional

from loguru import logger

from src.client.embedding import SparseEmbeddingClient, create_sparse_embedding_client
from src.db.milvus import BaseMilvusManager
from src.db.milvus.repositories.base.chunk_repository import ChunkRepository
from src.retrieve.capabilities.base import BaseCapability, CapabilityDescriptor
from src.retrieve.types.query import LexicalQuery
from src.retrieve.types.result import ChunkItem, RetrieveResult


class BM25Search(BaseCapability):
    """稀疏向量全文检索

    使用 BGE-M3 模型将查询文本编码为稀疏向量，
    再对 Milvus chunk_store 的 sparse_vector 字段执行 ANN 检索。
    IP（内积）度量下的稀疏向量检索实现全文关键词匹配排序。

    对应 Collection: chunk_store
    对应 Repository: ChunkRepository
    """

    def __init__(
        self,
        milvus_manager: Optional[BaseMilvusManager] = None,
        sparse_embedding_client: Optional[SparseEmbeddingClient] = None,
    ) -> None:
        super().__init__()
        self._repository = ChunkRepository(manager=milvus_manager)
        self._sparse_client = sparse_embedding_client or create_sparse_embedding_client()

    async def _do_execute(self, **kwargs: Any) -> RetrieveResult:
        query: LexicalQuery = kwargs["query"]

        if not query.query_text:
            raise ValueError("BM25Search 需要 query_text 参数")

        query_sparse_vector = await self._sparse_client.aembed_sparse(query.query_text)

        filter_expr = query.filters.to_milvus_filter_expr() if query.filters else None

        raw_results = self._repository.search_sparse(
            sparse_vectors=[query_sparse_vector],
            sparse_field="sparse_vector",
            top_k=query.top_k,
            filter_expr=filter_expr,
        )

        hits = raw_results[0] if raw_results else []
        items = self._build_result_items(hits)

        if query.score_threshold is not None and items:
            before_count = len(items)
            items = [it for it in items if it.score >= query.score_threshold]
            filtered_count = before_count - len(items)
            if filtered_count:
                logger.debug(
                    f"BM25 召回阈值过滤: {filtered_count}/{before_count} 条 "
                    f"score < {query.score_threshold} 被过滤"
                )

        return RetrieveResult(
            items=items,
            total_count=len(items),
        )

    def _build_result_items(self, hits: List[Dict[str, Any]]) -> List[ChunkItem]:
        items: List[ChunkItem] = []
        for hit in hits:
            entity = hit.get("entity", {})
            items.append(ChunkItem(
                chunk_id=str(hit.get("id", "")),
                score=hit.get("score", 0.0),
                document_id=entity.get("document_id"),
                knowledge_base_id=entity.get("knowledge_base_id"),
                text=entity.get("text"),
                metadata={
                    k: v for k, v in entity.items()
                    if k not in (
                        "document_id", "knowledge_base_id",
                        "vector", "sparse_vector",
                    )
                },
            ))
        return items

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="bm25_search",
            display_name="稀疏向量全文检索（路由名 bm25_sparse）",
            description=(
                "路由标识 **bm25_sparse**：**BGE-M3 learned sparse representation** + Milvus sparse_vector 相似度检索；"
                "**不是**传统 BM25 倒排统计。查询为自然语言（整句或你认为更利于该路的改写均可），由稀疏编码器内部处理，无需刻意「空格拆词」。"
                "可与稠密向量路组合；若路由计划里为该路提供了 ``params.query_text``，则使用该改写，否则用用户原问。"
            ),
            input_schema={
                "query_text": "str - 默认=用户原问；可选由 route_plan.params.query_text 按路覆盖",
                "top_k": "int - 返回数量上限，默认 10",
                "filters": "MetadataFilter - 元数据过滤条件（可选）",
            },
            output_type="RetrieveResult[ChunkItem]",
        )
