#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : auth.py
@Author  : caixiongjiang
@Date    : 2026/01/21 10:00
@Function: 
    认证依赖模块
    提供 API 认证相关的依赖注入功能
@Modify History:
    2026/02/18 - 实现简化版用户认证（Header 提取 user_id）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional

from fastapi import Header, HTTPException, Query, WebSocket, status


async def get_current_user_id(
    x_user_id: str = Header(..., alias="X-User-Id", description="用户ID")
) -> str:
    """
    从请求头中提取当前用户ID

    生产环境应替换为 JWT Token 验证逻辑。

    Args:
        x_user_id: 请求头中的用户ID

    Returns:
        用户ID字符串

    Raises:
        HTTPException: 如果用户ID为空
    """
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(status_code=401, detail="缺少有效的用户标识")
    return x_user_id.strip()


async def get_current_user_id_from_token(
    token: str = Query(..., description="用户ID（query token 通道，与 X-User-Id 等价）")
) -> str:
    """
    从 query 参数 ``token`` 提取当前用户 ID。

    适用场景：浏览器原生无法自定义请求头的资源加载（如 react-pdf 的
    ``<Document file={url}>``、``<img src>`` 等），它们只能走普通 GET，
    无法携带 ``X-User-Id`` header。此时改用 ``?token=<user_id>`` 鉴权，
    与 WebSocket 的 query token 通道保持一致。

    生产环境应替换为 JWT Token 验证逻辑。

    Args:
        token: query 参数中的用户ID

    Returns:
        用户ID字符串

    Raises:
        HTTPException: 如果 token 为空
    """
    user_id = (token or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="缺少有效的用户标识")
    return user_id



async def get_current_user_id_ws(websocket: WebSocket) -> Optional[str]:
    """
    从 WebSocket 握手中提取当前用户 ID

    背景
    ----
    浏览器原生 WebSocket API **不能** 自定义 HTTP header，无法复用 HTTP 版的
    ``X-User-Id``。生产实践有两种通用做法：

    1. **query token**（首选）: 客户端 ``ws://host/api/chat/ws?token=<id>``；
       因为 query 在握手期就到达服务端，可以在 ``accept()`` 之前完成校验。
    2. **Sec-WebSocket-Protocol 子协议**: 把 token 拼到子协议字符串里
       （如 ``aks-chat-v1.<token>``），也能避免暴露到 URL 上（部分 CDN 会记
       录 URL）；本函数也兼容这种方式。

    返回 ``None`` 表示鉴权失败，调用方应当 ``close(code=1008)``。本函数
    **不直接抛 HTTPException**，因为在 ``accept()`` 之前 FastAPI 还没有
    建立 ASGI 响应循环，抛异常的效果不可预期。

    Args:
        websocket: FastAPI WebSocket 实例（注入由路由侧完成）

    Returns:
        用户 ID 字符串；鉴权失败返回 ``None``
    """
    # 1) 首选：query token
    token = websocket.query_params.get("token") or websocket.query_params.get(
        "user_id"
    )
    if token and token.strip():
        return token.strip()

    # 2) 备选：Sec-WebSocket-Protocol 形如 "aks-chat-v1.<token>"
    raw = websocket.headers.get("sec-websocket-protocol") or ""
    for sub in [s.strip() for s in raw.split(",") if s.strip()]:
        if "." in sub:
            _, _, candidate = sub.partition(".")
            if candidate:
                return candidate

    return None


async def close_unauthorized(websocket: WebSocket, reason: str = "unauthorized") -> None:
    """统一关闭"未鉴权"的 WS 连接

    code=1008 = Policy Violation（WS 协议规范定义为"鉴权失败"的标准码）
    """
    try:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=reason)
    except Exception:  # noqa: BLE001
        # 已经断开等场景；忽略
        pass
