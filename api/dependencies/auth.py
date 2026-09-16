#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : auth.py
@Author  : caixiongjiang
@Date    : 2026/01/21 10:00
@Function: 
    认证依赖模块
    提供 API 认证相关的依赖注入功能。

    两种登录模式（由 AUTH_MODE 环境变量决定，同一份代码支持不同部署）：
      - logto（公网部署，默认）：沿用 X-User-Id 透传，行为保持不变
      - oa（内部部署）：校验本域 JWT（Authorization: Bearer / query token），
                        user_id 取 JWT.sub（OA 工号）

@Modify History:
    2026/02/18 - 实现简化版用户认证（Header 提取 user_id）
    2026/09/16 - 新增 AUTH_MODE=oa 的本域 JWT 校验（HTTP / query / WebSocket 三通道）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional

from fastapi import Header, HTTPException, Query, WebSocket, status

from src.auth import AuthTokenError, decode_access_token, is_oa_auth_enabled


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization 头中提取 Bearer Token"""
    if not authorization:
        return None

    scheme, _, param = authorization.partition(" ")
    if scheme.strip().lower() != "bearer":
        return None

    return param.strip() or None


def _verify_oa_token(token: str) -> str:
    """校验本域 JWT 并返回 user_id，失败统一抛出 401"""
    try:
        return decode_access_token(token)
    except AuthTokenError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


async def get_current_user_id(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> str:
    """
    从请求中提取当前用户ID

    - OA 模式：校验 Authorization: Bearer <本域JWT>，返回 JWT.sub
    - logto 模式：读取 X-User-Id 请求头（公网部署沿用原有行为）

    Returns:
        用户ID字符串

    Raises:
        HTTPException: 缺少有效凭证时返回 401
    """
    if is_oa_auth_enabled():
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(
                status_code=401,
                detail="缺少登录凭证（Authorization: Bearer）",
            )
        return _verify_oa_token(token)

    if not x_user_id or not x_user_id.strip():
        raise HTTPException(status_code=401, detail="缺少有效的用户标识")
    return x_user_id.strip()


async def get_current_user_id_from_token(
    token: str = Query(..., description="登录凭证（query token 通道，与 Authorization 等价）")
) -> str:
    """
    从 query 参数 ``token`` 提取当前用户 ID。

    适用场景：浏览器原生无法自定义请求头的资源加载（如 react-pdf 的
    ``<Document file={url}>``、``<img src>`` 等），它们只能走普通 GET，
    无法携带 ``Authorization`` header。此时改用 ``?token=<凭证>`` 鉴权，
    与 WebSocket 的 query token 通道保持一致。

    - OA 模式：token 为本域 JWT，校验后取 sub
    - logto 模式：token 即 user_id（沿用原有行为）

    Args:
        token: query 参数中的凭证

    Returns:
        用户ID字符串

    Raises:
        HTTPException: 如果凭证为空或校验失败
    """
    raw_token = (token or "").strip()
    if not raw_token:
        raise HTTPException(status_code=401, detail="缺少有效的用户标识")

    if is_oa_auth_enabled():
        return _verify_oa_token(raw_token)

    return raw_token


async def get_current_user_id_ws(websocket: WebSocket) -> Optional[str]:
    """
    从 WebSocket 握手中提取当前用户 ID

    背景
    ----
    浏览器原生 WebSocket API **不能** 自定义 HTTP header，无法复用 HTTP 版的
    ``Authorization``。生产实践有两种通用做法：

    1. **query token**（首选）: 客户端 ``ws://host/api/chat/ws?token=<凭证>``；
       因为 query 在握手期就到达服务端，可以在 ``accept()`` 之前完成校验。
    2. **Sec-WebSocket-Protocol 子协议**: 把 token 拼到子协议字符串里
       （如 ``aks-chat-v1.<凭证>``），也能避免暴露到 URL 上（部分 CDN 会记
       录 URL）；本函数也兼容这种方式。

    - OA 模式：凭证为本域 JWT，校验失败返回 None
    - logto 模式：凭证即 user_id（沿用原有行为）

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

    # 2) 备选：Sec-WebSocket-Protocol 形如 "aks-chat-v1.<token>"
    if not (token and token.strip()):
        raw = websocket.headers.get("sec-websocket-protocol") or ""
        for sub in [s.strip() for s in raw.split(",") if s.strip()]:
            if "." in sub:
                _, _, candidate = sub.partition(".")
                if candidate:
                    token = candidate
                    break

    if not (token and token.strip()):
        return None

    credential = token.strip()

    if is_oa_auth_enabled():
        try:
            return decode_access_token(credential)
        except AuthTokenError:
            return None

    return credential


async def close_unauthorized(websocket: WebSocket, reason: str = "unauthorized") -> None:
    """统一关闭"未鉴权"的 WS 连接

    code=1008 = Policy Violation（WS 协议规范定义为"鉴权失败"的标准码）
    """
    try:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=reason)
    except Exception:  # noqa: BLE001
        # 已经断开等场景；忽略
        pass