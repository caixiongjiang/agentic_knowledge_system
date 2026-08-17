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
# 思考强度（pi 风格的标准 7 档词汇）
# ============================================================

# pi 的标准档位顺序（从低到高）。所有模型共用这套词汇，每模型通过
# ``thinkingLevelMap`` 声明各自支持哪些档位、以及档位到厂商原生字符串的映射。
# 详见 config/thinking_models.json。
EXTENDED_THINKING_LEVELS: List[str] = [
    "off",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
]

# ``off`` 之外的可选档位（用于 resolve 时区分 off 与其余档位的缺省语义）
THINKING_LEVELS_NO_OFF: List[str] = [
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
]


class ThinkingModelSpec(BaseModel):
    """``config/thinking_models.json`` 中单个模型的思考强度声明。

    - ``reasoning``：模型是否支持思考链（不支持时该条目本身不应出现，但保留
      字段以兼容旧裸数组格式降级）。
    - ``default``：新建会话时前端默认选中的档位；必须在 ``thinkingLevelMap``
      支持的档位集合内。
    - ``thinking_level_map``：键 = pi 标准 7 档；值 = ``str``（透传给 LiteLLM 的
      ``reasoning_effort``，如 ``"high"`` 或厂商原生 ``"max"``）/ ``None``（该
      档不支持，前端隐藏）/ 缺省（``off`` 及 ``minimal..high`` 默认支持并透传档位
      名本身；``xhigh`` / ``max`` 是 opt-in，缺省视为不支持）。
    """

    reasoning: bool = True
    default: str = "medium"
    thinking_level_map: Dict[str, Optional[str]] = Field(
        default_factory=dict, alias="thinkingLevelMap",
    )

    model_config = ConfigDict(
        extra="ignore", protected_namespaces=(), populate_by_name=True,
    )

    def resolve_reasoning_effort(self, level: str) -> Optional[str]:
        """把 pi 标准档位翻译成要下发给 LiteLLM 的 ``reasoning_effort`` 字符串。

        返回 ``None`` 表示"不下发该参数"；返回字符串表示透传。调用方应先用
        ``clamp_thinking_level`` 把 level 归位到该模型支持的档位。

        翻译规则（统一走 ``thinking_level_map``，off 不特判）：
        - ``off`` → ``thinking_level_map["off"]``：字符串（如 ``"none"``）透传，
          显式关闭思考链；缺省 → ``None``（不下发，让模型按默认）；
          显式 ``null`` = 不能关思考（``clamp`` 已归位，不会到达）。
        - ``minimal..high`` → 字符串透传；缺省 → 透传档位名本身。
        - ``xhigh/max`` → 同上（``clamp`` 已保证有非空字符串映射）。
        """
        if not self.reasoning:
            return None
        if level not in self.thinking_level_map:
            return None if level == "off" else level
        mapped = self.thinking_level_map[level]
        if mapped is None:
            return None  # 显式 null = 不支持（防御式）
        return mapped


def get_supported_thinking_levels(spec: Optional[ThinkingModelSpec]) -> List[str]:
    """根据 ``ThinkingModelSpec`` 计算该模型支持的档位列表（保持 EXTENDED 顺序）。

    规则（与 pi ``getSupportedThinkingLevels`` 一致）：

    - 无 spec 或 ``reasoning=False`` → 仅 ``["off"]``（不能思考，但可显式关）。
    - 否则遍历 EXTENDED_THINKING_LEVELS：
      - ``map[level]`` 为非空字符串 → 支持，透传该字符串；
      - ``map[level] is None``（显式 null） → 该档不支持，跳过
        （``off:null`` 表示"不能关思考"，前端隐藏 off）；
      - ``level`` 在 map 中缺省 → 默认支持并透传档位名本身，**但** ``xhigh``/``max``
        是 opt-in，缺省视为不支持。
    """
    if spec is None or not spec.reasoning:
        return ["off"]

    out: List[str] = []
    for level in EXTENDED_THINKING_LEVELS:
        if level in spec.thinking_level_map:
            mapped = spec.thinking_level_map[level]
            if mapped is None:
                # 显式 null → 不支持（含 off:null 表示不能关思考）
                continue
            out.append(level)
        else:
            # 缺省：xhigh/max 是 opt-in（缺省不支持）；其余档位默认支持
            if level in ("xhigh", "max"):
                continue
            out.append(level)
    return out


def clamp_thinking_level(spec: Optional[ThinkingModelSpec], level: str) -> str:
    """把任意请求档位归位到该模型实际支持的最近档位（pi ``clampThinkingLevel``）。

    先向上（更高强度）找，再向下（更低强度）找；都找不到回落到 ``"off"``。
    """
    available = get_supported_thinking_levels(spec)
    if level in available:
        return level
    idx = EXTENDED_THINKING_LEVELS.index(level) if level in EXTENDED_THINKING_LEVELS else -1
    if idx >= 0:
        for i in range(idx, len(EXTENDED_THINKING_LEVELS)):
            if EXTENDED_THINKING_LEVELS[i] in available:
                return EXTENDED_THINKING_LEVELS[i]
        for i in range(idx - 1, -1, -1):
            if EXTENDED_THINKING_LEVELS[i] in available:
                return EXTENDED_THINKING_LEVELS[i]
    return available[0] if available else "off"


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
    thinking_levels: List[str] = Field(
        default_factory=list,
        description=(
            "该模型支持的思考强度档位（pi 标准 7 档子集，保持顺序）。"
            "supports_thinking=False 时为 ['off']；前端据此渲染档位下拉。"
        ),
    )
    default_thinking_level: Optional[str] = Field(
        default=None,
        description=(
            "新建会话时默认选中的档位（必须在 thinking_levels 内）。"
            "supports_thinking=False 时为 None。"
        ),
    )
    supports_multimodal: bool = Field(
        default=False,
        description="模型是否支持多模态读图（来自 config/multimodal_models.json 白名单）",
    )
    max_context: Optional[int] = Field(
        default=None,
        description=(
            "模型自身声明的最大上下文长度（tokens）：优先取 "
            "config/long_context_models.json，其次取 proxy /v1/model/info 的 "
            "max_input_tokens；None 表示两处都未提供。"
            "注意这是模型能力值，实际参与预算的窗口是 "
            "min(该值, [chat.context] max_context_cap)，见 ModelContextCatalog。"
        ),
    )

    # 非公开：档位 → 厂商原生 reasoning_effort 字符串的映射，供
    # ``resolve_reasoning_effort`` 在后端调用 LLM 前做翻译。不暴露给前端。
    thinking_level_map: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="档位到厂商原生 reasoning_effort 的映射（内部用，不下发前端）",
    )

    model_config = ConfigDict(extra="ignore", protected_namespaces=())

    def resolve_reasoning_effort(self, level: str) -> Optional[str]:
        """把 pi 标准档位翻译成要下发给 LiteLLM 的 ``reasoning_effort`` 字符串。

        返回 ``None`` 表示"不下发该参数"；返回字符串表示透传该字符串。调用方应
        先用 ``clamp_thinking_level`` 把 level 归位到该模型支持的档位，再调用本方法。

        翻译规则（统一走 ``thinking_level_map``，off 不再特判 None）：
        - ``off`` → ``thinking_level_map["off"]``：字符串（如 ``"none"``）则透传，
          显式下发以关闭思考链；缺省则返回 ``None``（不下发，让模型按默认）；
          显式 ``null`` 表示该模型不能关思考（``clamp`` 已归位，不会到达）。
        - ``minimal..high`` → ``thinking_level_map[level]``：字符串透传；缺省则
          透传档位名本身（如 ``"medium"``）。
        - ``xhigh/max`` → 同上（``clamp`` 已保证 ``map`` 有非空字符串映射）。
        - 不支持的档位（map 显式 null 且被传入）→ 返回 ``None``（防御式）。
        """
        if not self.supports_thinking:
            return None
        if level not in self.thinking_level_map:
            # 缺省：off → None（不下发）；minimal..high → 透传档位名本身
            return None if level == "off" else level
        mapped = self.thinking_level_map[level]
        if mapped is None:
            # 显式 null = 不支持（clamp 已归位，正常不到达；防御式返回 None）
            return None
        return mapped  # 字符串透传（含 off 的 "none" 或厂商原生 "max"）



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
    # config/long_context_models.json 的路径（相对于项目根）
    _LONG_CONTEXT_MODELS_PATH = Path(__file__).resolve().parents[3] / "config" / "long_context_models.json"

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = max(0, int(ttl_seconds))
        self._lock = threading.Lock()
        self._cache: Optional[List[LLMModelInfo]] = None
        self._cache_at: float = 0.0
        # 失败兜底缓存（不参与 TTL，刷新失败时降级用）
        self._fallback_cache: List[LLMModelInfo] = []
        # thinking 模型白名单（从 config/thinking_models.json 加载）
        # thinking 模型声明（从 config/thinking_models.json 加载：bare_name -> spec）
        self._thinking_models: Dict[str, ThinkingModelSpec] = self._load_thinking_models()
        # 兼容旧调用方：裸名集合（supports_thinking 判断用）
        self._thinking_names: Set[str] = set(self._thinking_models.keys())
        # multimodal 模型白名单（从 config/multimodal_models.json 加载）
        self._multimodal_models: Set[str] = self._load_multimodal_models()
        # 长上下文模型声明（从 config/long_context_models.json 加载：model -> max_context tokens）
        self._long_context_map: Dict[str, int] = self._load_long_context_models()

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

    def peek_max_context(self, bare_name: str) -> Optional[int]:
        """从**已有缓存**里查模型声明的上下文长度；缓存为空时返回 None。

        专供 ``ModelContextCatalog`` 在对话主链路上调用：绝不触发 proxy 拉取，
        避免把 5s 超时的 HTTP 往返引入每轮预算计量。
        """
        cache = self._cache or self._fallback_cache
        if not cache:
            return None
        target = (bare_name or "").strip()
        if not target:
            return None
        for m in cache:
            if self._bare_model_name(m.id) == target and m.max_context:
                return int(m.max_context)
        return None

    def peek_thinking_spec(self, bare_name: str) -> Optional[ThinkingModelSpec]:
        """从配置里查模型的思考强度声明（不依赖 proxy 缓存，不触发拉取）。

        供 ``ChatService`` 在调用 LLM 前把用户选的 ``thinking_level`` 翻译成
        ``reasoning_effort`` 字符串。``bare_name`` 为裸名（不含 ``litellm_proxy/``
        前缀）；找不到返回 ``None``（模型不支持思考）。
        """
        target = (bare_name or "").strip()
        if not target:
            return None
        return self._thinking_models.get(target)

    def resolve_reasoning_effort(
        self, model: str, thinking_level: str
    ) -> Optional[str]:
        """把 pi 标准档位翻译成要下发给 LiteLLM 的 ``reasoning_effort`` 字符串。

        入参 ``model`` 可以是裸名或带 ``litellm_proxy/`` 前缀的 SDK id。流程：
        1. 取裸名查 ``ThinkingModelSpec``；不存在或不支持思考 → 返回 ``None``；
        2. 用 ``clamp_thinking_level`` 把 ``thinking_level`` 归位到该模型支持的档位；
        3. 按档位映射得到 ``reasoning_effort`` 字符串（``off`` → ``None``，不下发）。

        返回 ``None`` 表示"不下发 ``reasoning_effort``"（模型不支持思考，或档位为 off）。
        """
        bare = self._bare_model_name(model or "")
        spec = self._thinking_models.get(bare)
        if spec is None or not spec.reasoning:
            return None
        clamped = clamp_thinking_level(spec, thinking_level)
        # 统一走 spec.resolve_reasoning_effort（off 不再特判 None）
        return spec.resolve_reasoning_effort(clamped)

    def clamp_thinking_level(self, model: str, thinking_level: str) -> str:
        """把请求档位归位到该模型实际支持的最近 pi 档位（返回标准档位名，非 effort 字符串）。

        模型不支持思考时返回 ``"off"``。供 ``ChatService`` 在构造 ``ChatTurnContext``
        时把用户 / session 的 ``thinking_level`` 钳位成可持久化、可下发的合法值。
        """
        bare = self._bare_model_name(model or "")
        spec = self._thinking_models.get(bare)
        if spec is None or not spec.reasoning:
            return "off"
        return clamp_thinking_level(spec, thinking_level)

    def invalidate(self) -> None:
        """清空缓存；下一次 ``list_models`` 强制刷新。"""
        with self._lock:
            self._cache = None
            self._cache_at = 0.0

    # ---- 内部 ----

    @classmethod
    def _load_thinking_models(cls) -> Dict[str, ThinkingModelSpec]:
        """从 ``config/thinking_models.json`` 加载思考强度声明。

        新格式（推荐）::

            {
              "models": {
                "deepseek-v4-pro": {
                  "reasoning": true,
                  "default": "medium",
                  "thinkingLevelMap": {
                    "off": "none", "minimal": null, "low": "low",
                    "medium": "medium", "high": "high",
                    "xhigh": null, "max": null
                  }
                }
              }
            }

        旧格式（向后兼容，裸数组）::

            { "models": ["deepseek-v4-flash", "glm-5.1", ...] }

        旧数组会被升级为 ``ThinkingModelSpec(reasoning=True, default="medium")``，
        其 ``thinking_level_map`` 为空（即支持 off + minimal..high，透传档位名）。

        返回 ``{bare_name: ThinkingModelSpec}``；文件不存在或解析失败时返回空字典
        （降级为全部不支持思考）。
        """
        path = cls._THINKING_MODELS_PATH
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.debug(f"[LiteLLMRegistry] thinking 声明文件不存在: {path}")
            return {}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[LiteLLMRegistry] 加载 thinking 声明失败: {e}")
            return {}

        raw = data.get("models")
        result: Dict[str, ThinkingModelSpec] = {}
        if isinstance(raw, dict):
            for name, spec in raw.items():
                if not isinstance(name, str) or not name.strip():
                    continue
                if isinstance(spec, dict):
                    tlm = spec.get("thinkingLevelMap") or spec.get("thinking_level_map") or {}
                    # 归一化键值：value 只允许 str / None
                    norm_map: Dict[str, Optional[str]] = {}
                    for k, v in (tlm or {}).items():
                        if not isinstance(k, str):
                            continue
                        norm_map[k] = v if (v is None or isinstance(v, str)) else None
                    result[name.strip()] = ThinkingModelSpec(
                        reasoning=bool(spec.get("reasoning", True)),
                        default=str(spec.get("default", "medium")),
                        thinking_level_map=norm_map,
                    )
                else:
                    result[name.strip()] = ThinkingModelSpec()
        elif isinstance(raw, list):
            # 旧裸数组格式：升级为默认 spec
            for m in raw:
                if isinstance(m, str) and m.strip():
                    result[m.strip()] = ThinkingModelSpec()
        logger.debug(f"[LiteLLMRegistry] 加载 thinking 声明: {len(result)} 个模型")
        return result

    @classmethod
    def _load_multimodal_models(cls) -> Set[str]:
        """从 ``config/multimodal_models.json`` 加载支持多模态读图的模型白名单。

        JSON 格式::

            { "models": ["qwen3.7-flash", "qwen3.7-plus", ...] }

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

    @classmethod
    def _load_long_context_models(cls) -> Dict[str, int]:
        """从 ``config/long_context_models.json`` 加载模型上下文长度声明。

        JSON 格式（向后兼容）::

            {
              "models": {
                "deepseek-v4-pro": 1000000,
                "qwen3.7-plus": {"max_context": 262144, "max_output": 8192}
              }
            }

        返回 ``{model_name: max_context_tokens}`` 字典；对象形式只取
        ``max_context``（``max_output`` 由 ModelContextCatalog 使用）。
        文件不存在或解析失败时返回空字典。
        """
        path = cls._LONG_CONTEXT_MODELS_PATH
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("models") or {}
            result: Dict[str, int] = {}
            for k, v in raw.items():
                if not isinstance(k, str) or not k.strip():
                    continue
                name = k.strip()
                if isinstance(v, int) and v > 0:
                    result[name] = v
                elif isinstance(v, dict):
                    mc = v.get("max_context")
                    if isinstance(mc, int) and mc > 0:
                        result[name] = mc
            logger.debug(f"[LiteLLMRegistry] 加载 long_context 声明: {len(result)} 个模型")
            return result
        except FileNotFoundError:
            logger.debug(f"[LiteLLMRegistry] long_context 声明文件不存在: {path}")
            return {}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[LiteLLMRegistry] 加载 long_context 声明失败: {e}")
            return {}

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

        return self._parse_models_response(
            payload, info_map, self._thinking_models, self._multimodal_models, self._long_context_map,
        )

    # LiteLLM SDK 走 proxy 的官方前缀。SDK 看到该前缀会按 OpenAI 协议把请求转发
    # 给 ``api_base`` 指向的 LiteLLM Proxy，并在转发前**剥离这个前缀**——也就是
    # proxy 实际看到的 ``model`` 还是裸名（`deepseek-v4-flash` 等），不影响代理
    # 端的路由配置。
    PROXY_MODEL_PREFIX = "litellm_proxy/"

    @staticmethod
    def _parse_models_response(
        payload: Any,
        info_map: Optional[Dict[str, Dict[str, Any]]] = None,
        thinking_models: Optional[Dict[str, ThinkingModelSpec]] = None,
        multimodal_models: Optional[Set[str]] = None,
        long_context_map: Optional[Dict[str, int]] = None,
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
        thinking_specs = thinking_models or {}
        multimodal_set = multimodal_models or set()
        long_ctx_map = long_context_map or {}

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

            info = info_map.get(mid) or {}
            mode = info.get("mode")
            if mode and mode != "chat":
                continue
            if not mode:
                lowered = mid.lower()
                if any(kw in lowered for kw in non_chat_keywords):
                    continue

            normalized_id, label, provider = LiteLLMRegistry._normalize_proxy_id(mid)
            bare = LiteLLMRegistry._bare_model_name(mid)
            spec = thinking_specs.get(bare) or thinking_specs.get(mid)
            if spec is not None:
                tlevels = get_supported_thinking_levels(spec)
                tdefault = spec.default if spec.default in tlevels else (
                    tlevels[0] if tlevels else "off"
                )
                tmap = dict(spec.thinking_level_map)
            else:
                tlevels = ["off"]
                tdefault = None
                tmap = {}
            out.append(
                LLMModelInfo(
                    id=normalized_id,
                    label=label,
                    provider=provider,
                    supports_thinking=spec is not None and spec.reasoning,
                    thinking_levels=tlevels,
                    default_thinking_level=tdefault,
                    supports_multimodal=mid in multimodal_set,
                    max_context=LiteLLMRegistry._resolve_declared_context(
                        bare, long_ctx_map, info,
                    ),
                    thinking_level_map=tmap,
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

    @staticmethod
    def _bare_model_name(raw_id: str) -> str:
        """剥离 ``litellm_proxy/`` 前缀，返回用于查 long_context 白名单的裸名。"""
        if raw_id.startswith(LiteLLMRegistry.PROXY_MODEL_PREFIX):
            return raw_id[len(LiteLLMRegistry.PROXY_MODEL_PREFIX):]
        return raw_id

    @staticmethod
    def _resolve_declared_context(
        bare: str,
        long_ctx_map: Dict[str, int],
        model_info: Dict[str, Any],
    ) -> Optional[int]:
        """解析模型自身声明的上下文长度：本地声明优先，其次 proxy 上报。

        小于统一上限的模型**不再被剔除**——它们照常出现在选择器里，
        由 ``ModelContextCatalog`` 按 ``min(声明值, max_context_cap)`` 计量。
        """
        declared = long_ctx_map.get(bare)
        if isinstance(declared, int) and declared > 0:
            return declared
        for key in ("max_input_tokens", "max_tokens"):
            v = (model_info or {}).get(key)
            if isinstance(v, int) and v > 0:
                return v
        return None

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
            bare = self._bare_model_name(mid)
            spec = self._thinking_models.get(bare) or self._thinking_models.get(mid)
            if spec is not None:
                tlevels = get_supported_thinking_levels(spec)
                tdefault = spec.default if spec.default in tlevels else (
                    tlevels[0] if tlevels else "off"
                )
                tmap = dict(spec.thinking_level_map)
            else:
                tlevels = ["off"]
                tdefault = None
                tmap = {}
            out.append(
                LLMModelInfo(
                    id=sdk_id,
                    label=label,
                    provider=provider,
                    supports_thinking=spec is not None and spec.reasoning,
                    thinking_levels=tlevels,
                    default_thinking_level=tdefault,
                    supports_multimodal=mid in self._multimodal_models,
                    max_context=self._long_context_map.get(bare),
                    thinking_level_map=tmap,
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
    "ThinkingModelSpec",
    "EXTENDED_THINKING_LEVELS",
    "THINKING_LEVELS_NO_OFF",
    "get_supported_thinking_levels",
    "clamp_thinking_level",
]
