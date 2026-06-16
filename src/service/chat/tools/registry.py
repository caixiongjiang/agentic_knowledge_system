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


def get_tool_definition(name: str) -> ToolDefinition | None:
    return _TOOL_BY_NAME.get(name)
