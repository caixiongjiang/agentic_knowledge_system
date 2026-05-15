#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat 业务编排层（Phase 2 起逐步落地）

    - Phase 2: ``tools`` ── KnowledgeNavToolKit 公共基类
    - Phase 3: ``types`` / ``session_service`` / ``title_service`` / ``chat_service``
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.service.chat.chat_service import ChatService, ChatServiceConfig
from src.service.chat.session_service import (
    ChatSessionService,
    generate_message_id,
    generate_session_id,
)
from src.service.chat.title_service import (
    DEFAULT_TITLE_PROMPT_SYSTEM,
    TitleService,
    fallback_title,
)
from src.service.chat.tools import KnowledgeNavToolKit
from src.service.chat.types import (
    EVENT_TYPES_FROM_STREAM,
    ChatEvent,
    ChatEventType,
    ChatRequest,
    ChatTurnContext,
    ChatTurnResult,
)

__all__ = [
    # tools
    "KnowledgeNavToolKit",
    # types
    "ChatEvent",
    "ChatEventType",
    "ChatRequest",
    "ChatTurnContext",
    "ChatTurnResult",
    "EVENT_TYPES_FROM_STREAM",
    # services
    "ChatService",
    "ChatServiceConfig",
    "ChatSessionService",
    "TitleService",
    # helpers
    "generate_session_id",
    "generate_message_id",
    "fallback_title",
    "DEFAULT_TITLE_PROMPT_SYSTEM",
]
