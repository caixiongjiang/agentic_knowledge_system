#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_vector_search.py
@Author  : caixiongjiang
@Date    : 2026/02/28
@Function: 
    Chunk 粒度向量语义检索原子能力
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List, Optional

from src.client.embedding import EmbeddingClient
from src.db.milvus import BaseMilvusManager
from src.db.milvus.repositories.base.chunk_repository import ChunkRepository
from src.retrieve.capabilities.base import CapabilityDescriptor
from src.retrieve.capabilities.semantic.base_vector_search import BaseVectorSearch
from src.retrieve.types.result import ChunkItem, RetrieveResult


class ChunkVectorSearch(BaseVectorSearch):
    """Chunk 粒度向量语义检索

    对 Milvus chunk_store Collection 执行 ANN 向量检索，
    返回与查询语义最相似的文本块（Chunk）。

    对应 Collection: chunk_store
    对应 Repository: ChunkRepository
    """

    def __init__(
        self,
        embedding_client: Optional[EmbeddingClient] = None,
        milvus_manager: Optional[BaseMilvusManager] = None,
    ) -> None:
        repository = ChunkRepository(manager=milvus_manager)
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
                    if k not in ("document_id", "knowledge_base_id", "vector", "sparse_vector")
                },
            ))
        return items

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="chunk_vector_search",
            display_name="Chunk 向量语义检索",
            description=(
                "在 chunk_store 中执行向量 ANN 检索，"
                "召回与查询语义最相似的文本块。"
                "适用于事实性问答、精确定位单一知识点。"
            ),
            input_schema={
                "query_text": "str - 自然语言查询（与 query_vector 二选一）",
                "query_vector": "List[float] - 预计算向量（与 query_text 二选一）",
                "top_k": "int - 返回数量上限，默认 10",
                "filters": "MetadataFilter - 元数据过滤条件（可选）",
            },
            output_type="RetrieveResult[ChunkItem]",
        )
