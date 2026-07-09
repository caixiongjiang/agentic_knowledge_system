#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_context.py
@Function:
    Section 摘要抽取的上下文构造层。

    对应 splitter/element_processor.py 的角色：把上游消息 payload
    转成 extract 层用的内存聚合体，并组装 LLM 输入文本。纯函数，
    无 LLM / 无 DB 依赖。

    - build_sections_from_payload：从 SplitEndMessage 的 sections + chunks
      构造 SectionWithChunks 列表（不访问任何数据库，消除写库竞态）
    - build_section_combined_text：将 section 标题 + 各 chunk 拼接为
      组合正文（image chunk 走占位符，与 split 阶段规则一致）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Dict, List

from loguru import logger

from src.index.common_file_extract.extract.models import SectionWithChunks
from src.types.utils.image_chunk_text import format_image_chunk_placeholder


# Chunk 类型常量（与 ChunkType 枚举值一致）
_CHUNK_TYPE_TEXT = "text"
_CHUNK_TYPE_IMAGE = "image"
_CHUNK_TYPE_TABLE = "table"
_CHUNK_TYPE_CODE = "code_block"


def build_sections_from_payload(
    sections_data: List[Dict[str, Any]],
    chunks_data: List[Dict[str, Any]],
) -> List[SectionWithChunks]:
    """
    从 SplitEndMessage 的自包含 payload 构造 SectionWithChunks 列表。

    不访问任何数据库；输入完全来自消息体，消除写库竞态。

    Args:
        sections_data: SplitEndMessage.sections，每项含
            section_id / title / level / page_index / chunk_id_list
        chunks_data: SplitEndMessage.chunks，每项含
            chunk_id / section_id / chunk_type / text /
            image_caption / image_footnote / page_index / language

    Returns:
        SectionWithChunks 列表（顺序与 sections_data 一致）
    """
    # chunk_id -> chunk payload，便于按 section.chunk_id_list 取数
    chunk_map: Dict[str, Dict[str, Any]] = {
        c.get("chunk_id"): c for c in chunks_data if c.get("chunk_id")
    }

    result: List[SectionWithChunks] = []
    for s in sections_data:
        section_id = s.get("section_id")
        if not section_id:
            continue
        chunk_id_list = s.get("chunk_id_list") or []
        section_chunks: List[Dict[str, Any]] = []
        for cid in chunk_id_list:
            c = chunk_map.get(cid)
            if c is not None:
                section_chunks.append(c)

        result.append(SectionWithChunks(
            section_id=section_id,
            title=s.get("title") or "",
            level=int(s.get("level") or 0),
            page_index=s.get("page_index"),
            chunks=section_chunks,
            chunk_id_list=[cid for cid in chunk_id_list if cid],
        ))

    logger.info(
        f"SectionSummary: 从消息 payload 构造上下文 sections={len(result)}, "
        f"chunks={len(chunk_map)}"
    )
    return result


def build_section_combined_text(section: SectionWithChunks) -> str:
    """
    将 section 标题 + 各 chunk 拼接为组合正文（供 LLM 输入）。

    - text / table / code_block：使用 chunk payload 的 text 字段（split 阶段原文）
    - image：使用 format_image_chunk_placeholder(caption, footnote) 占位符
    - chunk 之间以空行分隔
    """
    parts: List[str] = []
    for c in section.chunks:
        ctype = c.get("chunk_type") or _CHUNK_TYPE_TEXT

        if ctype == _CHUNK_TYPE_IMAGE:
            caption = c.get("image_caption")
            footnote = c.get("image_footnote")
            # 与 split 阶段占位符规则一致：始终输出标题/脚注两行
            parts.append(format_image_chunk_placeholder(caption, footnote))
        else:
            # text / table / code_block 用 payload.text（split 阶段 get_text_content 原文）
            text = (c.get("text") or "").strip()
            if text:
                parts.append(text)

    return "\n\n".join(parts)
