#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""context_window 工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.client.llm.types import ToolSchema
from src.retrieve.types.result import ChunkItem
from src.service.chat.tools.base import ToolDefinition
from src.service.chat.tools.helpers import format_chunks_for_llm

if TYPE_CHECKING:
    from src.service.chat.tools.kit import KnowledgeNavToolKit

NAME = "context_window"

SCHEMA: ToolSchema = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "扩展指定 chunk 的上下文窗口，获取同一 section 内前后相邻的 chunk。"
            "适用于需要看上下文（前一段、后一段）来理解某个片段的情况。"
            "返回的相邻 chunk 正文为预览（默认 200 字）；"
            "若想看某条 chunk 自身的完整正文，请用 read_chunks 而非本工具。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chunk_id": {
                    "type": "string",
                    "description": (
                        "目标 chunk 的引用号（参考片段里显示的 alias，"
                        "形如 c1 / c2 / c10；不是 UUID）。"
                    ),
                },
                "window_size": {
                    "type": "integer",
                    "description": "前后各扩展的 chunk 数量",
                    "default": 2,
                    "minimum": 1,
                },
            },
            "required": ["chunk_id"],
        },
    },
}


async def handle(
    kit: KnowledgeNavToolKit,
    chunk_id: str,
    window_size: int = 2,
) -> str:
    from src.retrieve.types.enums import GranularityLevel
    from src.retrieve.types.query import NavigationQuery

    cap = kit.cap("context_window")
    query = NavigationQuery(
        anchor_id=chunk_id,
        anchor_type=GranularityLevel.CHUNK,
        window_size=window_size,
        include_content=True,
    )
    result = await cap.execute(query=query)
    chunks = [it for it in result.items if isinstance(it, ChunkItem)]
    kit.supplemented.extend(chunks)
    kit.note_result_count(len(chunks))
    logger.debug(f"context_window({chunk_id}) → {len(chunks)} chunks")
    return format_chunks_for_llm(chunks, alias_map=kit.alias_map)


DEFINITION = ToolDefinition(name=NAME, schema=SCHEMA, handler=handle)
