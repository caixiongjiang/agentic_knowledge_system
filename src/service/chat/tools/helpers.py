#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""Chat Agent 工具公共辅助函数。"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

from src.prompts.chat.retrieval_hints import SEMANTIC_RECALL_LITERAL_HINT
from src.retrieve.types.result import ChunkItem
from src.service.chat.chunk_alias_map import ChunkAliasMap

_ALIAS_PATTERN = re.compile(r"^c\d+$")


def looks_like_alias(value: str) -> bool:
    """判断字符串是否符合 alias 命名模式（``c\\d+``）。"""
    return bool(value) and _ALIAS_PATTERN.match(value) is not None


def format_chunks_for_llm(
    chunks: List[ChunkItem],
    max_preview: int = 200,
    *,
    alias_map: Optional[ChunkAliasMap] = None,
    append_semantic_literal_hint: bool = False,
) -> str:
    """把 ChunkItem 列表渲染为给 LLM 看的预览文本。"""
    if not chunks:
        return "未找到相关内容。"
    truncated_aliases: List[str] = []
    lines = [
        f"找到 {len(chunks)} 个相关片段（每条正文为预览，最多 {max_preview} 字）:",
    ]
    for chunk in chunks:
        meta = chunk.metadata or {}
        chunk_type = meta.get("chunk_type") or meta.get("type") or "text"
        full_text = chunk.text or ""
        is_truncated = len(full_text) > max_preview
        text = full_text[:max_preview]
        doc = chunk.document_id or "N/A"
        sec = chunk.section_id or "N/A"
        cid_label = (
            alias_map.alias_for(chunk.chunk_id)
            if alias_map and chunk.chunk_id
            else chunk.chunk_id
        )
        suffix = ""
        if is_truncated:
            suffix = (
                f" …(预览，已截断；完整 {len(full_text)} 字，"
                f"调用 read_chunks(chunk_ids=[\"{cid_label}\"]) 获取全文)"
            )
            truncated_aliases.append(cid_label)

        type_hint = ""
        if chunk_type == "image":
            cap = meta.get("image_caption")
            fn = meta.get("image_footnote")
            cap_line = f"\n  标题：{cap}" if cap else ""
            fn_line = f"\n  脚注：{fn}" if fn else ""
            type_hint = (
                f"{cap_line}{fn_line}"
                f"\n  提示：图片内容请用 read_image_chunks(chunk_ids=[\"{cid_label}\"])"
            )
        elif chunk_type == "table":
            cap = meta.get("table_caption")
            fn = meta.get("table_footnote")
            cap_line = f"\n  标题：{cap}" if cap else ""
            fn_line = f"\n  脚注：{fn}" if fn else ""
            type_hint = f"{cap_line}{fn_line}"

        lines.append(
            f"- chunk_id={cid_label}, chunk_type={chunk_type}, "
            f"section_id={sec}, document_id={doc}, "
            f"score={chunk.score:.4f}{type_hint}\n  {text}{suffix}",
        )
    if truncated_aliases:
        lines.append(
            f"提示：以上 {len(truncated_aliases)} 条片段的正文为预览，"
            f"如需完整文本请用 read_chunks 一次性批量取回。",
        )
    if append_semantic_literal_hint:
        lines.append(SEMANTIC_RECALL_LITERAL_HINT)
    return "\n".join(lines)


def skeleton_outline_to_text(outline_tree: list) -> str:
    """SkeletonNode 列表转可读目录树文本。"""
    lines: List[str] = []

    def _walk(node: Any, depth: int = 0) -> None:
        indent = "  " * depth
        section_id = getattr(node, "section_id", "")
        title = getattr(node, "title", "") or "(无标题)"
        chunk_count = getattr(node, "chunk_count", 0)
        level = getattr(node, "level", None)
        level_part = f" L{level}" if level is not None else ""
        lines.append(
            f"{indent}- [{section_id}{level_part}] {title}（{chunk_count}个片段）",
        )
        for child in getattr(node, "children", []):
            _walk(child, depth + 1)

    for node in outline_tree:
        _walk(node)
    return "\n".join(lines) if lines else "(空目录)"


def count_outline_nodes(outline_tree: list) -> int:
    """统计 skeleton 目录树中的章节节点数。"""
    total = 0

    def _walk(node: Any) -> None:
        nonlocal total
        total += 1
        for child in getattr(node, "children", []):
            _walk(child)

    for node in outline_tree:
        _walk(node)
    return total


def dedupe_preserve_order(chunk_ids: List[str]) -> List[str]:
    seen: set = set()
    ordered: List[str] = []
    for cid in chunk_ids:
        if not isinstance(cid, str) or not cid or cid in seen:
            continue
        seen.add(cid)
        ordered.append(cid)
    return ordered


def resolve_chunk_id_list(
    chunk_ids: List[str],
    *,
    alias_map: Optional[ChunkAliasMap],
    use_alias: bool,
    tool_name: str,
) -> Tuple[List[str], List[str], Optional[str]]:
    """
    解析 chunk_ids 列表（alias unwrap 后）。

    Returns:
        (real_ids, unresolved_aliases, early_error_message)
    """
    ordered_ids = dedupe_preserve_order(chunk_ids)
    if not ordered_ids:
        return [], [], f"{tool_name}: 所有传入的 chunk_id 都为空或重复。"

    unresolved_aliases: List[str] = []
    real_ids: List[str] = []
    if use_alias:
        for cid in ordered_ids:
            if alias_map is not None and alias_map.is_alias(cid):
                unresolved_aliases.append(cid)
            elif alias_map is None and looks_like_alias(cid):
                unresolved_aliases.append(cid)
            else:
                real_ids.append(cid)
    else:
        real_ids = list(ordered_ids)

    if not real_ids:
        return [], unresolved_aliases, (
            f"{tool_name}: 所有传入的 chunk_id 在当前会话中都无法解析为真实 id。\n"
            f"未解析项：{', '.join(unresolved_aliases) or '(无)'}"
        )
    return real_ids, unresolved_aliases, None


def extract_match_snippet(
    text: str,
    query: str,
    mode: str,
    *,
    context_chars: int = 80,
) -> str:
    """从 chunk 正文中截取命中位置附近的 snippet。"""
    if not text:
        return "(空正文)"

    if mode == "boolean":
        preview_len = context_chars * 2
        if len(text) <= preview_len:
            return text
        return f"{text[:preview_len]} …(布尔匹配，预览 {preview_len} 字)"

    pattern = query if mode == "regex" else re.escape(query)
    try:
        match = re.search(pattern, text, re.IGNORECASE if mode != "regex" else 0)
    except re.error:
        match = None

    if not match:
        preview_len = context_chars * 2
        shown = text[:preview_len]
        suffix = f" …(共 {len(text)} 字)" if len(text) > preview_len else ""
        return f"{shown}{suffix}"

    start, end = match.span()
    win_start = max(0, start - context_chars)
    win_end = min(len(text), end + context_chars)
    prefix = "…" if win_start > 0 else ""
    suffix = "…" if win_end < len(text) else ""
    before = text[win_start:start]
    hit = text[start:end]
    after = text[end:win_end]
    return f"{prefix}{before}>>>{hit}<<<{after}{suffix}"


def format_grep_chunks_for_llm(
    chunks: List[ChunkItem],
    *,
    query: str,
    mode: str,
    context_chars: int = 80,
    alias_map: Optional[ChunkAliasMap] = None,
) -> str:
    """把 grep 命中结果渲染为带 snippet 的 LLM 文本（alias 模式）。"""
    if not chunks:
        return "未找到相关内容。"

    lines = [
        f"共 {len(chunks)} 条命中（snippet 展示命中处 ±{context_chars} 字；"
        "完整正文请用 read_chunks）：",
    ]
    for chunk in chunks:
        meta = chunk.metadata or {}
        chunk_type = meta.get("chunk_type") or meta.get("type") or "text"
        full_text = chunk.text or ""
        cid_label = (
            alias_map.alias_for(chunk.chunk_id)
            if alias_map and chunk.chunk_id
            else chunk.chunk_id
        )
        snippet = extract_match_snippet(
            full_text,
            query,
            mode,
            context_chars=context_chars,
        )
        doc = chunk.document_id or "N/A"
        sec = chunk.section_id or "N/A"
        read_hint = ""
        if len(full_text) > context_chars * 2:
            read_hint = (
                f"\n  提示：完整 {len(full_text)} 字，"
                f"read_chunks(chunk_ids=[\"{cid_label}\"])"
            )
        lines.append(
            f"- chunk_id={cid_label}, chunk_type={chunk_type}, "
            f"section_id={sec}, document_id={doc}\n  {snippet}{read_hint}",
        )
    return "\n".join(lines)


def apply_alias_labels_to_result(
    result: str,
    real_ids: List[str],
    *,
    alias_map: Optional[ChunkAliasMap],
    use_alias: bool,
) -> str:
    if not use_alias or alias_map is None:
        return result
    for cid in real_ids:
        alias = alias_map.alias_for(cid)
        if alias != cid:
            result = result.replace(f"chunk_id={cid}", f"chunk_id={alias}")
            result = result.replace(cid, alias)
    return result
