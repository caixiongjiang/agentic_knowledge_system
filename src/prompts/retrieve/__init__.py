#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/02/28
@Function:
    检索模块（retrieve）相关 Prompt 的统一入口

    子模块:
    - route_planner: LLM₁ 路由规划
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.prompts.retrieve.route_planner import (
    ROUTE_PLANNER_SYSTEM,
    ROUTE_PLANNER_USER,
    format_routes_description,
)

__all__ = [
    "ROUTE_PLANNER_SYSTEM",
    "ROUTE_PLANNER_USER",
    "format_routes_description",
]
