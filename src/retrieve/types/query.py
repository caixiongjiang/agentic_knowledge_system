#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : query.py
@Author  : caixiongjiang
@Date    : 2026/02/28
@Function: 
    检索查询参数模型定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from src.retrieve.types.enums import (
    ConsistencyLevel, GranularityLevel, MatchMode, SemanticTarget,
)


@dataclass
class MetadataFilter:
    """通用元数据过滤条件

    在各类检索中用于缩小查询范围。
    所有字段均为可选，多个字段同时指定时取 AND 交集。
    """
    user_id: Optional[str] = None
    document_id: Optional[str] = None
    document_ids: Optional[List[str]] = None
    section_ids: Optional[List[str]] = None
    knowledge_base_id: Optional[str] = None
    knowledge_base_name: Optional[str] = None
    label_id: Optional[str] = None
    source_type: Optional[str] = None
    date_range: Optional[Tuple[str, str]] = None

    def to_milvus_filter_expr(self) -> Optional[str]:
        """将过滤条件转化为 Milvus filter expression 字符串

        Returns:
            Milvus 兼容的过滤表达式，无条件时返回 None
        """
        parts: List[str] = []
        if self.user_id:
            parts.append(f"user_id == '{self.user_id}'")
        if self.document_id:
            parts.append(f"document_id == '{self.document_id}'")
        if self.document_ids:
            ids_str = ", ".join(f"'{d}'" for d in self.document_ids)
            parts.append(f"document_id in [{ids_str}]")
        if self.knowledge_base_id:
            parts.append(f"knowledge_base_id == '{self.knowledge_base_id}'")
        if self.label_id:
            parts.append(f"label_id == '{self.label_id}'")
        return " and ".join(parts) if parts else None


@dataclass
class SemanticQuery:
    """语义向量检索查询参数

    Attributes:
        query_text: 自然语言查询文本（与 query_vector 二选一）
        query_vector: 预计算的查询向量（与 query_text 二选一）
        target: 目标 Collection 类型
        top_k: 返回结果数量上限
        filters: 元数据过滤条件
        return_content: 是否同时从 MongoDB 获取全文内容（默认仅返回 ID + Score）
        consistency_level: Milvus 一致性级别（None 时使用 Collection 默认级别）
    """
    target: SemanticTarget
    top_k: int = 10
    query_text: Optional[str] = None
    query_vector: Optional[List[float]] = None
    filters: MetadataFilter = field(default_factory=MetadataFilter)
    return_content: bool = False
    consistency_level: Optional[ConsistencyLevel] = None

    def __post_init__(self) -> None:
        if not self.query_text and not self.query_vector:
            raise ValueError("query_text 和 query_vector 必须至少提供一个")


@dataclass
class LexicalQuery:
    """字面检索统一查询参数

    Attributes:
        query_text: 自然语言查询文本（BM25Search 使用）
        keywords: 关键词列表（ExactMatch 使用）
        match_mode: 字面匹配模式（ExactMatch 使用）
        bool_expression: 布尔表达式字符串（BooleanSearch 使用）
        top_k: 返回结果数量上限
        target_granularity: 目标检索粒度
        filters: 元数据过滤条件
    """
    top_k: int = 10
    query_text: Optional[str] = None
    keywords: Optional[List[str]] = None
    match_mode: MatchMode = MatchMode.EXACT
    bool_expression: Optional[str] = None
    target_granularity: GranularityLevel = GranularityLevel.CHUNK
    filters: MetadataFilter = field(default_factory=MetadataFilter)
