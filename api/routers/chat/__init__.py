#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat API 路由汇聚

    挂载关系：

      /api/chat/sessions/*      — 会话 CRUD（REST）
      /api/chat/models          — LiteLLM 模型清单（REST，白名单 enrich）
      /api/chat/ws              — 流式对话（WebSocket）
@Modify History:
    2026-05-11 - 首版（Phase 4）
    2026-05-19 - 增加 /models 端点，前端模型选择器接入 LiteLLM Proxy
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from fastapi import APIRouter

from api.routers.chat.models import router as models_router
from api.routers.chat.sessions import router as sessions_router
from api.routers.chat.ws import router as ws_router

chat_router = APIRouter(prefix="/api/chat")
chat_router.include_router(sessions_router, prefix="/sessions")
chat_router.include_router(models_router, prefix="/models")
chat_router.include_router(ws_router)

__all__ = ["chat_router"]
