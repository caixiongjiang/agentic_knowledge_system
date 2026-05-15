#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : retrieve.py
@Author  : caixiongjiang
@Date    : 2026/01/21 10:00
@Function: 
    Knowledge 检索 API 模型
    定义检索相关的请求和响应 Pydantic 模型
@Modify History:
    2026/04/03 - 实现完整 API 模型
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ==================== 请求模型 ====================


class RetrieveRequestSchema(BaseModel):
    """智能检索请求"""
    query_text: str = Field(..., description="查询文本", min_length=1, max_length=2000)
    knowledge_base_id: Optional[str] = Field(
        default=None, description="知识库 ID（可选，不指定则全局检索）",
    )
    document_id: Optional[str] = Field(
        default=None, description="文档 ID（可选，限定单文档内检索）",
    )
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    enable_rerank: bool = Field(default=True, description="是否启用 Reranker 精排")
    enable_validation: bool = Field(
        default=True, description="是否启用 LLM 结果验证",
    )
    route_hints: Optional[List[str]] = Field(
        default=None, description="路由提示（建议激活的路由名称列表）",
    )


class CustomRetrieveRequestSchema(BaseModel):
    """自定义路由组合检索请求"""
    query_text: str = Field(..., description="查询文本", min_length=1, max_length=2000)
    routes: List[Dict[str, Any]] = Field(
        ...,
        description="路由配置列表, 每项: {route, top_k, params}",
        min_length=1,
    )
    knowledge_base_id: Optional[str] = Field(default=None, description="知识库 ID")
    document_id: Optional[str] = Field(default=None, description="文档 ID")
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    enable_rerank: bool = Field(default=True, description="是否启用精排")
    enable_validation: bool = Field(default=False, description="是否启用结果验证")


class SingleRetrieveRequestSchema(BaseModel):
    """单能力直调请求"""
    capability_name: str = Field(
        ..., description="原子能力名称 (如 chunk_dense, bm25_sparse)",
    )
    query_text: Optional[str] = Field(default=None, description="查询文本")
    top_k: int = Field(default=10, ge=1, le=100, description="返回数量")
    knowledge_base_id: Optional[str] = Field(default=None, description="知识库 ID")
    document_id: Optional[str] = Field(default=None, description="文档 ID")
    params: Dict[str, Any] = Field(
        default_factory=dict, description="能力特有参数",
    )


# ==================== 响应模型 ====================


class ChunkItemSchema(BaseModel):
    """单条检索结果"""
    chunk_id: str = Field(..., description="Chunk ID")
    score: float = Field(default=0.0, description="相关性分数")
    document_id: Optional[str] = Field(default=None, description="所属文档 ID")
    section_id: Optional[str] = Field(default=None, description="所属章节 ID")
    knowledge_base_id: Optional[str] = Field(default=None, description="知识库 ID")
    text: Optional[str] = Field(default=None, description="文本内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class PhaseTimingsSchema(BaseModel):
    """各阶段耗时"""
    planning_ms: float = 0.0
    recall_ms: float = 0.0
    alignment_ms: float = 0.0
    fusion_ms: float = 0.0
    rerank_ms: float = 0.0
    validation_ms: float = 0.0


class RetrieveResponseSchema(BaseModel):
    """检索响应"""
    items: List[ChunkItemSchema] = Field(
        default_factory=list, description="结果列表",
    )
    total_count: int = Field(default=0, description="结果总数")
    execution_time_ms: float = Field(default=0.0, description="总耗时 (ms)")
    phase_timings: PhaseTimingsSchema = Field(
        default_factory=PhaseTimingsSchema, description="各阶段耗时",
    )


class RouteInfoSchema(BaseModel):
    """可用路由信息"""
    name: str
    display_name: str
    description: str
