#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""roll_up 工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from loguru import logger

from src.client.llm.types import ToolSchema
from src.retrieve.types.result import ChunkItem, DocumentItem, SectionItem
from src.service.chat.tools.base import ToolDefinition
from src.service.chat.tools.helpers import format_chunks_for_llm

if TYPE_CHECKING:
    from src.service.chat.tools.kit import KnowledgeNavToolKit

NAME = "roll_up"

SCHEMA: ToolSchema = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "从 chunk 或 section 向上回溯。"
            "支持 chunk→section、chunk→document、section→document 三种路径。"
            "返回真实 id，可继续用于后续导航工具。"
            "section 结果含 text_level / chunk_count；document 结果含 section_count、"
            "source_type、文档摘要预览（最多 200 字），完整摘要请直接看引用块或用 read_chunks 取相关 chunk。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chunk_id": {
                    "type": "string",
                    "description": "起始 chunk 的引用号（如 c1 / c2），与 section_id 二选一",
                },
                "section_id": {
                    "type": "string",
                    "description": "起始 section 的 ID（真实 id），与 chunk_id 二选一",
                },
                "target": {
                    "type": "string",
                    "description": "目标粒度：section 或 document",
                    "enum": ["section", "document"],
                    "default": "section",
                },
            },
        },
    },
}


async def handle(
    kit: KnowledgeNavToolKit,
    chunk_id: Optional[str] = None,
    section_id: Optional[str] = None,
    target: str = "section",
) -> str:
    from src.retrieve.types.enums import GranularityLevel
    from src.retrieve.types.query import NavigationQuery

    if not chunk_id and not section_id:
        return "roll_up: 必须提供 chunk_id 或 section_id"
    if chunk_id and section_id:
        return "roll_up: chunk_id 和 section_id 只能传一个"

    anchor_id = chunk_id or section_id
    anchor_type = GranularityLevel.CHUNK if chunk_id else GranularityLevel.SECTION

    target_map = {
        "section": GranularityLevel.SECTION,
        "document": GranularityLevel.DOCUMENT,
    }
    target_granularity = target_map.get(target, GranularityLevel.SECTION)

    cap = kit.cap("roll_up")
    query = NavigationQuery(
        anchor_id=anchor_id,
        anchor_type=anchor_type,
        target_granularity=target_granularity,
        include_content=True,
    )
    result = await cap.execute(query=query)

    sections: List[SectionItem] = []
    documents: List[DocumentItem] = []
    chunks: List[ChunkItem] = []
    for item in result.items:
        if isinstance(item, SectionItem):
            sections.append(item)
        elif isinstance(item, DocumentItem):
            documents.append(item)
        elif isinstance(item, ChunkItem):
            chunks.append(item)

    lines: List[str] = []

    if documents:
        lines.append(f"找到 {len(documents)} 个所属文档:")
        for doc in documents:
            title = doc.title or "(无标题)"
            summary = (doc.summary or "")[:200]
            stats: List[str] = []
            if doc.section_count:
                stats.append(f"{doc.section_count}章节")
            if doc.source_type:
                stats.append(f"type={doc.source_type}")
            file_name = (doc.metadata or {}).get("file_name")
            if file_name:
                stats.append(f"file={file_name}")
            stats_part = f" [{', '.join(stats)}]" if stats else ""
            summary_part = (
                f"\n  摘要(预览，最多200字): {summary}" if summary else ""
            )
            lines.append(
                f"- document_id={doc.document_id}, score={doc.score:.4f}{stats_part}\n"
                f"  {title}{summary_part}",
            )

    if sections:
        lines.append(f"找到 {len(sections)} 个所属章节:")
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

    if chunks:
        lines.append(format_chunks_for_llm(chunks, alias_map=kit.alias_map))

    result_count = len(documents) + len(sections) + len(chunks)
    kit.note_result_count(result_count)
    logger.debug(
        f"roll_up({anchor_id}, target={target}) → "
        f"{len(documents)} docs, {len(sections)} sections, {len(chunks)} chunks",
    )
    return "\n".join(lines) if lines else "未找到上层信息。"


DEFINITION = ToolDefinition(name=NAME, schema=SCHEMA, handler=handle)
