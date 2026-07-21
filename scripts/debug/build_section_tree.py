#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""调试脚本：拉取已上传文件的 section 树，供人工核对。

数据来源：
- MySQL workspace_file_system  : 上传文件元数据（file_id / file_name / document_id / status）
- MySQL section_document       : section ↔ document + parent_section_id（拼树依赖）
- MySQL section_meta_info       : section 元信息（text_level / 页码范围 / section_type）
- MongoDB section_data         : section 正文（text=标题 / is_leaf / chunk_id_list / summary）

输出：按 document 分组，打印 section 层级树（含 level / is_leaf / chunk 数 / 页码）。
"""

import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

# 让脚本能 import 项目模块（读取 config / env）
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from pymongo import MongoClient
from sqlalchemy import create_engine, text


# ---------- 连接配置（与 config.toml / .env 一致） ----------
MYSQL_HOST = "192.168.201.14"
MYSQL_PORT = 3306
MYSQL_DB = "default"
MYSQL_USER = os.environ.get("MYSQL_USER", "caixj-test")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "caixj-test")

MONGO_HOST = "192.168.201.14"
MONGO_PORT = 27017
MONGO_DB = "default"
MONGO_USER = os.environ.get("MONGODB_USER", "caixj-test")
MONGO_PASSWORD = os.environ.get("MONGODB_PASSWORD", "caixj-test")
MONGO_AUTH_SOURCE = os.environ.get("MONGODB_AUTH_SOURCE", "admin")


def mysql_engine():
    url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    return create_engine(url, pool_pre_ping=True)


def mongo_client():
    uri = (
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/"
        f"?authSource={MONGO_AUTH_SOURCE}"
    )
    return MongoClient(uri)


def load_files(engine) -> List[Dict[str, Any]]:
    sql = text(
        """
        SELECT file_id, file_name, document_id, user_id, knowledge_base_id,
               knowledge_base_name, status, file_size, file_type, create_time
        FROM workspace_file_system
        WHERE deleted = 0
        ORDER BY create_time DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def load_sections(engine, document_id: str) -> List[Dict[str, Any]]:
    """从 section_document + section_meta_info 联合取一个文档的所有 section。"""
    sql = text(
        """
        SELECT
            sd.section_id,
            sd.parent_section_id,
            sd.document_id,
            sm.text_level,
            sm.section_type,
            sm.start_page_index,
            sm.end_page_index
        FROM section_document sd
        LEFT JOIN section_meta_info sm ON sm.section_id = sd.section_id
        WHERE sd.document_id = :doc_id
          AND sd.deleted = 0
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"doc_id": document_id}).mappings().all()
    return [dict(r) for r in rows]


def load_section_data(client, section_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not section_ids:
        return {}
    db = client[MONGO_DB]
    coll = db["section_data"]
    cur = coll.find(
        {"_id": {"$in": section_ids}},
        {
            "_id": 1,
            "text": 1,
            "is_leaf": 1,
            "chunk_id_list": 1,
            "parent_section_id": 1,
            "summary": 1,
        },
    )
    return {doc["_id"]: doc for doc in cur}


def build_tree(sections: List[Dict[str, Any]], data_map: Dict[str, Dict[str, Any]]):
    """按 parent_section_id 构建树，返回 (roots, children_map)。"""
    children: Dict[Optional[str], List[str]] = defaultdict(list)
    by_id: Dict[str, Dict[str, Any]] = {s["section_id"]: s for s in sections}

    for s in sections:
        # parent 优先取 section_document.parent_section_id，回退 Mongo 的 parent_section_id
        parent = s.get("parent_section_id")
        if parent is None:
            doc = data_map.get(s["section_id"], {})
            parent = doc.get("parent_section_id")
        children[parent].append(s["section_id"])

    roots = children.get(None, [])
    # 兜底：如果没有任何 parent=None 的根，把没出现在 children value 里的当根
    if not roots:
        all_children = set()
        for v in children.values():
            all_children.update(v)
        roots = [sid for sid in by_id if sid not in all_children]

    return roots, children, by_id


def render(
    sid: str,
    children: Dict[Optional[str], List[str]],
    by_id: Dict[str, Dict[str, Any]],
    data_map: Dict[str, Dict[str, Any]],
    depth: int,
    lines: List[str],
):
    meta = by_id.get(sid, {})
    doc = data_map.get(sid, {})
    title = doc.get("text") or "(无标题)"
    level = meta.get("text_level")
    is_leaf = doc.get("is_leaf")
    chunk_n = len(doc.get("chunk_id_list") or [])
    page = ""
    if meta.get("start_page_index") is not None:
        sp, ep = meta.get("start_page_index"), meta.get("end_page_index")
        page = f" p{sp+1}" + (f"-{ep+1}" if ep is not None and ep != sp else "")
    leaf_tag = ""
    if is_leaf is True:
        leaf_tag = " [leaf]"
    elif is_leaf is False:
        leaf_tag = " [rollup]"
    else:
        leaf_tag = " [is_leaf=?]"
    indent = "  " * depth
    lines.append(
        f"{indent}- {title}  (level={level}{leaf_tag}, chunks={chunk_n}{page})"
        f"  [{sid}]"
    )
    for child in children.get(sid, []):
        render(child, children, by_id, data_map, depth + 1, lines)


def main():
    engine = mysql_engine()
    client = mongo_client()

    files = load_files(engine)
    if not files:
        print("workspace_file_system 表里没有未删除的文件记录。")
        return

    print(f"共找到 {len(files)} 个文件记录（按 create_time 倒序）：\n")
    for f in files:
        print(
            f"  file_id={f['file_id']}  name={f['file_name']}  "
            f"document_id={f['document_id']}  status={f['status']}  "
            f"kb={f.get('knowledge_base_id')}"
        )
    print()

    # 按 document_id 聚合（同一个 document_id 可能被多个 file 引用）
    doc_to_files: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for f in files:
        if f.get("document_id"):
            doc_to_files[f["document_id"]].append(f)

    for doc_id, f_list in doc_to_files.items():
        print("=" * 80)
        print(f"Document: {doc_id}")
        print(f"  关联文件: {[f['file_name'] for f in f_list]}")
        sections = load_sections(engine, doc_id)
        print(f"  section_document 记录数: {len(sections)}")
        if not sections:
            print("  （无 section 记录，可能尚未走完 split 阶段）\n")
            continue

        section_ids = [s["section_id"] for s in sections]
        data_map = load_section_data(client, section_ids)
        print(f"  section_data 命中数: {len(data_map)} / {len(section_ids)}")

        # 一致性检查：parent_section_id 是否都指向集合内
        known = set(section_ids)
        dangling = [
            s["section_id"]
            for s in sections
            if s.get("parent_section_id") and s["parent_section_id"] not in known
        ]
        if dangling:
            print(f"  ⚠️ 有 {len(dangling)} 个 section 的 parent_section_id 指向集合外: {dangling[:3]}")

        # 一致性检查：Mongo parent_section_id vs MySQL parent_section_id
        mismatch = []
        for s in sections:
            m_parent = (data_map.get(s["section_id"], {}) or {}).get("parent_section_id")
            sql_parent = s.get("parent_section_id")
            if m_parent is not None and m_parent != sql_parent:
                mismatch.append((s["section_id"], sql_parent, m_parent))
        if mismatch:
            print(f"  ⚠️ MySQL/Mongo parent_section_id 不一致条数: {len(mismatch)}")
            for sid, sp, mp in mismatch[:3]:
                print(f"     {sid}: mysql={sp} mongo={mp}")

        roots, children, by_id = build_tree(sections, data_map)
        print(f"  根 section 数: {len(roots)}")
        print("  Section 树:")
        lines: List[str] = []
        # 多根时按 level+title 排序尽量稳定
        def _sort_key(sid):
            m = by_id.get(sid, {})
            d = data_map.get(sid, {}) or {}
            return (m.get("text_level") or 999, (d.get("text") or ""))
        for root in sorted(roots, key=_sort_key):
            render(root, children, by_id, data_map, 0, lines)
        for ln in lines:
            print("    " + ln)
        print()

    client.close()


if __name__ == "__main__":
    main()
