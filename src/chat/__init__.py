#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2025/12/31
@Function:
    Chat 协议层

    - ``stream_buffer``：流式累积器 ``StreamAccumulator``（Phase 0）
    - ``protocol``：WebSocket 传输协议 schema（Phase 4）
@Modify History:
    2026-05-09 - 加入 StreamAccumulator（Phase 0）
    2026-05-11 - 加入 protocol 模块（Phase 4）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.chat.protocol import (
    WS_SUBPROTOCOL,
    ChatRequestPayload,
    ClientFrame,
    ClientFrameType,
    ServerFrame,
    ServerFrameKind,
    chat_event_to_server_frame,
    make_error_frame,
    make_pong_frame,
    make_ready_frame,
    parse_client_frame,
)
from src.chat.stream_buffer import (
    StreamAccumulator,
    StreamEvent,
    StreamEventType,
)

__all__ = [
    # protocol
    "WS_SUBPROTOCOL",
    "ClientFrame",
    "ClientFrameType",
    "ChatRequestPayload",
    "ServerFrame",
    "ServerFrameKind",
    "chat_event_to_server_frame",
    "make_error_frame",
    "make_pong_frame",
    "make_ready_frame",
    "parse_client_frame",
    # stream
    "StreamAccumulator",
    "StreamEvent",
    "StreamEventType",
]
