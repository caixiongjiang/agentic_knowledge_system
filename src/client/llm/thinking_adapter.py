#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : thinking_adapter.py
@Author  : caixiongjiang
@Date    : 2026/05/20
@Function:
    各厂商大模型思考强度（Reasoning / Thinking）参数简易适配器。

    背景与动机：
    - 各大模型厂商（OpenAI、Anthropic、DeepSeek、Qwen、GLM、Gemini 等）对思考链
      控制的参数格式与字段规范各不相同：
      * OpenAI: reasoning_effort ("low" / "medium" / "high")
      * Anthropic: thinking {"type": "enabled", "budget_tokens": int}
      * Qwen (DashScope): extra_body {"enable_thinking": bool, "thinking_budget": int}
      * DeepSeek: reasoning_effort ("none" / "low" / "high" / "max") / extra_body {"thinking": {"type": "enabled" | "disabled"}}
      * GLM (智谱): reasoning_effort / extra_body {"thinking": {"type": "enabled" | "disabled"}}
      * Gemini (Google): extra_body {"thinking_config": {"thinking_budget": int}}
    - 不能完全依赖 LiteLLM Proxy 内部的隐式转换或 drop_params；在客户端组装参数时，
      由专门的思考参数适配器主动生成目标厂商所期望的完整参数字典（包含顶层字段与 extra_body），
      确保多模型在网关及直连模式下均能稳定生效。

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from loguru import logger


# ============================================================
# Token 预算映射表（pi 标准 7 档 -> 整数 tokens 预算）
# ============================================================

DEFAULT_THINKING_BUDGETS: Dict[str, int] = {
    "off": 0,
    "minimal": 1024,
    "low": 2048,
    "medium": 4096,
    "high": 8192,
    "xhigh": 16384,
    "max": 32768,
}


# ============================================================
# 抽象基类
# ============================================================


class BaseThinkingAdapter(ABC):
    """思考强度参数适配器基类"""

    @abstractmethod
    def adapt(
        self,
        model: str,
        level_or_effort: Any,
        *,
        max_tokens: Optional[int] = None,
        spec: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """根据模型与思考档位构建请求参数字典。

        :param model: 模型完整标识（如 "litellm_proxy/qwen3.7-flash" 或 "openai/deepseek-v4-flash"）
        :param level_or_effort: pi 标准档位（off/minimal/low/medium/high/xhigh/max）或 effort 字符串
        :param max_tokens: 本次请求允许的最大输出 tokens
        :param spec: 可选的 ThinkingModelSpec
        :return: 包含适配后参数的字典，供合并入 LLM 请求字典
        """
        pass

    def _normalize_level(self, level_or_effort: Any) -> str:
        """把传入的参数归一化为标准的 7 档字符串标识"""
        if level_or_effort is None:
            return "off"
        val = str(level_or_effort).strip().lower()
        if val in ("none", "off", "false", "0", "disabled"):
            return "off"
        if val in ("minimal", "min"):
            return "minimal"
        if val in ("low",):
            return "low"
        if val in ("medium", "med"):
            return "medium"
        if val in ("high",):
            return "high"
        if val in ("xhigh", "extra_high", "very_high"):
            return "xhigh"
        if val in ("max", "maximum"):
            return "max"
        return val


# ============================================================
# 厂商特定适配器
# ============================================================


class OpenAIThinkingAdapter(BaseThinkingAdapter):
    """OpenAI 系列（o1, o3-mini, o4 等）

    原生参数格式：reasoning_effort ("low" | "medium" | "high")
    注意：OpenAI 原生推理模型不支持完全关闭思考，若请求 off 则归位到 low。
    """

    def adapt(
        self,
        model: str,
        level_or_effort: Any,
        *,
        max_tokens: Optional[int] = None,
        spec: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        level = self._normalize_level(level_or_effort)
        if level in ("off", "minimal", "low"):
            effort = "low"
        elif level == "medium":
            effort = "medium"
        else:
            effort = "high"
        return {"reasoning_effort": effort}


class DeepSeekThinkingAdapter(BaseThinkingAdapter):
    """DeepSeek 系列（DeepSeek-R1 / V3 / V4 / 官方及各平台部署）

    官方规范（OpenAI SDK / Chat Completion）:
    - 思考开关：extra_body: {"thinking": {"type": "enabled" | "disabled"}}
    - 思考强度：reasoning_effort ("low" | "high" | "max")
      映射规则（deepseek-v4-flash 与 deepseek-v4-pro 一致）:
        low    -> low
        medium -> high
        high   -> high
        xhigh  -> high
        max    -> max
    - off 档位：
        reasoning_effort="none", extra_body={"thinking": {"type": "disabled"}}
    """

    def adapt(
        self,
        model: str,
        level_or_effort: Any,
        *,
        max_tokens: Optional[int] = None,
        spec: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        level = self._normalize_level(level_or_effort)
        extra_body = self._deepseek_extra_body(model, enabled=level != "off")
        if level == "off":
            return {
                "reasoning_effort": "none",
                "extra_body": extra_body,
            }

        # 官方映射表：low -> low; medium/high/xhigh -> high; max -> max; minimal -> low
        effort_map = {
            "minimal": "low",
            "low": "low",
            "medium": "high",
            "high": "high",
            "xhigh": "high",
            "max": "max",
        }
        effort = effort_map.get(level, "high")

        return {
            "reasoning_effort": effort,
            "extra_body": extra_body,
        }

    @staticmethod
    def _is_dashscope_route(model: str) -> bool:
        name = (model or "").lower()
        return any(tok in name for tok in ("ali-", "alibaba", "dashscope"))

    @classmethod
    def _deepseek_extra_body(cls, model: str, *, enabled: bool) -> Dict[str, Any]:
        extra: Dict[str, Any] = {
            "thinking": {"type": "enabled" if enabled else "disabled"},
        }
        # 阿里云 DashScope 兼容口默认关思考，只认 enable_thinking；
        # 仅发 thinking.type 时开关/强度在 Model Lake 上不会生效。
        if cls._is_dashscope_route(model):
            extra["enable_thinking"] = enabled
        return extra



class QwenThinkingAdapter(BaseThinkingAdapter):
    """阿里通义千问系列（Qwen3.8-Max, Qwen3.7, Qwen3.7 等）

    官方规范与差异：
    1. Qwen3.8-Max / Qwen3.8-Max-Preview（及 3.8 系列）：
       - 采用 reasoning_effort 控制思考强度，可选值：low、medium、xhigh（默认 xhigh）
       - 严禁与 thinking_budget 同时设置（同时设置会报错）
       - 档位映射：
         * off: reasoning_effort="none", extra_body={"enable_thinking": False}
         * minimal / low: reasoning_effort="low", extra_body={"enable_thinking": True}
         * medium: reasoning_effort="medium", extra_body={"enable_thinking": True}
         * high / xhigh / max: reasoning_effort="xhigh", extra_body={"enable_thinking": True}
    2. Qwen3.7 / Qwen3.5 / Qwen3-VL / Qwen3 及 QwQ 等非 3.8 模型：
       - 只支持思考开关，不支持强度；禁止下发 thinking_budget / reasoning_effort 档位
       - off: reasoning_effort="none", extra_body={"enable_thinking": False}
       - on:  extra_body={"enable_thinking": True}
    """

    def adapt(
        self,
        model: str,
        level_or_effort: Any,
        *,
        max_tokens: Optional[int] = None,
        spec: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        level = self._normalize_level(level_or_effort)
        bare_model = (model or "").lower().strip()
        for prefix in ("litellm_proxy/", "openai/"):
            if bare_model.startswith(prefix):
                bare_model = bare_model[len(prefix):]
        if "/" in bare_model:
            bare_model = bare_model.split("/", 1)[1]

        # 判断是否为 Qwen 3.8 系列（如 qwen3.8-max, qwen3.8-max-preview 等）
        is_qwen_38 = "3.8" in bare_model or "qwen3.8" in bare_model or "qwen-3.8" in bare_model

        if is_qwen_38:
            # Qwen 3.8 系列：仅支持 reasoning_effort (low/medium/xhigh)，严禁下发 thinking_budget
            if level == "off":
                return {
                    "reasoning_effort": "none",
                    "extra_body": {
                        "enable_thinking": False,
                        "thinking": {"type": "disabled"},
                    },
                }

            effort_map_38 = {
                "minimal": "low",
                "low": "low",
                "medium": "medium",
                "high": "xhigh",
                "xhigh": "xhigh",
                "max": "xhigh",
            }
            effort = effort_map_38.get(level, "xhigh")
            return {
                "reasoning_effort": effort,
                "extra_body": {
                    "enable_thinking": True,
                    "thinking": {"type": "enabled"},
                },
            }

        # Qwen 3.7 及其他非 3.8 模型：支持 thinking 开关与网关透传
        if level == "off":
            return {
                "reasoning_effort": "none",
                "extra_body": {
                    "enable_thinking": False,
                    "thinking": {"type": "disabled"},
                },
            }

        return {
            "extra_body": {
                "enable_thinking": True,
                "thinking": {"type": "enabled"},
            },
        }


class GLMThinkingAdapter(BaseThinkingAdapter):
    """智谱 GLM 系列（GLM-5.2, GLM-5.1, GLM-4.7, GLM-5.3 等）

    官方规范：
    1. thinking.type 控制深度思考模式：
       - enabled（默认）：启用动态思考（GLM-5.2, GLM-5.1, GLM-5, GLM-5-Turbo, GLM-5v-Turbo, GLM-4.6, GLM-4.6V, GLM-4.5
         为模型自动判断是否思考；GLM-5.3, GLM-4.7, GLM-4.5V 为强制思考）
       - disabled：禁用思考，直接给出回答
    2. reasoning_effort 控制开启思维链下的推理程度（仅 GLM-5.2 及以上支持）：
       - GLM-5.2:
         * 支持 max（默认且推荐，深度推理）、xhigh、high（增强推理）、medium、low、minimal、none
         * none 或 minimal 代表模型放弃思考 -> reasoning_effort="none", extra_body={"thinking": {"type": "disabled"}}
         * low / medium 映射为 high -> reasoning_effort="high", extra_body={"thinking": {"type": "enabled"}}
         * high -> reasoning_effort="high", extra_body={"thinking": {"type": "enabled"}}
         * xhigh 映射为 max -> reasoning_effort="max", extra_body={"thinking": {"type": "enabled"}}
         * max（默认且推荐）-> reasoning_effort="max", extra_body={"thinking": {"type": "enabled"}}
       - GLM-5.3:
         * 仅支持 max、high、low，其余输入将报错
         * low -> reasoning_effort="low", extra_body={"thinking": {"type": "enabled"}}
         * medium / high -> reasoning_effort="high", extra_body={"thinking": {"type": "enabled"}}
         * xhigh / max -> reasoning_effort="max", extra_body={"thinking": {"type": "enabled"}}
       - GLM-5.1 及以下版本（GLM-5.1, GLM-4.7 等）：
         * 不支持 reasoning_effort 档位细分
         * off: reasoning_effort="none", extra_body={"thinking": {"type": "disabled"}}
         * on:  extra_body={"thinking": {"type": "enabled"}}
    """

    def adapt(
        self,
        model: str,
        level_or_effort: Any,
        *,
        max_tokens: Optional[int] = None,
        spec: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        level = self._normalize_level(level_or_effort)
        bare = (model or "").lower().strip()
        for prefix in ("litellm_proxy/", "openai/"):
            if bare.startswith(prefix):
                bare = bare[len(prefix):]
        if "/" in bare:
            bare = bare.split("/", 1)[1]

        # 1. GLM-5.3 规则（仅支持 max, high, low）
        if "glm-5.3" in bare or "glm-53" in bare or "5.3" in bare:
            if level in ("off", "minimal"):
                return {
                    "reasoning_effort": "low",
                    "extra_body": {
                        "thinking": {"type": "disabled"},
                    },
                }
            effort_map = {
                "low": "low",
                "medium": "high",
                "high": "high",
                "xhigh": "max",
                "max": "max",
            }
            effort = effort_map.get(level, "high")
            return {
                "reasoning_effort": effort,
                "extra_body": {
                    "thinking": {"type": "enabled"},
                },
            }

        # 2. GLM-5.2 规则（支持 none/minimal, low/medium->high, high->high, xhigh/max->max）
        if "glm-5.2" in bare or "glm-52" in bare or "5.2" in bare:
            if level in ("off", "minimal"):
                return {
                    "reasoning_effort": "none",
                    "extra_body": {
                        "thinking": {"type": "disabled"},
                    },
                }
            effort_map = {
                "low": "high",
                "medium": "high",
                "high": "high",
                "xhigh": "max",
                "max": "max",
            }
            effort = effort_map.get(level, "high")
            return {
                "reasoning_effort": effort,
                "extra_body": {
                    "thinking": {"type": "enabled"},
                },
            }

        # 3. GLM-5.1 及其他 GLM 早期模型（仅支持 thinking.type 开关，不支持 reasoning_effort 档位）
        if level == "off":
            return {
                "reasoning_effort": "none",
                "extra_body": {
                    "thinking": {"type": "disabled"},
                },
            }

        return {
            "extra_body": {
                "thinking": {"type": "enabled"},
            },
        }




class MiMoThinkingAdapter(BaseThinkingAdapter):
    """小米 MiMo 系列（mimo-v2.5 / mimo-v2.5-pro）

    只支持思考开关，不支持强度：
    - off: reasoning_effort="none", extra_body={"thinking": {"type": "disabled"}}
    - on:  extra_body={"thinking": {"type": "enabled"}}
    官方把 reasoning_effort 除 none 以外的合法值都当成「开思考」，不下发强度档。
    """

    def adapt(
        self,
        model: str,
        level_or_effort: Any,
        *,
        max_tokens: Optional[int] = None,
        spec: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        level = self._normalize_level(level_or_effort)
        if level == "off":
            return {
                "reasoning_effort": "none",
                "extra_body": {
                    "thinking": {"type": "disabled"},
                },
            }
        return {
            "extra_body": {
                "thinking": {"type": "enabled"},
            },
        }


class AnthropicThinkingAdapter(BaseThinkingAdapter):
    """Anthropic Claude 系列（Claude 3.7 Sonnet 等 Extended Thinking）

    参数规范：
    - off: {"thinking": {"type": "disabled"}}
    - on:  {"thinking": {"type": "enabled", "budget_tokens": N}} (最小 1024)
    """

    def adapt(
        self,
        model: str,
        level_or_effort: Any,
        *,
        max_tokens: Optional[int] = None,
        spec: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        level = self._normalize_level(level_or_effort)
        if level == "off":
            return {
                "thinking": {"type": "disabled"},
                "extra_body": {"thinking": {"type": "disabled"}},
            }

        anthropic_budgets = {
            "minimal": 1024,
            "low": 2048,
            "medium": 4096,
            "high": 16384,
            "xhigh": 32768,
            "max": 65536,
        }
        budget = anthropic_budgets.get(level, 4096)
        if max_tokens and max_tokens > 1024 and budget >= max_tokens:
            budget = max(1024, max_tokens - 256)

        thinking_payload = {
            "type": "enabled",
            "budget_tokens": budget,
        }
        return {
            "thinking": thinking_payload,
            "extra_body": {"thinking": thinking_payload},
        }


class GeminiThinkingAdapter(BaseThinkingAdapter):
    """Google Gemini 系列（Gemini 2.0 Flash Thinking / 2.5 等）

    参数规范：
    - off: extra_body: {"thinking_config": {"thinking_budget": 0}}
    - on:  extra_body: {"thinking_config": {"thinking_budget": N}}
    """

    def adapt(
        self,
        model: str,
        level_or_effort: Any,
        *,
        max_tokens: Optional[int] = None,
        spec: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        level = self._normalize_level(level_or_effort)
        if level == "off":
            return {
                "extra_body": {
                    "thinking_config": {"thinking_budget": 0},
                },
            }

        gemini_budgets = {
            "minimal": 1024,
            "low": 2048,
            "medium": 4096,
            "high": 8192,
            "xhigh": 16384,
            "max": 32768,
        }
        budget = gemini_budgets.get(level, 4096)
        return {
            "extra_body": {
                "thinking_config": {"thinking_budget": budget},
            },
        }


class DefaultThinkingAdapter(BaseThinkingAdapter):
    """通用兜底适配器

    优先使用 ThinkingModelSpec 中的声明进行翻译；若无声明则透传 reasoning_effort。
    """

    def adapt(
        self,
        model: str,
        level_or_effort: Any,
        *,
        max_tokens: Optional[int] = None,
        spec: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        level = self._normalize_level(level_or_effort)
        if spec is not None and hasattr(spec, "resolve_reasoning_effort"):
            effort = spec.resolve_reasoning_effort(level)
            if effort is not None:
                return {"reasoning_effort": effort}
            return {}

        if level == "off":
            return {"reasoning_effort": "none"}
        return {"reasoning_effort": level}


# ============================================================
# 适配器工厂与注册
# ============================================================


def get_thinking_adapter(model: str) -> BaseThinkingAdapter:
    """根据模型标识获取对应的思考参数适配器。

    匹配规则（不区分大小写，去除网关及 provider 前缀后的裸模型名）：
    - 包含 'deepseek' -> DeepSeekThinkingAdapter
    - 包含 'qwen' 或 'qwq' -> QwenThinkingAdapter
    - 包含 'glm' 或 'chatglm' -> GLMThinkingAdapter
    - 包含 'mimo' -> MiMoThinkingAdapter
    - 包含 'claude' 或 'anthropic' -> AnthropicThinkingAdapter
    - 包含 'gemini' -> GeminiThinkingAdapter
    - 以 'o1' / 'o3' / 'o4' / 'gpt' 开头或包含 'openai' -> OpenAIThinkingAdapter
    - 其余 -> DefaultThinkingAdapter
    """
    bare_name = (model or "").lower().strip()
    for prefix in ("litellm_proxy/", "openai/"):
        if bare_name.startswith(prefix):
            bare_name = bare_name[len(prefix):]
    if "/" in bare_name:
        bare_name = bare_name.split("/", 1)[1]

    if "deepseek" in bare_name:
        return DeepSeekThinkingAdapter()
    if "qwen" in bare_name or "qwq" in bare_name:
        return QwenThinkingAdapter()
    if "glm" in bare_name or "chatglm" in bare_name:
        return GLMThinkingAdapter()
    if "mimo" in bare_name:
        return MiMoThinkingAdapter()
    if "claude" in bare_name or "anthropic" in bare_name:
        return AnthropicThinkingAdapter()
    if "gemini" in bare_name:
        return GeminiThinkingAdapter()
    if bare_name.startswith(("o1", "o3", "o4", "gpt")) or "openai" in bare_name:
        return OpenAIThinkingAdapter()

    return DefaultThinkingAdapter()


def merge_thinking_params(
    target_params: Dict[str, Any],
    adapted_params: Dict[str, Any],
) -> None:
    """把适配器构建出的思考参数安全地合并进目标请求字典中。

    - 普通字段直接赋值或覆盖；
    - `extra_body` 执行子字典递归更新，不丢弃原有的其他 extra 字段；
    - 兼容 LiteLLM Proxy / OpenAI SDK：OpenAI Python SDK 在发起 HTTP 请求时，
      会将 `extra_body` 中的字段拍平解包至 HTTP JSON 根层级。对于 LiteLLM Proxy 网关，
      网关需要请求体中显式包含 `extra_body: {...}` 才能将其完整转发给上游模型提供商。
      因此在 `target_params["extra_body"]` 内同步维护嵌套的 `extra_body`，
      使得经 SDK 拍平后发送给网关的 HTTP 请求中依然带有 `extra_body` 字典。
    """
    for key, val in adapted_params.items():
        if key == "extra_body" and isinstance(val, dict):
            if "extra_body" not in target_params or not isinstance(
                target_params["extra_body"], dict
            ):
                target_params["extra_body"] = {}
            target_params["extra_body"].update(val)
            # 同步填充嵌套 extra_body，确保 LiteLLM Proxy 网关透传有效
            if "extra_body" not in target_params["extra_body"] or not isinstance(
                target_params["extra_body"]["extra_body"], dict
            ):
                target_params["extra_body"]["extra_body"] = {}
            target_params["extra_body"]["extra_body"].update(val)
        else:
            target_params[key] = val
