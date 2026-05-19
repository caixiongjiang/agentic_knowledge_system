#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : retrieve_service.py
@Author  : caixiongjiang
@Date    : 2026/01/21 10:00
@Function: 
    Knowledge 检索编排服务
    三阶段 Pipeline: LLM₁ 路由规划 → 确定性多路召回 → LLM₂ 结果验证
@Modify History:
    2026/04/03 - 实现核心骨架 (Phase 2-5) + 完整 retrieve() 方法
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger

from src.client.embedding import EmbeddingClient, create_embedding_client
from src.retrieve.pipeline.fusion import create_fusion
from src.retrieve.pipeline.granularity_alignment import GranularityAligner
from src.retrieve.pipeline.parallel_recall import (
    ParallelRecallExecutor,
    is_lexical_route,
    is_semantic_route,
)
from src.retrieve.pipeline.rerank import RerankStage
from src.retrieve.pipeline.route_registry import RouteRegistry
from src.retrieve.pipeline.types import (
    FusedCandidate,
    FusionStrategy,
    PhaseTimings,
    RecallResult,
    RetrieveRequest,
    RetrieveResponse,
    RouteConfig,
    RoutePlan,
    ValidationResult,
)
from src.retrieve.types.enums import SearchMode
from src.retrieve.types.query import MetadataFilter
from src.retrieve.types.result import ChunkItem, RetrieveResult


class RetrieveService:
    """检索编排服务

    三阶段 Pipeline:
    - Phase 1: LLM₁ 路由规划 (RoutePlanner)
    - Phase 2-5: 确定性执行 (ParallelRecall → Alignment → Fusion → Rerank)
    - Phase 6: LLM₂ 结果验证 (ResultValidator)

    提供三种调用模式:
    - retrieve(): 完整 Pipeline（含 LLM₁ + LLM₂）
    - retrieve_custom(): 自定义路由组合（跳过 LLM₁，直接执行 Phase 2-6）
    - retrieve_single(): 直接调用单个原子能力（旁路模式）
    """

    def __init__(
        self,
        registry: Optional[RouteRegistry] = None,
        embedding_client: Optional[EmbeddingClient] = None,
    ) -> None:
        self._registry = registry or RouteRegistry()
        self._embedding_client = embedding_client

        self._recall_executor = ParallelRecallExecutor(self._registry)
        self._aligner = GranularityAligner()
        self._rerank_stage = RerankStage()

        # LLM 组件 — 延迟初始化
        self._planner = None
        self._validator = None

    def _get_embedding_client(self) -> EmbeddingClient:
        if self._embedding_client is None:
            self._embedding_client = create_embedding_client()
        return self._embedding_client

    def _get_planner(self):
        """延迟加载 LLM₁ 路由规划器"""
        if self._planner is None:
            from src.retrieve.planner.route_planner import RoutePlanner
            self._planner = RoutePlanner(registry=self._registry)
        return self._planner

    def _get_validator(self):
        """延迟加载 LLM₂ 结果验证 Agent（LiteLLM 客户端）"""
        if self._validator is None:
            from src.retrieve.validator.result_validator import ResultValidator
            client = self._create_validation_client()
            self._validator = ResultValidator(
                model=client,
                registry=self._registry,
            )
        return self._validator

    @staticmethod
    def _create_validation_client():
        """从组件配置创建验证 Agent 使用的 LiteLLM 客户端"""
        try:
            from src.utils.component_config_manager import get_component_config_manager
            mgr = get_component_config_manager()
            client = mgr.get_llm_client_for_component("result_validator")
        except Exception as e:
            logger.warning(f"加载 result_validator 配置失败，回退 fast 预设: {e}")
            from src.client.llm import create_llm_client_from_preset
            client = create_llm_client_from_preset("fast")
        logger.debug(f"创建验证 Agent 模型: {client.model}")
        return client

    # ==================== 完整 Pipeline ====================

    async def retrieve(
        self,
        request: RetrieveRequest,
        on_progress: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> RetrieveResponse:
        """智能检索（完整 Pipeline）

        Phase 1: LLM₁ 路由规划
        Phase 2-5: 多路并行召回 → 跨粒度对齐 → RRF 融合 → Rerank
        Phase 6: LLM₂ 结果验证 + 自主补全

        Args:
            on_progress: 可选的进度回调，接收阶段名称字符串
                ("planning" / "searching" / "reranking")
        """
        total_start = time.perf_counter()
        timings = PhaseTimings()

        await self._emit_progress(on_progress, "planning")

        # Phase 1: LLM₁ 路由规划
        t = time.perf_counter()
        try:
            planner = self._get_planner()
            route_plan = await planner.plan(
                query_text=request.query_text,
                filters=request.filters,
                top_k=request.top_k,
                route_hints=request.route_hints,
                conversation_context=request.conversation_context,
            )
        except Exception as e:
            logger.warning(f"LLM₁ 路由规划失败，回退默认路由: {e}")
            route_plan = self._default_route_plan(request)

        # 按 SearchMode 裁剪 route_plan（语义 / 字面 / 混合）
        route_plan = self._apply_search_mode(route_plan, request.search_mode, request)
        timings.planning_ms = (time.perf_counter() - t) * 1000

        # Phase 2-5: 确定性 Pipeline
        items, phase_timings_partial = await self._execute_pipeline(
            route_plan=route_plan,
            query_text=request.query_text,
            filters=request.filters,
            top_k=request.top_k,
            enable_rerank=request.enable_rerank,
            rerank_score_threshold=request.rerank_score_threshold,
            on_progress=on_progress,
        )
        timings.recall_ms = phase_timings_partial.recall_ms
        timings.alignment_ms = phase_timings_partial.alignment_ms
        timings.fusion_ms = phase_timings_partial.fusion_ms
        timings.rerank_ms = phase_timings_partial.rerank_ms

        # Phase 6: LLM₂ 结果验证
        validation_result = None
        if request.enable_validation and items:
            t = time.perf_counter()
            try:
                validator = self._get_validator()
                items, validation_result = await validator.validate(
                    query_text=request.query_text,
                    items=items,
                    max_rounds=request.max_validation_rounds,
                )
            except Exception as e:
                logger.warning(f"LLM₂ 结果验证失败，跳过: {e}")
            timings.validation_ms = (time.perf_counter() - t) * 1000

        total_ms = (time.perf_counter() - total_start) * 1000

        return RetrieveResponse(
            items=items[:request.top_k],
            total_count=len(items),
            route_plan=route_plan,
            validation_result=validation_result,
            execution_time_ms=total_ms,
            phase_timings=timings,
        )

    # ==================== 自定义路由 ====================

    async def retrieve_custom(
        self,
        routes: List[RouteConfig],
        query_text: str,
        filters: Optional[MetadataFilter] = None,
        top_k: int = 10,
        enable_rerank: bool = True,
        enable_validation: bool = False,
        max_validation_rounds: int = 3,
        rerank_score_threshold: Optional[float] = None,
    ) -> RetrieveResponse:
        """自定义路由组合（跳过 LLM₁ 规划，直接执行 Phase 2-6）"""
        total_start = time.perf_counter()
        filters = filters or MetadataFilter()

        route_plan = RoutePlan(route_plan=routes)

        items, timings = await self._execute_pipeline(
            route_plan=route_plan,
            query_text=query_text,
            filters=filters,
            top_k=top_k,
            enable_rerank=enable_rerank,
            rerank_score_threshold=rerank_score_threshold,
        )

        validation_result = None
        if enable_validation and items:
            t = time.perf_counter()
            try:
                validator = self._get_validator()
                items, validation_result = await validator.validate(
                    query_text=query_text,
                    items=items,
                    max_rounds=max_validation_rounds,
                )
            except Exception as e:
                logger.warning(f"LLM₂ 结果验证失败，跳过: {e}")
            timings.validation_ms = (time.perf_counter() - t) * 1000

        total_ms = (time.perf_counter() - total_start) * 1000

        return RetrieveResponse(
            items=items[:top_k],
            total_count=len(items),
            route_plan=route_plan,
            validation_result=validation_result,
            execution_time_ms=total_ms,
            phase_timings=timings,
        )

    # ==================== 单能力旁路 ====================

    async def retrieve_single(
        self, capability_name: str, **kwargs: Any,
    ) -> RetrieveResult:
        """直接调用单个原子能力（旁路模式）"""
        capability = self._registry.get(capability_name)
        return await capability.execute(**kwargs)

    # ==================== 内部方法 ====================

    async def _execute_pipeline(
        self,
        route_plan: RoutePlan,
        query_text: str,
        filters: MetadataFilter,
        top_k: int,
        enable_rerank: bool,
        rerank_score_threshold: Optional[float] = None,
        on_progress: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> tuple[List[ChunkItem], PhaseTimings]:
        """执行 Phase 2-5 确定性管道"""
        timings = PhaseTimings()

        await self._emit_progress(on_progress, "searching")

        # Phase 2: 并行多路召回
        t = time.perf_counter()
        recall_results: List[RecallResult] = await self._recall_executor.execute(
            routes=route_plan.route_plan,
            query_text=query_text,
            filters=filters,
        )
        timings.recall_ms = (time.perf_counter() - t) * 1000

        if not recall_results:
            return [], timings

        # 获取 query 向量（用于跨粒度对齐的 in-memory 精排）
        query_vector = None
        try:
            client = self._get_embedding_client()
            query_vector = await client.aembed(query_text)
        except Exception as e:
            logger.warning(f"获取 query 向量失败，跳过 in-memory 精排: {e}")

        # Phase 3: 跨粒度对齐
        t = time.perf_counter()
        aligned_results = await self._aligner.align(
            recall_results, query_vector,
        )
        timings.alignment_ms = (time.perf_counter() - t) * 1000

        # Phase 4: 融合 + 去重（按 RoutePlan.fusion_strategy 选择策略）
        t = time.perf_counter()
        fusion = create_fusion(
            strategy=route_plan.fusion_strategy,
            weights=route_plan.fusion_weights or None,
        )
        fused: List[FusedCandidate] = fusion.fuse(
            aligned_results, top_n=route_plan.rerank_top_n,
        )
        timings.fusion_ms = (time.perf_counter() - t) * 1000

        if not fused:
            return [], timings

        # Phase 5: Rerank（可选）
        await self._emit_progress(on_progress, "reranking")
        if enable_rerank:
            t = time.perf_counter()
            items = await self._rerank_stage.rerank(
                query=query_text,
                candidates=fused,
                top_k=top_k,
            )
            timings.rerank_ms = (time.perf_counter() - t) * 1000
        else:
            items = RerankStage._candidates_to_items(fused[:top_k])

        # Phase 5.5: 精排后分数阈值过滤
        if rerank_score_threshold is not None and items:
            before_count = len(items)
            items = [it for it in items if it.score >= rerank_score_threshold]
            filtered_count = before_count - len(items)
            if filtered_count:
                logger.info(
                    f"精排后阈值过滤: {filtered_count}/{before_count} 条结果 "
                    f"score < {rerank_score_threshold} 被过滤"
                )

        return items, timings

    @staticmethod
    async def _emit_progress(
        callback: Optional[Callable[[str], Awaitable[None]]],
        stage: str,
    ) -> None:
        """安全调用进度回调，异常不阻断主流程"""
        if callback is None:
            return
        try:
            await callback(stage)
        except Exception:
            logger.debug(f"进度回调异常 (stage={stage})，忽略")

    @staticmethod
    def _default_route_plan(request: RetrieveRequest) -> RoutePlan:
        """LLM₁ 失败时的回退默认路由计划"""
        recall_top_k = request.top_k * 3
        return RoutePlan(
            route_plan=[
                RouteConfig(route="chunk_dense", top_k=recall_top_k),
                RouteConfig(route="enhanced_chunk_dense", top_k=recall_top_k),
                RouteConfig(route="bm25_sparse", top_k=recall_top_k),
            ],
            rerank_top_n=min(recall_top_k * 2, 100),
        )

    @staticmethod
    def _apply_search_mode(
        plan: RoutePlan,
        mode: SearchMode,
        request: RetrieveRequest,
    ) -> RoutePlan:
        """按 ``SearchMode`` 过滤 ``RoutePlan.route_plan``

        - ``HYBRID``: 不裁剪
        - ``SEMANTIC``: 仅保留语义路由（chunk/enhanced/section/qa/summary _dense）
        - ``LEXICAL``: 仅保留字面路由（bm25_sparse / exact_match / boolean_search）
        - 其他模式（``STRUCTURED`` / ``GRAPH``）当前未实现具体路由，记录告警，
          保持 plan 原样以避免 0 路由

        若过滤后为空，回退到该 mode 下的最小可用集合。
        """
        if mode == SearchMode.HYBRID:
            return plan

        if mode == SearchMode.SEMANTIC:
            keep = [r for r in plan.route_plan if is_semantic_route(r.route)]
            fallback = [
                RouteConfig(route="chunk_dense", top_k=request.top_k * 3),
            ]
        elif mode == SearchMode.LEXICAL:
            keep = [r for r in plan.route_plan if is_lexical_route(r.route)]
            fallback = [
                RouteConfig(route="bm25_sparse", top_k=request.top_k * 3),
            ]
        else:
            logger.warning(
                f"SearchMode={mode} 当前未实现专用路由，按 HYBRID 处理",
            )
            return plan

        if not keep:
            logger.info(
                f"SearchMode={mode} 过滤后无可用路由，回退默认: "
                f"{[r.route for r in fallback]}"
            )
            keep = fallback
        else:
            dropped = [r.route for r in plan.route_plan if r not in keep]
            if dropped:
                logger.debug(f"SearchMode={mode} 已剔除路由: {dropped}")

        plan.route_plan = keep
        return plan
