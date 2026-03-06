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
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field


class ChunkItem(BaseModel):
    """Chunk 粒度检索结果项"""
    chunk_id: str
    score: float
    document_id: Optional[str] = None
    section_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SectionItem(BaseModel):
    """Section 粒度检索结果项"""
    section_id: str
    score: float
    document_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    title: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QAItem(BaseModel):
    """原子 QA 对检索结果项"""
    qa_id: str
    score: float
    document_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SummaryItem(BaseModel):
    """摘要检索结果项"""
    summary_id: str
    score: float
    document_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    summary_text: Optional[str] = None
    summary_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentItem(BaseModel):
    """Document 粒度检索结果项"""
    document_id: str
    score: float = 0.0
    title: Optional[str] = None
    source_type: Optional[str] = None
    summary: Optional[str] = None
    section_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ElementItem(BaseModel):
    """Element 粒度检索结果项"""
    element_id: str
    score: float = 0.0
    element_type: Optional[str] = None
    content: Optional[str] = None
    page_index: Optional[int] = None
    element_index: Optional[int] = None
    document_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SkeletonNode(BaseModel):
    """文档骨架树的节点"""
    section_id: str
    title: Optional[str] = None
    level: int = 1
    chunk_count: int = 0
    children: List["SkeletonNode"] = Field(default_factory=list)


class SkeletonItem(BaseModel):
    """文档骨架检索结果项"""
    document_id: str
    score: float = 0.0
    title: Optional[str] = None
    outline_tree: List[SkeletonNode] = Field(default_factory=list)
    total_sections: int = 0
    total_chunks: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


T = TypeVar(
    "T",
    ChunkItem, SectionItem, QAItem, SummaryItem,
    DocumentItem, ElementItem, SkeletonItem,
)


class RetrieveResult(BaseModel, Generic[T]):
    """统一检索结果容器

    Attributes:
        items: 检索结果列表
        total_count: 命中结果总数
        source_capability: 产生此结果的原子能力名称
        execution_time_ms: 本次检索耗时（毫秒）
    """
    items: List[T] = Field(default_factory=list)
    total_count: int = 0
    source_capability: str = ""
    execution_time_ms: float = 0.0
