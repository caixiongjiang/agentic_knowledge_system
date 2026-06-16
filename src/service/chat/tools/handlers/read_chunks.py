#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""read_chunks 工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from loguru import logger

from src.client.llm.types import ToolSchema
from src.service.chat.tools.base import ToolDefinition
from src.service.chat.tools.helpers import resolve_chunk_id_list

if TYPE_CHECKING:
    from src.service.chat.tools.kit import KnowledgeNavToolKit

NAME = "read_chunks"

SCHEMA: ToolSchema = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "批量取已知 chunk 的**完整正文**（不走 200 字预览截断），与其他工具一样"
            "**默认按 alias 模式**工作——传入和返回的引用号都是 `c1` / `c2` 这种 alias，"
            "与 search_knowledge_base / drill_down / context_window 完全一致。"
            "在 search_knowledge_base / drill_down / context_window 看到 preview 被截断、"
            "内容不全、或公式/表格被切掉时，把相关的 alias 一次性传进来取回完整文本。"
            "本工具不换粒度、不取邻居，只是把指定 chunk 的全文拿出来；"
            "如果想看相邻片段请用 context_window，想换粒度请用 drill_down / roll_up。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chunk_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "目标 chunk 的引用号列表，**默认按 alias 传入**，例如 "
                        "[\"c1\", \"c3\", \"c12\"]；可一次最多传 10 条，"
                        "避免上下文被一次性塞爆。"
                        "若显式把 use_alias 设为 false，则改传真实 chunk_id。"
                    ),
                    "minItems": 1,
                    "maxItems": 10,
                },
                "max_chars": {
                    "type": "integer",
                    "description": (
                        "可选：每条 chunk 最多返回字符数。"
                        "<=0 表示不截断（默认）。"
                        ">0 时本工具仍会显式标注「截断 + 完整长度」。"
                    ),
                    "default": 0,
                    "minimum": 0,
                },
                "use_alias": {
                    "type": "boolean",
                    "description": (
                        "是否启用 alias 模式，**默认 true**——和其他工具一样按 "
                        "`c1` / `c2` 引用号工作；返回文本也用 alias 标签。"
                        "false 时改用真实 chunk_id（一般不需要切换，仅当外部脚本 "
                        "明确想看真实 id 时才传 false）。"
                    ),
                    "default": True,
                },
            },
            "required": ["chunk_ids"],
        },
    },
}


async def handle(
    kit: KnowledgeNavToolKit,
    chunk_ids: List[str],
    max_chars: int = 0,
    use_alias: bool = True,
) -> str:
    if not chunk_ids:
        return "read_chunks: chunk_ids 不能为空。"

    real_ids, unresolved_aliases, early_error = resolve_chunk_id_list(
        chunk_ids,
        alias_map=kit.alias_map,
        use_alias=use_alias,
        tool_name=NAME,
    )
    if early_error:
        if unresolved_aliases and "无法解析" in early_error:
            early_error += (
                "\n请确认这些引用号是否来自最近一次工具返回；如已过期，"
                "请用 search_knowledge_base / drill_down 重新拿最新的引用号。"
            )
        return early_error

    from src.db.mongodb.repositories.chunk_data_repository import (
        ChunkDataRepository,
    )

    try:
        chunk_data_list = await ChunkDataRepository().get_by_ids(real_ids)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"read_chunks 取 ChunkData 异常: {e}")
        return f"read_chunks 失败: {e}"

    from src.types.utils.chunk_search_text import resolve_chunk_display_text

    text_map: Dict[str, str] = {}
    for chunk_data in chunk_data_list:
        text_map[str(chunk_data.id)] = resolve_chunk_display_text(chunk_data)

    lines: List[str] = [
        f"read_chunks: 已返回 {len(text_map)}/{len(real_ids)} 条完整 chunk 正文"
        f"{'（alias 模式）' if use_alias else '（real-id 模式）'}。",
    ]
    missing: List[str] = []
    for cid in real_ids:
        full_text = text_map.get(cid)
        label = (
            kit.alias_map.alias_for(cid)
            if use_alias and kit.alias_map and cid
            else cid
        )
        if full_text is None:
            missing.append(label)
            continue
        if max_chars and max_chars > 0 and len(full_text) > max_chars:
            shown = full_text[:max_chars]
            suffix = (
                f" …(已按 max_chars={max_chars} 截断；"
                f"完整 {len(full_text)} 字)"
            )
        else:
            shown = full_text
            suffix = f"  (完整 {len(full_text)} 字)"
        lines.append(f"--- chunk_id={label}{suffix} ---\n{shown}")
    if missing:
        lines.append(
            f"以下 {len(missing)} 条未在 ChunkData 中找到，可能已删除或 id 无效："
            f"{', '.join(missing)}",
        )
    if unresolved_aliases:
        lines.append(
            f"以下 {len(unresolved_aliases)} 个引用号在当前会话 alias_map 中"
            f"无法解析（可能已过期或来自其他会话），未尝试查询数据库："
            f"{', '.join(unresolved_aliases)}",
        )
    kit.note_result_count(len(real_ids) - len(missing))
    return "\n".join(lines)


DEFINITION = ToolDefinition(name=NAME, schema=SCHEMA, handler=handle)
