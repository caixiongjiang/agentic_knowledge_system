#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
存量 chunk_data 回填 search_text / display text。

用法:
  .venv/bin/python scripts/migrate_chunk_search_text.py [--dry-run] [--limit N]

说明:
  - 适配 2026/06/08 ChunkData 重构后的 text_meta 结构
  - image/table：从 text_meta 拼接 search_text（检索源）和展示文本
  - text chunk：search_text = text_meta.text（若未设置）
  - 完成后需对 image/table chunk 触发重嵌入（re-embed）以更新 Milvus 向量
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.types.utils.chunk_search_text import (
    resolve_chunk_display_text,
    resolve_chunk_search_text,
)


async def migrate(*, dry_run: bool, limit: int | None) -> None:
    from src.db.mongodb.mongodb_manager import MongoDBManager
    from src.db.mongodb.models.chunk_data import ChunkData

    await MongoDBManager.get_instance()

    query = {"deleted": 0}
    cursor = ChunkData.find(query)
    if limit:
        cursor = cursor.limit(limit)

    docs = await cursor.to_list()
    updated = 0
    skipped = 0

    for doc in docs:
        search = resolve_chunk_search_text(doc)
        display = resolve_chunk_display_text(doc)

        if doc.search_text == search:
            skipped += 1
            continue

        if dry_run:
            print(
                f"[dry-run] {doc.id} type={doc.chunk_type} "
                f"search_len={len(search)} display_len={len(display)}",
            )
        else:
            doc.search_text = search
            if doc.enhanced_text:
                from src.types.utils.chunk_search_text import (
                    format_table_search_text_from_display,
                )
                parts = doc.enhanced_text.split("\n", 1)
                if len(parts) == 2:
                    title, body = parts[0], parts[1]
                    doc.enhanced_text = (
                        f"{title}\n{format_table_search_text_from_display(body)}"
                        if "table_caption:" in body.lower()
                        else doc.enhanced_text
                    )
            await doc.save()

        updated += 1

    print(f"完成: 处理 {len(docs)} 条, 更新 {updated}, 跳过 {skipped}")
    if updated and not dry_run:
        print(
            "提示: image/table chunk 已向量化源文本变更，"
            "请对相关文档触发 re-embed 以更新 Milvus 向量。",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="回填 chunk search_text / display text")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    parser.add_argument("--limit", type=int, default=None, help="最多处理条数")
    args = parser.parse_args()
    asyncio.run(migrate(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
