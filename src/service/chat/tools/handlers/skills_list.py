#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""skills_list 工具：列出当前可用技能（仅 name + description）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.service.chat.tools.base import ToolDefinition

if TYPE_CHECKING:
    from src.service.chat.tools.kit import KnowledgeNavToolKit

NAME = "skills_list"

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "列出当前可用技能（仅 name + description）。"
            "需要某技能的完整指令时用 skill_view(name) 加载。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "可选：按类别过滤",
                },
            },
        },
    },
}


def _render_skills_list(
    registry,
    *,
    enabled_tools: list[str],
    category: Optional[str] = None,
) -> str:
    """渲染技能列表文本。"""
    descriptors = registry.list_descriptors()

    if category:
        descriptors = [d for d in descriptors if d.category == category]

    if not descriptors:
        return "当前没有可用技能。"

    # 按 category 分组
    groups: dict[str, list] = {}
    for d in descriptors:
        groups.setdefault(d.category, []).append(d)

    lines = ["<available_skills>"]
    for cat in sorted(groups):
        lines.append(f"  {cat}:")
        for d in groups[cat]:
            source_tag = " [内置]" if d.source == "builtin" else " [自定义]"
            lines.append(f"    - {d.name}: {d.description}{source_tag}")
    lines.append("</available_skills>")
    lines.append("")
    lines.append("用 skill_view(name=\"技能名\") 加载某个技能的完整指令。")

    return "\n".join(lines)


async def handle(kit: KnowledgeNavToolKit, category: Optional[str] = None) -> str:
    from src.service.skill.registry_singleton import get_registry

    reg = get_registry()
    return _render_skills_list(reg, enabled_tools=kit.enabled_tools, category=category)


DEFINITION = ToolDefinition(name=NAME, schema=SCHEMA, handler=handle)
