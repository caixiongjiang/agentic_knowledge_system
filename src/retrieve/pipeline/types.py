#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : types.py
@Author  : caixiongjiang
@Date    : 2026/04/03
@Function: 
    Pipeline 流转的核心数据结构定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.retrieve.types.enums import SearchMode
from src.retrieve.types.query import MetadataFilter
from src.retrieve.types.result import ChunkItem


# ==================== 路由配置 ====================


class RouteConfig(BaseModel):
    """单条召回路由配置"""
    route: str = Field(..., description="路由标识 (如 chunk_dense, bm25_sparse)")
    top_k: int = Field(default=20, description="该路由的召回数量上限")
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "路由特有参数。通用键 ``query_text``：若填写，则该路检索使用该字符串；"
            "否则使用请求级用户原问。其余键见各路说明（如 exact_match 的 keywords / match_mode，"
            "boolean_search 的 bool_expression，score_threshold 等）"
        ),
    )


class FusionStrategy(str, Enum):
    """融合策略"""
    RRF = "rrf"
    WEIGHTED_SUM = "weighted_sum"


# ==================== LLM₁ 输出 ====================


class QueryAnalysis(BaseModel):
    """LLM₁ 的查询意图分析"""
    intent: str = Field(default="general", description="意图分类")
    key_entities: List[str] = Field(default_factory=list, description="关键实体")
    contains_jargon: bool = Field(default=False, description="是否包含专有名词/代码")
    context_dependent: bool = Field(default=False, description="是否依赖上下文")
    reasoning: str = Field(default="", description="分析推理过程")


class RoutePlan(BaseModel):
    """LLM₁ 输出的完整路由计划"""
    query_analysis: QueryAnalysis = Field(default_factory=QueryAnalysis)
    route_plan: List[RouteConfig] = Field(default_factory=list)
    fusion_strategy: FusionStrategy = Field(default=FusionStrategy.RRF)
    fusion_weights: Dict[str, float] = Field(
        default_factory=dict,
        description=(
            "仅 WEIGHTED_SUM 策略生效：路由名 → 权重；"
            "未列出的路由使用默认权重 1.0"
        ),
    )
    rerank_top_n: int = Field(default=50, description="送入 Reranker 的候选数量")


# ==================== Pipeline 中间产物 ====================


class RecallResult(BaseModel):
    """单路召回的结果，携带来源路由信息"""
    route: str = Field(..., description="产生此结果的路由标识")
    items: List[ChunkItem] = Field(default_factory=list)
    total_count: int = 0
    execution_time_ms: float = 0.0


class FusedCandidate(BaseModel):
    """RRF 融合后的单个候选"""
    chunk_id: str
    rrf_score: float = Field(default=0.0, description="RRF 融合分数")
    source_routes: List[str] = Field(
        default_factory=list,
        description="贡献了此 chunk 的路由列表",
    )
    document_id: Optional[str] = None
    section_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== LLM₂ 验证 ====================


class ValidationResult(BaseModel):
    """LLM₂ 验证的完整结果（Agent 模式）"""
    passed: bool = Field(
        default=True,
        description="验证是否通过：已结束工具阶段，且 [验证状态]/结论为可可靠回答",
    )
    rounds: int = Field(
        default=0,
        description="LLM 调用次数（每次 bind_tools 推理计 1 次，含最终结论）",
    )
    adjustment_rounds: int = Field(
        default=0,
        description="含并行工具批次的「调整」轮数（每轮内可同时执行多工具，上限由 max_rounds 控制）",
    )
    tool_calls_count: int = Field(default=0, description="工具调用总次数")
    tool_calls_summary: List[str] = Field(
        default_factory=list,
        description="工具调用摘要, 如 ['context_window(chunk_id=xxx)', 're_retrieve(query=...)']",
    )
    supplemented_items: List[ChunkItem] = Field(
        default_factory=list,
        description="补全过程中新增的 Chunk",
    )
    reasoning: str = Field(default="", description="Agent 最终的验证结论")
    total_validation_time_ms: float = 0.0


# ==================== 顶层输入/输出 ====================


class RetrieveRequest(BaseModel):
    """检索请求"""
    query_text: str = Field(..., description="查询文本")
    filters: MetadataFilter = Field(default_factory=MetadataFilter)
    top_k: int = Field(default=10, description="最终返回数量")
    search_mode: SearchMode = Field(
        default=SearchMode.HYBRID,
        description="检索模式 (SEMANTIC / LEXICAL / HYBRID)",
    )
    enable_rerank: bool = Field(default=True, description="是否启用 Reranker 精排")
    enable_validation: bool = Field(
        default=True, description="是否启用 LLM₂ 结果验证",
    )
    route_hints: Optional[List[str]] = Field(
        default=None,
        description="路由提示（可选，建议激活的路由名称列表）",
    )
    max_validation_rounds: int = Field(
        default=3,
        description="LLM₂ 含并行工具批次的「调整」轮数上限（每轮可一次并行多工具，非 LangGraph 步数）",
    )
    rerank_score_threshold: Optional[float] = Field(
        default=None,
        description="精排后分数阈值, 低于此值的结果将被过滤 (None 表示不过滤)",
    )


class PhaseTimings(BaseModel):
    """各阶段耗时明细"""
    planning_ms: float = 0.0
    recall_ms: float = 0.0
    alignment_ms: float = 0.0
    fusion_ms: float = 0.0
    rerank_ms: float = 0.0
    validation_ms: float = 0.0


class RetrieveResponse(BaseModel):
    """检索响应"""
    items: List[ChunkItem] = Field(default_factory=list, description="最终结果列表")
    total_count: int = Field(default=0, description="结果总数")
    route_plan: Optional[RoutePlan] = Field(
        default=None, description="LLM₁ 的路由计划（可审计）",
    )
    validation_result: Optional[ValidationResult] = Field(
        default=None, description="LLM₂ 的验证结果（可审计）",
    )
    execution_time_ms: float = Field(default=0.0, description="总耗时")
    phase_timings: PhaseTimings = Field(default_factory=PhaseTimings)
