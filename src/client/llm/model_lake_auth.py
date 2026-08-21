#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : model_lake_auth.py
@Author  : caixiongjiang
@Date    : 2026/08/19
@Function:
    Model Lake 入站鉴权。后端无人登录态时：
    Service JWT：``POST {AUTH_BASE}/auth/client/token``
    body ``{"client_id","client_secret"}``，读 ``data.access_token`` / ``data.expires_in``
    （默认 3600s），到期前 60s 刷新。
    只打 ``/model-lake/v1/*``，禁止 ``unified/v1``。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from loguru import logger

from src.utils.env_manager import normalize_model_lake_api_base

MODEL_LAKE_GATEWAY_TYPES = frozenset({"model_lake", "openai", "openai_compatible"})
_REFRESH_SKEW_SECONDS = 60.0
_TOKEN_HTTP_TIMEOUT = 10.0


def is_model_lake_gateway(gateway_type: Optional[str]) -> bool:
    return (gateway_type or "").strip().lower() in MODEL_LAKE_GATEWAY_TYPES


def looks_like_auth_failure(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        m in text
        for m in (
            "expired_token",
            "invalid_token",
            "missing_token",
            "invalid_api_key",
            "expired_api_key",
            "unauthorized",
            "authenticationerror",
            "status code 401",
            "error code: 401",
            "http/1.1 401",
        )
    )


def extract_access_token(payload: Any) -> Tuple[Optional[str], Optional[float]]:
    """解析 Auth 响应：``{code:200, data:{access_token, expires_in}}``。"""
    if not isinstance(payload, dict):
        return None, None
    if payload.get("code") not in (None, 200, "200"):
        return None, None
    data = payload["data"] if isinstance(payload.get("data"), dict) else payload
    token = data.get("access_token") or data.get("token")
    if not token or not isinstance(token, str):
        return None, None
    try:
        ttl = float(data["expires_in"]) if data.get("expires_in") is not None else 3600.0
    except (TypeError, ValueError):
        ttl = 3600.0
    return token, ttl


class ModelLakeAuthError(RuntimeError):
    """凭证缺失或换票失败（fail-closed）。"""


class ModelLakeAuthProvider:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._exp: float = 0.0

    def invalidate(self) -> None:
        with self._lock:
            self._token = None
            self._exp = 0.0

    def get_token(self, *, force_refresh: bool = False) -> str:
        from src.utils.env_manager import get_env_manager

        env = get_env_manager()
        if not env.has_auth_client_credentials():
            raise ModelLakeAuthError(
                "Model Lake 未配置凭证：请设置 AUTH_BASE + AUTH_CLIENT_ID + AUTH_CLIENT_SECRET"
            )

        with self._lock:
            now = time.time()
            if not force_refresh and self._token and now < self._exp - _REFRESH_SKEW_SECONDS:
                return self._token

            url = env.get_auth_client_token_url()
            client_id = env.get_auth_client_id()
            client_secret = env.get_auth_client_secret()
            logger.debug(f"[ModelLakeAuth] POST {url} 换取 Service JWT")
            try:
                with httpx.Client(timeout=_TOKEN_HTTP_TIMEOUT) as client:
                    resp = client.post(
                        url,
                        headers={"Content-Type": "application/json", "Accept": "application/json"},
                        json={"client_id": client_id, "client_secret": client_secret},
                    )
                    resp.raise_for_status()
                    body = resp.json()
            except Exception as e:  # noqa: BLE001
                raise ModelLakeAuthError(f"Auth 换取 Service JWT 失败: {e}") from e

            if body.get("code") != 200:
                raise ModelLakeAuthError(f"换 token 失败: {body}")
            token, ttl = extract_access_token(body)
            if not token:
                raise ModelLakeAuthError("Auth 响应缺少 data.access_token")

            self._token = token
            self._exp = time.time() + (ttl or 3600.0)
            logger.info("[ModelLakeAuth] 已换取 Service JWT")
            return token

    def authorization_header(self, *, force_refresh: bool = False) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.get_token(force_refresh=force_refresh)}"}


_provider: Optional[ModelLakeAuthProvider] = None
_provider_lock = threading.Lock()


def get_model_lake_auth() -> ModelLakeAuthProvider:
    global _provider
    if _provider is None:
        with _provider_lock:
            if _provider is None:
                _provider = ModelLakeAuthProvider()
    return _provider


def reset_model_lake_auth() -> None:
    global _provider
    with _provider_lock:
        _provider = None


__all__ = [
    "MODEL_LAKE_GATEWAY_TYPES",
    "ModelLakeAuthError",
    "ModelLakeAuthProvider",
    "extract_access_token",
    "get_model_lake_auth",
    "is_model_lake_gateway",
    "looks_like_auth_failure",
    "normalize_model_lake_api_base",
    "reset_model_lake_auth",
]
