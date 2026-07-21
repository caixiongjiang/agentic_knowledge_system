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


# ==================== 召回全链路统计（v1.1 审计 / 前端「召回链路」栏目） ====================


class RouteRecallStat(BaseModel):
    """单条路由的召回统计"""
    route: str = Field(..., description="路由标识")
    top_k: int = Field(default=0, description="该路召回上限")
    recalled_count: int = Field(default=0, description="Phase 2 该路原始召回 item 数")
    aligned_count: Optional[int] = Field(
        default=None,
        description=(
            "Phase 3 跨粒度对齐后的 chunk 数。"
            "section/qa/summary 路由展开成 chunk 后数量会变；chunk 级路由与 recalled_count 一致。"
        ),
    )
    final_count: Optional[int] = Field(
        default=None,
        description=(
            "Phase 5 rerank 后最终结果中该路贡献的 chunk 数。"
            "按 FusedCandidate.source_routes 归属统计——一个 final chunk 若被多路命中，"
            "则对各路各计 1 次，故 sum(final_count) ≥ rerank_count。"
        ),
    )
    execution_time_ms: float = Field(default=0.0, description="该路执行耗时")
    sample_chunk_ids: List[str] = Field(
        default_factory=list,
        description="该路召回的前 N 个 chunk_id（截断展示，便于人工核对）",
    )


class RecallStats(BaseModel):
    """一次检索的全链路统计，供前端「召回链路」栏目渲染。

    覆盖 Phase 2(召回) → 3(对齐) → 4(融合) → 5(rerank) → 5.5(阈值过滤) 各阶段计数。
    chunk_id 列表均截断（_RECALL_STATS_CHUNK_ID_CAP，默认 20），避免响应膨胀。
    直答短路时 short_circuited=True，fused/rerank 字段留空。
    """
    routes: List[RouteRecallStat] = Field(default_factory=list)
    fused_count: int = Field(default=0, description="Phase 4 融合去重后候选数")
    fused_chunk_ids: List[str] = Field(
        default_factory=list, description="融合后候选 chunk_id（截断）",
    )
    rerank_count: int = Field(default=0, description="Phase 5 rerank 后数量")
    final_chunk_ids: List[str] = Field(
        default_factory=list, description="最终返回的 chunk_id（按分数降序，截断）",
    )
    dropped_by_threshold: int = Field(
        default=0, description="Phase 5.5 精排后阈值过滤掉的数量",
    )
    short_circuited: bool = Field(
        default=False, description="是否走直答短路（True 时 fused/rerank 为空）",
    )


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
    route_hints: Optional[List[str]] = Field(
        default=None,
        description="路由提示（可选，建议激活的路由名称列表）",
    )
    conversation_context: Optional[str] = Field(
        default=None,
        description="对话历史上下文（最近几轮 user/assistant 消息摘要），用于指代消解和查询增强",
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


class DirectAnswer(BaseModel):
    """直答短路结果（v1.1 qa_dense 高置信命中时产出）

    当 qa_dense 路由 top1 score ≥ θ_direct 且 answer 存在时，跳过
    align/fusion/rerank，直接返回 QA 的 answer 作为答案，附带来源标注。
    决策 a：纯 answer + 来源标注（不拼 chunk 预览）。
    """
    answer: str = Field(..., description="直答正文（来自 atomic_qa.answer）")
    qa_id: str = Field(default="", description="命中的 qa_id")
    question: str = Field(default="", description="命中的 question（供审计/展示）")
    score: float = Field(default=0.0, description="qa_dense 命中相似度分数")
    source_chunk_ids: List[str] = Field(
        default_factory=list,
        description="QA 所依据的 chunk_id 列表（chunk 级溯源）",
    )
    document_id: Optional[str] = None
    section_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None


class RetrieveResponse(BaseModel):
    """检索响应"""
    items: List[ChunkItem] = Field(default_factory=list, description="最终结果列表")
    total_count: int = Field(default=0, description="结果总数")
    route_plan: Optional[RoutePlan] = Field(
        default=None, description="LLM₁ 的路由计划（可审计）",
    )
    execution_time_ms: float = Field(default=0.0, description="总耗时")
    phase_timings: PhaseTimings = Field(default_factory=PhaseTimings)
    planner_model: Optional[str] = Field(
        default=None, description="查询转化使用的 LLM₁ 模型名称",
    )
    # v1.1 直答短路：非空表示本次检索命中高置信 QA，直接返回 answer，items 为空
    direct_answer: Optional[DirectAnswer] = Field(
        default=None,
        description=(
            "直答短路结果。非空时调用方应直接采用 answer 作为答案，"
            "无需再走 items 渲染；items 此时为空列表。"
        ),
    )
    # v1.1 召回全链路统计：每路召回/对齐/融合/rerank 计数 + chunk_id 截断列表，供前端「召回链路」栏目
    recall_stats: Optional[RecallStats] = Field(
        default=None,
        description="召回全链路统计（审计 / 前端「召回链路」栏目渲染）",
    )
