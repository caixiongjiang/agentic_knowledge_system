#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : tool_definitions.py
@Author  : caixiongjiang
@Date    : 2026/04/03
@Function:
    LLM₂ 可调用的工具定义（供检索结果验证 Prompt 使用）
@Modify History:
    2026-04-08 - 迁移至 src/prompts/retrieve/
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "context_window",
        "description": "扩展指定 chunk 的上下文窗口，获取同一 section 内前后相邻的 chunk",
        "parameters": {
            "chunk_id": {
                "type": "string",
                "description": "目标 chunk 的 ID",
                "required": True,
            },
            "window_size": {
                "type": "integer",
                "description": "前后各扩展的 chunk 数量，默认 2",
                "required": False,
            },
        },
    },
    {
        "name": "drill_down",
        "description": "从 section 或 document 级别向下钻取到子 chunk 列表",
        "parameters": {
            "section_id": {
                "type": "string",
                "description": "目标 section 的 ID",
                "required": False,
            },
            "document_id": {
                "type": "string",
                "description": "目标 document 的 ID（与 section_id 二选一）",
                "required": False,
            },
        },
    },
    {
        "name": "roll_up",
        "description": "从 chunk 上溯到所属 section 的标题和摘要，提供全局视角",
        "parameters": {
            "chunk_id": {
                "type": "string",
                "description": "目标 chunk 的 ID",
                "required": True,
            },
        },
    },
    {
        "name": "skeleton",
        "description": "获取文档的骨架结构（目录树），帮助理解整体组织",
        "parameters": {
            "document_id": {
                "type": "string",
                "description": "目标 document 的 ID",
                "required": True,
            },
        },
    },
    {
        "name": "re_retrieve",
        "description": "用改写后的 query 重新做一次语义检索，补充原始召回不足的内容",
        "parameters": {
            "query_text": {
                "type": "string",
                "description": "改写后的查询文本",
                "required": True,
            },
            "route": {
                "type": "string",
                "description": "使用的路由名称，默认 chunk_dense",
                "required": False,
            },
            "top_k": {
                "type": "integer",
                "description": "召回数量，默认 10",
                "required": False,
            },
        },
    },
]


def format_tools_for_prompt() -> str:
    """将工具定义格式化为 LLM prompt 可读的文本"""
    lines = []
    for tool in TOOL_DEFINITIONS:
        lines.append(f"### {tool['name']}")
        lines.append(f"描述: {tool['description']}")
        lines.append("参数:")
        for pname, pspec in tool["parameters"].items():
            req = "必填" if pspec.get("required") else "可选"
            lines.append(f"  - {pname} ({pspec['type']}, {req}): {pspec['description']}")
        lines.append("")
    return "\n".join(lines)
