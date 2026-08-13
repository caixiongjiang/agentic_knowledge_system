#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""ModelContextCatalog ── 模型上下文真相源

解析顺序（max_context / max_output）
--------------------------------
1. ``config/long_context_models.json``（显式声明，最高优先）
2. LiteLLM Proxy ``/v1/model/info`` 上报值（经 LiteLLMRegistry 缓存，不触发网络）
3. LiteLLM SDK ``get_model_info`` 的 max_input_tokens / max_output_tokens（若可得）
4. 默认值 DEFAULT_MAX_CONTEXT / DEFAULT_MAX_OUTPUT

统一上限
--------
实际参与预算的窗口是 ``min(模型声明值, max_context_cap)``：
声明值更大的模型按统一上限封顶，**声明值更小的模型按自己的上限**（不会被抬高）。

tokenizer 映射
--------------
``config/tokenizer_map.json``：proxy alias → LiteLLM 可识别 tokenizer 名。
未命中则返回原 model（调用方走 heuristic）。
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loguru import logger

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_LONG_CONTEXT_PATH = _PROJECT_ROOT / "config" / "long_context_models.json"
_TOKENIZER_MAP_PATH = _PROJECT_ROOT / "config" / "tokenizer_map.json"

DEFAULT_MAX_CONTEXT = 200_000
DEFAULT_MAX_OUTPUT = 8192
PROXY_PREFIX = "litellm_proxy/"

UNIFIED_MAX_CONTEXT_CAP = 200_000
"""统一上下文上限（Cursor 式）：参与预算的窗口取 ``min(模型声明值, 本上限)``。

- 声明值 > 上限（如 1M 模型）→ 按 200K 计量；
- 声明值 < 上限（如 128K 模型）→ 按其自身的 128K 计量，不会被抬高到 200K。

配置项 ``[chat.context] max_context_cap``；设为 0 关闭封顶、完全按模型声明值。"""


@dataclass(frozen=True)
class ModelContextSpec:
    """单个模型的上下文规格。"""

    bare_name: str
    max_context: int
    """实际参与预算的上下文长度（已应用统一上限）"""
    max_output: int
    tokenizer_model: Optional[str]
    """LiteLLM token_counter 可用的模型名；None 表示应走 heuristic。"""
    source: str
    """max_context 来源：config / proxy / litellm / default"""
    declared_max_context: int = 0
    """模型声明的原始上下文长度（未封顶）"""
    capped: bool = False
    """``max_context`` 是否被统一上限截断"""


class ModelContextCatalog:
    """进程内模型上下文目录（线程安全只读缓存）。"""

    def __init__(
        self,
        *,
        long_context_path: Optional[Path] = None,
        tokenizer_map_path: Optional[Path] = None,
        default_max_context: int = DEFAULT_MAX_CONTEXT,
        default_max_output: int = DEFAULT_MAX_OUTPUT,
        max_context_cap: Optional[int] = None,
    ) -> None:
        self._long_context_path = long_context_path or _LONG_CONTEXT_PATH
        self._tokenizer_map_path = tokenizer_map_path or _TOKENIZER_MAP_PATH
        self._default_max_context = int(default_max_context)
        self._default_max_output = int(default_max_output)
        self._cap_override = max_context_cap
        self._max_context_cap = UNIFIED_MAX_CONTEXT_CAP
        self._lock = threading.Lock()
        self._config_specs: Dict[str, Tuple[int, Optional[int]]] = {}
        self._tokenizer_map: Dict[str, str] = {}
        self._warned_unknown: set[str] = set()
        self._loaded = False

    def reload(self) -> None:
        """强制重载配置文件。"""
        with self._lock:
            self._config_specs = self._load_long_context_file()
            self._tokenizer_map = self._load_tokenizer_map()
            self._max_context_cap = (
                int(self._cap_override)
                if self._cap_override is not None
                else self._load_max_context_cap()
            )
            self._loaded = True

    @property
    def max_context_cap(self) -> int:
        """当前生效的统一上下文上限；0 表示未封顶。"""
        self._ensure_loaded()
        return self._max_context_cap

    @staticmethod
    def _load_max_context_cap() -> int:
        """从 ``[chat.context] max_context_cap`` 读统一上限；异常时回落常量。"""
        try:
            from src.utils.config_manager import get_config_manager

            raw = get_config_manager().get(
                "chat.context.max_context_cap", UNIFIED_MAX_CONTEXT_CAP,
            )
            cap = int(raw)
            return cap if cap > 0 else 0
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ModelContextCatalog] 读取 max_context_cap 失败: {e}")
            return UNIFIED_MAX_CONTEXT_CAP

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.reload()

    @staticmethod
    def bare_name(model: str) -> str:
        raw = (model or "").strip()
        if raw.startswith(PROXY_PREFIX):
            return raw[len(PROXY_PREFIX):]
        # 兼容 openai/xxx 这类带 provider 前缀的离线名：取最后一段作别名查找
        return raw

    def resolve(self, model: str) -> ModelContextSpec:
        """解析模型的 max_context / max_output / tokenizer。"""
        self._ensure_loaded()
        bare = self.bare_name(model)
        max_context: Optional[int] = None
        max_output: Optional[int] = None
        source = "default"

        cfg = self._config_specs.get(bare)
        if cfg is not None:
            max_context, max_output = cfg[0], cfg[1]
            source = "config"
        else:
            proxy_ctx = self._try_proxy_limits(bare)
            if proxy_ctx is not None:
                max_context = proxy_ctx
                source = "proxy"
            else:
                litellm_ctx, litellm_out = self._try_litellm_limits(bare, model)
                if litellm_ctx is not None:
                    max_context = litellm_ctx
                    source = "litellm"
                if litellm_out is not None and max_output is None:
                    max_output = litellm_out

        if max_context is None or max_context <= 0:
            max_context = self._default_max_context
            if source == "default" and bare not in self._warned_unknown:
                self._warned_unknown.add(bare)
                logger.warning(
                    f"[ModelContextCatalog] 未知模型 {bare!r}（本地未声明、proxy 未上报），"
                    f"使用默认 max_context={max_context}；"
                    f"若该模型窗口更小，请在 config/long_context_models.json 中声明"
                )
            source = "default" if source != "config" else source

        if max_output is None or max_output <= 0:
            max_output = self._default_max_output

        # 统一上限（Cursor 式）：max_context = min(声明值, cap)。
        # 声明值小于 cap 的模型保留自身上限，不会被抬高到 cap。
        declared = int(max_context)
        cap = self._max_context_cap
        capped = cap > 0 and declared > cap
        max_context = min(declared, cap) if cap > 0 else declared

        tokenizer_model = self._tokenizer_map.get(bare)
        return ModelContextSpec(
            bare_name=bare,
            max_context=int(max_context),
            max_output=int(max_output),
            tokenizer_model=tokenizer_model,
            source=source,
            declared_max_context=declared,
            capped=capped,
        )

    def resolve_tokenizer_model(self, model: str) -> Optional[str]:
        """返回 token_counter 应用的模型名；未映射返回 None。"""
        self._ensure_loaded()
        return self._tokenizer_map.get(self.bare_name(model))

    def max_context_map(self) -> Dict[str, int]:
        """供 registry 过滤复用：bare_name → max_context。"""
        self._ensure_loaded()
        return {k: v[0] for k, v in self._config_specs.items()}

    def _load_long_context_file(self) -> Dict[str, Tuple[int, Optional[int]]]:
        path = self._long_context_path
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("models") or {}
            result: Dict[str, Tuple[int, Optional[int]]] = {}
            for k, v in raw.items():
                if not isinstance(k, str) or not k.strip():
                    continue
                name = k.strip()
                if isinstance(v, int) and v > 0:
                    result[name] = (v, None)
                elif isinstance(v, dict):
                    mc = v.get("max_context")
                    mo = v.get("max_output")
                    if isinstance(mc, int) and mc > 0:
                        mo_val = mo if isinstance(mo, int) and mo > 0 else None
                        result[name] = (mc, mo_val)
            logger.debug(
                f"[ModelContextCatalog] 加载 long_context: {len(result)} 个模型"
            )
            return result
        except FileNotFoundError:
            logger.debug(f"[ModelContextCatalog] long_context 文件不存在: {path}")
            return {}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ModelContextCatalog] 加载 long_context 失败: {e}")
            return {}

    def _load_tokenizer_map(self) -> Dict[str, str]:
        path = self._tokenizer_map_path
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("map") or {}
            result = {
                str(k).strip(): str(v).strip()
                for k, v in raw.items()
                if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip()
            }
            logger.debug(
                f"[ModelContextCatalog] 加载 tokenizer_map: {len(result)} 条"
            )
            return result
        except FileNotFoundError:
            logger.debug(f"[ModelContextCatalog] tokenizer_map 不存在: {path}")
            return {}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ModelContextCatalog] 加载 tokenizer_map 失败: {e}")
            return {}

    @staticmethod
    def _try_proxy_limits(bare: str) -> Optional[int]:
        """从 LiteLLMRegistry 的**已有缓存**取 proxy 上报的上下文长度。

        registry 的缓存由 ``GET /api/chat/models`` 填充；这里只读不拉，
        缓存为空时返回 None 交给下一级兜底，绝不在对话链路上引入 HTTP 往返。
        """
        try:
            from src.client.llm.registry import get_litellm_registry

            return get_litellm_registry().peek_max_context(bare)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[ModelContextCatalog] peek proxy limits 失败: {e}")
            return None

    @staticmethod
    def _try_litellm_limits(
        bare: str, raw_model: str
    ) -> Tuple[Optional[int], Optional[int]]:
        """尽力从 litellm 模型信息拿 max_input / max_output；失败返回 (None, None)。"""
        try:
            import litellm

            # litellm.get_model_info 对 proxy alias 通常失败，这里仅作次优兜底
            for candidate in (bare, raw_model):
                try:
                    info = litellm.get_model_info(candidate)  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(info, dict):
                    continue
                mc = info.get("max_input_tokens") or info.get("max_tokens")
                mo = info.get("max_output_tokens")
                mc_i = int(mc) if isinstance(mc, int) and mc > 0 else None
                mo_i = int(mo) if isinstance(mo, int) and mo > 0 else None
                if mc_i or mo_i:
                    return mc_i, mo_i
        except Exception:  # noqa: BLE001
            pass
        return None, None


_catalog_singleton: Optional[ModelContextCatalog] = None
_catalog_lock = threading.Lock()


def get_model_context_catalog() -> ModelContextCatalog:
    global _catalog_singleton
    if _catalog_singleton is None:
        with _catalog_lock:
            if _catalog_singleton is None:
                _catalog_singleton = ModelContextCatalog()
    return _catalog_singleton


__all__ = [
    "DEFAULT_MAX_CONTEXT",
    "DEFAULT_MAX_OUTPUT",
    "UNIFIED_MAX_CONTEXT_CAP",
    "ModelContextCatalog",
    "ModelContextSpec",
    "get_model_context_catalog",
]
