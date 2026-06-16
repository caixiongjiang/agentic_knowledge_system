#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : registry.py
@Author  : caixiongjiang
@Date    : 2026/05/19
@Function:
    LiteLLM 模型注册中心

    负责把 LiteLLM Proxy 的 ``/v1/models`` 暴露给业务代码 / 前端，做以下工作：

    1. **拉取真相源**：调用 ``<proxy_base>/v1/models``（OpenAI 兼容格式）拿
       proxy 当前路由的全部模型；同时若 proxy 暴露 ``/v1/model/info``（
       LiteLLM 增强字段）则一并合并，便于过滤 chat 模式。
    2. **白名单 enrich**：仅保留 chat 类模型，并把字段裁剪到前端真正需要
       的最小集合（``id / label / provider``）；**不**透出 LiteLLM 原始
       ``model_info`` 中的能力标签 / 价格 / 内部 alias 等敏感信息。
    3. **TTL 缓存**：5 分钟内复用上一次结果，避免每次开下拉框打 proxy；
       提供 ``invalidate()`` 给运维做 hot-reload。
    4. **离线兜底**：proxy 不可达时，从 ``[llm.presets.*]`` 中出现过的
       model 字符串去重作为最小可用列表，保证前端不至于"模型清单为空"。

    本模块只做"读模型清单"。具体调用模型（chat / embedding / rerank）依然
    走 ``LLMClient`` / ``EmbeddingClient`` / ``RerankerClient``——它们各
    自把 ``api_base`` / ``api_key`` 注入给 LiteLLM。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 输出结构
# ============================================================


class LLMModelInfo(BaseModel):
    """前端可见的最小模型描述

    设计原则：**只暴露用于渲染下拉的字段**。能力 / 价格 / 内部 alias 不出现，
    避免把 proxy 的内部命名规则泄露给客户端。
    """

    id: str = Field(
        ...,
        description="LiteLLM 模型字符串（如 'openai/gpt-4o-mini'），同时是 API 入参",
    )
    label: str = Field(..., description="UI 上显示的友好名称（去掉 provider 前缀）")
    provider: str = Field(..., description="provider 名（用于前端按 provider 分组）")
    supports_thinking: bool = Field(
        default=False,
        description="模型是否支持思考链 / reasoning（来自 config/thinking_models.json 白名单）",
    )
    supports_multimodal: bool = Field(
        default=False,
        description="模型是否支持多模态读图（来自 config/multimodal_models.json 白名单）",
    )

    model_config = ConfigDict(extra="ignore", protected_namespaces=())


# ============================================================
# 注册中心
# ============================================================


class LiteLLMRegistry:
    """LiteLLM 模型清单的进程内注册中心

    生命周期
    --------
    通常作为模块级单例使用（见 ``get_litellm_registry()``）。线程安全：内部
    用一把简单锁保护 cache，缓存命中读不加锁，未命中拉 proxy 时序列化。
    """

    DEFAULT_TTL_SECONDS = 300  # 5 min
    HTTP_TIMEOUT_SECONDS = 5.0

    # config/thinking_models.json 的路径（相对于项目根）
    _THINKING_MODELS_PATH = Path(__file__).resolve().parents[3] / "config" / "thinking_models.json"
    # config/multimodal_models.json 的路径（相对于项目根）
    _MULTIMODAL_MODELS_PATH = Path(__file__).resolve().parents[3] / "config" / "multimodal_models.json"

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = max(0, int(ttl_seconds))
        self._lock = threading.Lock()
        self._cache: Optional[List[LLMModelInfo]] = None
        self._cache_at: float = 0.0
        # 失败兜底缓存（不参与 TTL，刷新失败时降级用）
        self._fallback_cache: List[LLMModelInfo] = []
        # thinking 模型白名单（从 config/thinking_models.json 加载）
        self._thinking_models: Set[str] = self._load_thinking_models()
        # multimodal 模型白名单（从 config/multimodal_models.json 加载）
        self._multimodal_models: Set[str] = self._load_multimodal_models()

    # ---- 公共 API ----

    def list_models(self, *, force_refresh: bool = False) -> List[LLMModelInfo]:
        """返回当前可见的 chat 模型清单。

        Args:
            force_refresh: 强制忽略 TTL 立即拉一次 proxy

        Returns:
            按 ``provider`` + ``label`` 排序后的 ``LLMModelInfo`` 列表；
            proxy 不可达时返回离线兜底（基于 ``[llm.presets.*]`` 的 model
            字符串去重）。
        """
        if not force_refresh and self._is_fresh():
            assert self._cache is not None
            return list(self._cache)

        with self._lock:
            # double-check：可能已有别的线程刷新过了
            if not force_refresh and self._is_fresh():
                assert self._cache is not None
                return list(self._cache)

            try:
                fresh = self._fetch_from_proxy()
                self._cache = fresh
                self._cache_at = time.monotonic()
                self._fallback_cache = list(fresh)  # 同时刷新兜底
                logger.info(f"[LiteLLMRegistry] 刷新成功，共 {len(fresh)} 个 chat 模型")
                return list(fresh)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"[LiteLLMRegistry] 拉取 /v1/models 失败，启用离线兜底: {e}"
                )
                fallback = self._build_offline_fallback()
                # 失败时缓存兜底结果，但 TTL 缩短为 30s 以便尽快重试
                self._cache = fallback
                self._cache_at = time.monotonic() - max(0, self._ttl - 30)
                return list(fallback)

    def invalidate(self) -> None:
        """清空缓存；下一次 ``list_models`` 强制刷新。"""
        with self._lock:
            self._cache = None
            self._cache_at = 0.0

    # ---- 内部 ----

    @classmethod
    def _load_thinking_models(cls) -> Set[str]:
        """从 ``config/thinking_models.json`` 加载支持 thinking 的模型白名单。

        JSON 格式::

            { "models": ["deepseek-v4-flash", "glm-5.1", ...] }

        返回模型名的 set；文件不存在或解析失败时返回空集（降级为全部不支持）。
        """
        path = cls._THINKING_MODELS_PATH
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            models = data.get("models") or []
            result = {str(m).strip() for m in models if isinstance(m, str) and m.strip()}
            logger.debug(f"[LiteLLMRegistry] 加载 thinking 白名单: {len(result)} 个模型")
            return result
        except FileNotFoundError:
            logger.debug(f"[LiteLLMRegistry] thinking 白名单文件不存在: {path}")
            return set()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[LiteLLMRegistry] 加载 thinking 白名单失败: {e}")
            return set()

    @classmethod
    def _load_multimodal_models(cls) -> Set[str]:
        """从 ``config/multimodal_models.json`` 加载支持多模态读图的模型白名单。

        JSON 格式::

            { "models": ["qwen3.6-flash", "qwen3.7-plus", ...] }

        返回模型名的 set；文件不存在或解析失败时返回空集（降级为全部不支持）。
        """
        path = cls._MULTIMODAL_MODELS_PATH
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            models = data.get("models") or []
            result = {str(m).strip() for m in models if isinstance(m, str) and m.strip()}
            logger.debug(f"[LiteLLMRegistry] 加载 multimodal 白名单: {len(result)} 个模型")
            return result
        except FileNotFoundError:
            logger.debug(f"[LiteLLMRegistry] multimodal 白名单文件不存在: {path}")
            return set()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[LiteLLMRegistry] 加载 multimodal 白名单失败: {e}")
            return set()

    def _is_fresh(self) -> bool:
        if self._cache is None:
            return False
        return (time.monotonic() - self._cache_at) < self._ttl

    def _resolve_proxy_config(self) -> Dict[str, Any]:
        """读取 ``[proxy]`` + ``.env`` 的 LiteLLM Proxy 配置。"""
        try:
            from src.utils.config_manager import get_config_manager
            from src.utils.env_manager import get_env_manager

            return get_config_manager().get_proxy_full_config(get_env_manager())
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[LiteLLMRegistry] 读取 proxy 配置失败: {e}")
            return {}

    def _fetch_from_proxy(self) -> List[LLMModelInfo]:
        cfg = self._resolve_proxy_config()
        api_base = (cfg.get("api_base") or "").strip()
        api_key = (cfg.get("api_key") or "").strip()
        if not api_base:
            raise RuntimeError(
                "未配置 LiteLLM Proxy api_base（检查 .env: LITELLM_PROXY_URL）"
            )

        url = api_base.rstrip("/") + "/v1/models"
        headers: Dict[str, str] = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        with httpx.Client(timeout=self.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            payload = resp.json()

        # 同时尝试拉 LiteLLM Proxy 的增强 endpoint（携带 mode 字段，便于过滤）
        info_map: Dict[str, Dict[str, Any]] = {}
        try:
            with httpx.Client(timeout=self.HTTP_TIMEOUT_SECONDS) as client:
                info_resp = client.get(
                    api_base.rstrip("/") + "/v1/model/info", headers=headers,
                )
                if info_resp.status_code == 200:
                    info_payload = info_resp.json()
                    for item in info_payload.get("data") or []:
                        mid = item.get("model_name") or item.get("id")
                        if mid:
                            info_map[mid] = item.get("model_info") or {}
        except Exception as e:  # noqa: BLE001
            # /v1/model/info 是 LiteLLM 私有扩展，没就降级（按 mode 不可知处理）
            logger.debug(f"[LiteLLMRegistry] /v1/model/info 不可用: {e}")

        return self._parse_models_response(payload, info_map, self._thinking_models, self._multimodal_models)

    # LiteLLM SDK 走 proxy 的官方前缀。SDK 看到该前缀会按 OpenAI 协议把请求转发
    # 给 ``api_base`` 指向的 LiteLLM Proxy，并在转发前**剥离这个前缀**——也就是
    # proxy 实际看到的 ``model`` 还是裸名（`deepseek-v4-flash` 等），不影响代理
    # 端的路由配置。
    PROXY_MODEL_PREFIX = "litellm_proxy/"

    @staticmethod
    def _parse_models_response(
        payload: Any,
        info_map: Optional[Dict[str, Dict[str, Any]]] = None,
        thinking_models: Optional[Set[str]] = None,
        multimodal_models: Optional[Set[str]] = None,
    ) -> List[LLMModelInfo]:
        """解析 ``/v1/models`` 响应；只保留 chat 类模型，并归一化 id 给 SDK 用。

        OpenAI 兼容格式::

            { "object": "list", "data": [ { "id": "...", "object": "model", ... } ] }

        过滤策略
        --------
        1. 若 ``info_map[id].mode`` 明确等于 ``chat``：保留；
        2. 若 ``info_map[id].mode`` 明确等于其他（``embedding`` / ``rerank``
           / ``image_generation`` 等）：剔除；
        3. ``info_map`` 缺该模型时（旧版 LiteLLM Proxy 不暴露 model_info）：
           按 id 启发式判断——id 中包含 ``embed`` / ``rerank`` / ``whisper``
           / ``tts`` 等明显非 chat 关键词的剔除，其他保留。

        归一化策略（关键）
        --------------------
        proxy 通常给模型配置 alias（如 ``deepseek-v4-flash`` / ``glm-5.1``）裸名，
        没有 ``provider/`` 前缀。LiteLLM SDK 拿到裸名时会尝试自己推断 provider
        然后失败抛 ``BadRequestError: LLM Provider NOT provided``。

        这里统一对**所有**没有显式 provider 前缀的 id 加上 ``litellm_proxy/``
        前缀，让 SDK 走代理透传分支。带显式 provider（如 ``openai/gpt-4o-mini``）
        的 id 也包一层，统一走代理透传——避免 SDK 走 OpenAI 直连分支拿不到
        本端 proxy 上设的 alias。
        """
        items = (payload or {}).get("data") or []
        info_map = info_map or {}
        thinking_set = thinking_models or set()
        multimodal_set = multimodal_models or set()

        non_chat_keywords = (
            "embed", "embedding",
            "rerank", "reranker",
            "whisper", "tts", "audio",
            "image", "vision-encoder", "moderation",
        )

        out: List[LLMModelInfo] = []
        for it in items:
            mid = (it or {}).get("id")
            if not isinstance(mid, str) or not mid:
                continue

            mode = (info_map.get(mid) or {}).get("mode")
            if mode and mode != "chat":
                continue
            if not mode:
                lowered = mid.lower()
                if any(kw in lowered for kw in non_chat_keywords):
                    continue

            normalized_id, label, provider = LiteLLMRegistry._normalize_proxy_id(mid)
            out.append(
                LLMModelInfo(
                    id=normalized_id,
                    label=label,
                    provider=provider,
                    supports_thinking=mid in thinking_set,
                    supports_multimodal=mid in multimodal_set,
                ),
            )

        out.sort(key=lambda m: m.label.lower())
        return out

    @staticmethod
    def _normalize_proxy_id(raw_id: str) -> tuple[str, str, str]:
        """把 proxy 返回的原始 id 归一化为 ``(sdk_id, ui_label, provider)``。

        - ``sdk_id``：交给 LiteLLM SDK 的 ``model`` 入参，**始终**带
          ``litellm_proxy/`` 前缀；
        - ``ui_label``：前端展示的友好名（去掉所有前缀后的最后一段）；
        - ``provider``：日志 / 调试用，不参与 UI 渲染。

        语义实例::

            "deepseek-v4-flash"           → (litellm_proxy/deepseek-v4-flash,
                                              deepseek-v4-flash, litellm_proxy)
            "openai/gpt-4o-mini"          → (litellm_proxy/openai/gpt-4o-mini,
                                              gpt-4o-mini, openai)
            "litellm_proxy/glm-5.1"       → (litellm_proxy/glm-5.1,
                                              glm-5.1, litellm_proxy)
        """
        if raw_id.startswith(LiteLLMRegistry.PROXY_MODEL_PREFIX):
            inner = raw_id[len(LiteLLMRegistry.PROXY_MODEL_PREFIX):]
            sdk_id = raw_id
        else:
            inner = raw_id
            sdk_id = LiteLLMRegistry.PROXY_MODEL_PREFIX + raw_id

        if "/" in inner:
            provider, _, label = inner.partition("/")
            provider = provider or "litellm_proxy"
            label = label or inner
        else:
            provider = "litellm_proxy"
            label = inner

        return sdk_id, label, provider

    def _build_offline_fallback(self) -> List[LLMModelInfo]:
        """离线兜底：从 ``[llm.presets.*]`` 抽取所有 model 字符串去重。"""
        if self._fallback_cache:
            # 上次有过成功的拉取结果，复用即可
            return list(self._fallback_cache)

        try:
            from src.utils.config_manager import get_config_manager

            presets = get_config_manager().get_llm_presets() or {}
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[LiteLLMRegistry] 离线兜底读 preset 失败: {e}")
            return []

        seen: set[str] = set()
        out: List[LLMModelInfo] = []
        for _, preset in presets.items():
            mid = (preset or {}).get("model")
            if not isinstance(mid, str) or not mid or mid in seen:
                continue
            seen.add(mid)
            sdk_id, label, provider = self._normalize_proxy_id(mid)
            out.append(
                LLMModelInfo(
                    id=sdk_id,
                    label=label,
                    provider=provider,
                    supports_thinking=mid in self._thinking_models,
                    supports_multimodal=mid in self._multimodal_models,
                ),
            )

        out.sort(key=lambda m: m.label.lower())
        return out


# ============================================================
# 单例
# ============================================================


_registry: Optional[LiteLLMRegistry] = None
_registry_lock = threading.Lock()


def get_litellm_registry() -> LiteLLMRegistry:
    """模块级单例工厂"""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = LiteLLMRegistry()
    return _registry


__all__ = [
    "LLMModelInfo",
    "LiteLLMRegistry",
    "get_litellm_registry",
]
