#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""ChatService 显式技能注入单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))


def test_build_forced_skills_block_returns_resolved_names() -> None:
    from src.service.chat.chat_service import ChatService

    skill = MagicMock()
    skill.body = "---\nname: research-report\n---\n# body"
    registry = MagicMock()
    registry.get.side_effect = lambda name: skill if name == "research-report" else None

    block, names = ChatService._build_forced_skills_block(
        ["research-report", "missing-skill"],
        registry,
    )
    assert names == ["research-report"]
    assert "【显式技能 / 最高优先级】" in block
    assert "无需**再 `skill_view`" in block
    assert "research-report" in block
    assert skill.body in block


def test_build_forced_skills_block_empty_when_none() -> None:
    from src.service.chat.chat_service import ChatService

    block, names = ChatService._build_forced_skills_block(None, MagicMock())
    assert block == ""
    assert names == []


def test_explicit_skills_override_in_system_prompt() -> None:
    from src.prompts.chat.system_prompt import build_chat_system_prompt

    text = build_chat_system_prompt(
        explicit_skill_names=["research-report"],
    )
    assert "本轮显式技能模式" in text
    assert "`research-report`" in text
    assert "HTML 调研报告" in text
    assert "{explicit_skills_override}" not in text


if __name__ == "__main__":
    test_build_forced_skills_block_returns_resolved_names()
    test_build_forced_skills_block_empty_when_none()
    test_explicit_skills_override_in_system_prompt()
    print("forced skills tests passed")
