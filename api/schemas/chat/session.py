#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : session.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat REST API 请求 / 响应模型

    设计要点
    --------
    - 与 ``src.db.mysql.models.conversation.chat_session.ChatSession`` 字段
      命名对齐，便于 DTO → ORM 直接构造；
    - 嵌套子模型（``Citation`` / ``ToolCallRecord`` / ``TokenUsageRecord``）
      照搬 MongoDB 端 Pydantic 定义的关键字段，避免前端跨库认知；
    - 列表返回统一用 ``PaginationResponse[T]`` 风格（``total / page / page_size``）。
@Modify History:
    2026-05-11 - 首版（Phase 4）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 请求模型
# ============================================================


class ChatSessionCreateRequest(BaseModel):
    """创建会话请求"""

    title: str = Field("新会话", max_length=255, description="会话标题（占位，首轮后异步覆盖）")
    knowledge_base_ids: List[str] = Field(
        default_factory=list,
        description="本会话允许检索的知识库 ID 列表；空表示用户全量 KB",
    )
    model_preset: str = Field("fast", description="LLM preset 名称")
    agent_mode: bool = Field(True, description="是否默认启用 Agent 工具循环")
    enable_thinking: bool = Field(False, description="是否默认启用思考链")
    max_tool_rounds: int = Field(5, ge=1, le=20, description="Agent 工具批次上限")
    system_prompt: Optional[str] = Field(
        None, description="用户自定义 system_prompt；None 表示用模块默认",
    )


class ChatSessionRenameRequest(BaseModel):
    """重命名会话请求"""

    title: str = Field(..., min_length=1, max_length=255, description="新标题")


# ============================================================
# 嵌套子模型
# ============================================================


class CitationItem(BaseModel):
    """命中片段引用（与 MongoDB Citation 子文档对齐）"""

    chunk_id: str
    document_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    score: float = 0.0

    # Phase A：UI 渲染扩展字段
    chunk_type: Optional[str] = None
    page_index: Optional[int] = None
    section_title: Optional[str] = None
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    preview: Optional[str] = None

    # Phase B：session 级 chunk alias（cN）
    alias: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ToolCallItem(BaseModel):
    """assistant 发起的单次工具调用记录（与 MongoDB ToolCallRecord 对齐）"""

    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result_brief: Optional[str] = None
    items_added: int = 0
    # 检索工具专用：持久化检索结果，供历史回放时前端渲染"查看"按钮
    retrieval_chunks: Optional[List[Dict[str, Any]]] = None
    retrieval_params: Optional[Dict[str, Any]] = None
    time_ms: Optional[float] = None

    model_config = ConfigDict(extra="ignore")


class TokenUsageItem(BaseModel):
    """单条 assistant 消息的 token 用量"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    thinking_tokens: Optional[int] = None
    total_tokens: int = 0

    model_config = ConfigDict(extra="ignore")


# ============================================================
# 响应模型
# ============================================================


class ChatSessionInfo(BaseModel):
    """会话详情（创建 / 重命名 / 单条 get 共用）"""

    session_id: str
    user_id: str
    title: str
    knowledge_base_ids: List[str] = Field(default_factory=list)
    model_preset: str = "fast"
    agent_mode: bool = True
    enable_thinking: bool = False
    max_tool_rounds: int = 5
    system_prompt: Optional[str] = None
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class ChatSessionUpdateResponse(BaseModel):
    """重命名 / 软删除 的统一返回"""

    session_id: str
    success: bool = True
    message: str = "ok"


class ChatSessionListItem(BaseModel):
    """会话列表中的轻量条目（不含 system_prompt 等长字段）

    必须保留 ``knowledge_base_ids``：前端按 KB 维度组织对话面板，需要据此把
    "本知识库的会话"从用户全量会话里筛出来；缺字段会导致前端过滤后总是空，
    每次刷新都触发 ensureSession → createChatSession，旧会话视觉上"消失"。
    """

    session_id: str
    title: str
    knowledge_base_ids: List[str] = Field(default_factory=list)
    model_preset: str = "fast"
    agent_mode: bool = True
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    create_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class ChatSessionListResponse(BaseModel):
    """会话列表分页响应"""

    items: List[ChatSessionListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


# ============================================================
# 消息历史响应
# ============================================================


class ChatMessageItem(BaseModel):
    """消息列表条目（与 MongoDB ChatMessage 字段对齐）"""

    message_id: str = Field(..., description="消息 ID（即 MongoDB _id）")
    role: str = Field(..., description="system / user / assistant / tool")
    content: str = ""
    thinking: Optional[str] = None
    tool_calls: List[ToolCallItem] = Field(default_factory=list)
    tool_call_id: Optional[str] = None
    citations: List[CitationItem] = Field(default_factory=list)
    usage: Optional[TokenUsageItem] = None
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    create_time: Optional[datetime] = None

    model_config = ConfigDict(extra="ignore")


class ChatMessageListResponse(BaseModel):
    """会话消息列表（按 create_time 正序，便于前端直接拼）"""

    session_id: str
    items: List[ChatMessageItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
