#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_enricher.py
@Author  : caixiongjiang
@Date    : 2026/05/14
@Function:
    Chunk 元数据补全器（Phase A：内联引用 UI）

    ChunkItem 自身只带 chunk_id / document_id / section_id / score / text，
    Citation 在前端要做"可点击 + 悬浮预览"必须额外补：
      - chunk_type   (text / image / table)        → 来自 ChunkMetaInfo
      - page_index   (int, 从 0 开始)              → 来自 ChunkMetaInfo
      - section_title                                → MongoDB SectionData.text
      - file_id      (用于跳转 /knowledge/file/N)  → WorkspaceFileSystem
      - file_name                                    → WorkspaceFileSystem
      - preview      (text[:200], 已可由调用方填)  → 不在本模块负责

    设计要点
    --------
    - **批量优先**：本模块只承担一次性批量查表，不做循环查 DB。
    - **跨库整合**：MySQL（chunk_meta_info / chunk_section_document /
      workspace_file_system）+ MongoDB（section_data）。
    - **多对一 document_id → file_id**：同 SHA256 文件在不同 KB 可能产出多
      条 (user_id, file_id) 记录共享同一 document_id。本模块按
      ``(user_id, knowledge_base_id, document_id)`` 精确匹配；若仍多条，取
      ``create_time`` 最早的一条（业务上即"最早入库的那份"）。
    - **错误隔离**：任何子查询失败都退化为 None 字段，不影响主流程；上层调
      用方按 Optional 兜底渲染。
@Modify History:
    2026-05-14 - 首版（Phase A: 内联引用）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from typing import Dict, List, Optional, Set

from loguru import logger
from pydantic import BaseModel

from src.db.mongodb.models.section_data import SectionData
from src.db.mysql.connection.factory import get_mysql_manager
from src.db.mysql.models.base.chunk_meta_info import ChunkMetaInfo
from src.db.mysql.models.base.chunk_section_document import ChunkSectionDocument
from src.db.mysql.models.business.workspace_file_system import WorkspaceFileSystem
from src.retrieve.types.result import ChunkItem


class ChunkMeta(BaseModel):
    """单个 chunk 的渲染元数据（enricher 返回值）"""

    chunk_id: str
    chunk_type: Optional[str] = None
    page_index: Optional[int] = None
    section_id: Optional[str] = None
    section_title: Optional[str] = None
    document_id: Optional[str] = None
    file_id: Optional[str] = None
    file_name: Optional[str] = None


async def enrich_chunks(
    chunks: List[ChunkItem],
    *,
    user_id: str,
    knowledge_base_id: Optional[str] = None,
) -> Dict[str, ChunkMeta]:
    """批量补全 chunk 的渲染元数据。

    Args:
        chunks: 待补全的 ChunkItem 列表（chunk_id / document_id / section_id 即可）。
        user_id: 当前对话用户，用于精确锁定 ``workspace_file_system`` 行。
        knowledge_base_id: 可选；进一步收敛多对一映射的歧义。

    Returns:
        ``chunk_id → ChunkMeta`` 的字典。**输入 chunk_id 一定能在结果里查到**
        （查不到的字段为 None）；用例代码可以直接 ``mapping[c.chunk_id]``。
    """
    if not chunks:
        return {}

    # 收敛输入：去重 + 收集所需 id 集合
    chunk_ids: List[str] = []
    seen_chunks: Set[str] = set()
    doc_ids: Set[str] = set()
    seed_section_by_chunk: Dict[str, str] = {}
    seed_doc_by_chunk: Dict[str, str] = {}
    for c in chunks:
        if c.chunk_id in seen_chunks:
            continue
        seen_chunks.add(c.chunk_id)
        chunk_ids.append(c.chunk_id)
        if c.section_id:
            seed_section_by_chunk[c.chunk_id] = c.section_id
        if c.document_id:
            seed_doc_by_chunk[c.chunk_id] = c.document_id
            doc_ids.add(c.document_id)

    # 初始化结果（先把 ChunkItem 已知的 section_id / document_id 兜底进去）
    out: Dict[str, ChunkMeta] = {
        cid: ChunkMeta(
            chunk_id=cid,
            section_id=seed_section_by_chunk.get(cid),
            document_id=seed_doc_by_chunk.get(cid),
        )
        for cid in chunk_ids
    }

    # ---- 1) MySQL: chunk_meta_info → chunk_type / page_index ----
    # ---- 2) MySQL: chunk_section_document → section_id / document_id（补 ChunkItem 漏的） ----
    # ---- 4) MySQL: workspace_file_system → file_id / file_name ----
    section_ids_needed: Set[str] = set(
        v for v in seed_section_by_chunk.values() if v
    )
    try:
        manager = get_mysql_manager()
        with manager.get_session() as db:
            # chunk_meta_info 批量
            metas = (
                db.query(ChunkMetaInfo)
                .filter(
                    ChunkMetaInfo.chunk_id.in_(chunk_ids),
                    ChunkMetaInfo.deleted == 0,
                )
                .all()
            )
            for m in metas:
                meta = out.get(m.chunk_id)
                if not meta:
                    continue
                meta.chunk_type = m.chunk_type
                meta.page_index = m.page_index

            # chunk_section_document 批量（用于补 ChunkItem 里缺失的 section_id / document_id）
            csds = (
                db.query(ChunkSectionDocument)
                .filter(
                    ChunkSectionDocument.chunk_id.in_(chunk_ids),
                    ChunkSectionDocument.deleted == 0,
                )
                .all()
            )
            for csd in csds:
                meta = out.get(csd.chunk_id)
                if not meta:
                    continue
                if not meta.section_id and csd.section_id:
                    meta.section_id = csd.section_id
                    section_ids_needed.add(csd.section_id)
                if not meta.document_id and csd.document_id:
                    meta.document_id = csd.document_id
                    doc_ids.add(csd.document_id)

            # workspace_file_system 批量：按 (user_id, document_id) 反查 file_id / file_name
            #
            # 同一 document_id 可能有多个 (file_id) 记录（不同 KB / 不同目录），
            # 这里以 (knowledge_base_id 优先) → create_time asc 排序后取首条。
            doc_to_file: Dict[str, WorkspaceFileSystem] = {}
            if doc_ids:
                q = db.query(WorkspaceFileSystem).filter(
                    WorkspaceFileSystem.user_id == user_id,
                    WorkspaceFileSystem.document_id.in_(doc_ids),
                    WorkspaceFileSystem.deleted == 0,
                )
                rows = q.order_by(WorkspaceFileSystem.create_time.asc()).all()
                # 优先匹配 knowledge_base_id；同 doc_id 多行时第一次写入即赢
                for row in rows:
                    if not row.document_id:
                        continue
                    if knowledge_base_id and row.knowledge_base_id != knowledge_base_id:
                        # 把"非匹配 KB"的也兜底放进去（KB 匹配的会在下一轮覆盖）
                        doc_to_file.setdefault(row.document_id, row)
                        continue
                    # KB 匹配：直接覆盖（KB 优先）
                    doc_to_file[row.document_id] = row

            for cid, meta in out.items():
                if meta.document_id and meta.document_id in doc_to_file:
                    fs = doc_to_file[meta.document_id]
                    meta.file_id = fs.file_id
                    meta.file_name = fs.file_name
    except Exception as e:  # noqa: BLE001
        logger.error(f"ChunkEnricher: MySQL 查询失败（忽略）: {e}")

    # ---- 3) MongoDB: section_data → section_title ----
    if section_ids_needed:
        try:
            section_docs = await SectionData.find(
                {"_id": {"$in": list(section_ids_needed)}}
            ).to_list()
            title_by_section: Dict[str, str] = {
                getattr(s, "id", None): (s.text or "")
                for s in section_docs
                if getattr(s, "id", None)
            }
            for meta in out.values():
                if meta.section_id and meta.section_id in title_by_section:
                    meta.section_title = title_by_section[meta.section_id] or None
        except Exception as e:  # noqa: BLE001
            logger.error(f"ChunkEnricher: MongoDB section_data 查询失败（忽略）: {e}")

    return out


class TurnEnrichCache:
    """单 turn 内的 chunk 元数据缓存。

    使用场景
    --------
    一次 chat turn 通常会触发两到三次 enrich 调用：

    - ``retrieval.done`` 帧需要把"初次检索的种子 chunks"提前 enrich 下发
      （方案 B 让前端 LLM 一吐引用就直接彩色 chip）；
    - 每轮 ``message.done`` 之前需要 enrich 全量 citations 落库；
    - 同一 turn 内不同轮 / 不同工具补充的 chunks 可能重叠。

    本类保证：**同 chunk_id 的 4 张表查询在一个 turn 内只跑一次**。

    线程模型：单 turn 异步串行运行，不需要锁。
    """

    def __init__(
        self,
        *,
        user_id: str,
        knowledge_base_id: Optional[str] = None,
    ) -> None:
        self._user_id = user_id
        self._kb_id = knowledge_base_id
        self._cache: Dict[str, ChunkMeta] = {}

    async def ensure(self, chunks: List[ChunkItem]) -> Dict[str, ChunkMeta]:
        """确保 ``chunks`` 中每个 chunk_id 都已 enrich 进缓存。

        Returns:
            **完整 chunk_id → ChunkMeta** 字典（包括本次新 enrich 的 + 缓存里已有的）。
        """
        if not chunks:
            return self._cache
        # 只对未在缓存中的 chunk 查表
        missing = [c for c in chunks if c.chunk_id not in self._cache]
        if missing:
            new_meta = await enrich_chunks(
                missing,
                user_id=self._user_id,
                knowledge_base_id=self._kb_id,
            )
            self._cache.update(new_meta)
        # 缩到只包含本次输入 chunks 对应的子集，避免上层无意中拿到无关项
        return {c.chunk_id: self._cache[c.chunk_id] for c in chunks if c.chunk_id in self._cache}

    def get(self, chunk_id: str) -> Optional[ChunkMeta]:
        return self._cache.get(chunk_id)

    @property
    def size(self) -> int:
        return len(self._cache)


__all__ = ["ChunkMeta", "enrich_chunks", "TurnEnrichCache"]
