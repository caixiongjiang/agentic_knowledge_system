#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_chunk_alias_map.py
@Author  : caixiongjiang
@Date    : 2026/05/14
@Function:
    ChunkAliasMap 单元测试（Phase B）

    覆盖点
    ------
    1. 基本分配：第一次 alias_for 分配 c1，重复同 chunk_id 返回同 alias；
    2. 双向映射：resolve_alias / alias_of 正反查询正确；
    3. Delta 管理：consume_turn_delta 返回本轮新增并清空；后续不重复；
    4. 历史重建：absorb_persisted 累加 + counter 推进到最大序号；
       rebuild_alias_map_from_history 正确累加所有 assistant.metadata；
    5. 跨 turn 复用：重建后 alias_for 新 chunk 从 max+1 起编号，不冲突；
    6. 文本替换：replace_chunk_ids_with_aliases 把已知 chunk-uuid 替换为 cN，
       未知保留；alias 命名识别 (is_alias)；
    7. 持久化冲突保护：absorb 同 alias 不同 chunk_id 不覆盖（warn）。

    运行::
        uv run python test/service/chat/test_chunk_alias_map.py

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import List

# 把项目根加入 sys.path，便于直接 ``python test/...`` 运行
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.service.chat.chunk_alias_map import (  # noqa: E402
    ChunkAliasMap,
    METADATA_ALIAS_ADDITIONS_KEY,
    rebuild_alias_map_from_history,
)


# ---------------------------------------------------------------------------
# 简易断言
# ---------------------------------------------------------------------------


def _eq(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------


def test_basic_allocation_and_idempotency() -> None:
    am = ChunkAliasMap()
    _eq(am.size, 0, "init size")
    _eq(am.alias_for("chunk-aaa"), "c1", "first alias")
    _eq(am.alias_for("chunk-bbb"), "c2", "second alias")
    _eq(am.alias_for("chunk-aaa"), "c1", "repeat same chunk")
    _eq(am.alias_for("chunk-ccc"), "c3", "third alias")
    _eq(am.size, 3, "size after 3 chunks")
    _eq(am.counter, 3, "counter")


def test_bidirectional_lookup() -> None:
    am = ChunkAliasMap()
    am.alias_for("chunk-x")
    am.alias_for("chunk-y")
    _eq(am.resolve_alias("c1"), "chunk-x", "alias→chunk c1")
    _eq(am.resolve_alias("c2"), "chunk-y", "alias→chunk c2")
    _eq(am.resolve_alias("c99"), None, "未知 alias → None")
    _eq(am.alias_of("chunk-x"), "c1", "chunk→alias")
    _eq(am.alias_of("chunk-zzz"), None, "未分配 chunk → None")


def test_is_alias() -> None:
    am = ChunkAliasMap()
    assert am.is_alias("c1")
    assert am.is_alias("c12345")
    assert not am.is_alias("cabc")
    assert not am.is_alias("chunk-aaa")
    assert not am.is_alias("")
    assert not am.is_alias("C1")  # 必须小写


def test_delta_consume() -> None:
    am = ChunkAliasMap()
    am.alias_for("chunk-a")
    am.alias_for("chunk-b")
    delta = am.consume_turn_delta()
    _eq(delta, {"c1": "chunk-a", "c2": "chunk-b"}, "first delta")
    # 再 consume 一次应为空
    _eq(am.consume_turn_delta(), {}, "second consume empty")
    # 新分配的 alias 仅出现在新的 delta
    am.alias_for("chunk-c")
    _eq(am.consume_turn_delta(), {"c3": "chunk-c"}, "incremental delta")


def test_absorb_persisted_and_counter() -> None:
    am = ChunkAliasMap()
    am.absorb_persisted({"c1": "chunk-a", "c3": "chunk-c"})
    _eq(am.resolve_alias("c1"), "chunk-a", "absorbed c1")
    _eq(am.resolve_alias("c3"), "chunk-c", "absorbed c3")
    _eq(am.counter, 3, "counter takes max alias number")
    # 新分配从 c4 起（跳过 c2）
    _eq(am.alias_for("chunk-new"), "c4", "skip-gap continuation")


def test_absorb_persisted_conflict_protection() -> None:
    am = ChunkAliasMap()
    am.absorb_persisted({"c1": "chunk-a"})
    # 同 alias 不同 chunk_id：以先到为准，不覆盖
    am.absorb_persisted({"c1": "chunk-impostor"})
    _eq(am.resolve_alias("c1"), "chunk-a", "no-overwrite on conflict")


def test_rebuild_from_history() -> None:
    history = [
        # user 消息没 alias_additions（也没有 metadata）
        SimpleNamespace(role="user", content="问 1", metadata=None),
        SimpleNamespace(
            role="assistant",
            content="答 1",
            metadata={METADATA_ALIAS_ADDITIONS_KEY: {"c1": "chunk-A", "c2": "chunk-B"}},
        ),
        SimpleNamespace(role="tool", content="...", metadata={}),
        SimpleNamespace(
            role="assistant",
            content="答 2",
            metadata={METADATA_ALIAS_ADDITIONS_KEY: {"c3": "chunk-C"}},
        ),
        # 没有 alias_additions 字段的老消息应被跳过而非崩
        SimpleNamespace(role="assistant", content="答 3 老消息", metadata={}),
    ]
    am = rebuild_alias_map_from_history(history)
    _eq(am.size, 3, "absorbed 3 mappings")
    _eq(am.counter, 3, "counter from history")
    _eq(am.resolve_alias("c2"), "chunk-B", "c2 from history")
    # 重建后再 alias_for 不应进 delta（rebuild 内部已清掉）
    _eq(am.consume_turn_delta(), {}, "no spurious delta after rebuild")
    # 下次新分配应是 c4
    _eq(am.alias_for("chunk-D"), "c4", "next allocation after rebuild")


def test_replace_chunk_ids_with_aliases() -> None:
    am = ChunkAliasMap()
    am.alias_for("chunk-4964fafe-0bc1-402d-9f0e-2c0e7ba66520")
    am.alias_for("chunk-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    text = (
        "根据 chunk-4964fafe-0bc1-402d-9f0e-2c0e7ba66520 和 "
        "chunk-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee，得出结论。"
        "另一个未知 chunk-99999999-0000-0000-0000-000000000000 不替换。"
    )
    replaced = am.replace_chunk_ids_with_aliases(text)
    assert "c1" in replaced, f"c1 missing: {replaced}"
    assert "c2" in replaced, f"c2 missing: {replaced}"
    # 未知保留
    assert "chunk-99999999-0000-0000-0000-000000000000" in replaced, replaced


def test_snapshot() -> None:
    am = ChunkAliasMap()
    am.alias_for("chunk-x")
    am.alias_for("chunk-y")
    snap = am.snapshot()
    _eq(snap, {"c1": "chunk-x", "c2": "chunk-y"}, "snapshot")
    # 修改 snapshot 不影响原 map
    snap["c1"] = "tampered"
    _eq(am.resolve_alias("c1"), "chunk-x", "snapshot is a copy")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> int:
    cases = [
        test_basic_allocation_and_idempotency,
        test_bidirectional_lookup,
        test_is_alias,
        test_delta_consume,
        test_absorb_persisted_and_counter,
        test_absorb_persisted_conflict_protection,
        test_rebuild_from_history,
        test_replace_chunk_ids_with_aliases,
        test_snapshot,
    ]
    failed: List[str] = []
    for fn in cases:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failed.append(fn.__name__)
            print(f"FAIL {fn.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{'='*60}")
    if failed:
        print(f"FAILED: {len(failed)}/{len(cases)} → {failed}")
        return 1
    print(f"ALL {len(cases)} PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
