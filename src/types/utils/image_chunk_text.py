#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
图片 Chunk 文本组装

用于基础阶段 embedding 与后续 LLM 上下文占位符。
"""

from typing import Optional


def _normalize_text(value: Optional[str]) -> Optional[str]:
    """去除空白后返回非空字符串，否则 None。"""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def has_image_caption_or_footnote(
    image_caption: Optional[str],
    image_footnote: Optional[str],
) -> bool:
    """是否存在可用的图片标题或脚注。"""
    return (
        _normalize_text(image_caption) is not None
        or _normalize_text(image_footnote) is not None
    )


def format_image_chunk_embed_text(
    image_caption: Optional[str] = None,
    image_footnote: Optional[str] = None,
    section_title: Optional[str] = None,
    page_index: Optional[int] = None,
) -> str:
    """
    组装图片 Chunk 的向量化源文本（检索用，无 [图片] 包装）。

    展示文本请使用 ``format_image_chunk_placeholder`` 或
    ``chunk_search_text.format_image_display_text``。
    """
    from src.types.utils.chunk_search_text import format_image_search_text

    return format_image_search_text(
        image_caption=image_caption,
        image_footnote=image_footnote,
        section_title=section_title,
        page_index=page_index,
    )


def format_image_chunk_placeholder(
    image_caption: Optional[str] = None,
    image_footnote: Optional[str] = None,
) -> str:
    """
    组装图片 Chunk 的 LLM 上下文占位符（§2.2）。

    始终输出标题/脚注两行，缺失项填「无」。
    """
    caption = _normalize_text(image_caption) or "无"
    footnote = _normalize_text(image_footnote) or "无"
    return f"[图片]\n标题：{caption}\n脚注：{footnote}"
