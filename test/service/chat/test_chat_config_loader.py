#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_chat_config_loader.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Phase 5 单元测试：

    1. ``ChatServiceConfig.from_config_manager()`` 正确读取 toml ``[chat]`` 节，
       并对各字段做类型规范化（``max_completion_tokens=0 → None``）；
       缺失字段沿用类默认值；ConfigManager 异常时退化为全部默认。
    2. ``ChatService._get_llm_client(preset)`` 直接调用
       ``create_llm_client_from_preset``，按 preset 名缓存，**不再读 components.json**
       （后者只服务于 RAG 抽取 Pipeline 的 Kafka Worker）。

    运行::
        uv run python test/service/chat/test_chat_config_loader.py

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Any, Dict

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.service.chat.chat_service import ChatService, ChatServiceConfig  # noqa: E402


def _hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


# ============================================================
# Fakes
# ============================================================


class _FakeConfigManager:
    """伪 ConfigManager.get_section()"""

    def __init__(self, sections: Dict[str, Dict[str, Any]]) -> None:
        self.sections = sections

    def get_section(self, section: str) -> Dict[str, Any]:
        return dict(self.sections.get(section, {}))


class _RaisingConfigManager:
    """get_section 总是抛异常"""

    def get_section(self, section: str) -> Dict[str, Any]:
        raise RuntimeError("boom")


class _FakeClient:
    def __init__(self, model: str) -> None:
        self.model = model


# ============================================================
# from_config_manager 用例
# ============================================================


def test_from_config_manager_full_load() -> bool:
    _hr("ChatServiceConfig.from_config_manager · 完整 toml 节加载")
    mgr = _FakeConfigManager({
        "chat": {
            "agent_model_preset": "smart",
            "title_model_preset": "quality",
            "default_agent_mode": False,
            "default_enable_thinking": True,
            "default_max_tool_rounds": 8,
            "thinking_budget": 8192,
            "max_completion_tokens": 1024,
            "retrieval": {"top_k": 16, "enable_validation": True},
            "history": {
                "max_messages": 60,
                "max_turns": 20,
                "max_tokens": 12000,
                "summary_compress_threshold_turns": 25,
                "summary_keep_recent_turns": 6,
            },
        }
    })
    cfg = ChatServiceConfig.from_config_manager(mgr)
    assert cfg.agent_model_preset == "smart"
    assert cfg.title_model_preset == "quality"
    assert cfg.default_agent_mode is False
    assert cfg.default_enable_thinking is True
    assert cfg.default_max_tool_rounds == 8
    assert cfg.thinking_budget == 8192
    assert cfg.max_completion_tokens == 1024
    assert cfg.retrieve_top_k == 16
    assert cfg.enable_validation_for_chat is True
    assert cfg.max_history_messages == 60
    assert cfg.max_history_turns == 20
    assert cfg.max_context_tokens == 12000
    assert cfg.summary_compress_threshold_turns == 25
    assert cfg.summary_keep_recent_turns == 6
    _ok("所有字段读取 + 类型转换正确")
    return True


def test_from_config_manager_missing_fields_use_defaults() -> bool:
    _hr("ChatServiceConfig.from_config_manager · 缺字段沿用默认")
    mgr = _FakeConfigManager({"chat": {"thinking_budget": 2048}})
    cfg = ChatServiceConfig.from_config_manager(mgr)
    default = ChatServiceConfig()
    assert cfg.thinking_budget == 2048
    assert cfg.retrieve_top_k == default.retrieve_top_k
    assert cfg.max_context_tokens == default.max_context_tokens
    assert cfg.agent_model_preset == default.agent_model_preset
    assert cfg.title_model_preset == default.title_model_preset
    _ok("仅指定 thinking_budget；其余沿用默认")
    return True


def test_from_config_manager_zero_completion_tokens_to_none() -> bool:
    _hr("ChatServiceConfig.from_config_manager · max_completion_tokens=0 → None")
    mgr = _FakeConfigManager({"chat": {"max_completion_tokens": 0}})
    cfg = ChatServiceConfig.from_config_manager(mgr)
    assert cfg.max_completion_tokens is None, (
        f"期望 None，实际 {cfg.max_completion_tokens!r}"
    )
    _ok("0 / 缺省 → None，让模型自决")
    return True


def test_from_config_manager_empty_section_returns_defaults() -> bool:
    _hr("ChatServiceConfig.from_config_manager · 空 [chat] 节")
    mgr = _FakeConfigManager({})
    cfg = ChatServiceConfig.from_config_manager(mgr)
    default = ChatServiceConfig()
    assert cfg.retrieve_top_k == default.retrieve_top_k
    assert cfg.thinking_budget == default.thinking_budget
    assert cfg.agent_model_preset == default.agent_model_preset
    assert cfg.title_model_preset == default.title_model_preset
    _ok("空节 → 全部默认值")
    return True


def test_from_config_manager_exception_safety() -> bool:
    _hr("ChatServiceConfig.from_config_manager · 异常安全")
    cfg = ChatServiceConfig.from_config_manager(_RaisingConfigManager())
    default = ChatServiceConfig()
    assert cfg.retrieve_top_k == default.retrieve_top_k
    assert cfg.agent_model_preset == default.agent_model_preset
    _ok("ConfigManager 抛错时返回类默认值")
    return True


def test_from_config_manager_independent_presets() -> bool:
    _hr("ChatServiceConfig · agent / title preset 互相独立")
    mgr = _FakeConfigManager({
        "chat": {
            "agent_model_preset": "reasoning",
            # 不指定 title_model_preset，应保持类默认 "fast"
        }
    })
    cfg = ChatServiceConfig.from_config_manager(mgr)
    assert cfg.agent_model_preset == "reasoning"
    assert cfg.title_model_preset == "fast"
    _ok("agent=reasoning, title=fast 互不影响")
    return True


# ============================================================
# _get_llm_client 用例
# ============================================================


def test_get_llm_client_direct_preset() -> bool:
    _hr("ChatService._get_llm_client · 直接走 preset，不读 components.json")
    svc = ChatService(config=ChatServiceConfig())
    svc._client_cache.clear()

    import src.client.llm as llm_pkg

    captured: Dict[str, int] = {"calls": 0, "last_preset": None}
    fake = _FakeClient(model="fake/m")

    def _patched(name: str):
        captured["calls"] += 1
        captured["last_preset"] = name
        return fake

    orig = llm_pkg.create_llm_client_from_preset
    llm_pkg.create_llm_client_from_preset = _patched  # type: ignore

    try:
        client = svc._get_llm_client("fast")
        assert client is fake, "应当直接返回 preset client"
        assert captured["calls"] == 1
        assert captured["last_preset"] == "fast"
        _ok("preset=fast → create_llm_client_from_preset 被调一次")

        # 再请求同 preset，走缓存
        client2 = svc._get_llm_client("fast")
        assert client2 is client
        assert captured["calls"] == 1
        _ok("缓存命中：create_llm_client_from_preset 仍只被调一次")

        # 请求不同 preset，再次构造
        svc._get_llm_client("reasoning")
        assert captured["calls"] == 2
        assert captured["last_preset"] == "reasoning"
        _ok("不同 preset → 重新构造（按 preset 名缓存）")
    finally:
        llm_pkg.create_llm_client_from_preset = orig

    return True


def test_get_llm_client_does_not_touch_components() -> bool:
    _hr("ChatService._get_llm_client · 不引用 ComponentConfigManager")
    # 故意把 ComponentConfigManager 弄坏；若 _get_llm_client 不依赖它，应 0 影响
    import src.utils.component_config_manager as comp_mod

    class _Boom:
        def get_component_config(self, name): raise RuntimeError("forbidden")
        def get_llm_client_for_component(self, name, **kw): raise RuntimeError("forbidden")

    orig_get_mgr = comp_mod.get_component_config_manager
    comp_mod.get_component_config_manager = lambda: _Boom()  # type: ignore

    import src.client.llm as llm_pkg
    fake = _FakeClient(model="fake/m")
    orig_preset = llm_pkg.create_llm_client_from_preset
    llm_pkg.create_llm_client_from_preset = lambda name: fake  # type: ignore

    try:
        svc = ChatService(config=ChatServiceConfig())
        svc._client_cache.clear()
        client = svc._get_llm_client("fast")
        assert client is fake
        _ok("即使 ComponentConfigManager 抛异常，_get_llm_client 仍然成功")
    finally:
        comp_mod.get_component_config_manager = orig_get_mgr
        llm_pkg.create_llm_client_from_preset = orig_preset

    return True


# ============================================================
# 入口
# ============================================================


TESTS = [
    test_from_config_manager_full_load,
    test_from_config_manager_missing_fields_use_defaults,
    test_from_config_manager_zero_completion_tokens_to_none,
    test_from_config_manager_empty_section_returns_defaults,
    test_from_config_manager_exception_safety,
    test_from_config_manager_independent_presets,
    test_get_llm_client_direct_preset,
    test_get_llm_client_does_not_touch_components,
]


def main() -> int:
    passed = 0
    failed = 0
    for fn in TESTS:
        try:
            if fn():
                passed += 1
            else:
                failed += 1
        except Exception:
            failed += 1
            print("\n  Exception in test:", fn.__name__)
            traceback.print_exc()

    _hr("总结")
    print(f"  通过: {passed}/{len(TESTS)}")
    print(f"  失败: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
