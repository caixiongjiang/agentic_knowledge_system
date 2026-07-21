#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : retrieve_service.py
@Author  : caixiongjiang
@Date    : 2026/01/21 10:00
@Function:
    Knowledge 检索编排服务
    Pipeline: LLM₁ 路由规划 → 多路召回 → 跨粒度对齐 → 融合 → Rerank
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
    DirectAnswer,
    FusedCandidate,
    FusionStrategy,
    PhaseTimings,
    RecallResult,
    RecallStats,
    RetrieveRequest,
    RetrieveResponse,
    RouteConfig,
    RoutePlan,
    RouteRecallStat,
)
from src.retrieve.types.enums import SearchMode
from src.retrieve.types.query import MetadataFilter
from src.retrieve.types.result import ChunkItem, RetrieveResult


# v1.1 直答短路：qa_dense top1 score ≥ 此阈值且 answer 存在时，跳过 align/fusion/rerank
_DEFAULT_DIRECT_ANSWER_THRESHOLD = 0.9

# v1.1 召回统计：chunk_id 列表截断上限，避免响应膨胀
_RECALL_STATS_CHUNK_ID_CAP = 20


class RetrieveService:
    """检索编排服务

    Pipeline:
    - Phase 1: LLM₁ 路由规划 (RoutePlanner)
    - Phase 2-5: ParallelRecall → Alignment → Fusion → Rerank

    提供三种调用模式:
    - retrieve(): 完整 Pipeline
    - retrieve_custom(): 自定义路由组合（跳过 LLM₁）
    - retrieve_single(): 直接调用单个原子能力
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

        self._planner = None

        # v1.1 直答短路配置
        self._direct_answer_enabled: bool = True
        self._direct_answer_threshold: float = _DEFAULT_DIRECT_ANSWER_THRESHOLD

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

    # ==================== 完整 Pipeline ====================

    async def retrieve(
        self,
        request: RetrieveRequest,
        on_progress: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> RetrieveResponse:
        """智能检索（完整 Pipeline）

        Phase 1: LLM₁ 路由规划
        Phase 2-5: 多路并行召回 → 跨粒度对齐 → RRF 融合 → Rerank

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

        route_plan = self._apply_search_mode(route_plan, request.search_mode, request)
        timings.planning_ms = (time.perf_counter() - t) * 1000

        items, phase_timings_partial, direct_answer, recall_stats = await self._execute_pipeline(
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

        total_ms = (time.perf_counter() - total_start) * 1000

        # 记录查询转化使用的 LLM₁ 模型名称
        planner_model = None
        try:
            planner_model = planner._llm_client.model
        except Exception:
            pass

        return RetrieveResponse(
            items=items[:request.top_k],
            total_count=len(items),
            route_plan=route_plan,
            execution_time_ms=total_ms,
            phase_timings=timings,
            planner_model=planner_model,
            direct_answer=direct_answer,
            recall_stats=recall_stats,
        )

    # ==================== 自定义路由 ====================

    async def retrieve_custom(
        self,
        routes: List[RouteConfig],
        query_text: str,
        filters: Optional[MetadataFilter] = None,
        top_k: int = 10,
        enable_rerank: bool = True,
        rerank_score_threshold: Optional[float] = None,
    ) -> RetrieveResponse:
        """自定义路由组合（跳过 LLM₁ 规划，直接执行 Phase 2-5）"""
        total_start = time.perf_counter()
        filters = filters or MetadataFilter()

        route_plan = RoutePlan(route_plan=routes)

        items, timings, direct_answer, recall_stats = await self._execute_pipeline(
            route_plan=route_plan,
            query_text=query_text,
            filters=filters,
            top_k=top_k,
            enable_rerank=enable_rerank,
            rerank_score_threshold=rerank_score_threshold,
        )

        total_ms = (time.perf_counter() - total_start) * 1000

        return RetrieveResponse(
            items=items[:top_k],
            total_count=len(items),
            route_plan=route_plan,
            execution_time_ms=total_ms,
            phase_timings=timings,
            direct_answer=direct_answer,
            recall_stats=recall_stats,
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
    ) -> tuple[List[ChunkItem], PhaseTimings, Optional[DirectAnswer], Optional[RecallStats]]:
        """执行 Phase 2-5 确定性管道

        v1.1：Phase 2 后插入「直答短路」判断——qa_dense top1 score ≥ θ_direct
        且 answer 存在时，跳过 Phase 3-5，返回空 items + DirectAnswer。

        v1.1 召回统计：各阶段计数 + chunk_id 截断列表汇总到 RecallStats，
        供前端「召回链路」栏目渲染（覆盖 recall → align → fuse → rerank → threshold）。
        """
        timings = PhaseTimings()
        direct_answer: Optional[DirectAnswer] = None
        recall_stats = RecallStats()

        await self._emit_progress(on_progress, "searching")

        # Phase 2: 并行多路召回
        t = time.perf_counter()
        recall_results: List[RecallResult] = await self._recall_executor.execute(
            routes=route_plan.route_plan,
            query_text=query_text,
            filters=filters,
        )
        timings.recall_ms = (time.perf_counter() - t) * 1000

        # 路由 top_k 查表（recall_results 里没有 top_k，从 plan 取）
        top_k_map = {r.route: r.top_k for r in route_plan.route_plan}
        # Phase 2 统计：每路原始召回数 + 前 N 个 chunk_id
        recall_stats.routes = self._build_route_stats(
            recall_results, top_k_map, aligned=False,
        )

        if not recall_results:
            return [], timings, None, recall_stats

        # v1.1 直答短路：qa_dense 高置信命中 → 直接返回 answer，跳过 align/fusion/rerank
        if self._direct_answer_enabled:
            direct_answer = self._maybe_direct_answer(recall_results)
            if direct_answer is not None:
                logger.info(
                    f"直答短路命中: qa_id={direct_answer.qa_id}, "
                    f"score={direct_answer.score:.4f} ≥ "
                    f"θ={self._direct_answer_threshold:.2f}"
                )
                recall_stats.short_circuited = True
                return [], timings, direct_answer, recall_stats

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
        # Phase 3 统计：回填每路对齐后 chunk 数（section/qa/summary 路由展开后会变）
        self._fill_aligned_counts(recall_stats.routes, aligned_results)

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

        # Phase 4 统计：融合去重后候选数 + chunk_id 截断列表
        recall_stats.fused_count = len(fused)
        recall_stats.fused_chunk_ids = [
            f.chunk_id for f in fused[:_RECALL_STATS_CHUNK_ID_CAP]
        ]

        if not fused:
            return [], timings, None, recall_stats

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
            recall_stats.dropped_by_threshold = filtered_count
            if filtered_count:
                logger.info(
                    f"精排后阈值过滤: {filtered_count}/{before_count} 条结果 "
                    f"score < {rerank_score_threshold} 被过滤"
                )

        # Phase 5 统计：rerank 后最终 chunk_id 列表（按分数降序，截断）
        recall_stats.rerank_count = len(items)
        recall_stats.final_chunk_ids = [
            it.chunk_id for it in items[:_RECALL_STATS_CHUNK_ID_CAP]
        ]

        # Phase 5 每路 final_count：按 FusedCandidate.source_routes 归属统计
        # （一个 final chunk 若被多路命中，对各路各计 1 次）
        final_id_set = {it.chunk_id for it in items}
        fused_source_map = {f.chunk_id: f.source_routes for f in fused}
        route_final_count: Dict[str, int] = {rs.route: 0 for rs in recall_stats.routes}
        for cid in final_id_set:
            for rt in fused_source_map.get(cid, []):
                if rt in route_final_count:
                    route_final_count[rt] += 1
        for rs in recall_stats.routes:
            rs.final_count = route_final_count.get(rs.route, 0)

        return items, timings, None, recall_stats

    @staticmethod
    def _build_route_stats(
        recall_results: List[RecallResult],
        top_k_map: Dict[str, int],
        aligned: bool = False,
    ) -> List[RouteRecallStat]:
        """从召回结果构建每路统计（Phase 2 原始召回数 + 前 N 个 chunk_id）。"""
        stats: List[RouteRecallStat] = []
        for rr in recall_results:
            sample = [
                it.chunk_id for it in rr.items[:_RECALL_STATS_CHUNK_ID_CAP]
                if getattr(it, "chunk_id", None)
            ]
            stats.append(RouteRecallStat(
                route=rr.route,
                top_k=top_k_map.get(rr.route, 0),
                recalled_count=rr.total_count or len(rr.items),
                execution_time_ms=rr.execution_time_ms,
                sample_chunk_ids=sample,
            ))
        return stats

    @staticmethod
    def _fill_aligned_counts(
        route_stats: List[RouteRecallStat],
        aligned_results: List[RecallResult],
    ) -> None:
        """回填 Phase 3 对齐后每路 chunk 数（section/qa/summary 路由展开后会变）。"""
        aligned_map = {rr.route: len(rr.items) for rr in aligned_results}
        for rs in route_stats:
            if rs.route in aligned_map:
                rs.aligned_count = aligned_map[rs.route]

    def _maybe_direct_answer(
        self,
        recall_results: List[RecallResult],
    ) -> Optional[DirectAnswer]:
        """v1.1 直答短路判断：扫描 qa_dense 路由召回，取 top1 QA。

        - 仅认 route == "qa_dense" 的结果（已由 normalize_to_chunk_items 归一为
          ChunkItem，metadata携带 _original_type="qa" / answer / source_chunk_ids / section_id）
        - top1 score ≥ θ_direct 且 answer 非空 → 返回 DirectAnswer
        - 否则返回 None（走正常 align/fusion/rerank）
        """
        best: Optional[ChunkItem] = None
        for rr in recall_results:
            if rr.route != "qa_dense":
                continue
            for it in rr.items:
                if it.metadata.get("_original_type") != "qa":
                    continue
                if best is None or it.score > best.score:
                    best = it
        if best is None:
            return None
        answer = (best.metadata.get("answer") or "").strip()
        if not answer:
            return None
        if best.score < self._direct_answer_threshold:
            return None
        return DirectAnswer(
            answer=answer,
            qa_id=str(best.metadata.get("_qa_id") or best.chunk_id.replace("qa:", "", 1)),
            question=str(best.metadata.get("question") or best.text or ""),
            score=float(best.score),
            source_chunk_ids=list(best.metadata.get("source_chunk_ids") or []),
            document_id=best.document_id,
            section_id=best.metadata.get("section_id"),
            knowledge_base_id=best.knowledge_base_id,
        )

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
