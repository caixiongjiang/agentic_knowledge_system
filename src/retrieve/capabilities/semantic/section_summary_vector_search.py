#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_summary_vector_search.py
@Function:
    章节级摘要向量语义检索原子能力
    对 Milvus section_summary_store Collection 执行 ANN 检索。
=================================================="""
from typing import Any, Dict, List, Optional

from src.client.embedding import EmbeddingClient
from src.db.milvus import BaseMilvusManager
from src.db.milvus.repositories.extract.summary_repository import (
    SectionSummaryRepository,
)
from src.retrieve.capabilities.base import CapabilityDescriptor
from src.retrieve.capabilities.semantic.base_vector_search import BaseVectorSearch
from src.retrieve.types.result import SummaryItem


class SectionSummaryVectorSearch(BaseVectorSearch):
    """章节级摘要向量语义检索

    对 Milvus section_summary_store Collection 执行 ANN 向量检索，
    返回与查询最相关的章节摘要。

    章节摘要由 SectionSummaryWorker 对每个 section 生成，父 section 通过
    rollup 聚合子 section 摘要。命中后可通过 MongoDB section_data 的
    chunk_id_list 下钻到具体 chunk。

    对应 Collection: section_summary_store
    对应 Repository: SectionSummaryRepository
    """

    def __init__(
        self,
        embedding_client: Optional[EmbeddingClient] = None,
        milvus_manager: Optional[BaseMilvusManager] = None,
    ) -> None:
        repository = SectionSummaryRepository(manager=milvus_manager)
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
            name="section_summary_vector_search",
            display_name="章节摘要向量语义检索",
            description=(
                "在 section_summary_store 中执行向量 ANN 检索，"
                "召回与查询最相关的章节摘要。"
                "适用于需要定位到具体章节的场景，命中后可通过 chunk_id_list 下钻。"
            ),
            input_schema={
                "query_text": "str - 自然语言查询（与 query_vector 二选一）",
                "query_vector": "List[float] - 预计算向量（与 query_text 二选一）",
                "top_k": "int - 返回数量上限，默认 10",
                "filters": "MetadataFilter - 元数据过滤条件（可选）",
            },
            output_type="RetrieveResult[SummaryItem]",
        )
