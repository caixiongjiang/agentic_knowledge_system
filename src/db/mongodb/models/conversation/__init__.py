#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/05/09
@Function:
    Conversation 类 Document 定义（对话/会话消息表）

    本目录与 MySQL 端 ``src/db/mysql/models/conversation/`` 概念对齐：
    存放所有"对话"领域的 MongoDB 文档（消息正文、思考、tool_calls、citations）。
    会话元信息（标题、计数、模型偏好）走 MySQL.chat_session。
@Modify History:
    2026-05-09 - 首版（Phase 1）：新增 ChatMessage
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.db.mongodb.models.conversation.chat_message import (
    ChatMessage,
    ChatRole,
    Citation,
    ToolCallRecord,
    TokenUsageRecord,
)

__all__ = [
    "ChatMessage",
    "ChatRole",
    "Citation",
    "ToolCallRecord",
    "TokenUsageRecord",
]
