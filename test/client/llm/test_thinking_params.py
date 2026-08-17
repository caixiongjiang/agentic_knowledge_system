#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""LLMClient reasoning_effort 透传与 Thinking Adapter 单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


from src.client.llm.client import _REASONING_UNSET  # 哨兵：模拟「调用方未传」
from src.client.llm.thinking_adapter import (
    AnthropicThinkingAdapter,
    DeepSeekThinkingAdapter,
    DefaultThinkingAdapter,
    GeminiThinkingAdapter,
    GLMThinkingAdapter,
    OpenAIThinkingAdapter,
    QwenThinkingAdapter,
    get_thinking_adapter,
    merge_thinking_params,
)


def _build(model="litellm_proxy/qwen3.7-plus", reasoning_effort=_REASONING_UNSET, cfg_effort=None):
    from src.client.llm.client import LLMClient, LLMClientConfig

    client = LLMClient(
        LLMClientConfig(
            model=model,
            default_reasoning_effort=cfg_effort,
        ),
    )
    params = client._build_params(  # noqa: SLF001
        [{"role": "user", "content": "hi"}],
        reasoning_effort=reasoning_effort,
    )
    return params


def test_call_none_and_cfg_none_sends_nothing() -> None:
    params = _build(reasoning_effort=None, cfg_effort=None)
    assert "reasoning_effort" not in params
    assert "extra_body" not in params
    assert params.get("drop_params") is False


def test_unset_falls_back_to_cfg_default() -> None:
    # 调用方未传 reasoning_effort（哨兵）→ 沿用 cfg.default_reasoning_effort
    params = _build(model="litellm_proxy/qwen3.7-plus", cfg_effort="high")
    assert params.get("reasoning_effort") == "high"
    assert params.get("extra_body", {}).get("enable_thinking") is True
    assert params.get("extra_body", {}).get("thinking_budget") == 8192


def test_explicit_none_is_off_no_fallback() -> None:
    # 显式 None = 不下发，即便 cfg 默认是 "high" 也不回落
    params = _build(reasoning_effort=None, cfg_effort="high")
    assert "reasoning_effort" not in params
    assert "extra_body" not in params


def test_call_overrides_cfg_default() -> None:
    params = _build(model="litellm_proxy/qwen3.7-plus", reasoning_effort="medium", cfg_effort="high")
    assert params.get("reasoning_effort") == "medium"
    assert params.get("extra_body", {}).get("thinking_budget") == 4096


def test_call_none_explicit_off() -> None:
    params = _build(model="litellm_proxy/qwen3.7-plus", reasoning_effort="none", cfg_effort="high")
    assert params.get("reasoning_effort") == "none"
    assert params.get("extra_body", {}).get("enable_thinking") is False


def test_call_native_max_passthrough() -> None:
    # 厂商原生字符串（如 'max'）
    params = _build(model="litellm_proxy/qwen3.7-plus", reasoning_effort="max", cfg_effort=None)
    assert params.get("reasoning_effort") == "max"
    assert params.get("extra_body", {}).get("thinking_budget") == 32768


# ---- 各厂商 Thinking Adapter 专项测试 ----


def test_deepseek_adapter() -> None:
    adapter = get_thinking_adapter("litellm_proxy/deepseek-v4-flash")
    assert isinstance(adapter, DeepSeekThinkingAdapter)

    # off
    res_off = adapter.adapt("deepseek-v4-flash", "off")
    assert res_off["reasoning_effort"] == "none"
    assert res_off["extra_body"]["thinking"]["type"] == "disabled"

    # low -> low
    res_low = adapter.adapt("deepseek-v4-flash", "low")
    assert res_low["reasoning_effort"] == "low"
    assert res_low["extra_body"]["thinking"]["type"] == "enabled"

    # medium -> high
    res_med = adapter.adapt("deepseek-v4-flash", "medium")
    assert res_med["reasoning_effort"] == "high"
    assert res_med["extra_body"]["thinking"]["type"] == "enabled"

    # high -> high
    res_high = adapter.adapt("deepseek-v4-flash", "high")
    assert res_high["reasoning_effort"] == "high"
    assert res_high["extra_body"]["thinking"]["type"] == "enabled"

    # max -> max
    res_max = adapter.adapt("deepseek-v4-flash", "max")
    assert res_max["reasoning_effort"] == "max"
    assert res_max["extra_body"]["thinking"]["type"] == "enabled"


def test_qwen_adapter() -> None:
    adapter = get_thinking_adapter("litellm_proxy/qwen3.7-flash")
    assert isinstance(adapter, QwenThinkingAdapter)

    # 1. Qwen 3.7 / 3.7 测试：通过 extra_body.thinking_budget 控制
    # off
    res_off = adapter.adapt("qwen3.7-flash", "off")
    assert res_off["reasoning_effort"] == "none"
    assert res_off["extra_body"]["enable_thinking"] is False

    # low / medium / high
    res_low = adapter.adapt("qwen3.7-flash", "low")
    assert res_low["reasoning_effort"] == "low"
    assert res_low["extra_body"]["enable_thinking"] is True
    assert res_low["extra_body"]["thinking_budget"] == 2048

    res_high = adapter.adapt("qwen3.7-flash", "high")
    assert res_high["reasoning_effort"] == "high"
    assert res_high["extra_body"]["thinking_budget"] == 8192

    # 2. Qwen 3.8-Max 测试：通过 reasoning_effort (low/medium/xhigh) 控制，严禁下发 thinking_budget
    adapter_38 = get_thinking_adapter("litellm_proxy/qwen3.8-max")
    assert isinstance(adapter_38, QwenThinkingAdapter)

    # off
    res_38_off = adapter_38.adapt("qwen3.8-max", "off")
    assert res_38_off["reasoning_effort"] == "none"
    assert res_38_off["extra_body"]["enable_thinking"] is False
    assert "thinking_budget" not in res_38_off["extra_body"]

    # minimal / low -> low
    res_38_min = adapter_38.adapt("qwen3.8-max", "minimal")
    assert res_38_min["reasoning_effort"] == "low"
    assert res_38_min["extra_body"]["enable_thinking"] is True
    assert "thinking_budget" not in res_38_min["extra_body"]

    res_38_low = adapter_38.adapt("qwen3.8-max", "low")
    assert res_38_low["reasoning_effort"] == "low"
    assert res_38_low["extra_body"]["enable_thinking"] is True
    assert "thinking_budget" not in res_38_low["extra_body"]

    # medium -> medium
    res_38_med = adapter_38.adapt("qwen3.8-max", "medium")
    assert res_38_med["reasoning_effort"] == "medium"
    assert res_38_med["extra_body"]["enable_thinking"] is True
    assert "thinking_budget" not in res_38_med["extra_body"]

    # high / xhigh / max -> xhigh
    res_38_high = adapter_38.adapt("qwen3.8-max", "high")
    assert res_38_high["reasoning_effort"] == "xhigh"
    assert res_38_high["extra_body"]["enable_thinking"] is True
    assert "thinking_budget" not in res_38_high["extra_body"]

    res_38_xhigh = adapter_38.adapt("qwen3.8-max", "xhigh")
    assert res_38_xhigh["reasoning_effort"] == "xhigh"
    assert res_38_xhigh["extra_body"]["enable_thinking"] is True
    assert "thinking_budget" not in res_38_xhigh["extra_body"]

    res_38_max = adapter_38.adapt("qwen3.8-max", "max")
    assert res_38_max["reasoning_effort"] == "xhigh"
    assert res_38_max["extra_body"]["enable_thinking"] is True
    assert "thinking_budget" not in res_38_max["extra_body"]

    # 3. Qwen 3.8-Max-Preview 测试
    res_38_prev = adapter_38.adapt("qwen3.8-max-preview", "xhigh")
    assert res_38_prev["reasoning_effort"] == "xhigh"
    assert "thinking_budget" not in res_38_prev["extra_body"]


def test_glm_adapter() -> None:
    adapter = get_thinking_adapter('litellm_proxy/glm-5.2')
    assert isinstance(adapter, GLMThinkingAdapter)

    # GLM-5.2: off / minimal -> none / disabled
    res_off = adapter.adapt('glm-5.2', 'off')
    assert res_off['reasoning_effort'] == 'none'
    assert res_off['extra_body']['thinking']['type'] == 'disabled'

    res_min = adapter.adapt('glm-5.2', 'minimal')
    assert res_min['reasoning_effort'] == 'none'
    assert res_min['extra_body']['thinking']['type'] == 'disabled'

    # GLM-5.2: low / medium / high -> high / enabled
    res_low = adapter.adapt('glm-5.2', 'low')
    assert res_low['reasoning_effort'] == 'high'
    assert res_low['extra_body']['thinking']['type'] == 'enabled'

    res_med = adapter.adapt('glm-5.2', 'medium')
    assert res_med['reasoning_effort'] == 'high'
    assert res_med['extra_body']['thinking']['type'] == 'enabled'

    res_high = adapter.adapt('glm-5.2', 'high')
    assert res_high['reasoning_effort'] == 'high'
    assert res_high['extra_body']['thinking']['type'] == 'enabled'

    # GLM-5.2: xhigh / max -> max / enabled
    res_xhigh = adapter.adapt('glm-5.2', 'xhigh')
    assert res_xhigh['reasoning_effort'] == 'max'
    assert res_xhigh['extra_body']['thinking']['type'] == 'enabled'

    res_max = adapter.adapt('glm-5.2', 'max')
    assert res_max['reasoning_effort'] == 'max'
    assert res_max['extra_body']['thinking']['type'] == 'enabled'

    # GLM-5.1: off -> disabled, on -> enabled (不发 reasoning_effort)
    adapter_51 = get_thinking_adapter('litellm_proxy/glm-5.1')
    res_51_off = adapter_51.adapt('glm-5.1', 'off')
    assert res_51_off['reasoning_effort'] == 'none'
    assert res_51_off['extra_body']['thinking']['type'] == 'disabled'

    res_51_high = adapter_51.adapt('glm-5.1', 'high')
    assert 'reasoning_effort' not in res_51_high
    assert res_51_high['extra_body']['thinking']['type'] == 'enabled'

    # GLM-5.3: low -> low, medium/high -> high, xhigh/max -> max
    adapter_53 = get_thinking_adapter('litellm_proxy/glm-5.3')
    res_53_low = adapter_53.adapt('glm-5.3', 'low')
    assert res_53_low['reasoning_effort'] == 'low'
    assert res_53_low['extra_body']['thinking']['type'] == 'enabled'

    res_53_high = adapter_53.adapt('glm-5.3', 'high')
    assert res_53_high['reasoning_effort'] == 'high'
    assert res_53_high['extra_body']['thinking']['type'] == 'enabled'

    res_53_max = adapter_53.adapt('glm-5.3', 'max')
    assert res_53_max['reasoning_effort'] == 'max'
    assert res_53_max['extra_body']['thinking']['type'] == 'enabled'



def test_anthropic_adapter() -> None:
    adapter = get_thinking_adapter("claude-3-7-sonnet-20250219")
    assert isinstance(adapter, AnthropicThinkingAdapter)

    # off
    res_off = adapter.adapt("claude-3-7-sonnet", "off")
    assert res_off["thinking"]["type"] == "disabled"

    # medium with max_tokens budget cap
    res_med = adapter.adapt("claude-3-7-sonnet", "medium", max_tokens=2048)
    assert res_med["thinking"]["type"] == "enabled"
    # budget 4096 > max_tokens 2048 -> clamp to 2048 - 256 = 1792
    assert res_med["thinking"]["budget_tokens"] == 1792


def test_gemini_adapter() -> None:
    adapter = get_thinking_adapter("gemini/gemini-2.0-flash-thinking-exp")
    assert isinstance(adapter, GeminiThinkingAdapter)

    # off
    res_off = adapter.adapt("gemini", "off")
    assert res_off["extra_body"]["thinking_config"]["thinking_budget"] == 0

    # high
    res_high = adapter.adapt("gemini", "high")
    assert res_high["extra_body"]["thinking_config"]["thinking_budget"] == 8192


def test_openai_adapter() -> None:
    adapter = get_thinking_adapter("openai/o3-mini")
    assert isinstance(adapter, OpenAIThinkingAdapter)

    res_low = adapter.adapt("o3-mini", "low")
    assert res_low["reasoning_effort"] == "low"

    res_high = adapter.adapt("o3-mini", "max")
    assert res_high["reasoning_effort"] == "high"


def test_merge_thinking_params() -> None:
    target = {
        "model": "test",
        "extra_body": {"custom_flag": True},
    }
    adapted = {
        "reasoning_effort": "high",
        "extra_body": {"enable_thinking": True, "thinking_budget": 4096},
    }
    merge_thinking_params(target, adapted)
    assert target["reasoning_effort"] == "high"
    assert target["extra_body"]["custom_flag"] is True
    assert target["extra_body"]["enable_thinking"] is True
    assert target["extra_body"]["thinking_budget"] == 4096


# ---- Registry 层：off 语义回归 ----


def test_registry_off_respects_map() -> None:
    from src.client.llm.registry import (
        ThinkingModelSpec, LLMModelInfo,
    )

    # 场景1: off:"none" → 透传 "none"（显式关思考，DeepSeek 等默认思考模型需要此值）
    spec = ThinkingModelSpec(reasoning=True, thinking_level_map={
        "off": "none", "minimal": "minimal", "low": "low",
        "medium": "medium", "high": "high",
    })
    info = LLMModelInfo(
        id="x", label="x", provider="x", supports_thinking=True,
        thinking_levels=["off", "minimal", "low", "medium", "high"],
        thinking_level_map=spec.thinking_level_map,
    )
    assert info.resolve_reasoning_effort("off") == "none"
    assert info.resolve_reasoning_effort("medium") == "medium"

    # 场景2: off 缺省 → None（不下发，让模型按默认；适用默认不思考的模型）
    spec2 = ThinkingModelSpec(reasoning=True, thinking_level_map={
        "minimal": "minimal", "medium": "medium", "high": "high",
    })
    info2 = LLMModelInfo(
        id="y", label="y", provider="y", supports_thinking=True,
        thinking_levels=["off", "minimal", "low", "medium", "high"],
        thinking_level_map=spec2.thinking_level_map,
    )
    assert info2.resolve_reasoning_effort("off") is None
    assert info2.resolve_reasoning_effort("low") == "low"  # 缺省 → 透传档位名


def test_registry_off_null_hides_off() -> None:
    from src.client.llm.registry import (
        ThinkingModelSpec, get_supported_thinking_levels, clamp_thinking_level,
    )

    spec = ThinkingModelSpec(reasoning=True, thinking_level_map={
        "off": None, "minimal": "minimal", "low": "low",
        "medium": "medium", "high": "high", "xhigh": "max",
    })
    levels = get_supported_thinking_levels(spec)
    assert "off" not in levels          # off:null → 前端隐藏 off
    assert "xhigh" in levels            # opt-in 显式字符串 → 支持
    # 请求 off 时钳位到最近的可支持档（向上 → minimal）
    assert clamp_thinking_level(spec, "off") == "minimal"


def test_registry_empty_map_defaults_standard_levels() -> None:
    from src.client.llm.registry import (
        ThinkingModelSpec, get_supported_thinking_levels,
    )

    spec = ThinkingModelSpec(reasoning=True, thinking_level_map={})
    levels = get_supported_thinking_levels(spec)
    assert levels == ["off", "minimal", "low", "medium", "high"]


if __name__ == "__main__":
    test_call_none_and_cfg_none_sends_nothing()
    test_unset_falls_back_to_cfg_default()
    test_explicit_none_is_off_no_fallback()
    test_call_overrides_cfg_default()
    test_call_none_explicit_off()
    test_call_native_max_passthrough()
    test_deepseek_adapter()
    test_qwen_adapter()
    test_glm_adapter()
    test_anthropic_adapter()
    test_gemini_adapter()
    test_openai_adapter()
    test_merge_thinking_params()
    test_registry_off_respects_map()
    test_registry_off_null_hides_off()
    test_registry_empty_map_defaults_standard_levels()
    print("✅ All Thinking Adapter & Param tests passed!")
