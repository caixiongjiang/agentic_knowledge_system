#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
文档分块效果查看工具

根据 document_id 从三层数据库中查询 Chunk 和 Section 的完整信息，
按类型分类写入 Markdown 文件，方便查看分块效果。

数据来源：
  - MySQL: chunk_section_document（关系表）、section_document（关系表）、
           chunk_meta_info（Chunk元信息）、section_meta_info（Section元信息）
  - MongoDB: chunk_data（Chunk文本内容）、section_data（Section文本内容）

输出文件：
  tmp_results/document_split/<document_id>.md

用法：
    # 使用默认 document_id
    uv run python test/index/split/test_document_split.py

    # 指定 document_id
    DOCUMENT_ID=doc_xxxx uv run python test/index/split/test_document_split.py
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

OUTPUT_DIR = project_root / "tmp_results" / "document_split"


async def fetch_document_split_data(document_id: str) -> Dict[str, Any]:
    """从三层数据库中查询指定文档的所有分块数据

    Args:
        document_id: 文档ID

    Returns:
        包含所有查询结果的字典
    """
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    from src.db.mysql.connection import get_mysql_manager

    await get_mongodb_manager()
    mysql_manager = get_mysql_manager()

    # ========== 1. MySQL: 查询关系和元信息 ==========
    from src.db.mysql.repositories.base.chunk_section_document_repo import chunk_section_document_repo
    from src.db.mysql.repositories.base.section_document_repo import section_document_repo
    from src.db.mysql.repositories.base.chunk_meta_info_repo import chunk_meta_info_repo
    from src.db.mysql.repositories.base.section_meta_info_repo import section_meta_info_repo
    from src.db.mysql.repositories.base.element_meta_info_repo import element_meta_info_repo

    with mysql_manager.get_session() as session:
        chunk_relations = chunk_section_document_repo.get_by_document_id(session, document_id)
        section_relations = section_document_repo.get_by_document_id(session, document_id)

        chunk_ids = [r.chunk_id for r in chunk_relations]
        section_ids = [r.section_id for r in section_relations]

        chunk_meta_map: Dict[str, Any] = {}
        for cid in chunk_ids:
            meta = chunk_meta_info_repo.get_by_id(session, cid)
            if meta:
                chunk_meta_map[cid] = meta

        section_meta_map: Dict[str, Any] = {}
        for sid in section_ids:
            meta = section_meta_info_repo.get_by_id(session, sid)
            if meta:
                section_meta_map[sid] = meta

        # 查询该文档所有 element 的 (page_index, element_index)
        # element_index 是页面内序号（每页从 0 开始），需要配合 page_index 排序
        all_elements = element_meta_info_repo.get_by_document_id(session, document_id)
        element_order_map: Dict[str, tuple] = {
            e.element_id: (e.page_index or 0, e.element_index)
            for e in all_elements
        }

    # 构建关系映射
    chunk_to_section: Dict[str, Optional[str]] = {}
    chunk_to_parent: Dict[str, Optional[str]] = {}
    for r in chunk_relations:
        chunk_to_section[r.chunk_id] = r.section_id
        chunk_to_parent[r.chunk_id] = r.parent_chunk_id

    section_to_parent: Dict[str, Optional[str]] = {}
    for r in section_relations:
        section_to_parent[r.section_id] = r.parent_section_id

    # ========== 2. MongoDB: 查询文本内容 ==========
    # 注意：chunk/section ID 是 "chunk-<uuid>" / "section-<uuid>" 格式（非 ObjectId），
    # ChunkDataRepository.get_by_ids 会尝试转 PydanticObjectId 导致静默丢弃，
    # 因此直接用 Beanie Model 查询。
    from src.db.mongodb.models.chunk_data import ChunkData
    from src.db.mongodb.models.section_data import SectionData

    chunk_data_list: List[Any] = []
    if chunk_ids:
        chunk_data_list = await ChunkData.find(
            {"_id": {"$in": chunk_ids}, "deleted": 0}
        ).to_list()

    section_data_list: List[Any] = []
    if section_ids:
        section_data_list = await SectionData.find(
            {"_id": {"$in": section_ids}, "deleted": 0}
        ).to_list()

    chunk_data_map: Dict[str, Any] = {str(c.id): c for c in chunk_data_list}
    section_data_map: Dict[str, Any] = {str(s.id): s for s in section_data_list}

    return {
        "document_id": document_id,
        "chunk_ids": chunk_ids,
        "section_ids": section_ids,
        "chunk_relations": chunk_relations,
        "section_relations": section_relations,
        "chunk_meta_map": chunk_meta_map,
        "section_meta_map": section_meta_map,
        "chunk_to_section": chunk_to_section,
        "chunk_to_parent": chunk_to_parent,
        "section_to_parent": section_to_parent,
        "chunk_data_map": chunk_data_map,
        "section_data_map": section_data_map,
        "element_order_map": element_order_map,
    }


def chunk_sort_key(
    chunk_id: str,
    chunk_meta_map: Dict[str, Any],
    element_order_map: Dict[str, tuple],
) -> tuple:
    """计算 chunk 的排序键

    排序策略：取 chunk 关联的所有 element 中最小的 (page_index, element_index)。
    element_index 是页面内序号（每页从 0 开始），必须配合 page_index 使用。
    同一个 buffer flush 切出的多个 chunk 共享相同 element_ids，此时无法区分先后，
    以 chunk_id 作为稳定性兜底。

    Args:
        chunk_id: chunk ID
        chunk_meta_map: chunk_id -> chunk_meta_info 映射
        element_order_map: element_id -> (page_index, element_index) 映射

    Returns:
        (page_index, min_element_index, chunk_id) 排序元组
    """
    meta = chunk_meta_map.get(chunk_id)
    if meta and hasattr(meta, "element_ids") and meta.element_ids:
        orders = [element_order_map[eid] for eid in meta.element_ids if eid in element_order_map]
        if orders:
            min_order = min(orders)
            return (min_order[0], min_order[1], chunk_id)
    page = meta.page_index if meta and hasattr(meta, "page_index") and meta.page_index is not None else 9999
    return (page, 9999, chunk_id)


def write_markdown(data: Dict[str, Any], output_path: Path) -> None:
    """将分块数据按页面顺序写入 Markdown 文件

    核心布局：按页面分组，页面内按 element_index 顺序交错展示
    Section（作为标题）和 Chunk（作为内容块），还原文档原始阅读流。

    Args:
        data: fetch_document_split_data 返回的数据
        output_path: 输出文件路径
    """
    lines: List[str] = []

    document_id = data["document_id"]
    chunk_ids = data["chunk_ids"]
    section_ids = data["section_ids"]
    chunk_meta_map = data["chunk_meta_map"]
    section_meta_map = data["section_meta_map"]
    chunk_to_section = data["chunk_to_section"]
    chunk_to_parent = data["chunk_to_parent"]
    section_to_parent = data["section_to_parent"]
    chunk_data_map = data["chunk_data_map"]
    section_data_map = data["section_data_map"]
    element_order_map = data["element_order_map"]

    lines.append("# 文档分块效果查看")
    lines.append("")
    lines.append(f"- **Document ID**: `{document_id}`")
    lines.append(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Section 数量**: {len(section_ids)}")
    lines.append(f"- **Chunk 数量**: {len(chunk_ids)}")
    lines.append("")

    # ========== Chunk 类型分布 ==========
    type_counter: Dict[str, int] = defaultdict(int)
    for cid in chunk_ids:
        meta = chunk_meta_map.get(cid)
        chunk_type = meta.chunk_type if meta and hasattr(meta, "chunk_type") else "unknown"
        type_counter[chunk_type or "unknown"] += 1

    lines.append("## Chunk 类型分布")
    lines.append("")
    lines.append("| 类型 | 数量 |")
    lines.append("|------|------|")
    for t, count in sorted(type_counter.items()):
        lines.append(f"| {t} | {count} |")
    lines.append("")

    # ========== 按页面顺序查看（主视图）==========
    lines.append("---")
    lines.append("")
    lines.append("## 按页面顺序查看")
    lines.append("")

    # 构建每页的 item 列表: (element_index, priority, item_type, item_id)
    # priority: 0=section（同一 element_index 下标题先于内容）, 1=chunk
    page_items: Dict[int, List[tuple]] = defaultdict(list)

    for sid in section_ids:
        meta = section_meta_map.get(sid)
        if meta and hasattr(meta, "element_id") and meta.element_id:
            order = element_order_map.get(meta.element_id)
            if order:
                page_items[order[0]].append((order[1], 0, "section", sid))
                continue
        page = 9999
        if meta and hasattr(meta, "start_page_index") and meta.start_page_index is not None:
            page = meta.start_page_index
        page_items[page].append((9999, 0, "section", sid))

    for cid in chunk_ids:
        key = chunk_sort_key(cid, chunk_meta_map, element_order_map)
        page_items[key[0]].append((key[1], 1, "chunk", cid))

    def _format_element_range(item_id: str, item_type: str) -> str:
        """格式化 element 顺序信息"""
        if item_type == "section":
            meta = section_meta_map.get(item_id)
            if meta and hasattr(meta, "element_id") and meta.element_id:
                order = element_order_map.get(meta.element_id)
                if order:
                    return f"elem[{order[1]}]"
            return ""
        meta = chunk_meta_map.get(item_id)
        if not (meta and hasattr(meta, "element_ids") and meta.element_ids):
            return ""
        orders = [element_order_map[eid] for eid in meta.element_ids if eid in element_order_map]
        if not orders:
            return ""
        indices = sorted(set(o[1] for o in orders))
        if len(indices) == 1:
            return f"elem[{indices[0]}]"
        if len(indices) <= 3:
            return f"elem[{','.join(str(i) for i in indices)}]"
        return f"elem[{indices[0]}..{indices[-1]}]"

    global_chunk_counter = 0

    for page_num in sorted(page_items.keys()):
        items = sorted(
            page_items[page_num],
            key=lambda x: (x[0], x[1], x[3]),
        )

        lines.append(f"### Page {page_num}")
        lines.append("")

        for _elem_idx, _, item_type, item_id in items:
            if item_type == "section":
                section_data = section_data_map.get(item_id)
                section_meta = section_meta_map.get(item_id)

                title = section_data.text if section_data and section_data.text else "(无标题)"

                heading_depth = 4
                if section_meta and hasattr(section_meta, "text_level") and section_meta.text_level is not None:
                    heading_depth = min(section_meta.text_level + 3, 6)
                heading_prefix = "#" * heading_depth

                lines.append(f"{heading_prefix} {title}")
                lines.append("")

                meta_parts = [f"`{item_id}`"]
                if section_meta:
                    if hasattr(section_meta, "text_level") and section_meta.text_level is not None:
                        meta_parts.append(f"H{section_meta.text_level}")
                    if hasattr(section_meta, "start_page_index") and section_meta.start_page_index is not None:
                        page_range = f"P{section_meta.start_page_index}"
                        if hasattr(section_meta, "end_page_index") and section_meta.end_page_index is not None:
                            page_range += f"-P{section_meta.end_page_index}"
                        meta_parts.append(page_range)
                elem_info = _format_element_range(item_id, "section")
                if elem_info:
                    meta_parts.append(elem_info)
                parent_sid = section_to_parent.get(item_id)
                if parent_sid:
                    parent_data = section_data_map.get(parent_sid)
                    if parent_data and parent_data.text:
                        meta_parts.append(f"parent: {parent_data.text[:30]}")

                lines.append(f"> {' | '.join(meta_parts)}")
                lines.append("")

            else:
                global_chunk_counter += 1
                chunk_data = chunk_data_map.get(item_id)
                chunk_meta = chunk_meta_map.get(item_id)

                chunk_type = chunk_meta.chunk_type if chunk_meta and hasattr(chunk_meta, "chunk_type") else "unknown"
                elem_info = _format_element_range(item_id, "chunk")
                section_id = chunk_to_section.get(item_id)
                section_data = section_data_map.get(section_id) if section_id else None

                summary_parts = [f"[{chunk_type}] Chunk {global_chunk_counter}", f"`{item_id}`"]
                if elem_info:
                    summary_parts.append(elem_info)
                if section_data and section_data.text:
                    summary_parts.append(f"§ {section_data.text[:40]}")
                parent_id = chunk_to_parent.get(item_id)
                if parent_id:
                    summary_parts.append(f"parent: `{parent_id}`")

                lines.append("<details>")
                lines.append(f"<summary>{' | '.join(summary_parts)}</summary>")
                lines.append("")

                if chunk_data and chunk_data.text:
                    text = chunk_data.text
                    if chunk_type in ("table", "code_block"):
                        lines.append("```")
                        lines.append(text)
                        lines.append("```")
                    else:
                        lines.append(text)
                else:
                    lines.append("*(无文本内容)*")

                if chunk_data and hasattr(chunk_data, "summary") and chunk_data.summary:
                    lines.append("")
                    lines.append(f"> **摘要**: {chunk_data.summary}")

                lines.append("")
                lines.append("</details>")
                lines.append("")

    # ========== 按类型汇总（辅助视图）==========
    lines.append("---")
    lines.append("")
    lines.append("## 全部 Chunk 按类型汇总")
    lines.append("")

    def _sort_all_chunks(cids: List[str]) -> List[str]:
        return sorted(cids, key=lambda c: chunk_sort_key(c, chunk_meta_map, element_order_map))

    all_typed: Dict[str, List[str]] = defaultdict(list)
    for cid in chunk_ids:
        meta = chunk_meta_map.get(cid)
        chunk_type = meta.chunk_type if meta and hasattr(meta, "chunk_type") else "unknown"
        all_typed[chunk_type or "unknown"].append(cid)

    type_order = ["text", "code_block", "table", "image"]
    all_types_sorted = sorted(all_typed.keys(), key=lambda t: (type_order.index(t) if t in type_order else 99, t))

    for chunk_type in all_types_sorted:
        cids = _sort_all_chunks(all_typed[chunk_type])
        lines.append(f"### {chunk_type} ({len(cids)} 个)")
        lines.append("")

        for i, cid in enumerate(cids, 1):
            chunk_data = chunk_data_map.get(cid)
            chunk_meta = chunk_meta_map.get(cid)
            section_id = chunk_to_section.get(cid)
            section_data = section_data_map.get(section_id) if section_id else None

            meta_info = [f"`{cid}`"]
            if chunk_meta and hasattr(chunk_meta, "page_index") and chunk_meta.page_index is not None:
                meta_info.append(f"P{chunk_meta.page_index}")
            elem_info = _format_element_range(cid, "chunk")
            if elem_info:
                meta_info.append(elem_info)
            if section_data and section_data.text:
                meta_info.append(f"Section: {section_data.text[:30]}")

            text_preview = ""
            if chunk_data and chunk_data.text:
                text_preview = chunk_data.text[:80].replace("\n", " ")
                if len(chunk_data.text) > 80:
                    text_preview += "..."

            lines.append(f"{i}. {' | '.join(meta_info)}")
            if text_preview:
                lines.append(f"   > {text_preview}")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown 文件已写入: {output_path}")


async def main() -> None:
    document_id = os.getenv("DOCUMENT_ID", "")
    if not document_id:
        print("请通过环境变量 DOCUMENT_ID 指定文档ID，例如:")
        print("  DOCUMENT_ID=doc_xxxx uv run python test/index/split/test_document_split.py")
        sys.exit(1)

    print(f"查询文档: {document_id}")
    print("=" * 60)

    data = await fetch_document_split_data(document_id)

    print(f"  Section 数量: {len(data['section_ids'])}")
    print(f"  Chunk 数量:   {len(data['chunk_ids'])}")
    print(f"  Element 数量: {len(data['element_order_map'])}")
    print(f"  MongoDB Chunk 文本:   {len(data['chunk_data_map'])} 条")
    print(f"  MongoDB Section 文本: {len(data['section_data_map'])} 条")

    output_path = OUTPUT_DIR / f"{document_id}.md"
    write_markdown(data, output_path)

    print("=" * 60)
    print("完成!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(1)
    except Exception as e:
        print(f"执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    """
    使用方式：
    DOCUMENT_ID=doc_xxxx uv run python test/index/split/test_document_split.py
    """
