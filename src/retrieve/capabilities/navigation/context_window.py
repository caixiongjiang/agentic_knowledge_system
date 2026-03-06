#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : context_window.py
@Author  : caixiongjiang
@Date    : 2026/03/05
@Function: 
    滑动窗口上下文扩充原子能力
    给定一个 Chunk 锚点，获取同一 Section 内前后相邻的 Chunk
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.db.mongodb.repositories.chunk_data_repository import ChunkDataRepository
from src.db.mysql.connection.base import BaseMySQLManager
from src.db.mysql.repositories.base.chunk_meta_info_repo import ChunkMetaInfoRepository
from src.db.mysql.repositories.base.chunk_section_document_repo import (
    ChunkSectionDocumentRepository,
)
from src.db.mysql.repositories.base.element_meta_info_repo import (
    ElementMetaInfoRepository,
)
from src.retrieve.capabilities.base import BaseCapability, CapabilityDescriptor
from src.retrieve.types.enums import TraverseDirection
from src.retrieve.types.query import NavigationQuery
from src.retrieve.types.result import ChunkItem, RetrieveResult


class ContextWindow(BaseCapability):
    """滑动窗口上下文扩充

    给定一个 chunk_id 锚点，获取同一 Section 内前后各 K 个相邻 Chunk。
    不跨越 Section 边界。

    Chunk 之间没有显式的 index 字段，顺序通过 chunk_meta_info.element_ids
    中第一个 Element 的 (page_index, element_index) 推导。
    """

    def __init__(
        self,
        mysql_manager: Optional[BaseMySQLManager] = None,
        chunk_rel_repo: Optional[ChunkSectionDocumentRepository] = None,
        chunk_meta_repo: Optional[ChunkMetaInfoRepository] = None,
        element_meta_repo: Optional[ElementMetaInfoRepository] = None,
        chunk_data_repo: Optional[ChunkDataRepository] = None,
    ) -> None:
        super().__init__()
        self._mysql_manager = mysql_manager
        self._chunk_rel_repo = chunk_rel_repo or ChunkSectionDocumentRepository()
        self._chunk_meta_repo = chunk_meta_repo or ChunkMetaInfoRepository()
        self._element_meta_repo = element_meta_repo or ElementMetaInfoRepository()
        self._chunk_data_repo = chunk_data_repo or ChunkDataRepository()

    def _get_mysql_manager(self) -> BaseMySQLManager:
        if self._mysql_manager is None:
            from src.db.mysql.connection.factory import get_mysql_manager
            self._mysql_manager = get_mysql_manager()
        return self._mysql_manager

    async def _do_execute(self, **kwargs: Any) -> RetrieveResult:
        query: NavigationQuery = kwargs["query"]
        anchor_id = query.anchor_id
        direction = query.direction
        window_size = query.window_size

        manager = self._get_mysql_manager()
        with manager.get_session() as session:
            anchor_rel = self._chunk_rel_repo.get_by_id(session, anchor_id)
            if not anchor_rel:
                raise ValueError(f"锚点 Chunk 不存在: {anchor_id}")

            section_id = anchor_rel.section_id
            if not section_id:
                return RetrieveResult(items=[], total_count=0)

            all_chunk_rels = self._chunk_rel_repo.get_by_section_id(
                session, section_id,
            )
            if not all_chunk_rels:
                return RetrieveResult(items=[], total_count=0)

            sorted_chunks = self._sort_chunks_by_element_position(
                session, all_chunk_rels,
            )

            anchor_pos = None
            for i, (chunk_id, _) in enumerate(sorted_chunks):
                if chunk_id == anchor_id:
                    anchor_pos = i
                    break

            if anchor_pos is None:
                return RetrieveResult(items=[], total_count=0)

            adjacent = self._select_adjacent(
                sorted_chunks, anchor_pos, direction, window_size,
            )

        items = self._build_items(adjacent, anchor_pos, sorted_chunks, window_size)

        if query.include_content:
            chunk_ids = [item.chunk_id for item in items]
            await self._enrich_content(items, chunk_ids)

        return RetrieveResult(items=items, total_count=len(items))

    def _get_chunk_sort_key(
        self, session: Session, chunk_id: str,
    ) -> Tuple[int, int, int]:
        """获取 Chunk 的排序键：(page_index, element_index, split_seq)

        - page_index / element_index 来自第一个关联 Element 的位置
        - split_seq 来自 chunk_meta_info，用于区分同一 Element 切分出的多个 Chunk
        """
        chunk_meta = self._chunk_meta_repo.get_by_id(session, chunk_id)
        if not chunk_meta or not chunk_meta.element_ids:
            return (999999, 999999, 999999)

        split_seq = chunk_meta.split_seq if chunk_meta.split_seq is not None else 0

        first_element_id = chunk_meta.element_ids[0]
        element_meta = self._element_meta_repo.get_by_id(session, first_element_id)
        if not element_meta:
            return (999999, 999999, split_seq)

        return (element_meta.page_index or 0, element_meta.element_index or 0, split_seq)

    def _sort_chunks_by_element_position(
        self, session: Session, chunk_rels: list,
    ) -> List[Tuple[str, Tuple[int, int, int]]]:
        """按 Element 位置 + split_seq 对 Section 内所有 Chunk 排序

        Returns:
            [(chunk_id, (page_index, element_index, split_seq)), ...] 按阅读顺序排列
        """
        keyed: List[Tuple[str, Tuple[int, int, int]]] = []
        for rel in chunk_rels:
            sort_key = self._get_chunk_sort_key(session, rel.chunk_id)
            keyed.append((rel.chunk_id, sort_key))

        keyed.sort(key=lambda x: x[1])
        return keyed

    def _select_adjacent(
        self,
        sorted_chunks: List[Tuple[str, Tuple[int, int, int]]],
        anchor_pos: int,
        direction: TraverseDirection,
        window_size: int,
    ) -> List[Tuple[str, Tuple[int, int, int]]]:
        """根据方向和窗口大小选取相邻 Chunk"""
        if direction == TraverseDirection.PREV:
            start = max(0, anchor_pos - window_size)
            return sorted_chunks[start:anchor_pos]
        elif direction == TraverseDirection.NEXT:
            end = min(len(sorted_chunks), anchor_pos + window_size + 1)
            return sorted_chunks[anchor_pos + 1:end]
        else:
            start = max(0, anchor_pos - window_size)
            end = min(len(sorted_chunks), anchor_pos + window_size + 1)
            return [
                c for i, c in enumerate(sorted_chunks[start:end])
                if (start + i) != anchor_pos
            ]

    def _build_items(
        self,
        adjacent: List[Tuple[str, Tuple[int, int, int]]],
        anchor_pos: int,
        sorted_chunks: List[Tuple[str, Tuple[int, int, int]]],
        window_size: int,
    ) -> List[ChunkItem]:
        items: List[ChunkItem] = []
        for chunk_id, sort_key in adjacent:
            chunk_pos = None
            for i, (cid, _) in enumerate(sorted_chunks):
                if cid == chunk_id:
                    chunk_pos = i
                    break

            if chunk_pos is not None:
                distance = abs(chunk_pos - anchor_pos)
                score = 1.0 - distance / (window_size + 1)
            else:
                score = 0.5

            items.append(ChunkItem(
                chunk_id=chunk_id,
                score=score,
                metadata={
                    "page_index": sort_key[0],
                    "element_index": sort_key[1],
                },
            ))
        return items

    async def _enrich_content(
        self, items: List[ChunkItem], chunk_ids: List[str],
    ) -> None:
        """从 MongoDB 批量获取 Chunk 文本内容并补全 document_id / section_id"""
        if not chunk_ids:
            return
        chunk_data_list = await self._chunk_data_repo.get_by_ids(chunk_ids)
        data_map: Dict[str, str] = {}
        for cd in chunk_data_list:
            data_map[str(cd.id)] = cd.text or ""
        for item in items:
            item.text = data_map.get(item.chunk_id)

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="context_window",
            display_name="滑动窗口上下文扩充",
            description=(
                "给定一个 Chunk 锚点，获取同一 Section 内前后相邻的 Chunk，"
                "用于阅读上下文补全。通过 Element 的 (page_index, element_index) "
                "推导 Chunk 顺序，不跨越 Section 边界。"
            ),
            input_schema={
                "anchor_id": "str - 锚点 Chunk ID",
                "anchor_type": "GranularityLevel.CHUNK",
                "direction": "TraverseDirection - PREV/NEXT/BOTH",
                "window_size": "int - 单方向窗口大小，默认 3",
                "include_content": "bool - 是否获取全文，默认 True",
            },
            output_type="RetrieveResult[ChunkItem]",
        )
