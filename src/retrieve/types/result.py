#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : result.py
@Author  : caixiongjiang
@Date    : 2026/02/28
@Function: 
    检索结果模型定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, TypeVar


@dataclass
class ChunkItem:
    """Chunk 粒度检索结果项"""
    chunk_id: str
    score: float
    document_id: Optional[str] = None
    section_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SectionItem:
    """Section 粒度检索结果项"""
    section_id: str
    score: float
    document_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QAItem:
    """原子 QA 对检索结果项"""
    qa_id: str
    score: float
    document_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SummaryItem:
    """摘要检索结果项"""
    summary_id: str
    score: float
    document_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    summary_text: Optional[str] = None
    summary_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


T = TypeVar("T", ChunkItem, SectionItem, QAItem, SummaryItem)


@dataclass
class RetrieveResult(Generic[T]):
    """统一检索结果容器

    Attributes:
        items: 检索结果列表
        total_count: 命中结果总数
        source_capability: 产生此结果的原子能力名称
        execution_time_ms: 本次检索耗时（毫秒）
    """
    items: List[T] = field(default_factory=list)
    total_count: int = 0
    source_capability: str = ""
    execution_time_ms: float = 0.0
