#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""ContextBudgeter / ModelContextCatalog 单测（不依赖 DB / LLM 网络）。"""
from __future__ import annotations

import json
from pathlib import Path

from src.service.chat.context.budgeter import (
    TOOL_OUTPUT_ELIDED,
    ContextBudgetInput,
    ContextBudgeter,
    truncate_tool_output,
)
from src.service.chat.context.catalog import ModelContextCatalog


ROOT = Path(__file__).resolve().parents[3]
LONG_CTX = ROOT / "config" / "profiles" / "litellm" / "long_context_models.json"


def test_catalog_parses_object_and_int_formats(tmp_path: Path) -> None:
    cfg = tmp_path / "long.json"
    cfg.write_text(json.dumps({
        "models": {
            "a": 128000,
            "b": {"max_context": 262144, "max_output": 4096},
        }
    }), encoding="utf-8")
    cat = ModelContextCatalog(long_context_path=cfg)
    sa = cat.resolve("litellm_proxy/a")
    assert sa.max_context == 128000
    assert sa.source == "config"
    sb = cat.resolve("litellm_proxy/b")
    # 统一上限（Cursor 式）：声明 262144 的模型按 200K 参与预算，
    # 原始声明保留在 declared_max_context 供排查。
    assert sb.declared_max_context == 262144
    assert sb.max_context == 200_000
    assert sb.capped is True
    assert sb.max_output == 4096
    # cap=0 关闭封顶时按模型声明值
    uncapped = ModelContextCatalog(
        long_context_path=cfg, max_context_cap=0,
    ).resolve("litellm_proxy/b")
    assert uncapped.max_context == 262144
    assert uncapped.capped is False


def test_catalog_loads_project_config() -> None:
    cat = ModelContextCatalog(
        long_context_path=LONG_CTX,
    )
    spec = cat.resolve("litellm_proxy/deepseek-v4-flash")
    assert spec.max_context >= 200_000


def test_budgeter_breakdown_sums_to_used() -> None:
    cat = ModelContextCatalog(long_context_path=LONG_CTX)
    budgeter = ContextBudgeter(catalog=cat, threshold_ratio=0.8)
    report = budgeter.evaluate(ContextBudgetInput(
        model="litellm_proxy/deepseek-v4-flash",
        system_prompt="system " * 20,
        history=[],
        user_message="user question " * 30,
        tools_schema=[{"type": "function", "function": {"name": "search", "parameters": {}}}],
        reserved_output_tokens=8192,
    ))
    parts = sum(
        report.breakdown[k]
        for k in ("system", "skills", "tools_schema", "summary", "history", "user")
    )
    assert report.used_tokens == parts
    assert report.reserved_output > 0
    assert report.soft_limit == report.max_context - report.reserved_output
    # 展示口径：满窗口做分母（与 Cursor 一致）
    assert report.ratio == report.used_tokens / report.max_context


class _Msg:
    """rebuild_messages_from_history 只读 role / content 属性。"""

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content


def test_skills_split_out_of_system_prompt() -> None:
    cat = ModelContextCatalog(long_context_path=LONG_CTX)
    budgeter = ContextBudgeter(catalog=cat, threshold_ratio=0.9)
    skills = "## 可用技能\n" + ("- skill-alpha: 用于测试的技能条目\n" * 40)
    base = dict(
        model="litellm_proxy/deepseek-v4-flash",
        history=[],
        user_message="",
        reserved_output_tokens=8192,
    )
    without = budgeter.evaluate(ContextBudgetInput(
        system_prompt="你是知识库助手。" * 20 + skills, **base,
    ))
    with_split = budgeter.evaluate(ContextBudgetInput(
        system_prompt="你是知识库助手。" * 20 + skills, skills_block=skills, **base,
    ))
    # 拆分不改变总量，只把 skills 从 system 里挪出来
    assert with_split.used_tokens == without.used_tokens
    assert with_split.breakdown["skills"] > 0
    assert with_split.breakdown["system"] == (
        without.breakdown["system"] - with_split.breakdown["skills"]
    )


def test_summary_split_out_of_history() -> None:
    cat = ModelContextCatalog(long_context_path=LONG_CTX)
    budgeter = ContextBudgeter(catalog=cat, threshold_ratio=0.9)
    report = budgeter.evaluate(ContextBudgetInput(
        model="litellm_proxy/deepseek-v4-flash",
        system_prompt="",
        history=[
            _Msg("summary", "早期对话摘要：" * 30),
            _Msg("user", "接下来的问题" * 10),
            _Msg("assistant", "回答内容" * 10),
        ],
        user_message="",
        reserved_output_tokens=8192,
    ))
    assert report.breakdown["summary"] > 0
    assert report.breakdown["history"] > 0
    assert report.used_tokens == report.breakdown["summary"] + report.breakdown["history"]


def test_will_compact_at_tracks_soft_limit() -> None:
    cat = ModelContextCatalog(long_context_path=LONG_CTX)
    budgeter = ContextBudgeter(catalog=cat, threshold_ratio=0.9)
    report = budgeter.evaluate(ContextBudgetInput(
        model="litellm_proxy/deepseek-v4-flash",
        system_prompt="hello",
        history=[],
        user_message="",
        reserved_output_tokens=8192,
    ))
    assert report.will_compact_at == int(report.soft_limit * 0.9)
    assert report.will_compact_at < report.max_context


def test_truncate_tool_output_keeps_head_tail() -> None:
    cat = ModelContextCatalog(long_context_path=LONG_CTX)
    text = ("HEAD-" * 2000) + ("TAIL-" * 2000)
    out = truncate_tool_output(
        text,
        max_tokens=200,
        model="litellm_proxy/deepseek-v4-flash",
        catalog=cat,
    )
    assert "truncated" in out
    assert out.startswith("HEAD-")
    assert out.endswith("TAIL-" ) or out.rstrip().endswith("TAIL-") or "TAIL-" in out[-80:]


if __name__ == "__main__":
    # 允许直接运行
    test_catalog_loads_project_config()
    test_budgeter_breakdown_sums_to_used()
    test_truncate_tool_output_keeps_head_tail()
    print("ok")


def _tiny_catalog(tmp_path: Path) -> ModelContextCatalog:
    """4K 窗口的小模型，便于用少量文本触发收缩。"""
    cfg = tmp_path / "long.json"
    cfg.write_text(json.dumps({
        "models": {"tiny": {"max_context": 4000, "max_output": 1000}}
    }), encoding="utf-8")
    return ModelContextCatalog(
        long_context_path=cfg, max_context_cap=0,
    )


def _loop_messages(tool_payload_words: int) -> list:
    payload = "lorem ipsum dolor sit amet " * tool_payload_words
    def _asst(tc_id: str) -> dict:
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": tc_id,
                "type": "function",
                "function": {"name": "search", "arguments": "{}"},
            }],
        }
    return [
        {"role": "system", "content": "you are an agent"},
        {"role": "user", "content": "question"},
        _asst("t1"),
        {"role": "tool", "tool_call_id": "t1", "content": payload},
        _asst("t2"),
        {"role": "tool", "tool_call_id": "t2", "content": payload},
    ]


def test_evaluate_messages_breakdown_sums_to_used(tmp_path: Path) -> None:
    budgeter = ContextBudgeter(catalog=_tiny_catalog(tmp_path), threshold_ratio=0.9)
    report = budgeter.evaluate_messages(
        _loop_messages(10),
        model="tiny",
        tools_schema=[{"type": "function", "function": {"name": "search", "parameters": {}}}],
        reserved_output_tokens=1000,
    )
    assert report.used_tokens == (
        report.breakdown["system"]
        + report.breakdown["history"]
        + report.breakdown["tools_schema"]
    )
    assert report.max_context == 4000
    assert report.soft_limit == 3000
    assert report.will_compact_at == 2700


def test_shrink_is_noop_when_under_budget(tmp_path: Path) -> None:
    budgeter = ContextBudgeter(catalog=_tiny_catalog(tmp_path), threshold_ratio=0.9)
    messages = _loop_messages(5)
    before = [dict(m) for m in messages]
    outcome = budgeter.shrink_messages_to_fit(
        messages, model="tiny", reserved_output_tokens=1000, floor_tokens=100,
    )
    assert outcome.applied is False
    assert outcome.fits is True
    assert messages == before


def test_shrink_trims_oldest_tool_output_first(tmp_path: Path) -> None:
    budgeter = ContextBudgeter(catalog=_tiny_catalog(tmp_path), threshold_ratio=0.9)
    # 启发式估算（英文字符/4 × 1.2 安全系数）比旧 tokenizer 高约 20%，
    # 这里取 300 词使"只收紧最旧一条、最新一轮保持全文"在启发式口径下仍成立。
    messages = _loop_messages(300)
    newest_before = messages[5]["content"]
    outcome = budgeter.shrink_messages_to_fit(
        messages, model="tiny", reserved_output_tokens=1000, floor_tokens=100,
    )

    assert outcome.applied is True
    assert outcome.fits is True
    assert outcome.freed_tokens > 0
    # 一条都不能少：assistant.tool_calls 与 role=tool 的配对必须完整
    assert len(messages) == 6
    assert [m["role"] for m in messages] == [
        "system", "user", "assistant", "tool", "assistant", "tool",
    ]
    assert [m["tool_call_id"] for m in messages if m["role"] == "tool"] == ["t1", "t2"]
    # 最旧的先被收缩，最新一轮保持全文；system / user 不受影响
    assert len(messages[3]["content"]) < len(newest_before)
    assert messages[5]["content"] == newest_before
    assert messages[0]["content"] == "you are an agent"
    assert messages[1]["content"] == "question"
    # 收缩后确实落回目标线以内
    assert outcome.report.used_tokens <= outcome.report.soft_limit


def test_shrink_elides_when_floor_not_enough(tmp_path: Path) -> None:
    budgeter = ContextBudgeter(catalog=_tiny_catalog(tmp_path), threshold_ratio=0.9)
    messages = _loop_messages(400)
    outcome = budgeter.shrink_messages_to_fit(
        messages, model="tiny", reserved_output_tokens=1000, floor_tokens=2000,
    )
    # floor 太大 → 一级收紧不够，二级把最旧的整条省略
    assert outcome.elided_count >= 1
    assert messages[3]["content"] == TOOL_OUTPUT_ELIDED
    assert len(messages) == 6


def _cap_catalog(tmp_path: Path, models: dict, cap: int) -> ModelContextCatalog:
    cfg = tmp_path / "long.json"
    cfg.write_text(json.dumps({"models": models}), encoding="utf-8")
    return ModelContextCatalog(
        long_context_path=cfg, max_context_cap=cap,
    )


def test_catalog_keeps_model_limit_below_cap(tmp_path: Path) -> None:
    """有效窗口 = min(声明值, cap)：小于 cap 的模型按自身窗口，不被抬高。"""
    cat = _cap_catalog(
        tmp_path,
        {"big": 1_000_000, "small": 128_000, "tiny": 32_768},
        cap=200_000,
    )
    big = cat.resolve("litellm_proxy/big")
    assert big.max_context == 200_000 and big.capped is True
    assert big.declared_max_context == 1_000_000

    for name, declared in (("small", 128_000), ("tiny", 32_768)):
        spec = cat.resolve(f"litellm_proxy/{name}")
        assert spec.max_context == declared, name
        assert spec.declared_max_context == declared
        assert spec.capped is False, name


def test_budget_soft_limit_follows_smaller_window(tmp_path: Path) -> None:
    """小窗口模型的 soft_limit / will_compact_at 应基于自身窗口而非统一上限。"""
    cat = _cap_catalog(tmp_path, {"tiny": 32_768}, cap=200_000)
    budgeter = ContextBudgeter(catalog=cat, threshold_ratio=0.9)
    report = budgeter.evaluate(ContextBudgetInput(
        model="litellm_proxy/tiny",
        system_prompt="hello",
        reserved_output_tokens=4096,
    ))
    assert report.max_context == 32_768
    assert report.soft_limit == 32_768 - 4096
    assert report.will_compact_at == int((32_768 - 4096) * 0.9)


def test_catalog_cap_zero_disables_capping(tmp_path: Path) -> None:
    cat = _cap_catalog(tmp_path, {"big": 1_000_000}, cap=0)
    spec = cat.resolve("litellm_proxy/big")
    assert spec.max_context == 1_000_000
    assert spec.capped is False
