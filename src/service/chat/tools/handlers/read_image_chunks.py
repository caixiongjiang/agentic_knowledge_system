#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""read_image_chunks 工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from loguru import logger

from src.client.llm.types import ToolSchema
from src.service.chat.tools.base import ToolDefinition
from src.service.chat.tools.helpers import (
    apply_alias_labels_to_result,
    resolve_chunk_id_list,
)

if TYPE_CHECKING:
    from src.service.chat.tools.kit import KnowledgeNavToolKit

NAME = "read_image_chunks"

SCHEMA: ToolSchema = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "批量读取/理解图片 chunk。"
            "默认由工具内 VLM 返回文本描述（B 策略）；"
            "若 return_image_url=true 则返回压缩后的 image_url 供你自行看图（A 策略）。"
            "有 question 时，多张图片会**综合一次**回答；无 question 时一图一描述。"
            "图片会先按长边 512px 规则压缩。"
            "结果仅存在于本次对话，不会写入知识库。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chunk_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "目标图片 chunk 的引用号列表，**默认按 alias 传入**，"
                        "例如 [\"c1\", \"c3\"]；单次最多 10 条。"
                    ),
                    "minItems": 1,
                    "maxItems": 10,
                },
                "question": {
                    "type": "string",
                    "description": (
                        "可选：针对图片的具体问题。"
                        "传入时多张图片综合一次回答；不传则每张图单独返回 background 描述。"
                    ),
                },
                "return_image_url": {
                    "type": "boolean",
                    "description": (
                        "是否返回压缩后的 image_url（data URL）供主模型直接看图。"
                        "默认 false（工具内 VLM 返回文本）。"
                    ),
                    "default": False,
                },
                "use_alias": {
                    "type": "boolean",
                    "description": (
                        "是否启用 alias 模式，**默认 true**——返回文本里按 "
                        "`c1` / `c2` 引用号标记 chunk。"
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
    question: Optional[str] = None,
    return_image_url: bool = False,
    use_alias: bool = True,
) -> str:
    if not chunk_ids:
        return "read_image_chunks: chunk_ids 不能为空。"

    real_ids, unresolved_aliases, early_error = resolve_chunk_id_list(
        chunk_ids,
        alias_map=kit.alias_map,
        use_alias=use_alias,
        tool_name=NAME,
    )
    if early_error:
        return early_error

    from src.service.chat.image_chunk_reader_service import ImageChunkReaderService

    try:
        service = ImageChunkReaderService(kit=kit)
        result = await service.read_image_chunks(
            real_ids,
            question=question,
            return_image_url=return_image_url,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"read_image_chunks 执行异常: {e}")
        return f"read_image_chunks 失败: {e}"

    result = apply_alias_labels_to_result(
        result,
        real_ids,
        alias_map=kit.alias_map,
        use_alias=use_alias,
    )
    if unresolved_aliases:
        result += (
            f"\n以下 {len(unresolved_aliases)} 个引用号无法解析，已跳过："
            f"{', '.join(unresolved_aliases)}"
        )

    kit.note_result_count(len(real_ids))
    return result


DEFINITION = ToolDefinition(name=NAME, schema=SCHEMA, handler=handle)
