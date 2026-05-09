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
    - result_validator: LLM₂ 结果验证（工具说明见 tool_definitions，与 validator/tools 对齐）
    - tool_definitions: 验证阶段工具条目，供 system prompt 槽位 format_tools_for_prompt
@Modify History:
    2026-04-08 - 补充导出与说明
    2026-04-09 - Agent 模式
    2026-04-10 - 恢复导出 format_tools_for_prompt
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.prompts.retrieve.route_planner import (
    ROUTE_PLANNER_SYSTEM,
    ROUTE_PLANNER_USER,
    format_routes_description,
)
from src.prompts.retrieve.result_validator import (
    VALIDATOR_SYSTEM,
    VALIDATOR_USER,
    build_system_prompt,
    build_user_prompt,
)
from src.prompts.retrieve.tool_definitions import (
    TOOL_DEFINITIONS,
    format_tools_for_prompt,
)

__all__ = [
    "ROUTE_PLANNER_SYSTEM",
    "ROUTE_PLANNER_USER",
    "format_routes_description",
    "VALIDATOR_SYSTEM",
    "VALIDATOR_USER",
    "build_system_prompt",
    "build_user_prompt",
    "TOOL_DEFINITIONS",
    "format_tools_for_prompt",
]
