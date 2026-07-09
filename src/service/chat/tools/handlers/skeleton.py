#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""skeleton 工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from loguru import logger

from src.client.llm.types import ToolSchema
from src.retrieve.types.result import ChunkItem, SkeletonItem
from src.service.chat.tools.base import ToolDefinition
from src.service.chat.tools.helpers import count_outline_nodes, skeleton_outline_to_text

if TYPE_CHECKING:
    from src.service.chat.tools.kit import KnowledgeNavToolKit

NAME = "skeleton"

SCHEMA: ToolSchema = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "获取文档的骨架结构（目录树），帮助理解整体组织。"
            "返回每个章节的标题 / section_id / 层级(Lk) / 是否叶子 / 片段数 / 摘要预览，"
            "含目录和章节摘要，不含 chunk 正文。"
            "适用于单文档问答的「先看地图」入口，或需要定位相关章节时使用。"
            "命中目标 section 后可用 read_chunks 或 drill_down 下钻其 chunk_id_list。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "目标 document 的 ID",
                },
            },
            "required": ["document_id"],
        },
    },
}


async def handle(kit: KnowledgeNavToolKit, document_id: str) -> str:
    from src.retrieve.types.enums import GranularityLevel
    from src.retrieve.types.query import NavigationQuery

    cap = kit.cap("skeleton")
    query = NavigationQuery(
        anchor_id=document_id,
        anchor_type=GranularityLevel.DOCUMENT,
        include_content=False,
    )
    result = await cap.execute(query=query)

    chunks: List[ChunkItem] = []
    toc_text = ""
    section_count = 0
    for item in result.items:
        if isinstance(item, SkeletonItem):
            toc_text = skeleton_outline_to_text(item.outline_tree)
            section_count = count_outline_nodes(item.outline_tree)
            chunks.append(
                ChunkItem(
                    chunk_id=f"skeleton:{document_id}",
                    score=0.0,
                    document_id=document_id,
                    text=toc_text,
                    metadata={"_source_route": "navkit_skeleton"},
                ),
            )
    kit.supplemented.extend(chunks)
    kit.note_result_count(section_count if chunks else 0)
    logger.debug(f"skeleton({document_id}) → {len(chunks)} items")
    return toc_text if chunks else "未找到文档骨架。"


DEFINITION = ToolDefinition(name=NAME, schema=SCHEMA, handler=handle)
