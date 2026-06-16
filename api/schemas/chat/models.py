#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : models.py
@Author  : caixiongjiang
@Date    : 2026/05/19
@Function:
    Chat /models 端点的响应 schema

    与 ``src.client.llm.registry.LLMModelInfo`` 同形——这里之所以再独立
    一份 Pydantic 模型，是为了让 API 层有完整 OpenAPI 文档体（``ApiResponse``
    内嵌泛型展开），同时让"对客户端的契约"和"内部数据结构"在演进时可解耦。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class ChatModelItem(BaseModel):
    """前端模型选择器单条记录"""

    id: str = Field(
        ...,
        description=(
            "LiteLLM 模型字符串（如 'openai/gpt-4o-mini'）；"
            "WebSocket start 帧透传到 ``ChatRequestPayload.model``"
        ),
    )
    label: str = Field(..., description="UI 上显示的友好名称（去掉 provider 前缀）")
    provider: str = Field(..., description="provider 名（用于前端按 provider 分组）")
    supports_thinking: bool = Field(
        default=False,
        description="模型是否支持思考链 / reasoning（来自 config/thinking_models.json 白名单，前端据此控制 ThinkingChip 显隐）",
    )
    supports_multimodal: bool = Field(
        default=False,
        description="模型是否支持多模态读图（来自 config/multimodal_models.json 白名单，前端据此控制多模态 Chip 显隐）",
    )

    # ``model`` 字段需要解除 Pydantic v2 的保护命名空间
    model_config = ConfigDict(extra="ignore", protected_namespaces=())


class ChatModelListResponse(BaseModel):
    """``GET /api/chat/models`` 响应体"""

    models: List[ChatModelItem] = Field(default_factory=list)


__all__ = ["ChatModelItem", "ChatModelListResponse"]
