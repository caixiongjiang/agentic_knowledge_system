#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : qa_vector_search.py
@Author  : caixiongjiang
@Date    : 2026/02/28
@Function: 
    原子 QA 对向量语义检索原子能力
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List, Optional

from src.client.embedding import EmbeddingClient
from src.db.milvus import BaseMilvusManager
from src.db.milvus.repositories.extract.atomic_qa_repository import AtomicQARepository
from src.retrieve.capabilities.base import CapabilityDescriptor
from src.retrieve.capabilities.semantic.base_vector_search import BaseVectorSearch
from src.retrieve.types.result import QAItem


class QAVectorSearch(BaseVectorSearch):
    """原子 QA 对向量语义检索

    对 Milvus atomic_qa_store Collection 执行 ANN 向量检索，
    返回与查询最相似的问答对。

    QA 对由后台阶段从 Chunk 中抽取生成，每对包含一个精炼问题和对应答案。
    适合问答场景，尤其是用户提问的表述与原文差异较大时，
    通过匹配已抽取的"问题"来间接命中答案。

    对应 Collection: atomic_qa_store
    对应 Repository: AtomicQARepository
    """

    def __init__(
        self,
        embedding_client: Optional[EmbeddingClient] = None,
        milvus_manager: Optional[BaseMilvusManager] = None,
    ) -> None:
        repository = AtomicQARepository(manager=milvus_manager)
        super().__init__(repository=repository, embedding_client=embedding_client)

    def _build_result_items(self, hits: List[Dict[str, Any]]) -> List[QAItem]:
        items: List[QAItem] = []
        for hit in hits:
            entity = hit.get("entity", {})
            items.append(QAItem(
                qa_id=str(hit.get("id", "")),
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
            name="qa_vector_search",
            display_name="QA 对向量语义检索",
            description=(
                "在 atomic_qa_store 中执行向量 ANN 检索，"
                "通过匹配已抽取的问题来召回最相关的问答对。"
                "适用于用户提问与原文表述差异较大的场景。"
            ),
            input_schema={
                "query_text": "str - 自然语言查询（与 query_vector 二选一）",
                "query_vector": "List[float] - 预计算向量（与 query_text 二选一）",
                "top_k": "int - 返回数量上限，默认 10",
                "filters": "MetadataFilter - 元数据过滤条件（可选）",
            },
            output_type="RetrieveResult[QAItem]",
        )
