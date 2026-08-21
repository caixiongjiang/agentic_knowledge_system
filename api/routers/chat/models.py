#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : models.py
@Author  : caixiongjiang
@Date    : 2026/05/19
@Function:
    Chat 模型清单 REST 路由

    端点
    ----
        GET /api/chat/models    - 拉取当前可见的 chat 模型清单（白名单 + 缓存）
        POST /api/chat/models/refresh
                                - 强制刷新缓存（运维 / 调试用）

    设计取舍
    --------
    - **不直接代理网关 /v1/models**：经 ``LiteLLMRegistry`` 按档案 ``visible``
      白名单裁剪，仅返回 ``id / label / provider`` 等前端字段。
    - **路径下不暴露 preset / default 字段**：``[presets]`` 是抽取 pipeline /
      检索组件 / 工具的真相源，不是 chat 前端的事。
    - **鉴权**：与其他 chat 路由一致，依赖 ``X-User-Id`` 头。模型清单本身不含
      用户态数据；加鉴权只是与同 prefix 路由保持一致风格。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from loguru import logger

from api.dependencies.auth import get_current_user_id
from api.schemas.chat import ChatModelItem, ChatModelListResponse
from api.schemas.common import ApiResponse
from src.client.llm import get_litellm_registry


router = APIRouter(tags=["Chat / Models"])


@router.get(
    "",
    response_model=ApiResponse[ChatModelListResponse],
    summary="拉取 chat 模型清单",
)
async def list_chat_models(
    refresh: bool = Query(
        False,
        description="是否强制刷新（绕过 5min TTL 缓存，慎用）",
    ),
    user_id: str = Depends(get_current_user_id),
) -> ApiResponse[ChatModelListResponse]:
    """返回当前档案 ``visible`` 白名单与网关库存的交集。

    网关不可达且没有上次成功缓存时返回空列表，不编造兜底模型。
    """
    registry = get_litellm_registry()
    items = registry.list_models(force_refresh=bool(refresh))
    payload = ChatModelListResponse(
        models=[
            ChatModelItem(
                id=m.id,
                label=m.label,
                provider=m.provider,
                supports_thinking=m.supports_thinking,
                thinking_levels=m.thinking_levels,
                default_thinking_level=m.default_thinking_level,
                supports_multimodal=m.supports_multimodal,
                max_context=m.max_context,
            )
            for m in items
        ],
    )
    logger.debug(
        f"GET /api/chat/models: user={user_id}, count={len(payload.models)}, "
        f"refresh={refresh}"
    )
    return ApiResponse.success(data=payload)


@router.post(
    "/refresh",
    response_model=ApiResponse[ChatModelListResponse],
    summary="强制刷新模型清单缓存",
)
async def refresh_chat_models(
    user_id: str = Depends(get_current_user_id),
) -> ApiResponse[ChatModelListResponse]:
    """绕过 5 分钟 TTL，立刻向 LiteLLM Proxy 重拉 ``/v1/models``。

    给运维 / 调试用——proxy 上线了新模型但前端还在等 TTL 过期时，调一次
    本端点即可立即生效。
    """
    registry = get_litellm_registry()
    registry.invalidate()
    items = registry.list_models(force_refresh=True)
    payload = ChatModelListResponse(
        models=[
            ChatModelItem(
                id=m.id,
                label=m.label,
                provider=m.provider,
                supports_thinking=m.supports_thinking,
                thinking_levels=m.thinking_levels,
                default_thinking_level=m.default_thinking_level,
                supports_multimodal=m.supports_multimodal,
                max_context=m.max_context,
            )
            for m in items
        ],
    )
    logger.info(
        f"POST /api/chat/models/refresh: user={user_id}, count={len(payload.models)}"
    )
    return ApiResponse.success(data=payload)
