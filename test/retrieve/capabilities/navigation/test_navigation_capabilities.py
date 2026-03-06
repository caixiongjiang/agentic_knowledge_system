#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_navigation_capabilities.py
@Author  : caixiongjiang
@Date    : 2026/03/05
@Function: 
    结构化导航与上下文游走能力 端到端测试
    - 连接真实 MySQL + MongoDB
    - 使用数据库中已有的文档数据（无需插入/清理）
    - 依次测试 Skeleton / DrillDown / ContextWindow / RollUp
    - 所有检索到的完整文本内容写入 Markdown 报告文件，供与原始 PDF 对比
    - image/table 类型的 Chunk 展示图片描述、表格内容等信息
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import ast
import asyncio
import traceback
import logging
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

REPORT_DIR = project_root / "test" / "retrieve" / "capabilities" / "navigation"
REPORT_PATH = REPORT_DIR / "navigation_test_report.md"

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# ==================== 辅助：Chunk 类型信息补充 ====================


def _build_chunk_meta_map(
    mysql_manager: Any,
    chunk_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    """从 MySQL ChunkMetaInfo 批量获取 chunk_type 和 image 元数据

    Returns:
        {chunk_id: {"chunk_type": str, "image_file_path": str|None, ...}}
    """
    from src.db.mysql.repositories.base.chunk_meta_info_repo import ChunkMetaInfoRepository
    repo = ChunkMetaInfoRepository()
    result: Dict[str, Dict[str, Any]] = {}
    with mysql_manager.get_session() as session:
        for cid in chunk_ids:
            meta = repo.get_by_id(session, cid)
            if meta:
                result[cid] = {
                    "chunk_type": meta.chunk_type or "unknown",
                    "image_file_path": meta.image_file_path,
                    "image_file_name": meta.image_file_name,
                    "bucket_name": meta.bucket_name,
                }
            else:
                result[cid] = {"chunk_type": "unknown"}
    return result


async def _build_chunk_summary_map(chunk_ids: List[str]) -> Dict[str, Optional[str]]:
    """从 MongoDB ChunkData 批量获取 summary 字段"""
    from src.db.mongodb.repositories.chunk_data_repository import ChunkDataRepository
    repo = ChunkDataRepository()
    data_list = await repo.get_by_ids(chunk_ids)
    return {str(cd.id): cd.summary for cd in data_list}


def _format_element_content(element_type: Optional[str], raw_content: Optional[str]) -> str:
    """根据 element 类型将 content dict 格式化为可读文本

    ElementData.content 在能力层被 str() 序列化，这里尝试解析并格式化。
    """
    if not raw_content:
        return "(空)"

    try:
        content_dict = ast.literal_eval(raw_content)
    except (ValueError, SyntaxError):
        return raw_content

    if not isinstance(content_dict, dict):
        return raw_content

    parts: List[str] = []

    if element_type == "text":
        text = content_dict.get("text", "")
        return text if text else "(空文本)"

    elif element_type == "image":
        captions = content_dict.get("image_caption", [])
        footnotes = content_dict.get("image_footnote", [])
        if captions:
            parts.append("[图片标题]")
            for c in captions:
                parts.append(f"  {c}")
        if footnotes:
            parts.append("[图片脚注]")
            for f in footnotes:
                parts.append(f"  {f}")
        if not parts:
            parts.append("(图片无文本描述)")
        return "\n".join(parts)

    elif element_type == "table":
        captions = content_dict.get("table_caption", [])
        footnotes = content_dict.get("table_footnote", [])
        body = content_dict.get("table_body", "")
        if captions:
            parts.append("[表格标题]")
            for c in captions:
                parts.append(f"  {c}")
        if body:
            parts.append("[表格内容]")
            parts.append(body)
        if footnotes:
            parts.append("[表格脚注]")
            for f in footnotes:
                parts.append(f"  {f}")
        if not parts:
            parts.append("(表格无内容)")
        return "\n".join(parts)

    elif element_type == "discarded":
        text = content_dict.get("text", "")
        return f"[已丢弃] {text}" if text else "(已丢弃，无文本)"

    return raw_content


# ==================== ReportWriter ====================


class ReportWriter:
    """将测试结果写入 Markdown 报告"""

    def __init__(self) -> None:
        self._buf = StringIO()
        self._pass_count = 0
        self._fail_count = 0

    def h1(self, text: str) -> None:
        self._buf.write(f"# {text}\n\n")

    def h2(self, text: str) -> None:
        self._buf.write(f"## {text}\n\n")

    def h3(self, text: str) -> None:
        self._buf.write(f"### {text}\n\n")

    def h4(self, text: str) -> None:
        self._buf.write(f"#### {text}\n\n")

    def meta(self, key: str, value: str) -> None:
        self._buf.write(f"- **{key}**: {value}\n")

    def meta_end(self) -> None:
        self._buf.write("\n")

    def text(self, content: str) -> None:
        self._buf.write(f"{content}\n\n")

    def divider(self) -> None:
        self._buf.write("---\n\n")

    def full_text_block(self, label: str, content: str) -> None:
        self._buf.write(f"**{label}**\n\n")
        self._buf.write("```\n")
        self._buf.write(content if content else "(空)")
        self._buf.write("\n```\n\n")

    def write_chunk(
        self,
        idx: int,
        chunk_id: str,
        score: float,
        text: Optional[str],
        section_id: Optional[str],
        chunk_meta: Optional[Dict[str, Any]],
        summary: Optional[str] = None,
        extra_meta: Optional[Dict[str, str]] = None,
    ) -> None:
        """写入一个完整的 Chunk 条目，自动处理不同类型"""
        self.h4(f"Chunk #{idx} — `{chunk_id}`")
        self.meta("score", f"{score:.3f}")
        if section_id:
            self.meta("section_id", f"`{section_id}`")

        chunk_type = "unknown"
        if chunk_meta:
            chunk_type = chunk_meta.get("chunk_type", "unknown")
            self.meta("chunk_type", chunk_type)
            if chunk_type == "image":
                img_path = chunk_meta.get("image_file_path") or ""
                img_name = chunk_meta.get("image_file_name") or ""
                bucket = chunk_meta.get("bucket_name") or ""
                if img_name:
                    self.meta("image_file", f"`{img_name}`")
                if img_path:
                    self.meta("image_path", f"`{bucket}/{img_path}`" if bucket else f"`{img_path}`")

        if extra_meta:
            for k, v in extra_meta.items():
                self.meta(k, v)
        self.meta_end()

        if text:
            self.full_text_block("Chunk 完整文本", text)
        elif chunk_type == "image":
            img_info = f"[图片类型 Chunk] 文本内容为空，图片存储在对象存储中"
            if summary:
                img_info += f"\n\n图片摘要: {summary}"
            self.full_text_block("Chunk 内容（图片）", img_info)
        elif summary:
            self.full_text_block("Chunk 摘要", summary)
        else:
            self.full_text_block("Chunk 完整文本", "(无文本内容)")

    def write_element(
        self,
        idx: int,
        element_id: str,
        score: float,
        element_type: Optional[str],
        page_index: Optional[int],
        element_index: Optional[int],
        raw_content: Optional[str],
    ) -> None:
        """写入一个完整的 Element 条目，按类型格式化内容"""
        self.h4(f"Element #{idx} — `{element_id}`")
        self.meta("type", element_type or "unknown")
        self.meta("page_index", str(page_index))
        self.meta("element_index", str(element_index))
        self.meta_end()

        formatted = _format_element_content(element_type, raw_content)
        label = {
            "text": "文本内容",
            "image": "图片描述",
            "table": "表格内容",
            "discarded": "丢弃内容",
        }.get(element_type or "", "Element 内容")
        self.full_text_block(label, formatted)

    def tree_node(self, title: str, level: int, chunk_count: int, section_id: str, depth: int = 0) -> None:
        indent = "  " * depth
        self._buf.write(f"{indent}- **[L{level}]** {title}  _(chunks: {chunk_count}, id: `{section_id}`)_\n")

    def record_pass(self, name: str) -> None:
        self._pass_count += 1
        print(f"  [PASS] {name}")

    def record_fail(self, name: str, err: str) -> None:
        self._fail_count += 1
        print(f"  [FAIL] {name}: {err}")
        self._buf.write(f"> **FAIL**: {err}\n\n")

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._buf.getvalue(), encoding="utf-8")
        print(f"\n  报告已写入: {path}")
        print(f"  通过: {self._pass_count}, 失败: {self._fail_count}")


# ==================== 数据库初始化 ====================


async def init_databases():
    from src.db.mysql.connection.factory import get_mysql_manager
    mysql_manager = get_mysql_manager()

    from src.db.mongodb.mongodb_manager import MongoDBManager
    await MongoDBManager.get_instance()

    return mysql_manager


# ==================== 数据发现 ====================


async def discover_data(mysql_manager: Any, rw: ReportWriter) -> Optional[dict]:
    from src.db.mysql.repositories.base.chunk_section_document_repo import ChunkSectionDocumentRepository
    from src.db.mysql.repositories.base.section_document_repo import SectionDocumentRepository
    from src.db.mysql.repositories.base.chunk_meta_info_repo import ChunkMetaInfoRepository

    chunk_rel_repo = ChunkSectionDocumentRepository()
    section_doc_repo = SectionDocumentRepository()
    chunk_meta_repo = ChunkMetaInfoRepository()

    with mysql_manager.get_session() as session:
        from src.db.mysql.models.base.section_document import SectionDocument
        first = session.query(SectionDocument).filter(SectionDocument.deleted == 0).first()
        if not first:
            return None
        document_id = first.document_id

        section_rels = section_doc_repo.get_by_document_id(session, document_id)
        section_ids = [r.section_id for r in section_rels]

        chunk_rels = chunk_rel_repo.get_by_document_id(session, document_id)
        chunk_ids = [r.chunk_id for r in chunk_rels]

        test_section_id = section_ids[0] if section_ids else None
        section_chunks: List[str] = []
        if test_section_id:
            sc = chunk_rel_repo.get_by_section_id(session, test_section_id)
            section_chunks = [r.chunk_id for r in sc]

        test_chunk_id = chunk_ids[0] if chunk_ids else None
        element_ids: List[str] = []
        if test_chunk_id:
            cm = chunk_meta_repo.get_by_id(session, test_chunk_id)
            if cm and cm.element_ids:
                element_ids = cm.element_ids

        test_element_id = element_ids[0] if element_ids else None

    rw.h2("测试数据概览")
    rw.meta("document_id", f"`{document_id}`")
    rw.meta("test_section_id", f"`{test_section_id}`")
    rw.meta("test_chunk_id", f"`{test_chunk_id}`")
    rw.meta("test_element_id", f"`{test_element_id}`")
    rw.meta("总 Section 数", str(len(section_ids)))
    rw.meta("总 Chunk 数", str(len(chunk_ids)))
    rw.meta_end()
    rw.divider()

    return {
        "document_id": document_id,
        "section_ids": section_ids,
        "chunk_ids": chunk_ids,
        "test_section_id": test_section_id,
        "section_chunks": section_chunks,
        "test_chunk_id": test_chunk_id,
        "element_ids": element_ids,
        "test_element_id": test_element_id,
    }


# ==================== Skeleton ====================


async def test_skeleton(mysql_manager: Any, data: dict, rw: ReportWriter) -> bool:
    rw.h2("1. Skeleton — 文档骨架/目录树提取")
    from src.retrieve.capabilities.navigation import Skeleton
    from src.retrieve.types.query import NavigationQuery
    from src.retrieve.types.enums import GranularityLevel

    try:
        skeleton = Skeleton(mysql_manager=mysql_manager)
        query = NavigationQuery(
            anchor_id=data["document_id"],
            anchor_type=GranularityLevel.DOCUMENT,
            max_depth=5,
        )
        result = await skeleton.execute(query=query)
        item = result.items[0]

        rw.meta("文档标题", item.title or "(无)")
        rw.meta("总 Section 数", str(item.total_sections))
        rw.meta("总 Chunk 数", str(item.total_chunks))
        rw.meta("耗时", f"{result.execution_time_ms:.1f}ms")
        rw.meta_end()

        rw.h3("文档目录树")

        def write_tree(nodes: list, depth: int = 0) -> None:
            for node in nodes:
                rw.tree_node(
                    title=node.title or "[未命名]",
                    level=node.level,
                    chunk_count=node.chunk_count,
                    section_id=node.section_id,
                    depth=depth,
                )
                if node.children:
                    write_tree(node.children, depth + 1)

        write_tree(item.outline_tree)
        rw._buf.write("\n")
        rw.divider()
        rw.record_pass("Skeleton")
        return True

    except Exception as e:
        rw.record_fail("Skeleton", str(e))
        traceback.print_exc()
        return False


# ==================== DrillDown ====================


async def test_drill_down(mysql_manager: Any, data: dict, rw: ReportWriter) -> bool:
    rw.h2("2. DrillDown — 跨粒度下钻")
    from src.retrieve.capabilities.navigation import DrillDown
    from src.retrieve.types.query import NavigationQuery
    from src.retrieve.types.enums import GranularityLevel, ElementType

    drill = DrillDown(mysql_manager=mysql_manager)
    ok = True

    # ---- Document → Section ----
    try:
        rw.h3("2.1 Document → Section（按阅读顺序）")
        query = NavigationQuery(
            anchor_id=data["document_id"],
            anchor_type=GranularityLevel.DOCUMENT,
            target_granularity=GranularityLevel.SECTION,
            include_content=True,
        )
        result = await drill.execute(query=query)
        rw.meta("返回数量", str(result.total_count))
        rw.meta("耗时", f"{result.execution_time_ms:.1f}ms")
        rw.meta_end()

        for i, item in enumerate(result.items):
            rw.h4(f"Section #{i+1} — `{item.section_id}`")
            rw.meta("score", f"{item.score:.3f}")
            rw.meta("text_level", str(item.metadata.get("text_level", "N/A")))
            rw.meta_end()
            rw.full_text_block("Section 标题/内容", item.title or "(无内容)")

        rw.record_pass("DrillDown: Document → Section")
    except Exception as e:
        rw.record_fail("DrillDown: Document → Section", str(e))
        ok = False

    # ---- Document → Chunk ----
    try:
        rw.h3("2.2 Document → Chunk（按阅读顺序，完整文本）")
        query = NavigationQuery(
            anchor_id=data["document_id"],
            anchor_type=GranularityLevel.DOCUMENT,
            target_granularity=GranularityLevel.CHUNK,
            include_content=True,
        )
        result = await drill.execute(query=query)
        rw.meta("返回数量", str(result.total_count))
        rw.meta("耗时", f"{result.execution_time_ms:.1f}ms")
        rw.meta_end()

        chunk_ids = [item.chunk_id for item in result.items]
        meta_map = _build_chunk_meta_map(mysql_manager, chunk_ids)
        summary_map = await _build_chunk_summary_map(chunk_ids)

        for i, item in enumerate(result.items):
            rw.write_chunk(
                idx=i + 1,
                chunk_id=item.chunk_id,
                score=item.score,
                text=item.text,
                section_id=item.section_id,
                chunk_meta=meta_map.get(item.chunk_id),
                summary=summary_map.get(item.chunk_id),
            )

        rw.record_pass("DrillDown: Document → Chunk")
    except Exception as e:
        rw.record_fail("DrillDown: Document → Chunk", str(e))
        ok = False

    # ---- Document → Element ----
    try:
        rw.h3("2.3 Document → Element（按页码排序）")
        query = NavigationQuery(
            anchor_id=data["document_id"],
            anchor_type=GranularityLevel.DOCUMENT,
            target_granularity=GranularityLevel.ELEMENT,
            include_content=True,
        )
        result = await drill.execute(query=query)
        rw.meta("返回数量", str(result.total_count))
        rw.meta("耗时", f"{result.execution_time_ms:.1f}ms")
        rw.meta_end()

        type_counts: dict = {}
        for item in result.items:
            t = item.element_type or "unknown"
            type_counts[t] = type_counts.get(t, 0) + 1
        rw.text("**Element 类型分布**: " + ", ".join(f"{t}: {c}" for t, c in sorted(type_counts.items())))

        for i, item in enumerate(result.items):
            rw.write_element(
                idx=i + 1,
                element_id=item.element_id,
                score=item.score,
                element_type=item.element_type,
                page_index=item.page_index,
                element_index=item.element_index,
                raw_content=item.content,
            )

        rw.record_pass("DrillDown: Document → Element")
    except Exception as e:
        rw.record_fail("DrillDown: Document → Element", str(e))
        ok = False

    # ---- Section → Chunk ----
    if data["test_section_id"]:
        try:
            rw.h3(f"2.4 Section → Chunk（Section: `{data['test_section_id']}`）")
            query = NavigationQuery(
                anchor_id=data["test_section_id"],
                anchor_type=GranularityLevel.SECTION,
                target_granularity=GranularityLevel.CHUNK,
                include_content=True,
            )
            result = await drill.execute(query=query)
            rw.meta("返回数量", str(result.total_count))
            rw.meta("耗时", f"{result.execution_time_ms:.1f}ms")
            rw.meta_end()

            cids = [item.chunk_id for item in result.items]
            meta_map = _build_chunk_meta_map(mysql_manager, cids)
            summary_map = await _build_chunk_summary_map(cids)

            for i, item in enumerate(result.items):
                rw.write_chunk(
                    idx=i + 1,
                    chunk_id=item.chunk_id,
                    score=item.score,
                    text=item.text,
                    section_id=item.section_id,
                    chunk_meta=meta_map.get(item.chunk_id),
                    summary=summary_map.get(item.chunk_id),
                )

            rw.record_pass("DrillDown: Section → Chunk")
        except Exception as e:
            rw.record_fail("DrillDown: Section → Chunk", str(e))
            ok = False

    # ---- Chunk → Element ----
    if data["test_chunk_id"]:
        try:
            rw.h3(f"2.5 Chunk → Element（Chunk: `{data['test_chunk_id']}`）")
            query = NavigationQuery(
                anchor_id=data["test_chunk_id"],
                anchor_type=GranularityLevel.CHUNK,
                target_granularity=GranularityLevel.ELEMENT,
                include_content=True,
            )
            result = await drill.execute(query=query)
            rw.meta("返回数量", str(result.total_count))
            rw.meta("耗时", f"{result.execution_time_ms:.1f}ms")
            rw.meta_end()

            for i, item in enumerate(result.items):
                rw.write_element(
                    idx=i + 1,
                    element_id=item.element_id,
                    score=item.score,
                    element_type=item.element_type,
                    page_index=item.page_index,
                    element_index=item.element_index,
                    raw_content=item.content,
                )

            rw.record_pass("DrillDown: Chunk → Element")
        except Exception as e:
            rw.record_fail("DrillDown: Chunk → Element", str(e))
            ok = False

    # ---- Document → Element (仅表格) ----
    try:
        rw.h3("2.6 Document → Element（仅 TABLE 类型）")
        query = NavigationQuery(
            anchor_id=data["document_id"],
            anchor_type=GranularityLevel.DOCUMENT,
            target_granularity=GranularityLevel.ELEMENT,
            element_type_filter=ElementType.TABLE,
            include_content=True,
        )
        result = await drill.execute(query=query)
        rw.meta("返回数量", str(result.total_count))
        rw.meta("耗时", f"{result.execution_time_ms:.1f}ms")
        rw.meta_end()

        for i, item in enumerate(result.items):
            rw.write_element(
                idx=i + 1,
                element_id=item.element_id,
                score=item.score,
                element_type=item.element_type,
                page_index=item.page_index,
                element_index=item.element_index,
                raw_content=item.content,
            )

        rw.record_pass("DrillDown: Document → Element (TABLE)")
    except Exception as e:
        rw.record_fail("DrillDown: Document → Element (TABLE)", str(e))
        ok = False

    rw.divider()
    return ok


# ==================== ContextWindow ====================


async def test_context_window(mysql_manager: Any, data: dict, rw: ReportWriter) -> bool:
    rw.h2("3. ContextWindow — 滑动窗口上下文扩充")
    from src.retrieve.capabilities.navigation import ContextWindow
    from src.retrieve.types.query import NavigationQuery
    from src.retrieve.types.enums import GranularityLevel, TraverseDirection
    from src.db.mysql.repositories.base.chunk_section_document_repo import ChunkSectionDocumentRepository

    chunk_rel_repo = ChunkSectionDocumentRepository()
    best_section_id: Optional[str] = None
    best_chunk_ids: List[str] = []

    with mysql_manager.get_session() as session:
        for sid in data["section_ids"]:
            rels = chunk_rel_repo.get_by_section_id(session, sid)
            if len(rels) > len(best_chunk_ids):
                best_chunk_ids = [r.chunk_id for r in rels]
                best_section_id = sid

    section_chunks = best_chunk_ids
    chosen_section_id = best_section_id

    if len(section_chunks) < 2:
        rw.text("所有 Section 的 Chunk 数不足，跳过此测试。")
        rw.divider()
        rw.record_pass("ContextWindow (跳过)")
        return True

    mid_idx = len(section_chunks) // 2
    anchor_chunk_id = section_chunks[mid_idx]
    ctx = ContextWindow(mysql_manager=mysql_manager)

    rw.meta("锚点 Chunk", f"`{anchor_chunk_id}`")
    rw.meta("所属 Section", f"`{chosen_section_id}`")
    rw.meta("Section 内 Chunk 总数", str(len(section_chunks)))
    rw.meta("锚点在 Section 中的位置", f"第 {mid_idx + 1} 个 (未排序)")
    rw.meta_end()

    ok = True

    async def _run_ctx_test(
        sub_title: str,
        direction: TraverseDirection,
        window_size: int,
        label_prefix: str,
    ) -> bool:
        try:
            rw.h3(sub_title)
            query = NavigationQuery(
                anchor_id=anchor_chunk_id,
                anchor_type=GranularityLevel.CHUNK,
                direction=direction,
                window_size=window_size,
                include_content=True,
            )
            result = await ctx.execute(query=query)
            rw.meta("返回数量", str(result.total_count))
            rw.meta("耗时", f"{result.execution_time_ms:.1f}ms")
            rw.meta_end()

            cids = [item.chunk_id for item in result.items]
            meta_map = _build_chunk_meta_map(mysql_manager, cids)
            summary_map = await _build_chunk_summary_map(cids)

            for i, item in enumerate(result.items):
                tag = " **← 锚点**" if item.chunk_id == anchor_chunk_id else ""
                rw.write_chunk(
                    idx=i + 1,
                    chunk_id=item.chunk_id,
                    score=item.score,
                    text=item.text,
                    section_id=None,
                    chunk_meta=meta_map.get(item.chunk_id),
                    summary=summary_map.get(item.chunk_id),
                    extra_meta={
                        "page_index (首 Element)": str(item.metadata.get("page_index", "N/A")),
                        "element_index (首 Element)": str(item.metadata.get("element_index", "N/A")),
                        "备注": tag.strip() if tag.strip() else "相邻 Chunk",
                    },
                )

            rw.record_pass(label_prefix)
            return True
        except Exception as e:
            rw.record_fail(label_prefix, str(e))
            traceback.print_exc()
            return False

    if not await _run_ctx_test("3.1 BOTH 方向 (window_size=3)", TraverseDirection.BOTH, 3, "ContextWindow: BOTH"):
        ok = False
    if not await _run_ctx_test("3.2 PREV 方向 (window_size=2)", TraverseDirection.PREV, 2, "ContextWindow: PREV"):
        ok = False
    if not await _run_ctx_test("3.3 NEXT 方向 (window_size=2)", TraverseDirection.NEXT, 2, "ContextWindow: NEXT"):
        ok = False

    rw.divider()
    return ok


# ==================== RollUp ====================


async def test_roll_up(mysql_manager: Any, data: dict, rw: ReportWriter) -> bool:
    rw.h2("4. RollUp — 跨粒度上溯")
    from src.retrieve.capabilities.navigation import RollUp
    from src.retrieve.types.query import NavigationQuery
    from src.retrieve.types.enums import GranularityLevel

    roll = RollUp(mysql_manager=mysql_manager)
    ok = True

    paths = [
        ("4.1", "Element → Chunk", data["test_element_id"], GranularityLevel.ELEMENT, GranularityLevel.CHUNK),
        ("4.2", "Element → Section", data["test_element_id"], GranularityLevel.ELEMENT, GranularityLevel.SECTION),
        ("4.3", "Element → Document", data["test_element_id"], GranularityLevel.ELEMENT, GranularityLevel.DOCUMENT),
        ("4.4", "Chunk → Section", data["test_chunk_id"], GranularityLevel.CHUNK, GranularityLevel.SECTION),
        ("4.5", "Chunk → Document", data["test_chunk_id"], GranularityLevel.CHUNK, GranularityLevel.DOCUMENT),
        ("4.6", "Section → Document", data["test_section_id"], GranularityLevel.SECTION, GranularityLevel.DOCUMENT),
    ]

    for num, label, anchor_id, anchor_type, target in paths:
        if not anchor_id:
            rw.h3(f"{num} {label} — 跳过（无可用锚点）")
            continue

        try:
            rw.h3(f"{num} {label}（锚点: `{anchor_id}`）")
            query = NavigationQuery(
                anchor_id=anchor_id,
                anchor_type=anchor_type,
                target_granularity=target,
                include_content=True,
            )
            result = await roll.execute(query=query)
            rw.meta("返回数量", str(result.total_count))
            rw.meta("耗时", f"{result.execution_time_ms:.1f}ms")
            rw.meta_end()

            for i, item in enumerate(result.items):
                if target == GranularityLevel.CHUNK:
                    cids = [item.chunk_id]
                    meta_map = _build_chunk_meta_map(mysql_manager, cids)
                    summary_map = await _build_chunk_summary_map(cids)
                    rw.write_chunk(
                        idx=i + 1,
                        chunk_id=item.chunk_id,
                        score=item.score,
                        text=item.text,
                        section_id=item.section_id,
                        chunk_meta=meta_map.get(item.chunk_id),
                        summary=summary_map.get(item.chunk_id),
                    )

                elif target == GranularityLevel.SECTION:
                    rw.h4(f"Section #{i+1} — `{item.section_id}`")
                    rw.meta("document_id", f"`{item.document_id}`" if item.document_id else "N/A")
                    rw.meta("text_level", str(item.metadata.get("text_level", "N/A")))
                    rw.meta_end()
                    rw.full_text_block("Section 标题/内容", item.title or "(无内容)")

                elif target == GranularityLevel.DOCUMENT:
                    rw.h4(f"Document — `{item.document_id}`")
                    rw.meta("title", item.title or "(无)")
                    rw.meta_end()
                    rw.full_text_block("文档摘要", item.summary or "(无摘要)")

            rw.record_pass(f"RollUp: {label}")
        except Exception as e:
            rw.record_fail(f"RollUp: {label}", str(e))
            traceback.print_exc()
            ok = False

    rw.text("\n> **跳过**: Link → Chunk（图谱相关，不在本次测试范围）")
    rw.divider()
    return ok


# ==================== 一致性验证 ====================


async def test_consistency(mysql_manager: Any, data: dict, rw: ReportWriter) -> bool:
    rw.h2("5. 一致性验证 — DrillDown ↔ RollUp 双向校验")
    from src.retrieve.capabilities.navigation import DrillDown, RollUp
    from src.retrieve.types.query import NavigationQuery
    from src.retrieve.types.enums import GranularityLevel

    drill = DrillDown(mysql_manager=mysql_manager)
    roll = RollUp(mysql_manager=mysql_manager)

    try:
        q = NavigationQuery(
            anchor_id=data["document_id"],
            anchor_type=GranularityLevel.DOCUMENT,
            target_granularity=GranularityLevel.SECTION,
            include_content=False,
        )
        drill_result = await drill.execute(query=q)
        drill_section_ids = [item.section_id for item in drill_result.items]

        rw.text(f"DrillDown: Document → {len(drill_section_ids)} 个 Section")

        mismatch = 0
        for sid in drill_section_ids[:5]:
            q2 = NavigationQuery(
                anchor_id=sid,
                anchor_type=GranularityLevel.SECTION,
                target_granularity=GranularityLevel.DOCUMENT,
                include_content=False,
            )
            r = await roll.execute(query=q2)
            if r.items and r.items[0].document_id != data["document_id"]:
                mismatch += 1
                rw.text(f"- **不一致**: Section `{sid}` 上溯到 `{r.items[0].document_id}`")

        if mismatch == 0:
            rw.text(f"所有 Section 上溯均回到原始 Document (验证了 {min(5, len(drill_section_ids))} 个)")

        if data["test_section_id"]:
            q3 = NavigationQuery(
                anchor_id=data["test_section_id"],
                anchor_type=GranularityLevel.SECTION,
                target_granularity=GranularityLevel.CHUNK,
                include_content=False,
            )
            cr = await drill.execute(query=q3)
            if cr.items:
                q4 = NavigationQuery(
                    anchor_id=cr.items[0].chunk_id,
                    anchor_type=GranularityLevel.CHUNK,
                    target_granularity=GranularityLevel.SECTION,
                    include_content=False,
                )
                rr = await roll.execute(query=q4)
                if rr.items and rr.items[0].section_id == data["test_section_id"]:
                    rw.text("Section → Chunk → Section 双向一致")
                else:
                    rw.text("Section → Chunk → Section **不一致**")
                    rw.record_fail("Consistency", "Section → Chunk → Section 不一致")
                    return False

        rw.divider()
        rw.record_pass("Consistency")
        return True

    except Exception as e:
        rw.record_fail("Consistency", str(e))
        traceback.print_exc()
        return False


# ==================== 入口 ====================


async def run_all_tests() -> None:
    print(f"\n{'='*60}")
    print("  结构化导航与上下文游走能力 — 端到端测试")
    print(f"{'='*60}")
    print(f"  报告将写入: {REPORT_PATH}")

    rw = ReportWriter()
    rw.h1("结构化导航与上下文游走能力 — 测试报告")
    rw.meta("生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    rw.meta("说明", "所有文本内容均为完整输出，可与原始 PDF 逐项对比。image 类型 Chunk 会标注类型和图片存储路径。")
    rw.meta_end()
    rw.divider()

    try:
        mysql_manager = await init_databases()
        print("  [OK] 数据库连接就绪")

        data = await discover_data(mysql_manager, rw)
        if data is None:
            print("  [FAIL] 数据库中没有可用的测试数据")
            return

        print("  [OK] 数据发现完成\n")
        print("  开始执行测试...")

        await test_skeleton(mysql_manager, data, rw)
        await test_drill_down(mysql_manager, data, rw)
        await test_context_window(mysql_manager, data, rw)
        await test_roll_up(mysql_manager, data, rw)
        await test_consistency(mysql_manager, data, rw)

    except Exception as e:
        print(f"  [FAIL] 未捕获异常: {e}")
        traceback.print_exc()

    rw.save(REPORT_PATH)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
