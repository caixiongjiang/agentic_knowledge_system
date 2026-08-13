#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""Chat Agent 工具注册表。"""

from __future__ import annotations

from typing import Dict, List, Sequence

from src.client.llm.types import ToolSchema
from src.service.chat.tools.base import ToolDefinition
from src.service.chat.tools.handlers import ALL_TOOL_DEFINITIONS

DEFAULT_NAV_TOOLS: Sequence[str] = tuple(
    definition.name for definition in ALL_TOOL_DEFINITIONS
)

_TOOL_BY_NAME: Dict[str, ToolDefinition] = {
    definition.name: definition for definition in ALL_TOOL_DEFINITIONS
}

BUILTIN_NAV_SCHEMAS: List[ToolSchema] = [
    definition.schema for definition in ALL_TOOL_DEFINITIONS
]

AGENT_ENABLED_TOOLS: Sequence[str] = (
    "search_knowledge_base",
    "grep_chunks",
    "context_window",
    "drill_down",
    "skeleton",
    "roll_up",
    "read_chunks",
    "read_image_chunks",
    "skills_list",
    "skill_view",
)
"""Agent 模式固定启用的工具集；system prompt 渲染与上下文计量共用同一真相源。"""


def agent_tools_schema() -> List[ToolSchema]:
    """``AGENT_ENABLED_TOOLS`` 对应的 schema 列表（顺序与常量一致）。"""
    index = {schema["function"]["name"]: schema for schema in BUILTIN_NAV_SCHEMAS}
    return [index[name] for name in AGENT_ENABLED_TOOLS if name in index]


def get_tool_definition(name: str) -> ToolDefinition | None:
    return _TOOL_BY_NAME.get(name)
