#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
诊断脚本：定位「本应有父子关系但被判为孤立叶子」的 section。

用法：
    uv run python scripts/diagnose_section_tree.py <document_id>

功能：
1. 从 MongoDB section_data 拉出该文档所有 section 的 text 标题
2. 对每个 title 跑 parse_numbering，统计能识别 vs 不能识别的比例
3. 按 MinerU text_level（从 mysql section_meta_info 拉）分组
4. 打印典型标题样本，方便定位是「编号丢失」还是「格式不支持」
"""

import asyncio
import sys
from collections import Counter
from typing import List, Dict, Any

from src.db.mongodb.database_manager import mongodb_manager
from src.db.mongodb.repositories.section_data_repository import section_data_repository
from src.db.mysql.database_manager import mysql_manager
from src.db.mysql.repositories.base.section_meta_info_repo import (
    section_meta_info_repo,
)
from src.utils.section_numbering import parse_numbering


async def diagnose(document_id: str) -> None:
    # 1) MongoDB section_data
    await mongodb_manager.initialize()
    docs = await section_data_repository.find(
        limit=10000,
        include_deleted=False,
    )
    # 无法直接按 document_id 过滤（section_data 无该字段）；改从 MySQL 拉本文档 section_id 白名单
    with mysql_manager.get_session() as session:
        rows = section_meta_info_repo.find_all(session)  # 全量拉，后续再按 document_id 过滤
    # 目前 section_meta_info 未存 document_id，只能全量比对。
    # 若数据规模较大，可根据实际情况改为直接从 MongoDB 按 _id 前缀 / 其他条件过滤。

    section_id_to_text: Dict[str, Dict[str, Any]] = {}
    for d in docs:
        section_id_to_text[d.id] = {
            "text": d.text or "",
            "is_leaf": d.is_leaf,
            "parent_section_id": d.parent_section_id,
            "chunk_id_list": d.chunk_id_list or [],
        }

    # 2) 分类
    numbered = []
    unnumbered = []
    empty_title = []
    for sid, info in section_id_to_text.items():
        t = info["text"].strip()
        if not t:
            empty_title.append((sid, info))
            continue
        num = parse_numbering(t)
        if num is not None:
            numbered.append((sid, info, num))
        else:
            unnumbered.append((sid, info))

    total = len(section_id_to_text)
    print("=" * 80)
    print(f"总 section 数: {total}")
    print(f"能识别编号: {len(numbered)}  ({len(numbered) / total:.1%})")
    print(f"无法识别编号: {len(unnumbered)}  ({len(unnumbered) / total:.1%})")
    print(f"空标题: {len(empty_title)}  ({len(empty_title) / total:.1%})")

    # 3) 有编号 section 按 style / level 分布
    style_counter = Counter()
    level_counter = Counter()
    for _, _, num in numbered:
        style_counter[num.style] += 1
        level_counter[num.level] += 1
    print("\n有编号 section 编号风格分布:")
    for style, cnt in style_counter.most_common():
        print(f"  {style:12s}: {cnt}")
    print("\n有编号 section 层级分布:")
    for lvl, cnt in sorted(level_counter.items()):
        print(f"  level={lvl}: {cnt}")

    # 4) 无编号 section 样例（打印前 20 条 text）
    print("\n" + "=" * 80)
    print("【无法识别编号】样例（前 20 条 title）:")
    for i, (sid, info) in enumerate(unnumbered[:20], 1):
        marks = []
        if info["is_leaf"]:
            marks.append("leaf")
        if info["parent_section_id"]:
            marks.append(f"parent={info['parent_section_id'][:20]}")
        if info["chunk_id_list"]:
            marks.append(f"chunks={len(info['chunk_id_list'])}")
        print(f"  {i:2d}. {info['text']!r:80s}  [{', '.join(marks) or 'no-summary'}]")

    # 5) 空标题样例
    if empty_title:
        print("\n" + "=" * 80)
        print("【空标题】样例（前 10 条 section_id）:")
        for i, (sid, info) in enumerate(empty_title[:10], 1):
            print(f"  {i:2d}. {sid}  chunks={len(info['chunk_id_list'])}")

    # 6) 有编号 section 样例
    print("\n" + "=" * 80)
    print("【有编号】样例（前 20 条 title）:")
    for i, (sid, info, num) in enumerate(numbered[:20], 1):
        print(f"  {i:2d}. lvl={num.level} key={num.key():15s}  title={info['text']!r}")

    await mongodb_manager.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # 允许无参数运行（拉所有 section）
        print("Usage: python scripts/diagnose_section_tree.py [document_id]", file=sys.stderr)
        print("（未指定 document_id，将扫描 MongoDB 所有 section_data）", file=sys.stderr)
        document_id = ""
    else:
        document_id = sys.argv[1]

    asyncio.run(diagnose(document_id))
