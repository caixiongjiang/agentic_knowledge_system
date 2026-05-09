#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : fusion.py
@Author  : caixiongjiang
@Date    : 2026/04/03
@Function: 
    Phase 4: 多路召回结果融合 + 去重

    支持两种融合策略 (与 ``FusionStrategy`` 对齐):
    - RRF (Reciprocal Rank Fusion): 基于排名，跨引擎健壮，默认推荐
    - WEIGHTED_SUM: 基于分数，需先对每路 min-max 归一再按权重相加，
      适合分数尺度可比 / 已知各路质量差异时使用

@Modify History:
    2026/04/17 - 实现 WeightedSumFusion + create_fusion 工厂，统一融合接口
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from loguru import logger

from src.retrieve.pipeline.types import FusedCandidate, FusionStrategy, RecallResult
from src.retrieve.types.result import ChunkItem


_DEFAULT_RRF_K = 60


class BaseFusion(ABC):
    """融合策略基类，统一暴露 ``fuse()`` 接口"""

    strategy: FusionStrategy

    @abstractmethod
    def fuse(
        self,
        recall_results: List[RecallResult],
        top_n: Optional[int] = None,
    ) -> List[FusedCandidate]:
        ...

    @staticmethod
    def _build_candidate(
        cid: str,
        score: float,
        routes: List[str],
        meta_item: ChunkItem,
    ) -> FusedCandidate:
        return FusedCandidate(
            chunk_id=cid,
            rrf_score=score,
            source_routes=routes,
            document_id=meta_item.document_id,
            section_id=meta_item.section_id,
            knowledge_base_id=meta_item.knowledge_base_id,
            text=meta_item.text,
            metadata=meta_item.metadata,
        )


class RRFFusion(BaseFusion):
    """Reciprocal Rank Fusion + 去重

    RRF 公式: score(chunk) = Σ 1 / (k + rank_i(chunk))
    其中 k=60（标准取值），rank_i 是 chunk 在第 i 路中的排名（从 1 开始）。

    RRF 不依赖原始分数的绝对值，只关注相对排名，
    天然适合跨粒度、跨引擎的异构结果融合。
    """

    strategy = FusionStrategy.RRF

    def __init__(self, k: int = _DEFAULT_RRF_K) -> None:
        self._k = k

    def fuse(
        self,
        recall_results: List[RecallResult],
        top_n: Optional[int] = None,
    ) -> List[FusedCandidate]:
        start = time.perf_counter()

        score_map: Dict[str, float] = {}
        routes_map: Dict[str, List[str]] = {}
        meta_map: Dict[str, ChunkItem] = {}

        for rr in recall_results:
            for rank_0, item in enumerate(rr.items):
                cid = item.chunk_id
                rank = rank_0 + 1
                rrf_score = 1.0 / (self._k + rank)

                score_map[cid] = score_map.get(cid, 0.0) + rrf_score
                routes_map.setdefault(cid, []).append(rr.route)

                if cid not in meta_map:
                    meta_map[cid] = item

        candidates: List[FusedCandidate] = []
        for cid, score in score_map.items():
            candidates.append(self._build_candidate(
                cid=cid,
                score=score,
                routes=routes_map.get(cid, []),
                meta_item=meta_map[cid],
            ))

        candidates.sort(key=lambda c: c.rrf_score, reverse=True)

        if top_n is not None:
            candidates = candidates[:top_n]

        elapsed = (time.perf_counter() - start) * 1000
        logger.debug(
            f"RRF 融合完成: {sum(rr.total_count for rr in recall_results)} 项 "
            f"→ {len(candidates)} 候选, 耗时 {elapsed:.1f}ms"
        )
        return candidates


class WeightedSumFusion(BaseFusion):
    """加权求和融合

    步骤:
        1. 对每路结果做 min-max 归一化 (避免不同路分数尺度不可比)
        2. 按 ``weights[route]`` (默认 1.0) 加权累加
        3. 按总分降序

    适用场景:
        - 已知某路（如 enhanced_chunk_dense）质量更高，希望显式上权重
        - 各路分数尺度差异较大但仍含数值信息（不像 RRF 仅利用排名）

    与 RRF 的差异:
        - RRF 完全忽略分数大小，只看排名
        - WeightedSum 先归一再加权，对分数分布敏感

    Args:
        weights: 路由名 → 权重 的映射；缺省路由使用 ``default_weight``
        default_weight: 未在 ``weights`` 中出现的路由的默认权重
    """

    strategy = FusionStrategy.WEIGHTED_SUM

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        default_weight: float = 1.0,
    ) -> None:
        self._weights = dict(weights or {})
        self._default_weight = default_weight

    def fuse(
        self,
        recall_results: List[RecallResult],
        top_n: Optional[int] = None,
    ) -> List[FusedCandidate]:
        start = time.perf_counter()

        score_map: Dict[str, float] = {}
        routes_map: Dict[str, List[str]] = {}
        meta_map: Dict[str, ChunkItem] = {}

        for rr in recall_results:
            if not rr.items:
                continue

            weight = self._weights.get(rr.route, self._default_weight)

            scores = [it.score or 0.0 for it in rr.items]
            smin, smax = min(scores), max(scores)
            rng = smax - smin

            for item in rr.items:
                normalized = 1.0 if rng == 0 else ((item.score or 0.0) - smin) / rng
                contribution = weight * normalized

                cid = item.chunk_id
                score_map[cid] = score_map.get(cid, 0.0) + contribution
                routes_map.setdefault(cid, []).append(rr.route)

                if cid not in meta_map:
                    meta_map[cid] = item

        candidates: List[FusedCandidate] = []
        for cid, score in score_map.items():
            candidates.append(self._build_candidate(
                cid=cid,
                score=score,
                routes=routes_map.get(cid, []),
                meta_item=meta_map[cid],
            ))

        candidates.sort(key=lambda c: c.rrf_score, reverse=True)

        if top_n is not None:
            candidates = candidates[:top_n]

        elapsed = (time.perf_counter() - start) * 1000
        logger.debug(
            f"WeightedSum 融合完成: {sum(rr.total_count for rr in recall_results)} 项 "
            f"→ {len(candidates)} 候选, 耗时 {elapsed:.1f}ms, "
            f"weights={self._weights or '默认全 1.0'}"
        )
        return candidates


def create_fusion(
    strategy: FusionStrategy = FusionStrategy.RRF,
    *,
    weights: Optional[Dict[str, float]] = None,
    rrf_k: int = _DEFAULT_RRF_K,
) -> BaseFusion:
    """根据策略枚举创建对应的融合器

    Args:
        strategy: ``FusionStrategy.RRF`` 或 ``FusionStrategy.WEIGHTED_SUM``
        weights: 仅 WEIGHTED_SUM 使用的路由权重表
        rrf_k: 仅 RRF 使用的 k 参数

    Raises:
        ValueError: 未知策略
    """
    if strategy == FusionStrategy.RRF:
        return RRFFusion(k=rrf_k)
    if strategy == FusionStrategy.WEIGHTED_SUM:
        return WeightedSumFusion(weights=weights)
    raise ValueError(f"未知的融合策略: {strategy}")
