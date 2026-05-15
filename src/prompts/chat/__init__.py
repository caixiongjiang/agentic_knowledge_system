#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat 模块的 Prompt / 上下文组装层

    - ``system_prompt``       ── 知识库问答 Agent 的系统提示词
    - ``context_builder``     ── 检索片段渲染 + 历史 + 当前轮 → LiteLLM messages
    - ``history_compressor``  ── 长会话滑窗 / 摘要压缩
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.prompts.chat.system_prompt import (
    DEFAULT_CHAT_SYSTEM,
    build_chat_system_prompt,
)
from src.prompts.chat.context_builder import (
    compose_chat_messages,
    format_retrieved_chunks_for_context,
    rebuild_messages_from_history,
)
from src.prompts.chat.history_compressor import (
    SummarizeFn,
    apply_history_window,
    apply_token_window,
    compress_history_to_summary,
    count_message_tokens,
    drop_assistant_tool_dangling,
    estimate_history_tokens,
    summarize_history,
)

__all__ = [
    "DEFAULT_CHAT_SYSTEM",
    "build_chat_system_prompt",
    "compose_chat_messages",
    "format_retrieved_chunks_for_context",
    "rebuild_messages_from_history",
    "SummarizeFn",
    "apply_history_window",
    "apply_token_window",
    "compress_history_to_summary",
    "count_message_tokens",
    "drop_assistant_tool_dangling",
    "estimate_history_tokens",
    "summarize_history",
]
