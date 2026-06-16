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
    - **不直接代理 LiteLLM Proxy 的 /v1/models**：经过 ``LiteLLMRegistry``
      做白名单 enrich，仅返回 ``id / label / provider``，不暴露 proxy 内部的
      能力字段、定价、alias 等。
    - **路径下不暴露 preset / default 字段**：preset 是后台 RAG 抽取 / 起标题
      / 摘要等组件的真相源，不是 chat 前端的事。
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
    """返回当前 LiteLLM Proxy 路由的全部 chat 模型，按 provider/label 排序。

    前端"模型选择器"用此接口异步加载下拉。proxy 不可达时自动降级为离线兜底
    （由 ``[llm.presets.*]`` 的 model 字符串去重生成最小可用列表），保证
    UI 不会出现"清单为空"。
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
                supports_multimodal=m.supports_multimodal,
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
                supports_multimodal=m.supports_multimodal,
            )
            for m in items
        ],
    )
    logger.info(
        f"POST /api/chat/models/refresh: user={user_id}, count={len(payload.models)}"
    )
    return ApiResponse.success(data=payload)
