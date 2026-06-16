#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""grep_chunks 工具单元测试。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, patch

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def _hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


async def test_grep_chunks_literal_with_alias() -> bool:
    _hr("grep_chunks · literal + alias_map")
    from src.retrieve.types.result import ChunkItem
    from src.service.chat.chunk_alias_map import ChunkAliasMap
    from src.service.chat.tools import KnowledgeNavToolKit
    from src.service.chat.tools.handlers.grep_chunks import handle

    supp: List[ChunkItem] = []
    alias_map = ChunkAliasMap()
    kit = KnowledgeNavToolKit(
        supplemented_items=supp,
        enabled_tools=("grep_chunks",),
        alias_map=alias_map,
        user_id="user_1",
        knowledge_base_ids=["kb_1"],
    )

    fake_items = [
        ChunkItem(
            chunk_id="chunk-aaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            score=1.0,
            document_id="doc_1",
            section_id="sec_1",
            text="芯片型号 STM32F103 支持 GPIO 中断配置。",
        ),
    ]

    with patch(
        "src.service.chat.tools.handlers.grep_chunks._run_lexical_search",
        new=AsyncMock(return_value=fake_items),
    ), patch(
        "src.service.chat.tools.handlers.grep_chunks._enrich_chunk_items",
        new=AsyncMock(),
    ):
        out = await handle(kit, query="STM32F103", mode="literal")

    if "命中 1 条" not in out:
        print(f"  ❌ 未报告命中数: {out!r}")
        return False
    if "chunk_id=c1" not in out:
        print(f"  ❌ 未使用 alias: {out!r}")
        return False
    if ">>>STM32F103<<<" not in out:
        print(f"  ❌ 未高亮命中片段: {out!r}")
        return False
    if len(supp) != 1:
        print(f"  ❌ supplemented 未回填: {supp}")
        return False
    print("  ✅ literal 命中 + alias + snippet 高亮")
    return True


async def test_grep_chunks_document_id_filter() -> bool:
    _hr("grep_chunks · document_id 透传 filters")
    from src.retrieve.types.result import ChunkItem
    from src.service.chat.tools import KnowledgeNavToolKit
    from src.service.chat.tools.handlers import grep_chunks as mod

    kit = KnowledgeNavToolKit(
        supplemented_items=[],
        enabled_tools=("grep_chunks",),
        user_id="user_1",
        knowledge_base_ids=["kb_1"],
    )

    captured = {}

    async def _fake_run(**kwargs):
        captured.update(kwargs)
        return []

    with patch.object(mod, "_run_lexical_search", side_effect=_fake_run), patch.object(
        mod,
        "_enrich_chunk_items",
        new=AsyncMock(),
    ):
        out = await mod.handle(
            kit,
            query="GPIO",
            document_id="doc_target",
        )

    filters = captured.get("filters")
    if filters is None or filters.document_id != "doc_target":
        print(f"  ❌ document_id 未写入 filters: {filters}")
        return False
    if "未找到匹配 chunk" not in out:
        print(f"  ❌ 空结果提示异常: {out!r}")
        return False
    print("  ✅ document_id 正确透传到 MetadataFilter")
    return True


async def test_grep_chunks_boolean_mode() -> bool:
    _hr("grep_chunks · boolean 模式分发")
    from src.service.chat.tools import KnowledgeNavToolKit
    from src.service.chat.tools.handlers import grep_chunks as mod

    kit = KnowledgeNavToolKit(
        supplemented_items=[],
        enabled_tools=("grep_chunks",),
        user_id="user_1",
    )

    captured = {}

    async def _fake_run(**kwargs):
        captured.update(kwargs)
        return []

    with patch.object(mod, "_run_lexical_search", side_effect=_fake_run), patch.object(
        mod,
        "_enrich_chunk_items",
        new=AsyncMock(),
    ):
        await mod.handle(kit, query="GPIO AND 中断 NOT 示例", mode="boolean")

    if captured.get("resolved_mode") != "boolean":
        print(f"  ❌ 未走 boolean 模式: {captured}")
        return False
    print("  ✅ boolean 模式分发正确")
    return True


async def test_helpers_extract_snippet() -> bool:
    _hr("helpers · extract_match_snippet")
    from src.service.chat.tools.helpers import extract_match_snippet

    text = "前缀内容 ABC 目标词 后缀内容"
    snippet = extract_match_snippet(text, "目标词", "literal", context_chars=4)
    if ">>>目标词<<<" not in snippet:
        print(f"  ❌ snippet 异常: {snippet!r}")
        return False
    print(f"  ✅ snippet={snippet!r}")
    return True


async def main() -> int:
    tests = [
        test_helpers_extract_snippet,
        test_grep_chunks_literal_with_alias,
        test_grep_chunks_document_id_filter,
        test_grep_chunks_boolean_mode,
    ]
    results = []
    for fn in tests:
        try:
            ok = await fn()
            results.append((fn.__name__, ok))
        except Exception as e:  # noqa: BLE001
            print(f"  ❌ {fn.__name__} 异常: {e}")
            results.append((fn.__name__, False))

    passed = sum(1 for _, ok in results if ok)
    print("\n" + "=" * 70)
    print(f"  汇总: {passed}/{len(results)} 通过")
    for name, ok in results:
        print(f"    {'✅' if ok else '❌'} {name}")
    print("=" * 70)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
