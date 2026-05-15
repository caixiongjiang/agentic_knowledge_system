#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/05/09
@Function:
    Conversation 类 Schema 定义（对话/会话表）

    本目录存放所有"对话"领域的关系型表，与 base / business / extract 平级：
    - base：基础粒度元数据（chunk / section / element ...）
    - business：用户层资源管理（knowledge_base / workspace ...）
    - extract：从原文提取/生成的衍生数据（atomic_qa / summary ...）
    - conversation：用户对话与 Agent 轨迹（本目录，含 chat_session 等）

    设计要点：
    - 仅存放**会话元信息**（轻量、强一致），消息正文走 MongoDB（半结构化、长文本）
    - 通过共享的 user_id / session_id 与 MongoDB 端的 ChatMessage 关联
    - 字段命名与项目 base_model.py 中的 BaseModel / AgentMixin 风格保持一致
@Modify History:
    2026-05-09 - 首版（Phase 1）：新增 ChatSession
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.db.mysql.models.conversation.chat_session import ChatSession

__all__ = [
    "ChatSession",
]
