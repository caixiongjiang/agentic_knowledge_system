#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""drill_down 工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from loguru import logger

from src.client.llm.types import ToolSchema
from src.retrieve.types.result import ChunkItem, SectionItem
from src.service.chat.tools.base import ToolDefinition
from src.service.chat.tools.helpers import format_chunks_for_llm

if TYPE_CHECKING:
    from src.service.chat.tools.kit import KnowledgeNavToolKit

NAME = "drill_down"

SCHEMA: ToolSchema = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "从 document 或 section 级别向下钻取。"
            "支持 document→section、document→chunk、section→chunk 三种路径。"
            "返回的 chunk 列表中正文为预览（默认 200 字），完整内容请用 read_chunks。"
            "section 列表会包含 text_level / chunk_count / parent_section_id，"
            "便于判断章节层级与规模。"
            " 警告：document→chunk 会一次性返回整篇文档所有片段，"
            "**强烈建议**优先用 document→section 查目录、再 section→chunk 取所需章节，"
            "避免一次拉数百片段。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "section_id": {
                    "type": "string",
                    "description": "起始 section 的 ID（与 document_id 二选一）",
                },
                "document_id": {
                    "type": "string",
                    "description": "起始 document 的 ID（与 section_id 二选一）",
                },
                "target": {
                    "type": "string",
                    "description": (
                        "目标粒度：section 或 chunk。"
                        "document→section 返回章节列表（推荐起步），"
                        "其余路径返回片段列表（正文为预览）"
                    ),
                    "enum": ["section", "chunk"],
                    "default": "chunk",
                },
            },
        },
    },
}


async def handle(
    kit: KnowledgeNavToolKit,
    section_id: Optional[str] = None,
    document_id: Optional[str] = None,
    target: str = "chunk",
) -> str:
    from src.retrieve.types.enums import GranularityLevel
    from src.retrieve.types.query import NavigationQuery

    anchor_id = section_id or document_id or ""
    if not anchor_id:
        return "drill_down: 必须提供 section_id 或 document_id"
    anchor_type = (
        GranularityLevel.SECTION if section_id else GranularityLevel.DOCUMENT
    )

    target_map = {
        "section": GranularityLevel.SECTION,
        "chunk": GranularityLevel.CHUNK,
    }
    target_granularity = target_map.get(target, GranularityLevel.CHUNK)

    if (
        anchor_type == GranularityLevel.SECTION
        and target_granularity == GranularityLevel.SECTION
    ):
        return "drill_down: section_id 已经是章节级别，请指定 target=chunk"

    cap = kit.cap("drill_down")
    query = NavigationQuery(
        anchor_id=anchor_id,
        anchor_type=anchor_type,
        target_granularity=target_granularity,
        include_content=True,
    )
    result = await cap.execute(query=query)

    if target_granularity == GranularityLevel.SECTION:
        sections = [it for it in result.items if isinstance(it, SectionItem)]
        if not sections:
            return "未找到章节。"
        lines = [f"找到 {len(sections)} 个章节:"]
        for section in sections:
            title = section.title or "(无标题)"
            doc = section.document_id or "N/A"
            meta = section.metadata or {}
            level = meta.get("text_level")
            chunk_count = meta.get("chunk_count")
            parent = meta.get("parent_section_id")
            tag_parts: List[str] = []
            if level is not None:
                tag_parts.append(f"L{level}")
            if chunk_count is not None:
                tag_parts.append(f"{chunk_count}片段")
            if parent:
                tag_parts.append(f"parent={parent}")
            tag = f" [{', '.join(tag_parts)}]" if tag_parts else ""
            lines.append(
                f"- section_id={section.section_id}, document_id={doc}{tag}\n  {title}",
            )
        kit.note_result_count(len(sections))
        logger.debug(
            f"drill_down({anchor_id}, target=section) → {len(sections)} sections",
        )
        return "\n".join(lines)

    chunks = [it for it in result.items if isinstance(it, ChunkItem)]
    kit.supplemented.extend(chunks)
    kit.note_result_count(len(chunks))
    logger.debug(f"drill_down({anchor_id}, target=chunk) → {len(chunks)} chunks")
    return format_chunks_for_llm(chunks, alias_map=kit.alias_map)


DEFINITION = ToolDefinition(name=NAME, schema=SCHEMA, handler=handle)
