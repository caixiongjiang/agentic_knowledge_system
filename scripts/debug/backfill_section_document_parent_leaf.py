#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""一次性回填脚本：把 MongoDB section_data 里的 parent_section_id / is_leaf
回填到 MySQL section_document。

背景
----
v1.1（2026/07/17）把 section 树拓扑（parent_section_id / is_leaf）从 MongoDB
section_data 迁到 MySQL section_document。新链路（SectionSummaryWorker）会
直接写 MySQL；但迁移前已入库的旧数据，其拓扑只存在于 Mongo，需要本脚本回填，
否则骨架树重建 / TextAnalyzer 叶子过滤会读到 NULL。

范围
----
- 只回填 MySQL section_document 中 parent_section_id IS NULL 或 is_leaf IS NULL
  的行（已有值的不覆盖，幂等可重复执行）。
- 数据源是 Mongo section_data 旧文档里残留的 parent_section_id / is_leaf 字段
  （新代码不再写这两个字段，但旧文档仍保留，Beanie 加载时按 extra=ignore 丢弃，
  故本脚本用原生 pymongo 读取，不依赖 SectionData 模型）。
- Mongo 缺字段或文档不存在的行跳过，不报错。

用法
----
    MYSQL_USER=xxx MYSQL_PASSWORD=xxx \
    MONGODB_USER=xxx MONGODB_PASSWORD=xxx \
    uv run python scripts/debug/backfill_section_document_parent_leaf.py [--dry-run]

连接配置与 scripts/debug/build_section_tree.py 一致，默认指向 config.toml 的环境。
"""

import os
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from pymongo import MongoClient
from sqlalchemy import create_engine, text

# ---------- 连接配置 ----------
MYSQL_HOST = os.environ.get("MYSQL_HOST", "192.168.201.14")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_DB = os.environ.get("MYSQL_DB", "default")
MYSQL_USER = os.environ.get("MYSQL_USER", "caixj-test")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "caixj-test")

MONGO_HOST = os.environ.get("MONGODB_HOST", "192.168.201.14")
MONGO_PORT = int(os.environ.get("MONGODB_PORT", "27017"))
MONGO_DB = os.environ.get("MONGODB_DB", "default")
MONGO_USER = os.environ.get("MONGODB_USER", "caixj-test")
MONGO_PASSWORD = os.environ.get("MONGODB_PASSWORD", "caixj-test")
MONGO_AUTH_SOURCE = os.environ.get("MONGODB_AUTH_SOURCE", "admin")

BATCH = 500


def mysql_engine():
    url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    return create_engine(url, pool_pre_ping=True)


def mongo_client():
    uri = (
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/"
        f"?authSource={MONGO_AUTH_SOURCE}"
    )
    return MongoClient(uri)


def fetch_pending_sections(engine) -> List[Dict[str, Any]]:
    """取 parent_section_id 或 is_leaf 为 NULL 的 section_document 行。"""
    sql = text(
        """
        SELECT section_id
        FROM section_document
        WHERE deleted = 0
          AND (parent_section_id IS NULL OR is_leaf IS NULL)
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def fetch_mongo_topology(client, section_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """从 Mongo section_data 批量取 parent_section_id / is_leaf（原生 pymongo）。"""
    if not section_ids:
        return {}
    coll = client[MONGO_DB]["section_data"]
    cur = coll.find(
        {"_id": {"$in": section_ids}},
        {"_id": 1, "parent_section_id": 1, "is_leaf": 1},
    )
    out: Dict[str, Dict[str, Any]] = {}
    for doc in cur:
        sid = doc.get("_id")
        if not sid:
            continue
        out[str(sid)] = {
            "parent_section_id": doc.get("parent_section_id"),
            "is_leaf": doc.get("is_leaf"),
        }
    return out


def apply_updates(engine, updates: List[Dict[str, Any]], dry_run: bool) -> int:
    """批量 UPDATE section_document。返回成功条数。"""
    if not updates or dry_run:
        return 0
    sql = text(
        """
        UPDATE section_document
        SET parent_section_id = :parent_section_id,
            is_leaf = :is_leaf
        WHERE section_id = :section_id
        """
    )
    with engine.begin() as conn:
        for row in updates:
            conn.execute(sql, row)
    return len(updates)


def main():
    dry_run = "--dry-run" in sys.argv

    engine = mysql_engine()
    client = mongo_client()

    pending = fetch_pending_sections(engine)
    print(f"待回填 section_document 行数: {len(pending)}")
    if not pending:
        print("无需回填，退出。")
        return

    total_updated = 0
    total_skipped = 0
    for i in range(0, len(pending), BATCH):
        batch = pending[i : i + BATCH]
        section_ids = [r["section_id"] for r in batch]
        topo = fetch_mongo_topology(client, section_ids)

        updates: List[Dict[str, Any]] = []
        for r in batch:
            sid = r["section_id"]
            t = topo.get(sid)
            if not t:
                total_skipped += 1
                continue
            parent = t["parent_section_id"]
            is_leaf = t["is_leaf"]
            # 两者都缺则无意义
            if parent is None and is_leaf is None:
                total_skipped += 1
                continue
            updates.append({
                "section_id": sid,
                "parent_section_id": parent,
                "is_leaf": 1 if is_leaf else (0 if is_leaf is not None else None),
            })

        if dry_run:
            print(f"[dry-run] 批次 {i // BATCH + 1}: 拟更新 {len(updates)} 条, 跳过 {len(batch) - len(updates)} 条")
            total_updated += len(updates)
        else:
            n = apply_updates(engine, updates, dry_run)
            total_updated += n
            print(f"批次 {i // BATCH + 1}: 回填 {n} 条, 跳过 {len(batch) - len(updates)} 条 (Mongo 缺字段)")

    print(f"\n完成: 回填 {total_updated} 条, 跳过 {total_skipped} 条, dry_run={dry_run}")
    client.close()


if __name__ == "__main__":
    main()
