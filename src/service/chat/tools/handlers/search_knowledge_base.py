#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""search_knowledge_base 工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from src.client.llm.types import ToolSchema
from src.service.chat.tools.base import ToolDefinition
from src.service.chat.tools.helpers import format_chunks_for_llm
from src.service.chat.tools.runtime import get_current_tool_call_id

if TYPE_CHECKING:
    from src.service.chat.tools.kit import KnowledgeNavToolKit

NAME = "search_knowledge_base"

SCHEMA: ToolSchema = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "在知识库中做**语义相关**片段检索（路由规划 + 多路召回 + 融合 + 精排），"
            "返回与 query 最相关的 Top-K 段落，适合概念探索与开放式问题。"
            "**不保证**某术语在全文中的字面全部命中；若需穷举某词的全部出现或确认精确数值/配置，"
            "再用 `grep_chunks` 做字面全扫，并用 `read_chunks` 取全文。"
            "返回的每条 chunk 正文为预览（默认 200 字）；preview 不完整时用 `read_chunks`，"
            "**不要**用 `context_window`（只取邻居、不会让当前 chunk 变全文）。"
            "可用不同 query 多次调用；`chunk_type` 可过滤 text/image/table/code_block。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_text": {
                    "type": "string",
                    "description": "检索查询文本，描述需要查找的信息",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 30,
                },
                "chunk_type": {
                    "type": "string",
                    "description": "过滤 chunk 类型：text=文本, image=图片, table=表格, code_block=代码块。不指定则返回所有类型",
                    "enum": ["text", "image", "table", "code_block"],
                },
            },
            "required": ["query_text"],
        },
    },
}


async def handle(
    kit: KnowledgeNavToolKit,
    query_text: str,
    top_k: int = 10,
    chunk_type: Optional[str] = None,
) -> str:
    if kit.retrieve_service is None:
        return "search_knowledge_base: 检索服务不可用。"

    from src.retrieve.pipeline.types import RetrieveRequest
    from src.retrieve.types.query import MetadataFilter

    filters = MetadataFilter(user_id=kit.user_id, chunk_type=chunk_type)
    if kit.knowledge_base_ids:
        filters.knowledge_base_id = kit.knowledge_base_ids[0]
    if kit.scope_document_ids:
        filters.document_ids = list(kit.scope_document_ids)

    request = RetrieveRequest(
        query_text=query_text,
        filters=filters,
        top_k=top_k,
        conversation_context=None,
    )

    async def on_progress(stage: str) -> None:
        await kit.emit_progress(stage, channel="retrieval")

    try:
        response = await kit.retrieve_service.retrieve(
            request,
            on_progress=on_progress,
        )
        items = list(response.items or [])
        kit.supplemented.extend(items)
        kit.note_result_count(len(items))
        # 记录查询转化模型名称（前端展示）
        if response.planner_model:
            kit.note_execution_model(response.planner_model)
        logger.debug(f"search_knowledge_base({query_text!r}) → {len(items)} chunks")

        tc_id = get_current_tool_call_id()
        if tc_id:
            chunks_brief = [
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "score": chunk.score,
                    "preview": (chunk.text or "")[:200],
                }
                for chunk in items
            ]
            params: Dict[str, Any] = {
                "query_text": query_text,
                "top_k": top_k,
            }
            if chunk_type:
                params["chunk_type"] = chunk_type
            if response.route_plan:
                params["route_plan"] = response.route_plan.model_dump(
                    exclude_none=True,
                )
            kit.search_results[tc_id] = (chunks_brief, params)

        return format_chunks_for_llm(
            items,
            alias_map=kit.alias_map,
            append_semantic_literal_hint=True,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"search_knowledge_base 执行异常: {e}")
        return f"检索失败: {e}"


DEFINITION = ToolDefinition(name=NAME, schema=SCHEMA, handler=handle)
