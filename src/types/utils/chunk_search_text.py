#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Chunk 检索文本 vs 展示文本

- search_text：Embedding / BM25 / exact_match / Rerank 使用（无包装）
- display text：read_chunks / search 预览 / LLM 上下文（保留结构化包装）
"""

from __future__ import annotations

import re
from typing import Any, Optional, Tuple

from src.types.utils.image_chunk_text import (
    _normalize_text,
    format_image_chunk_placeholder,
    has_image_caption_or_footnote,
)

# ---- 表格 display 前缀（与 TableSplitter 一致） ----
_TABLE_CAPTION_RE = re.compile(
    r"^table_caption:\s*(.*)$", re.MULTILINE | re.IGNORECASE,
)
_TABLE_BODY_RE = re.compile(
    r"^table_body:\s*([\s\S]*)", re.MULTILINE | re.IGNORECASE,
)
_TABLE_FOOTNOTE_RE = re.compile(
    r"^table_footnote:\s*(.*)$", re.MULTILINE | re.IGNORECASE,
)


def format_image_search_text(
    image_caption: Optional[str] = None,
    image_footnote: Optional[str] = None,
    section_title: Optional[str] = None,
    page_index: Optional[int] = None,
) -> str:
    """图片 chunk 检索文本：caption + 可选 footnote，无 [图片] 包装。"""
    if has_image_caption_or_footnote(image_caption, image_footnote):
        parts = []
        caption = _normalize_text(image_caption)
        footnote = _normalize_text(image_footnote)
        if caption:
            parts.append(caption)
        if footnote:
            parts.append(footnote)
        return "\n".join(parts)

    section = _normalize_text(section_title) or "未知章节"
    if page_index is not None:
        return f"{section} page {page_index + 1}"
    return section


def format_image_display_text(
    image_caption: Optional[str] = None,
    image_footnote: Optional[str] = None,
    section_title: Optional[str] = None,
    page_index: Optional[int] = None,
) -> str:
    """图片 chunk 展示文本（LLM / read_chunks）。"""
    if has_image_caption_or_footnote(image_caption, image_footnote):
        return format_image_chunk_placeholder(image_caption, image_footnote)

    section = _normalize_text(section_title) or "未知章节"
    if page_index is not None:
        page_display = page_index + 1
        return f"[图片]\n章节：{section}\n页码：{page_display}"
    return f"[图片]\n章节：{section}"


def html_table_to_plain_rows(table_html: str) -> str:
    """将 HTML <table> 转为 ``col | col | col`` 纯文本行。"""
    if not table_html or not table_html.strip():
        return ""
    text = table_html.strip()
    if "<tr" not in text.lower():
        return text

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.IGNORECASE | re.DOTALL)
    plain_rows: list[str] = []
    for row in rows:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.IGNORECASE | re.DOTALL)
        if not cells:
            continue
        cleaned = [
            re.sub(r"<[^>]+>", "", c).strip().replace("\n", " ")
            for c in cells
        ]
        plain_rows.append(" | ".join(cleaned))
    return "\n".join(plain_rows) if plain_rows else text


def format_table_display_text(
    table_body: str = "",
    table_caption: Optional[str] = None,
    table_footnote: Optional[str] = None,
) -> str:
    """表格 chunk 展示文本（保留 table_caption:/table_body:/table_footnote: 前缀）。"""
    parts: list[str] = []
    caption = _normalize_text(table_caption)
    footnote = _normalize_text(table_footnote)
    body = (table_body or "").strip()
    if caption:
        parts.append(f"table_caption: {caption}")
    if body:
        parts.append(f"table_body: {body}")
    if footnote:
        parts.append(f"table_footnote: {footnote}")
    return "\n".join(parts)


def format_table_search_text(
    table_body: str = "",
    table_caption: Optional[str] = None,
    table_footnote: Optional[str] = None,
) -> str:
    """表格 chunk 检索文本：caption + 纯文本行 + 可选 footnote。"""
    parts: list[str] = []
    caption = _normalize_text(table_caption)
    footnote = _normalize_text(table_footnote)
    body = (table_body or "").strip()

    if caption:
        parts.append(caption)
    if body:
        if "<table" in body.lower() or "<tr" in body.lower():
            plain = html_table_to_plain_rows(body)
            if plain:
                parts.append(plain)
        else:
            parts.append(body)
    if footnote:
        parts.append(footnote)
    return "\n".join(parts)


def parse_table_display_text(display_text: str) -> Tuple[Optional[str], str, Optional[str]]:
    """从展示文本解析 table_caption / body / footnote。"""
    if not display_text:
        return None, "", None

    caption_m = _TABLE_CAPTION_RE.search(display_text)
    footnote_m = _TABLE_FOOTNOTE_RE.search(display_text)
    body_m = _TABLE_BODY_RE.search(display_text)

    caption = caption_m.group(1).strip() if caption_m else None
    footnote = footnote_m.group(1).strip() if footnote_m else None

    body = ""
    if body_m:
        body = body_m.group(1).strip()
        if footnote_m:
            body = body[: footnote_m.start() - body_m.start(1)].strip()

    return caption, body, footnote


def format_table_search_text_from_display(display_text: str) -> str:
    """从已组装的表格展示文本生成检索文本（用于切分后的 table chunk）。"""
    caption, body, footnote = parse_table_display_text(display_text)
    return format_table_search_text(body, caption, footnote)


def _is_image_display_text(text: str) -> bool:
    return text.strip().startswith("[图片]")


def derive_search_text_from_legacy(
    *,
    chunk_type: Optional[str],
    text: Optional[str],
    image_caption: Optional[str] = None,
    image_footnote: Optional[str] = None,
    table_caption: Optional[str] = None,
    table_body: Optional[str] = None,
    table_footnote: Optional[str] = None,
) -> str:
    """
    从存量数据推导 search_text（迁移脚本 & 运行时 fallback）。
    """
    ctype = (chunk_type or "").lower()

    if ctype == "image":
        if image_caption or image_footnote:
            return format_image_search_text(image_caption, image_footnote)
        if text and _is_image_display_text(text):
            return format_image_search_text_from_display(text)
        return text or ""

    if ctype == "table":
        if table_caption or table_body or table_footnote:
            return format_table_search_text(table_body or "", table_caption, table_footnote)
        if text and "table_caption:" in text.lower():
            return format_table_search_text_from_display(text)
        return text or ""

    return text or ""


def format_image_search_text_from_display(display_text: str) -> str:
    """从 [图片] 展示文本反推检索文本。"""
    if not display_text:
        return ""
    caption = None
    footnote = None
    for line in display_text.splitlines():
        line = line.strip()
        if line.startswith("标题："):
            val = line[len("标题："):].strip()
            caption = None if val == "无" else val
        elif line.startswith("脚注："):
            val = line[len("脚注："):].strip()
            footnote = None if val == "无" else val
    if caption or footnote:
        return format_image_search_text(caption, footnote)
    return display_text


def resolve_chunk_search_text(doc: Any) -> str:
    """从 ChunkData 解析检索文本（search_text 优先，否则从 text_meta 推导）。"""
    stored = getattr(doc, "search_text", None)
    if stored and str(stored).strip():
        return str(stored).strip()

    # 从 text_meta 推导
    text_meta = getattr(doc, "text_meta", None) or {}
    ctype = (getattr(doc, "chunk_type", None) or "").lower()

    if ctype == "image":
        return format_image_search_text(
            image_caption=text_meta.get("image_caption"),
            image_footnote=text_meta.get("image_footnote"),
            section_title=text_meta.get("section_title"),
            page_index=text_meta.get("page_index"),
        )

    if ctype == "table":
        return format_table_search_text(
            table_body=text_meta.get("table_body", ""),
            table_caption=text_meta.get("table_caption"),
            table_footnote=text_meta.get("table_footnote"),
        )

    # text / code_block / 兜底
    return text_meta.get("text", "") or ""


def resolve_chunk_display_text(doc: Any) -> str:
    """从 ChunkData 解析展示文本（从 text_meta 拼接）。"""
    text_meta = getattr(doc, "text_meta", None) or {}
    ctype = (getattr(doc, "chunk_type", None) or "").lower()

    if ctype == "image":
        return format_image_display_text(
            image_caption=text_meta.get("image_caption"),
            image_footnote=text_meta.get("image_footnote"),
            section_title=text_meta.get("section_title"),
            page_index=text_meta.get("page_index"),
        )

    if ctype == "table":
        return format_table_display_text(
            table_body=text_meta.get("table_body", ""),
            table_caption=text_meta.get("table_caption"),
            table_footnote=text_meta.get("table_footnote"),
        )

    # text / code_block / 兜底
    return text_meta.get("text", "") or ""
