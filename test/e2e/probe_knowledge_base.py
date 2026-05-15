#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : probe_knowledge_base.py
@Author  : caixiongjiang
@Date    : 2026/05/12
@Function:
    探测当前环境中"可用于 Chat E2E 测试"的知识库。

    流程
    ----
    1. 从 MySQL ``knowledge_base`` 表读取所有 ``deleted=0`` 的知识库；
    2. 对每个候选，在 Milvus ``chunk`` 集合用
       ``knowledge_base_id == <kb>`` 查询 chunk 计数；
    3. 返回第一条"至少 1 个 chunk 的"知识库（即真正可走 RAG 流程的）。

    既可作为模块被 ``test_chat_full_pipeline.py`` 导入，也可直接 CLI 运行：

        uv run python test/e2e/probe_knowledge_base.py

    输出
    ----
    JSON 单行，结构 ``{"user_id": ..., "knowledge_base_id": ...,
                       "knowledge_base_name": ..., "chunk_count": ...}``；
    找不到时输出 ``{}`` 并以非零码退出。

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


def _list_knowledge_bases() -> List[Dict[str, str]]:
    """MySQL：列出所有 deleted=0 的知识库（id / user / name）"""
    from sqlalchemy import select

    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.models.business.knowledge_base import KnowledgeBase

    mgr = get_mysql_manager()
    mgr.init_db()
    out: List[Dict[str, str]] = []
    with mgr.get_session() as session:
        stmt = (
            select(
                KnowledgeBase.knowledge_base_id,
                KnowledgeBase.user_id,
                KnowledgeBase.knowledge_base_name,
            )
            .where(KnowledgeBase.deleted == 0)
            .order_by(KnowledgeBase.update_time.desc())
            .limit(50)
        )
        for kb_id, user_id, name in session.execute(stmt).all():
            out.append({
                "knowledge_base_id": str(kb_id),
                "user_id": str(user_id),
                "knowledge_base_name": str(name or ""),
            })
    return out


def _count_chunks(kb_id: str) -> int:
    """Milvus：用 expr=knowledge_base_id==<kb_id> 估算 chunk 数（上限 1000）"""
    from src.db.milvus.repositories import ChunkRepository

    repo = ChunkRepository()
    try:
        # query(expr, limit=N) 走 metadata filter，返回 list[dict]
        rows = repo.query(
            f"knowledge_base_id == '{kb_id}'",
            output_fields=["id"],
            limit=1000,
        )
        return len(rows or [])
    except Exception as e:  # noqa: BLE001
        print(f"# Milvus 查询失败 kb={kb_id}: {e}", file=sys.stderr)
        return 0


def find_usable_kb() -> Optional[Dict[str, Any]]:
    """组合 MySQL + Milvus，找到第一条「有 chunk 索引」的知识库

    Returns:
        ``{"user_id", "knowledge_base_id", "knowledge_base_name", "chunk_count"}``
        失败返回 ``None``
    """
    kbs = _list_knowledge_bases()
    if not kbs:
        print("# MySQL 中没有 deleted=0 的 knowledge_base 记录", file=sys.stderr)
        return None

    candidates_no_chunk: List[Dict[str, Any]] = []
    for row in kbs:
        kb_id = row["knowledge_base_id"]
        cnt = _count_chunks(kb_id)
        if cnt > 0:
            return {**row, "chunk_count": cnt}
        candidates_no_chunk.append({**row, "chunk_count": 0})

    print(
        "# 找到知识库 {} 条，但 Milvus chunk 集合下均无对应 chunk："
        "可能还未跑抽取 Pipeline".format(len(kbs)),
        file=sys.stderr,
    )
    for c in candidates_no_chunk[:5]:
        print(
            f"#   - kb_id={c['knowledge_base_id']} user={c['user_id']} "
            f"name={c['knowledge_base_name']}",
            file=sys.stderr,
        )
    return None


def main() -> int:
    info = find_usable_kb()
    if info is None:
        print("{}")
        return 1
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
