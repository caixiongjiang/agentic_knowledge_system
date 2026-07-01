#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""skill_view 工具：加载某个技能的完整指令（Level 1/2）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.service.chat.tools.base import ToolDefinition

if TYPE_CHECKING:
    from src.service.chat.tools.kit import KnowledgeNavToolKit

NAME = "skill_view"

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "加载某个技能的完整指令（Level 1）；"
            "传 path 可加载其附带参考文件（Level 2，如 'templates/report-outline.md'）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "技能名（见 skills_list / 技能索引）",
                },
                "path": {
                    "type": "string",
                    "description": "可选：技能目录下的相对文件路径",
                },
            },
            "required": ["name"],
        },
    },
}


async def handle(
    kit: KnowledgeNavToolKit,
    name: str,
    path: Optional[str] = None,
) -> str:
    from src.service.skill.registry_singleton import get_registry

    reg = get_registry()

    if path:
        content = reg.get_file(name, path)
        return content or f"技能 '{name}' 下未找到文件 '{path}'。"

    skill = reg.get(name)
    if skill is None:
        return f"未找到技能 '{name}'（用 skills_list 查看可用技能）。"

    return skill.body


DEFINITION = ToolDefinition(name=NAME, schema=SCHEMA, handler=handle)
