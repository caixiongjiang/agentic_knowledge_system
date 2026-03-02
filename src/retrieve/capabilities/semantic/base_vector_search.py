#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : base_vector_search.py
@Author  : caixiongjiang
@Date    : 2026/02/28
@Function: 
    语义向量检索内部公共基类，封装 text→embed→search→format 流程
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from src.client.embedding import EmbeddingClient
from src.db.milvus.repositories.base_repository import BaseRepository as MilvusBaseRepository
from src.retrieve.capabilities.base import BaseCapability
from src.retrieve.types.query import SemanticQuery
from src.retrieve.types.result import RetrieveResult


class BaseVectorSearch(BaseCapability):
    """语义向量检索的内部公共基类

    封装了所有语义检索能力共享的流程：
    1. 查询文本 → EmbeddingClient 向量化
    2. 构建 Milvus filter expression
    3. 调用 Repository.search_by_vector / search
    4. 将 Milvus 原始结果转化为统一 RetrieveResult

    子类只需：
    - 提供具体的 Repository 实例
    - 实现 _build_result_items() 将 raw hits 转为具体的 Item 类型
    """

    def __init__(
        self,
        repository: MilvusBaseRepository,
        embedding_client: Optional[EmbeddingClient] = None,
    ) -> None:
        super().__init__()
        self._repository = repository
        self._embedding_client = embedding_client

    def _get_embedding_client(self) -> EmbeddingClient:
        """延迟获取 EmbeddingClient

        如果构造时未注入，则通过工厂函数创建。
        """
        if self._embedding_client is None:
            from src.client.embedding import create_embedding_client
            self._embedding_client = create_embedding_client()
        return self._embedding_client

    async def _ensure_query_vector(self, query: SemanticQuery) -> List[float]:
        """确保 query 拥有向量表示

        如果只提供了 query_text，则调用 EmbeddingClient 生成向量。
        """
        if query.query_vector is not None:
            return query.query_vector

        client = self._get_embedding_client()
        return await client.aembed(query.query_text)

    async def _do_execute(self, **kwargs: Any) -> RetrieveResult:
        """统一执行流程"""
        query: SemanticQuery = kwargs["query"]

        query_vector = await self._ensure_query_vector(query)

        filter_expr = query.filters.to_milvus_filter_expr() if query.filters else None

        consistency_level_value = (
            query.consistency_level.value if query.consistency_level else None
        )

        raw_results = self._repository.search(
            vectors=[query_vector],
            vector_field="vector",
            top_k=query.top_k,
            filter_expr=filter_expr,
            consistency_level=consistency_level_value,
        )

        hits = raw_results[0] if raw_results else []
        items = self._build_result_items(hits)

        return RetrieveResult(
            items=items,
            total_count=len(items),
        )

    @abstractmethod
    def _build_result_items(self, hits: List[Dict[str, Any]]) -> list:
        """将 Milvus 原始搜索结果转化为具体的 Item 类型列表

        Args:
            hits: Milvus search 返回的单次查询命中列表，
                  每个 hit 包含 id, distance, score, entity 字段

        Returns:
            具体的结果项列表（ChunkItem / SectionItem / QAItem / SummaryItem）
        """
        ...
