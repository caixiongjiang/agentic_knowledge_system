#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : drill_down.py
@Author  : caixiongjiang
@Date    : 2026/03/05
@Function: 
    跨粒度下钻原子能力
    从高粒度向低粒度展开（Document→Section→Chunk→Element）
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.db.mongodb.repositories.chunk_data_repository import ChunkDataRepository
from src.db.mongodb.repositories.element_data_repository import ElementDataRepository
from src.db.mongodb.repositories.section_data_repository import SectionDataRepository
from src.db.mysql.connection.base import BaseMySQLManager
from src.db.mysql.repositories.base.chunk_meta_info_repo import ChunkMetaInfoRepository
from src.db.mysql.repositories.base.chunk_section_document_repo import (
    ChunkSectionDocumentRepository,
)
from src.db.mysql.repositories.base.element_meta_info_repo import (
    ElementMetaInfoRepository,
)
from src.db.mysql.repositories.base.section_document_repo import (
    SectionDocumentRepository,
)
from src.db.mysql.repositories.base.section_meta_info_repo import (
    SectionMetaInfoRepository,
)
from src.retrieve.capabilities.base import BaseCapability, CapabilityDescriptor
from src.retrieve.types.enums import ElementType, GranularityLevel
from src.retrieve.types.query import NavigationQuery
from src.retrieve.types.result import (
    ChunkItem,
    ElementItem,
    RetrieveResult,
    SectionItem,
)

_GRANULARITY_RANK = {
    GranularityLevel.DOCUMENT: 4,
    GranularityLevel.SECTION: 3,
    GranularityLevel.CHUNK: 2,
    GranularityLevel.ELEMENT: 1,
    GranularityLevel.LINK: 0,
}


class DrillDown(BaseCapability):
    """跨粒度下钻

    从高粒度向低粒度展开：
    - Document → Section / Chunk / Element
    - Section  → Chunk / Element
    - Chunk    → Element

    排序规则：
    - Section 通过 section_meta_info.element_id 指向的标题 Element
      的 (page_index, element_index) 确定阅读顺序
    - Chunk 通过 chunk_meta_info.element_ids 中第一个 Element
      的 (page_index, element_index) 确定阅读顺序
    - Element 直接按 (page_index, element_index) 排序
    """

    def __init__(
        self,
        mysql_manager: Optional[BaseMySQLManager] = None,
        section_doc_repo: Optional[SectionDocumentRepository] = None,
        section_meta_repo: Optional[SectionMetaInfoRepository] = None,
        chunk_rel_repo: Optional[ChunkSectionDocumentRepository] = None,
        chunk_meta_repo: Optional[ChunkMetaInfoRepository] = None,
        element_meta_repo: Optional[ElementMetaInfoRepository] = None,
        section_data_repo: Optional[SectionDataRepository] = None,
        chunk_data_repo: Optional[ChunkDataRepository] = None,
        element_data_repo: Optional[ElementDataRepository] = None,
    ) -> None:
        super().__init__()
        self._mysql_manager = mysql_manager
        self._section_doc_repo = section_doc_repo or SectionDocumentRepository()
        self._section_meta_repo = section_meta_repo or SectionMetaInfoRepository()
        self._chunk_rel_repo = chunk_rel_repo or ChunkSectionDocumentRepository()
        self._chunk_meta_repo = chunk_meta_repo or ChunkMetaInfoRepository()
        self._element_meta_repo = element_meta_repo or ElementMetaInfoRepository()
        self._section_data_repo = section_data_repo or SectionDataRepository()
        self._chunk_data_repo = chunk_data_repo or ChunkDataRepository()
        self._element_data_repo = element_data_repo or ElementDataRepository()

    def _get_mysql_manager(self) -> BaseMySQLManager:
        if self._mysql_manager is None:
            from src.db.mysql.connection.factory import get_mysql_manager
            self._mysql_manager = get_mysql_manager()
        return self._mysql_manager

    async def _do_execute(self, **kwargs: Any) -> RetrieveResult:
        query: NavigationQuery = kwargs["query"]
        anchor_type = query.anchor_type
        target = query.target_granularity

        if target is None:
            raise ValueError("DrillDown 需要指定 target_granularity")

        anchor_rank = _GRANULARITY_RANK.get(anchor_type, -1)
        target_rank = _GRANULARITY_RANK.get(target, -1)
        if anchor_rank <= target_rank:
            raise ValueError(
                f"下钻方向不合法: {anchor_type.value} → {target.value}，"
                f"anchor 的粒度必须高于 target"
            )

        manager = self._get_mysql_manager()
        with manager.get_session() as session:
            if anchor_type == GranularityLevel.DOCUMENT:
                if target == GranularityLevel.SECTION:
                    return await self._drill_doc_to_sections(session, query)
                elif target == GranularityLevel.CHUNK:
                    return await self._drill_doc_to_chunks(session, query)
                elif target == GranularityLevel.ELEMENT:
                    return await self._drill_doc_to_elements(session, query)

            elif anchor_type == GranularityLevel.SECTION:
                if target == GranularityLevel.CHUNK:
                    return await self._drill_section_to_chunks(session, query)
                elif target == GranularityLevel.ELEMENT:
                    return await self._drill_section_to_elements(session, query)

            elif anchor_type == GranularityLevel.CHUNK:
                if target == GranularityLevel.ELEMENT:
                    return await self._drill_chunk_to_elements(session, query)

            raise ValueError(
                f"不支持的下钻路径: {anchor_type.value} → {target.value}"
            )

    # ---- 排序辅助方法 ----

    def _get_element_sort_key(
        self, session: Session, element_id: Optional[str],
    ) -> Tuple[int, int]:
        """获取单个 element_id 的排序键 (page_index, element_index)"""
        if not element_id:
            return (999999, 999999)
        meta = self._element_meta_repo.get_by_id(session, element_id)
        if not meta:
            return (999999, 999999)
        return (meta.page_index or 0, meta.element_index or 0)

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
        page_idx, elem_idx = self._get_element_sort_key(session, chunk_meta.element_ids[0])
        return (page_idx, elem_idx, split_seq)

    def _sort_section_rels(
        self, session: Session, section_rels: list,
    ) -> list:
        """按 section_meta_info.element_id 指向的标题 Element 位置对 Section 排序"""
        keyed: List[Tuple[Tuple[int, int], Any]] = []
        for rel in section_rels:
            meta = self._section_meta_repo.get_by_id(session, rel.section_id)
            eid = meta.element_id if meta else None
            sort_key = self._get_element_sort_key(session, eid)
            keyed.append((sort_key, rel))
        keyed.sort(key=lambda x: x[0])
        return [rel for _, rel in keyed]

    def _sort_chunk_rels(
        self, session: Session, chunk_rels: list,
    ) -> list:
        """按 (page_index, element_index, split_seq) 对 Chunk 排序"""
        keyed: List[Tuple[Tuple[int, int, int], Any]] = []
        for rel in chunk_rels:
            sort_key = self._get_chunk_sort_key(session, rel.chunk_id)
            keyed.append((sort_key, rel))
        keyed.sort(key=lambda x: x[0])
        return [rel for _, rel in keyed]

    # ---- Document → Section ----

    async def _drill_doc_to_sections(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        section_rels = self._section_doc_repo.get_by_document_id(
            session, query.anchor_id,
        )
        if not section_rels:
            return RetrieveResult(items=[], total_count=0)

        section_rels = self._sort_section_rels(session, section_rels)
        section_ids = [rel.section_id for rel in section_rels]

        meta_map: Dict[str, Any] = {}
        for sid in section_ids:
            meta = self._section_meta_repo.get_by_id(session, sid)
            if meta:
                meta_map[sid] = meta

        items: List[SectionItem] = []
        for i, rel in enumerate(section_rels):
            meta = meta_map.get(rel.section_id)
            score = 1.0 - i / max(len(section_rels), 1)
            items.append(SectionItem(
                section_id=rel.section_id,
                score=score,
                document_id=rel.document_id,
                title=None,
                metadata={
                    "text_level": meta.text_level if meta else None,
                    "parent_section_id": rel.parent_section_id,
                },
            ))

        if query.include_content and section_ids:
            section_data_list = await self._section_data_repo.get_by_ids(section_ids)
            title_map = {str(sd.id): sd.text for sd in section_data_list}
            for item in items:
                item.title = title_map.get(item.section_id)

        return RetrieveResult(items=items, total_count=len(items))

    # ---- Document → Chunk ----

    async def _drill_doc_to_chunks(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        chunk_rels = self._chunk_rel_repo.get_by_document_id(
            session, query.anchor_id,
        )
        if not chunk_rels:
            return RetrieveResult(items=[], total_count=0)

        chunk_rels = self._sort_chunk_rels(session, chunk_rels)
        items = self._build_chunk_items(chunk_rels)

        if query.include_content:
            await self._enrich_chunk_content(items)

        return RetrieveResult(items=items, total_count=len(items))

    # ---- Document → Element ----

    async def _drill_doc_to_elements(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        elements = self._element_meta_repo.get_by_document_id(
            session, query.anchor_id,
        )
        if not elements:
            return RetrieveResult(items=[], total_count=0)

        if query.element_type_filter:
            elements = [
                e for e in elements
                if e.element_type == query.element_type_filter.value
            ]

        items = self._build_element_items(elements, query.anchor_id)

        if query.include_content:
            await self._enrich_element_content(items)

        return RetrieveResult(items=items, total_count=len(items))

    # ---- Section → Chunk ----

    async def _drill_section_to_chunks(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        chunk_rels = self._chunk_rel_repo.get_by_section_id(
            session, query.anchor_id,
        )
        if not chunk_rels:
            return RetrieveResult(items=[], total_count=0)

        chunk_rels = self._sort_chunk_rels(session, chunk_rels)
        items = self._build_chunk_items(chunk_rels)

        if query.include_content:
            await self._enrich_chunk_content(items)

        return RetrieveResult(items=items, total_count=len(items))

    # ---- Section → Element ----

    async def _drill_section_to_elements(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        chunk_rels = self._chunk_rel_repo.get_by_section_id(
            session, query.anchor_id,
        )
        if not chunk_rels:
            return RetrieveResult(items=[], total_count=0)

        seen_element_ids: set = set()
        unique_element_ids: List[str] = []
        for rel in chunk_rels:
            chunk_meta = self._chunk_meta_repo.get_by_id(session, rel.chunk_id)
            if chunk_meta and chunk_meta.element_ids:
                for eid in chunk_meta.element_ids:
                    if eid not in seen_element_ids:
                        seen_element_ids.add(eid)
                        unique_element_ids.append(eid)

        if not unique_element_ids:
            return RetrieveResult(items=[], total_count=0)

        element_metas = []
        for eid in unique_element_ids:
            meta = self._element_meta_repo.get_by_id(session, eid)
            if meta:
                element_metas.append(meta)

        element_metas.sort(key=lambda e: (
            e.page_index or 0,
            e.element_index or 0,
        ))

        if query.element_type_filter:
            element_metas = [
                e for e in element_metas
                if e.element_type == query.element_type_filter.value
            ]

        doc_id = chunk_rels[0].document_id if chunk_rels else None
        items = self._build_element_items(element_metas, doc_id)

        if query.include_content:
            await self._enrich_element_content(items)

        return RetrieveResult(items=items, total_count=len(items))

    # ---- Chunk → Element ----

    async def _drill_chunk_to_elements(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        chunk_meta = self._chunk_meta_repo.get_by_id(session, query.anchor_id)
        if not chunk_meta or not chunk_meta.element_ids:
            return RetrieveResult(items=[], total_count=0)

        element_ids = chunk_meta.element_ids
        element_metas = []
        for eid in element_ids:
            meta = self._element_meta_repo.get_by_id(session, eid)
            if meta:
                element_metas.append(meta)

        element_metas.sort(key=lambda e: (
            e.page_index or 0,
            e.element_index or 0,
        ))

        if query.element_type_filter:
            element_metas = [
                e for e in element_metas
                if e.element_type == query.element_type_filter.value
            ]

        chunk_rel = self._chunk_rel_repo.get_by_id(session, query.anchor_id)
        doc_id = chunk_rel.document_id if chunk_rel else None
        items = self._build_element_items(element_metas, doc_id)

        if query.include_content:
            await self._enrich_element_content(items)

        return RetrieveResult(items=items, total_count=len(items))

    # ---- Builder helpers ----

    def _build_chunk_items(self, chunk_rels: list) -> List[ChunkItem]:
        total = max(len(chunk_rels), 1)
        items: List[ChunkItem] = []
        for i, rel in enumerate(chunk_rels):
            items.append(ChunkItem(
                chunk_id=rel.chunk_id,
                score=1.0 - i / total,
                document_id=rel.document_id,
                section_id=rel.section_id,
            ))
        return items

    def _build_element_items(
        self, element_metas: list, document_id: Optional[str],
    ) -> List[ElementItem]:
        total = max(len(element_metas), 1)
        items: List[ElementItem] = []
        for i, meta in enumerate(element_metas):
            items.append(ElementItem(
                element_id=meta.element_id,
                score=1.0 - i / total,
                element_type=meta.element_type,
                page_index=meta.page_index,
                element_index=meta.element_index,
                document_id=document_id or meta.document_id,
                metadata={
                    "text_level": meta.text_level,
                },
            ))
        return items

    async def _enrich_chunk_content(self, items: List[ChunkItem]) -> None:
        chunk_ids = [item.chunk_id for item in items]
        if not chunk_ids:
            return
        chunk_data_list = await self._chunk_data_repo.get_by_ids(chunk_ids)
        data_map = {str(cd.id): cd.text for cd in chunk_data_list}
        for item in items:
            item.text = data_map.get(item.chunk_id)

    async def _enrich_element_content(self, items: List[ElementItem]) -> None:
        element_ids = [item.element_id for item in items]
        if not element_ids:
            return
        element_data_list = await self._element_data_repo.get_by_ids(element_ids)
        data_map = {}
        for ed in element_data_list:
            doc_id = str(ed.id)
            content = ed.content if hasattr(ed, "content") else None
            data_map[doc_id] = str(content) if content else None
        for item in items:
            item.content = data_map.get(item.element_id)

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="drill_down",
            display_name="跨粒度下钻",
            description=(
                "从高粒度向低粒度展开（Document→Section→Chunk→Element），"
                "支持按元素类型过滤（如仅提取表格）。"
                "适用于主题深挖、表格提取、结构化分析。"
            ),
            input_schema={
                "anchor_id": "str - 锚点 ID（document_id / section_id / chunk_id）",
                "anchor_type": "GranularityLevel - DOCUMENT/SECTION/CHUNK",
                "target_granularity": "GranularityLevel - 目标粒度",
                "element_type_filter": "ElementType - 元素类型过滤（可选）",
                "include_content": "bool - 是否获取全文，默认 True",
            },
            output_type="RetrieveResult[SectionItem | ChunkItem | ElementItem]",
        )
