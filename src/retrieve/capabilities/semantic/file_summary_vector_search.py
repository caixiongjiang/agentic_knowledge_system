#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : file_summary_vector_search.py
@Function:
    文档级摘要向量语义检索原子能力
    对 Milvus file_summary_store Collection 执行 ANN 检索。
=================================================="""
from typing import Any, Dict, List, Optional

from src.client.embedding import EmbeddingClient
from src.db.milvus import BaseMilvusManager
from src.db.milvus.repositories.extract.summary_repository import (
    FileSummaryRepository,
)
from src.retrieve.capabilities.base import CapabilityDescriptor
from src.retrieve.capabilities.semantic.base_vector_search import BaseVectorSearch
from src.retrieve.types.result import SummaryItem


class FileSummaryVectorSearch(BaseVectorSearch):
    """文档级摘要向量语义检索

    对 Milvus file_summary_store Collection 执行 ANN 向量检索，
    返回与查询最相关的文档摘要。

    文档摘要由 FileSummaryService 基于 section 摘要 rollup 生成，
    提供整篇文档的概览视角。适用于"有没有讲 X 的文档"、文档级主题定位。

    对应 Collection: file_summary_store
    对应 Repository: FileSummaryRepository
    """

    def __init__(
        self,
        embedding_client: Optional[EmbeddingClient] = None,
        milvus_manager: Optional[BaseMilvusManager] = None,
    ) -> None:
        repository = FileSummaryRepository(manager=milvus_manager)
        super().__init__(repository=repository, embedding_client=embedding_client)

    def _build_result_items(self, hits: List[Dict[str, Any]]) -> List[SummaryItem]:
        items: List[SummaryItem] = []
        for hit in hits:
            entity = hit.get("entity", {})
            items.append(SummaryItem(
                summary_id=str(hit.get("id", "")),
                score=hit.get("score", 0.0),
                document_id=entity.get("document_id"),
                knowledge_base_id=entity.get("knowledge_base_id"),
                summary_type=entity.get("type"),
                metadata={
                    k: v for k, v in entity.items()
                    if k not in ("document_id", "knowledge_base_id", "vector", "type")
                },
            ))
        return items

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="file_summary_vector_search",
            display_name="文档摘要向量语义检索",
            description=(
                "在 file_summary_store 中执行向量 ANN 检索，"
                "召回与查询最相关的文档级摘要。"
                "适用于需要概览整篇文档、快速定位相关文档的场景。"
            ),
            input_schema={
                "query_text": "str - 自然语言查询（与 query_vector 二选一）",
                "query_vector": "List[float] - 预计算向量（与 query_text 二选一）",
                "top_k": "int - 返回数量上限，默认 10",
                "filters": "MetadataFilter - 元数据过滤条件（可选）",
            },
            output_type="RetrieveResult[SummaryItem]",
        )
