#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""LLMClient thinking → reasoning_effort 映射单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def _build(thinking_budget=None, cfg_budget=0):
    from src.client.llm.client import LLMClient, LLMClientConfig

    client = LLMClient(
        LLMClientConfig(
            model="litellm_proxy/qwen3.7-plus",
            thinking_budget=cfg_budget,
        ),
    )
    params = client._build_params(  # noqa: SLF001
        [{"role": "user", "content": "hi"}],
        thinking_budget=thinking_budget,
    )
    return params


def test_off_does_not_send_extra_body_thinking() -> None:
    params = _build(thinking_budget=0)
    extra_body = params.get("extra_body") or {}
    assert "thinking" not in extra_body
    assert params.get("reasoning_effort") == "none"
    assert params.get("drop_params") is True


def test_on_maps_budget_to_reasoning_effort() -> None:
    params = _build(thinking_budget=4096)
    assert params.get("reasoning_effort") == "high"
    extra_body = params.get("extra_body") or {}
    assert "thinking" not in extra_body


def test_none_with_zero_cfg_sends_nothing() -> None:
    params = _build(thinking_budget=None, cfg_budget=0)
    assert "reasoning_effort" not in params
    extra_body = params.get("extra_body") or {}
    assert "thinking" not in extra_body


def test_none_with_cfg_budget_uses_preset() -> None:
    params = _build(thinking_budget=None, cfg_budget=2048)
    assert params.get("reasoning_effort") == "medium"


def test_budget_to_effort_helper() -> None:
    from src.client.llm.client import _budget_to_reasoning_effort

    assert _budget_to_reasoning_effort(512) == "low"
    assert _budget_to_reasoning_effort(2048) == "medium"
    assert _budget_to_reasoning_effort(8192) == "high"


if __name__ == "__main__":
    test_off_does_not_send_extra_body_thinking()
    test_on_maps_budget_to_reasoning_effort()
    test_none_with_zero_cfg_sends_nothing()
    test_none_with_cfg_budget_uses_preset()
    test_budget_to_effort_helper()
    print("✅ test_thinking_params passed")
