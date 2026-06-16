#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""单个 Chat Agent 工具的定义协议。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, TYPE_CHECKING

from src.client.llm.types import ToolSchema

if TYPE_CHECKING:
    from src.service.chat.tools.kit import KnowledgeNavToolKit

ToolHandler = Callable[..., Awaitable[str]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    schema: ToolSchema
    handler: Callable[["KnowledgeNavToolKit", ...], Awaitable[str]]
