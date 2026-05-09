#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : route_planner.py
@Author  : caixiongjiang
@Date    : 2026/04/03
@Function: 
    LLM₁ 路由规划核心逻辑
    调用 LLM 分析查询意图并生成多路召回路由计划
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import json
import re
from typing import Any, Dict, List, Optional

from loguru import logger

from src.client.llm import LLMClient, create_llm_client_from_preset
from src.retrieve.pipeline.route_registry import RouteRegistry
from src.utils.component_config_manager import get_component_config_manager
from src.retrieve.pipeline.types import (
    FusionStrategy,
    QueryAnalysis,
    RouteConfig,
    RoutePlan,
)
from src.prompts.retrieve.route_planner import (
    ROUTE_PLANNER_SYSTEM,
    ROUTE_PLANNER_USER,
    format_routes_description,
)
from src.retrieve.types.query import MetadataFilter


class RoutePlanner:
    """LLM₁ 路由规划器

    1. 从 RouteRegistry 动态获取所有可用路由描述
    2. 构建 prompt，调用 LLM 分析查询意图
    3. 解析 JSON 输出为 RoutePlan
    4. 校验路由有效性，过滤无效路由
    """

    def __init__(
        self,
        registry: RouteRegistry,
        llm_client: Optional[LLMClient] = None,
        llm_preset: Optional[str] = None,
    ) -> None:
        self._registry = registry
        self.last_llm_raw_text: Optional[str] = None
        if llm_client is not None:
            self._llm_client = llm_client
        elif llm_preset is not None:
            self._llm_client = create_llm_client_from_preset(llm_preset)
        else:
            try:
                self._llm_client = get_component_config_manager().get_llm_client_for_component(
                    "route_planner",
                )
            except Exception as e:
                logger.warning(
                    f"从 components 加载 route_planner LLM 失败，回退 reasoning 预设: {e}",
                )
                self._llm_client = create_llm_client_from_preset("reasoning")

    async def plan(
        self,
        query_text: str,
        filters: Optional[MetadataFilter] = None,
        top_k: int = 10,
        route_hints: Optional[List[str]] = None,
    ) -> RoutePlan:
        """生成路由计划

        Args:
            query_text: 用户查询
            filters: 元数据过滤条件
            top_k: 最终需要的结果数量
            route_hints: 路由提示

        Returns:
            RoutePlan 路由计划
        """
        descriptors = self._registry.list_descriptors()
        routes_desc = format_routes_description(descriptors)

        system_msg = ROUTE_PLANNER_SYSTEM.format(routes_description=routes_desc)

        filters_desc = "无" if not filters else self._format_filters(filters)
        hints_desc = ""
        if route_hints:
            hints_desc = f"建议路由: {', '.join(route_hints)}"

        user_msg = ROUTE_PLANNER_USER.format(
            query_text=query_text,
            filters_desc=filters_desc,
            top_k=top_k,
            hints_desc=hints_desc,
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        try:
            response = await self._llm_client.agenerate(
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            )
            raw_text = response.content or ""
            self.last_llm_raw_text = raw_text  # 测试 / 调试用
            plan = self._parse_plan(raw_text)
            plan = self._validate_plan(plan, top_k)
            logger.info(
                f"LLM₁ 路由规划完成: "
                f"意图={plan.query_analysis.intent}, "
                f"路由={[r.route for r in plan.route_plan]}"
            )
            return plan

        except Exception as e:
            logger.error(f"LLM₁ 路由规划失败: {e}")
            raise

    def _parse_plan(self, raw_text: str) -> RoutePlan:
        """从 LLM 输出解析 RoutePlan JSON"""
        json_str = self._extract_json(raw_text)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}, 原始文本: {raw_text[:500]}")
            raise ValueError(f"LLM 输出不是有效 JSON: {e}") from e

        query_analysis = QueryAnalysis(**data.get("query_analysis", {}))

        route_plan = []
        for r in data.get("route_plan", []):
            route_plan.append(RouteConfig(
                route=r.get("route", ""),
                top_k=r.get("top_k", 20),
                params=r.get("params", {}),
            ))

        fusion_str = data.get("fusion_strategy", "rrf")
        try:
            fusion = FusionStrategy(fusion_str)
        except ValueError:
            fusion = FusionStrategy.RRF

        return RoutePlan(
            query_analysis=query_analysis,
            route_plan=route_plan,
            fusion_strategy=fusion,
            rerank_top_n=data.get("rerank_top_n", 50),
        )

    def _validate_plan(self, plan: RoutePlan, top_k: int) -> RoutePlan:
        """校验并过滤无效路由"""
        valid_routes = []
        for rc in plan.route_plan:
            if self._registry.has(rc.route):
                valid_routes.append(rc)
            else:
                logger.warning(f"LLM₁ 输出了无效路由: {rc.route}")

        if not valid_routes:
            logger.warning("LLM₁ 未输出有效路由，回退默认")
            valid_routes = [
                RouteConfig(route="chunk_dense", top_k=top_k * 3),
                RouteConfig(route="bm25_sparse", top_k=top_k * 3),
            ]

        plan.route_plan = valid_routes
        return plan

    @staticmethod
    def _extract_json(text: str) -> str:
        """从 LLM 文本输出中提取 JSON 块"""
        # 优先匹配 ```json ... ``` 代码块
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 否则匹配第一个 { ... } 块
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0).strip()

        return text.strip()

    @staticmethod
    def _format_filters(filters: MetadataFilter) -> str:
        parts = []
        if filters.knowledge_base_id:
            parts.append(f"知识库: {filters.knowledge_base_id}")
        if filters.document_id:
            parts.append(f"文档: {filters.document_id}")
        if filters.source_type:
            parts.append(f"来源类型: {filters.source_type}")
        return ", ".join(parts) if parts else "无"
