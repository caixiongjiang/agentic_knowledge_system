#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""ContextBudgeter ── 完整请求 token 预算器

计量对象：system + history + user(+mentions/skills) + tools schema + reserved_output。
超 soft_limit 时由调用方触发压缩 / 截断 tool 输出；硬超窗抛 ``ContextOverflowError``。

token 估算统一走 ``_heuristic_count``（中英文字符比经验值），不再依赖任何 tokenizer。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from loguru import logger

from src.prompts.chat.context_builder import rebuild_messages_from_history
from src.prompts.chat.history_compressor import (
    _heuristic_count,
    _serialize_message_for_count,
)
from src.service.chat.context.catalog import (
    ModelContextCatalog,
    get_model_context_catalog,
)


class ContextOverflowError(RuntimeError):
    """请求在压缩/截断后仍无法落入窗口。"""

    def __init__(self, report: "ContextBudgetReport", message: str = "") -> None:
        self.report = report
        super().__init__(message or f"context overflow: used={report.used_tokens} soft={report.soft_limit}")


@dataclass
class ContextBudgetInput:
    model: str
    system_prompt: str = ""
    history: Sequence[Any] = field(default_factory=list)
    user_message: str = ""
    tools_schema: Optional[Sequence[Dict[str, Any]]] = None
    reserved_output_tokens: int = 8192
    skills_block: str = ""
    """``system_prompt`` 内嵌的技能索引原文；单独计量并从 system 分项中扣除。"""


@dataclass
class ContextBudgetReport:
    used_tokens: int
    max_context: int
    soft_limit: int
    reserved_output: int
    ratio: float
    over_soft_limit: bool
    counting: str  # 始终 "heuristic"（已移除 tokenizer，统一走字符估算）
    breakdown: Dict[str, int]
    model: str = ""
    will_compact_at: int = 0
    """触发自动压缩的绝对 token 数（``soft_limit × threshold_ratio``）。"""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "used_tokens": self.used_tokens,
            "max_context": self.max_context,
            "soft_limit": self.soft_limit,
            "reserved_output": self.reserved_output,
            "ratio": self.ratio,
            "over_soft_limit": self.over_soft_limit,
            "counting": self.counting,
            "breakdown": dict(self.breakdown),
            "model": self.model,
            "will_compact_at": self.will_compact_at,
        }


TOOL_OUTPUT_ELIDED = "[tool output omitted: context budget]"
"""工具结果被完全省略时的占位符（保留消息本身，避免破坏 tool_calls 配对）。"""


@dataclass
class ContextShrinkOutcome:
    """工具循环内预算收缩的结果。"""

    applied: bool
    """是否实际改动过 messages"""
    freed_tokens: int
    shrunk_count: int
    """被收紧到 floor 的工具结果条数"""
    elided_count: int
    """被完全省略的工具结果条数"""
    report: ContextBudgetReport
    """收缩后的最终计量"""
    fits: bool
    """收缩后是否已落入 soft_limit"""


def truncate_tool_output(
    text: str,
    *,
    max_tokens: int,
    model: str,
    catalog: Optional[ModelContextCatalog] = None,
    head_ratio: float = 0.7,
    heuristic_safety_factor: float = 1.2,
) -> str:
    """截断单条工具结果，保留头尾。``max_tokens`` 为硬顶。"""
    if not text or max_tokens <= 0:
        return text or ""
    catalog = catalog or get_model_context_catalog()
    used = _count_text_tokens(
        text, model=model, catalog=catalog, safety_factor=heuristic_safety_factor,
    )
    if used <= max_tokens:
        return text

    # 按字符比例粗切：token≈char/ratio，留余量
    # 先按 used/max 比例缩字符
    keep_chars = max(64, int(len(text) * (max_tokens / max(used, 1)) * 0.95))
    head_char = max(32, int(keep_chars * head_ratio))
    tail_chars = max(32, keep_chars - head_char)
    if head_char + tail_chars >= len(text):
        return text
    omitted = len(text) - head_char - tail_chars
    return (
        f"{text[:head_char]}\n"
        f"...[tool output truncated: omitted ~{omitted} chars]...\n"
        f"{text[-tail_chars:]}"
    )


def _count_text_tokens(
    text: str,
    *,
    model: str,
    catalog: ModelContextCatalog,
    safety_factor: float,
) -> int:
    """统一走中英文字符比经验估算（``_heuristic_count``），乘安全系数。"""
    if not text:
        return 0
    return int(_heuristic_count(text) * max(1.0, safety_factor))


class ContextBudgeter:
    """完整请求预算器。"""

    def __init__(
        self,
        *,
        catalog: Optional[ModelContextCatalog] = None,
        threshold_ratio: float = 0.8,
        reserved_output_fallback: int = 8192,
        heuristic_safety_factor: float = 1.2,
        tool_output_hard_cap_tokens: int = 32000,
    ) -> None:
        self._catalog = catalog or get_model_context_catalog()
        self._threshold_ratio = float(threshold_ratio)
        self._reserved_output_fallback = int(reserved_output_fallback)
        self._heuristic_safety_factor = float(heuristic_safety_factor)
        self._tool_output_hard_cap_tokens = int(tool_output_hard_cap_tokens)

    @property
    def tool_output_hard_cap_tokens(self) -> int:
        return self._tool_output_hard_cap_tokens

    @property
    def threshold_ratio(self) -> float:
        return self._threshold_ratio

    def resolve_reserved_output(
        self,
        model: str,
        *,
        preset_max_tokens: Optional[int] = None,
    ) -> int:
        spec = self._catalog.resolve(model)
        candidates = [spec.max_output, self._reserved_output_fallback]
        if isinstance(preset_max_tokens, int) and preset_max_tokens > 0:
            candidates.append(preset_max_tokens)
        return max(1, min(candidates))

    def evaluate(self, inp: ContextBudgetInput) -> ContextBudgetReport:
        spec = self._catalog.resolve(inp.model)
        reserved = max(1, int(inp.reserved_output_tokens or self._reserved_output_fallback))
        reserved = min(reserved, spec.max_output, spec.max_context // 4 or reserved)
        soft_limit = max(1, spec.max_context - reserved)

        breakdown: Dict[str, int] = {
            "system": 0,
            "skills": 0,
            "tools_schema": 0,
            "summary": 0,
            "history": 0,
            "user": 0,
            "reserved_output": reserved,
        }

        # system（技能索引嵌在其中，下一步拆出并扣除）
        if inp.system_prompt:
            breakdown["system"] = self._count_messages(
                [{"role": "system", "content": inp.system_prompt}],
                model=inp.model,
            )

        # skills：技能索引由 SkillRegistry.build_index() 生成后拼进 system_prompt。
        # 单列一项便于观测，并从 system 扣除，保证分项加和恒等于 used。
        if inp.skills_block.strip():
            n = _count_text_tokens(
                inp.skills_block,
                model=inp.model,
                catalog=self._catalog,
                safety_factor=self._heuristic_safety_factor,
            )
            n = min(n, breakdown["system"])
            breakdown["skills"] = n
            breakdown["system"] -= n

        # history：拆成 summary（持久化上下文摘要）与 history（原始对话）
        if inp.history:
            try:
                hist_msgs = rebuild_messages_from_history(inp.history)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"rebuild history for budget failed: {e}")
                hist_msgs = []
            groups = (
                ("summary", [m for m in hist_msgs if m.get("role") == "summary"]),
                ("history", [m for m in hist_msgs if m.get("role") != "summary"]),
            )
            for key, msgs in groups:
                if not msgs:
                    continue
                breakdown[key] = self._count_messages(msgs, model=inp.model)

        # user：调用方传入的是**给 LLM 的 user 副本**，已含 @ 引用块与显式技能块
        if inp.user_message:
            breakdown["user"] = self._count_messages(
                [{"role": "user", "content": inp.user_message}],
                model=inp.model,
            )

        # tools schema
        if inp.tools_schema:
            breakdown["tools_schema"] = self._count_tools(
                list(inp.tools_schema), model=inp.model
            )

        used = sum(
            breakdown[k]
            for k in ("system", "skills", "tools_schema", "summary", "history", "user")
        )
        # 展示口径与 Cursor 对齐：用满窗口做分母，reserved_output 不计入 used。
        # 压缩触发仍走 soft_limit（= max_context - reserved_output），保证请求
        # 连同输出预留一起能落进窗口。
        ratio = used / spec.max_context if spec.max_context > 0 else 1.0
        return ContextBudgetReport(
            used_tokens=used,
            max_context=spec.max_context,
            soft_limit=soft_limit,
            reserved_output=reserved,
            ratio=ratio,
            over_soft_limit=used > soft_limit * self._threshold_ratio,
            counting="heuristic",
            breakdown=breakdown,
            model=inp.model,
            will_compact_at=int(soft_limit * self._threshold_ratio),
        )

    # ------------------------------------------------------------
    # 工具循环内预算（每次 LLM 调用前）
    # ------------------------------------------------------------

    def evaluate_messages(
        self,
        messages: Sequence[Dict[str, Any]],
        *,
        model: str,
        tools_schema: Optional[Sequence[Dict[str, Any]]] = None,
        reserved_output_tokens: Optional[int] = None,
    ) -> ContextBudgetReport:
        """对**已装配的 OpenAI messages** 直接计量。

        与 ``evaluate`` 的差异：入参就是即将发给 LLM 的 messages 本身。工具
        循环每轮会往里追加 assistant / tool 消息，用它可以在每次调用前拿到
        真实用量，而不必从 ChatMessage 反向重建。

        分项按 role 归并：所有 system 消息（含摘要注入）计入 ``system``，
        其余计入 ``history``；``skills`` / ``summary`` / ``user`` 在此口径下
        无法拆分，保持为 0 以维持 ``breakdown`` 结构一致。
        """
        spec = self._catalog.resolve(model)
        reserved = max(
            1, int(reserved_output_tokens or self._reserved_output_fallback),
        )
        reserved = min(reserved, spec.max_output, spec.max_context // 4 or reserved)
        soft_limit = max(1, spec.max_context - reserved)

        breakdown: Dict[str, int] = {
            "system": 0,
            "skills": 0,
            "tools_schema": 0,
            "summary": 0,
            "history": 0,
            "user": 0,
            "reserved_output": reserved,
        }

        groups = (
            ("system", [m for m in messages if m.get("role") == "system"]),
            ("history", [m for m in messages if m.get("role") != "system"]),
        )
        for key, msgs in groups:
            if not msgs:
                continue
            breakdown[key] = self._count_messages(list(msgs), model=model)

        if tools_schema:
            breakdown["tools_schema"] = self._count_tools(
                list(tools_schema), model=model,
            )

        used = breakdown["system"] + breakdown["history"] + breakdown["tools_schema"]
        ratio = used / spec.max_context if spec.max_context > 0 else 1.0
        return ContextBudgetReport(
            used_tokens=used,
            max_context=spec.max_context,
            soft_limit=soft_limit,
            reserved_output=reserved,
            ratio=ratio,
            over_soft_limit=used > soft_limit * self._threshold_ratio,
            counting="heuristic",
            breakdown=breakdown,
            model=model,
            will_compact_at=int(soft_limit * self._threshold_ratio),
        )

    def shrink_messages_to_fit(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: str,
        tools_schema: Optional[Sequence[Dict[str, Any]]] = None,
        reserved_output_tokens: Optional[int] = None,
        floor_tokens: int = 512,
    ) -> ContextShrinkOutcome:
        """**原地**收缩 messages 直到落入预算，返回收缩结果。

        只改 ``role=tool`` 消息的 ``content``，从最旧的开始、够了就停——
        既不删消息（``assistant.tool_calls`` 与 ``role=tool`` 的配对永远完整），
        也不碰 system / user / assistant 正文，最近一轮工具结果保持全文。

        两级处置：先把旧工具结果收紧到 ``floor_tokens``；仍超则把更旧的整条
        换成 ``TOOL_OUTPUT_ELIDED`` 占位。两级都用尽仍超出 ``soft_limit``，
        由调用方按 ``fits=False`` 决定是否放弃本次请求。

        目标线取 ``will_compact_at``（而非 ``soft_limit``），给下一轮工具结果
        留出与首轮同样的余量。
        """
        report = self.evaluate_messages(
            messages,
            model=model,
            tools_schema=tools_schema,
            reserved_output_tokens=reserved_output_tokens,
        )
        target = report.will_compact_at
        if report.used_tokens <= target:
            return ContextShrinkOutcome(
                applied=False,
                freed_tokens=0,
                shrunk_count=0,
                elided_count=0,
                report=report,
                fits=True,
            )

        overflow = report.used_tokens - target
        freed = shrunk = elided = 0
        floor = max(0, int(floor_tokens))

        def _count(text: str) -> int:
            return _count_text_tokens(
                text,
                model=model,
                catalog=self._catalog,
                safety_factor=self._heuristic_safety_factor,
            )

        # 一级：旧工具结果收紧到 floor
        if floor > 0:
            for m in messages:
                if overflow <= 0:
                    break
                if m.get("role") != "tool":
                    continue
                content = m.get("content") or ""
                if not content:
                    continue
                before = _count(content)
                if before <= floor:
                    continue
                new_content = truncate_tool_output(
                    content,
                    max_tokens=floor,
                    model=model,
                    catalog=self._catalog,
                    heuristic_safety_factor=self._heuristic_safety_factor,
                )
                after = _count(new_content)
                if after >= before:
                    continue
                m["content"] = new_content
                freed += before - after
                overflow -= before - after
                shrunk += 1

        # 二级：仍超 → 最旧的工具结果整条省略
        if overflow > 0:
            stub_tokens = _count(TOOL_OUTPUT_ELIDED)
            for m in messages:
                if overflow <= 0:
                    break
                if m.get("role") != "tool":
                    continue
                content = m.get("content") or ""
                if not content or content == TOOL_OUTPUT_ELIDED:
                    continue
                before = _count(content)
                if before <= stub_tokens:
                    continue
                m["content"] = TOOL_OUTPUT_ELIDED
                freed += before - stub_tokens
                overflow -= before - stub_tokens
                elided += 1

        final = self.evaluate_messages(
            messages,
            model=model,
            tools_schema=tools_schema,
            reserved_output_tokens=reserved_output_tokens,
        )
        return ContextShrinkOutcome(
            applied=bool(shrunk or elided),
            freed_tokens=freed,
            shrunk_count=shrunk,
            elided_count=elided,
            report=final,
            fits=final.used_tokens <= final.soft_limit,
        )

    def _count_messages(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: str,
    ) -> int:
        if not messages:
            return 0
        total = 0
        for m in messages:
            total += _heuristic_count(_serialize_message_for_count(m))
        return int(total * max(1.0, self._heuristic_safety_factor))

    def _count_tools(
        self,
        tools: List[Dict[str, Any]],
        *,
        model: str,
    ) -> int:
        if not tools:
            return 0
        raw = json.dumps(tools, ensure_ascii=False)
        return int(_heuristic_count(raw) * max(1.0, self._heuristic_safety_factor))


__all__ = [
    "TOOL_OUTPUT_ELIDED",
    "ContextShrinkOutcome",
    "ContextBudgetInput",
    "ContextBudgetReport",
    "ContextBudgeter",
    "ContextOverflowError",
    "truncate_tool_output",
]
