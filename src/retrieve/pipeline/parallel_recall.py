#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : parallel_recall.py
@Author  : caixiongjiang
@Date    : 2026/04/03
@Function: 
    Phase 2: 并行多路召回执行器
    根据 RoutePlan 并行调用各路 Capability，返回混合粒度结果

    本模块同时对外暴露 ``build_query_for_route`` / ``normalize_to_chunk_items``
    /  ``is_lexical_route`` / ``is_semantic_route`` 等可复用的纯函数，
    供 SearchMode 过滤等场景共享，避免重复手写 Query 构造逻辑。

@Modify History:
    2026/04/17 - 修复跳过未注册路由后 ``routes[i]`` 错位的索引问题；
                 抽出可复用的 query 构造 / 结果归一 / 路由分类函数
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import asyncio
import time
from typing import Any, List

from loguru import logger

from src.retrieve.pipeline.route_registry import RouteRegistry
from src.retrieve.pipeline.types import RecallResult, RouteConfig
from src.retrieve.types.enums import MatchMode, SemanticTarget
from src.retrieve.types.query import LexicalQuery, MetadataFilter, SemanticQuery
from src.retrieve.types.result import (
    ChunkItem,
    QAItem,
    RetrieveResult,
    SectionItem,
    SummaryItem,
)


# ==================== 路由分类（公开常量） ====================

#: 语义路由名 → 对应 Milvus Collection target 的映射
SEMANTIC_ROUTE_TARGETS = {
    "chunk_dense": SemanticTarget.CHUNK,
    "enhanced_chunk_dense": SemanticTarget.ENHANCED,
    "section_dense": SemanticTarget.SECTION,
    "qa_dense": SemanticTarget.ATOMIC_QA,
    "section_summary_dense": SemanticTarget.SECTION_SUMMARY,
    "file_summary_dense": SemanticTarget.FILE_SUMMARY,
}

#: 字面 / 词法类路由名集合
LEXICAL_ROUTES = {"bm25_sparse", "exact_match", "boolean_search"}


def is_semantic_route(route_name: str) -> bool:
    return route_name in SEMANTIC_ROUTE_TARGETS


def is_lexical_route(route_name: str) -> bool:
    return route_name in LEXICAL_ROUTES


# ==================== Query 构造 / 结果归一（公开纯函数） ====================


def effective_route_query(route_cfg: RouteConfig, fallback_query: str) -> str:
    """单路检索实际使用的查询文本。

    LLM₁ 可在 ``route_plan[].params.query_text`` 中为该路单独给出改写；
    未提供或非空字符串时，使用本次检索的全局 ``fallback_query``（用户原问）。
    """
    override = route_cfg.params.get("query_text")
    if isinstance(override, str) and override.strip():
        return override.strip()
    return fallback_query


def build_query_for_route(
    route_cfg: RouteConfig,
    query_text: str,
    filters: MetadataFilter,
) -> Any:
    """根据路由类型构建对应的 Query 对象（公开复用）"""
    route = route_cfg.route
    score_threshold = route_cfg.params.get("score_threshold")
    q = effective_route_query(route_cfg, query_text)

    if route in SEMANTIC_ROUTE_TARGETS:
        return SemanticQuery(
            target=SEMANTIC_ROUTE_TARGETS[route],
            query_text=q,
            top_k=route_cfg.top_k,
            filters=filters,
            score_threshold=score_threshold,
        )

    if route == "bm25_sparse":
        return LexicalQuery(
            query_text=q,
            top_k=route_cfg.top_k,
            filters=filters,
            score_threshold=score_threshold,
        )

    if route == "exact_match":
        keywords = route_cfg.params.get("keywords", [q])
        match_mode_str = route_cfg.params.get("match_mode", "fuzzy")
        try:
            match_mode = MatchMode(match_mode_str)
        except ValueError:
            match_mode = MatchMode.FUZZY
        return LexicalQuery(
            keywords=keywords,
            match_mode=match_mode,
            top_k=route_cfg.top_k,
            filters=filters,
            score_threshold=score_threshold,
        )

    if route == "boolean_search":
        return LexicalQuery(
            bool_expression=route_cfg.params.get("bool_expression", q),
            top_k=route_cfg.top_k,
            filters=filters,
            score_threshold=score_threshold,
        )

    raise ValueError(f"不支持的路由类型: {route}")


def normalize_to_chunk_items(
    result: RetrieveResult, route: str,
) -> List[ChunkItem]:
    """将各种 Item 类型统一转为 ChunkItem（保留原始信息在 metadata 中）"""
    chunk_items: List[ChunkItem] = []

    for item in result.items:
        if isinstance(item, ChunkItem):
            item.metadata["_source_route"] = route
            chunk_items.append(item)
        elif isinstance(item, SectionItem):
            chunk_items.append(ChunkItem(
                chunk_id=f"section:{item.section_id}",
                score=item.score,
                document_id=item.document_id,
                knowledge_base_id=item.knowledge_base_id,
                text=item.title,
                metadata={
                    "_source_route": route,
                    "_original_type": "section",
                    "_section_id": item.section_id,
                    **item.metadata,
                },
            ))
        elif isinstance(item, QAItem):
            chunk_items.append(ChunkItem(
                chunk_id=f"qa:{item.qa_id}",
                score=item.score,
                document_id=item.document_id,
                knowledge_base_id=item.knowledge_base_id,
                text=item.question,
                metadata={
                    "_source_route": route,
                    "_original_type": "qa",
                    "_qa_id": item.qa_id,
                    "answer": item.answer,
                    **item.metadata,
                },
            ))
        elif isinstance(item, SummaryItem):
            chunk_items.append(ChunkItem(
                chunk_id=f"summary:{item.summary_id}",
                score=item.score,
                document_id=item.document_id,
                knowledge_base_id=item.knowledge_base_id,
                text=item.summary_text,
                metadata={
                    "_source_route": route,
                    "_original_type": "summary",
                    "_summary_id": item.summary_id,
                    **item.metadata,
                },
            ))

    return chunk_items


# ==================== 执行器 ====================


class ParallelRecallExecutor:
    """并行多路召回执行器"""

    def __init__(self, registry: RouteRegistry) -> None:
        self._registry = registry

    async def execute(
        self,
        routes: List[RouteConfig],
        query_text: str,
        filters: MetadataFilter,
    ) -> List[RecallResult]:
        """并行执行所有路由，返回各路结果

        注意：跳过未注册路由后，``routes[i]`` 与 ``results[i]`` 会错位，
        因此这里维护一份与 ``tasks`` 一一对应的 ``accepted_routes`` 列表。
        """
        accepted_routes: List[RouteConfig] = []
        tasks = []
        for route_cfg in routes:
            if not self._registry.has(route_cfg.route):
                logger.warning(f"跳过未注册路由: {route_cfg.route}")
                continue
            accepted_routes.append(route_cfg)
            tasks.append(self._execute_single(route_cfg, query_text, filters))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        recall_results: List[RecallResult] = []
        for i, result in enumerate(results):
            route_name = accepted_routes[i].route
            if isinstance(result, Exception):
                logger.error(f"路由 {route_name} 执行失败: {result}")
                continue
            if isinstance(result, RecallResult):
                recall_results.append(result)

        return recall_results

    async def _execute_single(
        self,
        route_cfg: RouteConfig,
        query_text: str,
        filters: MetadataFilter,
    ) -> RecallResult:
        """执行单路召回"""
        start = time.perf_counter()
        capability = self._registry.get(route_cfg.route)

        query_obj = build_query_for_route(route_cfg, query_text, filters)
        result: RetrieveResult = await capability.execute(query=query_obj)

        elapsed_ms = (time.perf_counter() - start) * 1000
        chunk_items = normalize_to_chunk_items(result, route_cfg.route)

        return RecallResult(
            route=route_cfg.route,
            items=chunk_items,
            total_count=len(chunk_items),
            execution_time_ms=elapsed_ms,
        )

    # 向后兼容：保留原静态方法名作为别名
    @staticmethod
    def _normalize_to_chunk_items(
        result: RetrieveResult, route: str,
    ) -> List[ChunkItem]:
        return normalize_to_chunk_items(result, route)
