#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""HierarchicalSummarizer ── map-reduce 分层摘要

手动 /summary 与自动 compaction 共用本管线：
- keep_recent_turns=0 → 压缩全部未总结消息（手动）
- keep_recent_turns=1 → 保留最近 1 轮（自动）

输入不截断；按"轮"切块，每块 ≤ chunk_budget，map 并发，必要时递归 reduce。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional, Sequence

from loguru import logger

from src.prompts.chat.summary_prompt import (
    SUMMARY_MAP_SYSTEM_PROMPT,
    SUMMARY_REDUCE_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
)
from src.service.chat.context.budgeter import ContextBudgeter
from src.service.chat.context.catalog import (
    ModelContextCatalog,
    get_model_context_catalog,
)

LLMGenerateFn = Callable[[List[dict], int], Awaitable[str]]
"""``(messages, max_tokens) -> summary_text``"""


@dataclass
class SummarizeResult:
    summary_text: str
    input_tokens: int
    summary_tokens: int
    chunk_count: int
    counting: str
    merged_old_summary: bool


class HierarchicalSummarizer:
    def __init__(
        self,
        *,
        generate_fn: LLMGenerateFn,
        model: str,
        catalog: Optional[ModelContextCatalog] = None,
        budgeter: Optional[ContextBudgeter] = None,
        chunk_budget_tokens: int = 24000,
        summary_target_tokens: int = 1500,
        map_concurrency: int = 4,
        heuristic_safety_factor: float = 1.2,
    ) -> None:
        self._generate = generate_fn
        self._model = model
        self._catalog = catalog or get_model_context_catalog()
        self._budgeter = budgeter or ContextBudgeter(
            catalog=self._catalog,
            heuristic_safety_factor=heuristic_safety_factor,
        )
        self._chunk_budget = int(chunk_budget_tokens)
        self._summary_target = int(summary_target_tokens)
        self._map_concurrency = max(1, int(map_concurrency))

        # 摘要模型自身窗口校验：不足则降级 chunk_budget
        spec = self._catalog.resolve(model)
        max_usable = max(4000, spec.max_context - self._summary_target - 2000)
        if self._chunk_budget > max_usable:
            logger.warning(
                f"[HierarchicalSummarizer] chunk_budget={self._chunk_budget} "
                f"> model usable={max_usable}，降级"
            )
            self._chunk_budget = max_usable

    async def summarize(
        self,
        messages: Sequence[Any],
        *,
        old_summary: Optional[str] = None,
        target_tokens: Optional[int] = None,
    ) -> SummarizeResult:
        target = int(target_tokens or self._summary_target)
        msgs = list(messages or [])
        if not msgs and not (old_summary or "").strip():
            return SummarizeResult("", 0, 0, 0, "heuristic", False)

        transcript_turns = self._split_turns(msgs)
        # 估算输入 token（粗略：整段 transcript）
        full_text = self._turns_to_text(transcript_turns)
        if old_summary:
            full_text = f"[之前的对话摘要]\n{old_summary}\n\n{full_text}"
        input_tokens = self._estimate_text_tokens(full_text)
        counting = "heuristic"

        # 小输入：直接 reduce（或单次摘要）
        if input_tokens <= self._chunk_budget or len(transcript_turns) <= 1:
            summary = await self._reduce(
                chunk_summaries=[full_text] if full_text.strip() else [],
                old_summary=None if full_text.startswith("[之前的对话摘要]") else old_summary,
                target_tokens=target,
                direct_transcript=full_text if input_tokens <= self._chunk_budget else None,
            )
            summary_tokens = self._estimate_text_tokens(summary)
            return SummarizeResult(
                summary_text=summary,
                input_tokens=input_tokens,
                summary_tokens=summary_tokens,
                chunk_count=1,
                counting=counting,
                merged_old_summary=bool(old_summary),
            )

        # map：按轮切块
        chunks = self._pack_turns(transcript_turns, self._chunk_budget)
        sem = asyncio.Semaphore(self._map_concurrency)

        async def _map_one(idx: int, chunk_turns: List[List[Any]]) -> str:
            async with sem:
                text = self._turns_to_text(chunk_turns)
                try:
                    return await self._map_chunk(text)
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"map chunk#{idx} 失败，降级规则提取: {e}")
                    return self._fallback_chunk_summary(chunk_turns)

        mapped = await asyncio.gather(*[
            _map_one(i, ch) for i, ch in enumerate(chunks)
        ])
        mapped = [m.strip() for m in mapped if (m or "").strip()]

        # 若块摘要加总仍超预算，递归一层
        mapped_text = "\n\n".join(f"[块摘要{i+1}]\n{m}" for i, m in enumerate(mapped))
        mapped_tokens = self._estimate_text_tokens(mapped_text)
        if mapped_tokens > self._chunk_budget and len(mapped) > 1:
            # 把块摘要再当"伪轮"递归
            pseudo = [
                type("M", (), {"role": "assistant", "content": m})()
                for m in mapped
            ]
            inner = await self.summarize(
                pseudo, old_summary=old_summary, target_tokens=target,
            )
            return SummarizeResult(
                summary_text=inner.summary_text,
                input_tokens=input_tokens,
                summary_tokens=inner.summary_tokens,
                chunk_count=len(chunks),
                counting="heuristic",
                merged_old_summary=bool(old_summary),
            )

        summary = await self._reduce(
            chunk_summaries=mapped,
            old_summary=old_summary,
            target_tokens=target,
        )
        summary_tokens = self._estimate_text_tokens(summary)
        return SummarizeResult(
            summary_text=summary,
            input_tokens=input_tokens,
            summary_tokens=summary_tokens,
            chunk_count=len(chunks),
            counting=counting,
            merged_old_summary=bool(old_summary),
        )

    async def _map_chunk(self, text: str) -> str:
        messages = [
            {"role": "system", "content": SUMMARY_MAP_SYSTEM_PROMPT},
            {"role": "user", "content": f"请摘要以下对话片段：\n\n{text}"},
        ]
        # map 输出不宜过长
        max_tokens = min(800, max(200, self._summary_target))
        return (await self._generate(messages, max_tokens) or "").strip()

    async def _reduce(
        self,
        *,
        chunk_summaries: List[str],
        old_summary: Optional[str],
        target_tokens: int,
        direct_transcript: Optional[str] = None,
    ) -> str:
        if direct_transcript is not None:
            body = direct_transcript
            system = SUMMARY_SYSTEM_PROMPT
        else:
            parts: List[str] = []
            if old_summary:
                parts.append(f"[之前的对话摘要]\n{old_summary.strip()}")
            for i, s in enumerate(chunk_summaries, 1):
                parts.append(f"[块摘要{i}]\n{s}")
            body = "\n\n".join(parts)
            system = SUMMARY_REDUCE_SYSTEM_PROMPT
        if not body.strip():
            return ""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"请合并为最终对话摘要：\n\n{body}"},
        ]
        # token→字数粗估，限制输出
        max_tokens = max(256, min(2000, target_tokens))
        return (await self._generate(messages, max_tokens) or "").strip()

    def _estimate_text_tokens(self, text: str) -> int:
        from src.service.chat.context.budgeter import _count_text_tokens

        return _count_text_tokens(
            text or "",
            model=self._model,
            catalog=self._catalog,
            safety_factor=self._budgeter._heuristic_safety_factor,  # noqa: SLF001
        )

    @staticmethod
    def _split_turns(messages: Sequence[Any]) -> List[List[Any]]:
        """按 user 消息切轮；非 user 开头的前缀并入第一轮。"""
        turns: List[List[Any]] = []
        current: List[Any] = []
        for m in messages:
            role = getattr(m, "role", None)
            if role == "user" and current:
                turns.append(current)
                current = [m]
            else:
                current.append(m)
        if current:
            turns.append(current)
        return turns or [[]]

    def _pack_turns(
        self, turns: List[List[Any]], budget: int
    ) -> List[List[List[Any]]]:
        packs: List[List[List[Any]]] = []
        buf: List[List[Any]] = []
        buf_tokens = 0
        for turn in turns:
            t_text = self._turns_to_text([turn])
            t_tokens, _ = self._estimate_text_tokens(t_text)
            t_tokens = max(1, t_tokens)
            if buf and buf_tokens + t_tokens > budget:
                packs.append(buf)
                buf = [turn]
                buf_tokens = t_tokens
            else:
                buf.append(turn)
                buf_tokens += t_tokens
        if buf:
            packs.append(buf)
        return packs or [turns]

    @staticmethod
    def _turns_to_text(turns: List[List[Any]]) -> str:
        lines: List[str] = []
        for turn in turns:
            for m in turn:
                role = getattr(m, "role", None)
                content = (getattr(m, "content", None) or "").strip()
                if not content:
                    continue
                if role == "summary":
                    lines.append(f"[之前的对话摘要] {content}")
                elif role == "user":
                    lines.append(f"用户: {content}")
                elif role == "assistant":
                    lines.append(f"助手: {content}")
                elif role == "tool":
                    # 保留短工具结果线索，避免完全丢失
                    snippet = content if len(content) <= 400 else content[:400] + "…"
                    name = ""
                    meta = getattr(m, "metadata", None) or {}
                    if isinstance(meta, dict):
                        name = meta.get("tool_name") or ""
                    prefix = f"工具{name}" if name else "工具"
                    lines.append(f"{prefix}: {snippet}")
        return "\n".join(lines)

    @staticmethod
    def _fallback_chunk_summary(chunk_turns: List[List[Any]]) -> str:
        """单块 map 失败时的规则降级：每轮 user 首句 + assistant 末句各截 200 字。"""
        bullets: List[str] = []
        for turn in chunk_turns:
            user_txt = ""
            asst_txt = ""
            for m in turn:
                role = getattr(m, "role", None)
                content = (getattr(m, "content", None) or "").strip()
                if role == "user" and content and not user_txt:
                    user_txt = content[:200]
                elif role == "assistant" and content:
                    asst_txt = content[:200]
            if user_txt or asst_txt:
                bullets.append(f"- 用户: {user_txt} / 助手: {asst_txt}")
        return "\n".join(bullets) if bullets else "(空片段)"


__all__ = ["HierarchicalSummarizer", "SummarizeResult", "LLMGenerateFn"]
