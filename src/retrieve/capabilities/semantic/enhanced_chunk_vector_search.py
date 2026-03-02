#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : enhanced_chunk_vector_search.py
@Author  : caixiongjiang
@Date    : 2026/02/28
@Function: 
    Enhanced Chunk 上下文增强向量语义检索原子能力
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List, Optional

from src.client.embedding import EmbeddingClient
from src.db.milvus import BaseMilvusManager
from src.db.milvus.repositories.enhanced.enhanced_chunk_repository import EnhancedChunkRepository
from src.retrieve.capabilities.base import CapabilityDescriptor
from src.retrieve.capabilities.semantic.base_vector_search import BaseVectorSearch
from src.retrieve.types.result import ChunkItem


class EnhancedChunkVectorSearch(BaseVectorSearch):
    """Enhanced Chunk 增强向量语义检索

    对 Milvus enhanced_chunk_store Collection 执行 ANN 向量检索。
    此 Collection 的向量融合了 Section 标题背景语义，
    适合处理包含歧义、代词或强依赖上下文背景的查询。

    对应 Collection: enhanced_chunk_store
    对应 Repository: EnhancedChunkRepository
    """

    def __init__(
        self,
        embedding_client: Optional[EmbeddingClient] = None,
        milvus_manager: Optional[BaseMilvusManager] = None,
    ) -> None:
        repository = EnhancedChunkRepository(manager=milvus_manager)
        super().__init__(repository=repository, embedding_client=embedding_client)

    def _build_result_items(self, hits: List[Dict[str, Any]]) -> List[ChunkItem]:
        items: List[ChunkItem] = []
        for hit in hits:
            entity = hit.get("entity", {})
            items.append(ChunkItem(
                chunk_id=str(hit.get("id", "")),
                score=hit.get("score", 0.0),
                document_id=entity.get("document_id"),
                knowledge_base_id=entity.get("knowledge_base_id"),
                metadata={
                    k: v for k, v in entity.items()
                    if k not in ("document_id", "knowledge_base_id", "vector")
                },
            ))
        return items

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="enhanced_chunk_vector_search",
            display_name="Enhanced Chunk 上下文增强语义检索",
            description=(
                "在 enhanced_chunk_store 中执行向量 ANN 检索。"
                "向量融合了章节标题的背景语义，能更好地处理歧义查询。"
                "适用于包含代词、上下文依赖的问题。"
            ),
            input_schema={
                "query_text": "str - 自然语言查询（与 query_vector 二选一）",
                "query_vector": "List[float] - 预计算向量（与 query_text 二选一）",
                "top_k": "int - 返回数量上限，默认 10",
                "filters": "MetadataFilter - 元数据过滤条件（可选）",
            },
            output_type="RetrieveResult[ChunkItem]",
        )
