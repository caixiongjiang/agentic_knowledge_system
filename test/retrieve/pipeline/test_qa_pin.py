#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_qa_pin.py
@Author  : caixiongjiang
@Date    : 2026/08/18
@Function:
    QA 置顶（两档、不短路）单元测试

    覆盖点
    ------
    1. score ≥ θ 且 answer 非空 → 产出置顶 QA，source_chunk_ids 保序去重；
    2. score < θ / answer 空 / 非 qa_dense → 不置顶；
    3. Top-K 剔除已置顶 chunk_id；
    4. 工具文案：置顶块在前，未置顶时退回普通 Top-K。

    运行::
        uv run python test/retrieve/pipeline/test_qa_pin.py

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieve.pipeline.types import DirectAnswer, RecallResult  # noqa: E402
from src.retrieve.types.result import ChunkItem  # noqa: E402
from src.service.chat.chunk_alias_map import ChunkAliasMap  # noqa: E402
from src.service.chat.tools.handlers.search_knowledge_base import (  # noqa: E402
    format_pinned_search_for_llm,
)
from src.service.knowledge.retrieve_service import RetrieveService  # noqa: E402


class _Failed(Exception):
    pass


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise _Failed(msg)


def _svc(threshold: float = 0.9) -> RetrieveService:
    svc = RetrieveService.__new__(RetrieveService)
    svc._qa_pin_threshold = threshold
    svc._qa_pin_enabled = True
    return svc


def _qa_item(
    score: float,
    *,
    answer: str = "脐橙褐斑的典型症状是果皮凹陷褐变。",
    qid: str = "qa-1",
    sources: Optional[List[str]] = None,
    question: str = "脐橙褐斑有哪些典型症状？",
) -> ChunkItem:
    return ChunkItem(
        chunk_id=f"qa:{qid}",
        score=score,
        document_id="doc-1",
        knowledge_base_id="kb-1",
        text=question,
        metadata={
            "_original_type": "qa",
            "_qa_id": qid,
            "answer": answer,
            "question": question,
            "source_chunk_ids": sources if sources is not None else [
                "chunk-a",
                "chunk-a",
                "chunk-b",
            ],
            "section_id": "sec-1",
        },
    )


def test_pin_above_threshold() -> None:
    svc = _svc()
    results = [
        RecallResult(
            route="qa_dense",
            items=[_qa_item(0.91)],
            total_count=1,
        ),
    ]
    pinned = svc._pick_pinned_qa(results)
    _assert(pinned is not None, "≥0.9 应置顶")
    assert pinned is not None
    _assert(pinned.qa_id == "qa-1", "qa_id 应对齐")
    _assert(abs(pinned.score - 0.91) < 1e-9, "score 应保留")
    _assert(pinned.source_chunk_ids == ["chunk-a", "chunk-b"], "依据 id 应保序去重")
    _assert("褐斑" in pinned.answer, "answer 应非空")


def test_no_pin_below_threshold() -> None:
    svc = _svc()
    results = [
        RecallResult(route="qa_dense", items=[_qa_item(0.89)], total_count=1),
    ]
    _assert(svc._pick_pinned_qa(results) is None, "<0.9 不应置顶")


def test_no_pin_empty_answer() -> None:
    svc = _svc()
    results = [
        RecallResult(
            route="qa_dense",
            items=[_qa_item(0.99, answer="   ")],
            total_count=1,
        ),
    ]
    _assert(svc._pick_pinned_qa(results) is None, "空 answer 不应置顶")


def test_ignore_non_qa_dense() -> None:
    svc = _svc()
    fake = _qa_item(0.99)
    results = [
        RecallResult(route="chunk_dense", items=[fake], total_count=1),
    ]
    _assert(svc._pick_pinned_qa(results) is None, "非 qa_dense 不应置顶")


def test_pick_highest_score() -> None:
    svc = _svc()
    results = [
        RecallResult(
            route="qa_dense",
            items=[
                _qa_item(0.92, qid="low", answer="次优"),
                _qa_item(0.97, qid="high", answer="最优"),
            ],
            total_count=2,
        ),
    ]
    pinned = svc._pick_pinned_qa(results)
    _assert(pinned is not None and pinned.qa_id == "high", "应取最高分 QA")


def test_drop_pinned_from_topk() -> None:
    items = [
        ChunkItem(chunk_id="chunk-a", score=0.8),
        ChunkItem(chunk_id="chunk-c", score=0.7),
        ChunkItem(chunk_id="chunk-b", score=0.6),
    ]
    kept = RetrieveService._drop_pinned_chunks(items, {"chunk-a", "chunk-b"})
    _assert([it.chunk_id for it in kept] == ["chunk-c"], "置顶 id 应从 Top-K 剔除")


def test_unique_chunk_ids_cap() -> None:
    ids = RetrieveService._unique_chunk_ids(
        ["a", "", "a", "b", "c", "d"],
        cap=2,
    )
    _assert(ids == ["a", "b"], "应保序去重并截断")


def test_format_pinned_then_items() -> None:
    alias = ChunkAliasMap()
    pinned = DirectAnswer(
        answer="答案正文",
        qa_id="qa-1",
        question="问题正文",
        score=0.93,
        source_chunk_ids=["chunk-a"],
    )
    evidence = [
        ChunkItem(chunk_id="chunk-a", score=0.93, text="依据原文一段"),
    ]
    items = [
        ChunkItem(chunk_id="chunk-z", score=0.4, text="其它片段"),
    ]
    text = format_pinned_search_for_llm(
        pinned, evidence, items, alias_map=alias,
    )
    _assert(text.index("【高置信原子问答】") < text.index("【依据原文】"), "QA 应在依据前")
    _assert(text.index("【依据原文】") < text.index("【其它相关片段】"), "依据应在 Top-K 前")
    _assert("答案正文" in text and "问题正文" in text, "应包含 Q/A")
    _assert("未短路" in text, "应明确未短路")
    _assert("c1" in text, "依据 chunk 应走 alias")


def test_format_without_pin() -> None:
    items = [ChunkItem(chunk_id="chunk-z", score=0.4, text="其它片段")]
    text = format_pinned_search_for_llm(None, [], items)
    _assert("【高置信原子问答】" not in text, "未置顶不应出现 QA 块")
    _assert("其它片段" in text, "应回退到普通 Top-K")


def main() -> int:
    tests = [
        test_pin_above_threshold,
        test_no_pin_below_threshold,
        test_no_pin_empty_answer,
        test_ignore_non_qa_dense,
        test_pick_highest_score,
        test_drop_pinned_from_topk,
        test_unique_chunk_ids_cap,
        test_format_pinned_then_items,
        test_format_without_pin,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
