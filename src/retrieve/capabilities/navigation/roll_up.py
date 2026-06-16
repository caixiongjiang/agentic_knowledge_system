#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : roll_up.py
@Author  : caixiongjiang
@Date    : 2026/03/05
@Function: 
    跨粒度上溯原子能力
    从低粒度向高粒度回溯（Element→Chunk→Section→Document）
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.db.mongodb.repositories.chunk_data_repository import ChunkDataRepository
from src.db.mongodb.repositories.document_data_repository import (
    DocumentDataRepository,
)
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
from src.retrieve.types.enums import GranularityLevel
from src.types.utils.chunk_search_text import resolve_chunk_display_text
from src.retrieve.types.query import NavigationQuery
from src.retrieve.types.result import (
    ChunkItem,
    DocumentItem,
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


class RollUp(BaseCapability):
    """跨粒度上溯

    从低粒度向高粒度回溯：
    - Element → Chunk / Section / Document
    - Chunk   → Section / Document
    - Section → Document
    - Link    → Chunk（TODO: 待 Neo4j 完善后实现）

    典型场景：图谱探索找到一个 Link，需要回溯到原始 Chunk 进行事实核查。
    """

    def __init__(
        self,
        mysql_manager: Optional[BaseMySQLManager] = None,
        chunk_rel_repo: Optional[ChunkSectionDocumentRepository] = None,
        section_doc_repo: Optional[SectionDocumentRepository] = None,
        section_meta_repo: Optional[SectionMetaInfoRepository] = None,
        chunk_meta_repo: Optional[ChunkMetaInfoRepository] = None,
        element_meta_repo: Optional[ElementMetaInfoRepository] = None,
        chunk_data_repo: Optional[ChunkDataRepository] = None,
        section_data_repo: Optional[SectionDataRepository] = None,
        document_data_repo: Optional[DocumentDataRepository] = None,
    ) -> None:
        super().__init__()
        self._mysql_manager = mysql_manager
        self._chunk_rel_repo = chunk_rel_repo or ChunkSectionDocumentRepository()
        self._section_doc_repo = section_doc_repo or SectionDocumentRepository()
        self._section_meta_repo = section_meta_repo or SectionMetaInfoRepository()
        self._chunk_meta_repo = chunk_meta_repo or ChunkMetaInfoRepository()
        self._element_meta_repo = element_meta_repo or ElementMetaInfoRepository()
        self._chunk_data_repo = chunk_data_repo or ChunkDataRepository()
        self._section_data_repo = section_data_repo or SectionDataRepository()
        self._document_data_repo = document_data_repo or DocumentDataRepository()

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
            raise ValueError("RollUp 需要指定 target_granularity")

        anchor_rank = _GRANULARITY_RANK.get(anchor_type, -1)
        target_rank = _GRANULARITY_RANK.get(target, -1)
        if anchor_rank >= target_rank:
            raise ValueError(
                f"上溯方向不合法: {anchor_type.value} → {target.value}，"
                f"anchor 的粒度必须低于 target"
            )

        manager = self._get_mysql_manager()
        with manager.get_session() as session:
            if anchor_type == GranularityLevel.ELEMENT:
                if target == GranularityLevel.CHUNK:
                    return await self._roll_element_to_chunk(session, query)
                elif target == GranularityLevel.SECTION:
                    return await self._roll_element_to_section(session, query)
                elif target == GranularityLevel.DOCUMENT:
                    return await self._roll_element_to_document(session, query)

            elif anchor_type == GranularityLevel.CHUNK:
                if target == GranularityLevel.SECTION:
                    return await self._roll_chunk_to_section(session, query)
                elif target == GranularityLevel.DOCUMENT:
                    return await self._roll_chunk_to_document(session, query)

            elif anchor_type == GranularityLevel.SECTION:
                if target == GranularityLevel.DOCUMENT:
                    return await self._roll_section_to_document(session, query)

            elif anchor_type == GranularityLevel.LINK:
                if target == GranularityLevel.CHUNK:
                    return await self._roll_link_to_chunk(session, query)

            raise ValueError(
                f"不支持的上溯路径: {anchor_type.value} → {target.value}"
            )

    # ---- Element → Chunk ----

    async def _roll_element_to_chunk(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        chunk_metas = self._chunk_meta_repo.get_by_element_id(
            session, query.anchor_id,
        )
        if not chunk_metas:
            return RetrieveResult(items=[], total_count=0)

        items: List[ChunkItem] = []
        for cm in chunk_metas:
            chunk_rel = self._chunk_rel_repo.get_by_id(session, cm.chunk_id)
            items.append(ChunkItem(
                chunk_id=cm.chunk_id,
                score=1.0,
                document_id=chunk_rel.document_id if chunk_rel else None,
                section_id=chunk_rel.section_id if chunk_rel else None,
                metadata={"source_element_id": query.anchor_id},
            ))

        if query.include_content:
            chunk_ids = [item.chunk_id for item in items]
            chunk_data_list = await self._chunk_data_repo.get_by_ids(chunk_ids)
            data_map = {str(cd.id): resolve_chunk_display_text(cd) for cd in chunk_data_list}
            for item in items:
                item.text = data_map.get(item.chunk_id)

        return RetrieveResult(items=items, total_count=len(items))

    # ---- Element → Section ----

    async def _roll_element_to_section(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        chunk_metas = self._chunk_meta_repo.get_by_element_id(
            session, query.anchor_id,
        )
        if not chunk_metas:
            return RetrieveResult(items=[], total_count=0)

        seen_section_ids: set = set()
        items: List[SectionItem] = []
        for cm in chunk_metas:
            chunk_rel = self._chunk_rel_repo.get_by_id(session, cm.chunk_id)
            if not chunk_rel or not chunk_rel.section_id:
                continue
            if chunk_rel.section_id in seen_section_ids:
                continue
            seen_section_ids.add(chunk_rel.section_id)

            section_meta = self._section_meta_repo.get_by_id(
                session, chunk_rel.section_id,
            )
            try:
                sec_chunk_count = len(
                    self._chunk_rel_repo.get_by_section_id(
                        session, chunk_rel.section_id,
                    )
                )
            except Exception:  # noqa: BLE001
                sec_chunk_count = 0
            items.append(SectionItem(
                section_id=chunk_rel.section_id,
                score=1.0,
                document_id=chunk_rel.document_id,
                title=None,
                metadata={
                    "source_element_id": query.anchor_id,
                    "text_level": section_meta.text_level if section_meta else None,
                    "chunk_count": sec_chunk_count,
                },
            ))

        if query.include_content and items:
            section_ids = [item.section_id for item in items]
            section_data_list = await self._section_data_repo.get_by_ids(section_ids)
            title_map = {str(sd.id): sd.text for sd in section_data_list}
            for item in items:
                item.title = title_map.get(item.section_id)

        return RetrieveResult(items=items, total_count=len(items))

    # ---- Element → Document ----

    async def _roll_element_to_document(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        element_meta = self._element_meta_repo.get_by_id(
            session, query.anchor_id,
        )
        if not element_meta:
            return RetrieveResult(items=[], total_count=0)

        document_id = element_meta.document_id
        if not document_id:
            return RetrieveResult(items=[], total_count=0)

        return await self._build_document_result(
            document_id, query.include_content,
            extra_metadata={"source_element_id": query.anchor_id},
        )

    # ---- Chunk → Section ----

    async def _roll_chunk_to_section(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        chunk_rel = self._chunk_rel_repo.get_by_id(session, query.anchor_id)
        if not chunk_rel or not chunk_rel.section_id:
            return RetrieveResult(items=[], total_count=0)

        section_id = chunk_rel.section_id
        section_meta = self._section_meta_repo.get_by_id(session, section_id)

        try:
            sec_chunk_count = len(
                self._chunk_rel_repo.get_by_section_id(session, section_id)
            )
        except Exception:  # noqa: BLE001
            sec_chunk_count = 0

        item = SectionItem(
            section_id=section_id,
            score=1.0,
            document_id=chunk_rel.document_id,
            title=None,
            metadata={
                "source_chunk_id": query.anchor_id,
                "text_level": section_meta.text_level if section_meta else None,
                "parent_section_id": None,
                "chunk_count": sec_chunk_count,
            },
        )

        section_rel = self._section_doc_repo.get_by_id(session, section_id)
        if section_rel:
            item.metadata["parent_section_id"] = section_rel.parent_section_id

        if query.include_content:
            section_data = await self._section_data_repo.get_by_id(section_id)
            if section_data:
                item.title = section_data.text

        return RetrieveResult(items=[item], total_count=1)

    # ---- Chunk → Document ----

    async def _roll_chunk_to_document(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        chunk_rel = self._chunk_rel_repo.get_by_id(session, query.anchor_id)
        if not chunk_rel or not chunk_rel.document_id:
            return RetrieveResult(items=[], total_count=0)

        return await self._build_document_result(
            chunk_rel.document_id, query.include_content,
            extra_metadata={"source_chunk_id": query.anchor_id},
        )

    # ---- Section → Document ----

    async def _roll_section_to_document(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        section_rel = self._section_doc_repo.get_by_id(session, query.anchor_id)
        if not section_rel or not section_rel.document_id:
            return RetrieveResult(items=[], total_count=0)

        return await self._build_document_result(
            section_rel.document_id, query.include_content,
            extra_metadata={"source_section_id": query.anchor_id},
        )

    # ---- Link → Chunk (TODO) ----

    async def _roll_link_to_chunk(
        self, session: Session, query: NavigationQuery,
    ) -> RetrieveResult:
        self.logger.warning(
            "Link → Chunk 上溯尚未实现，需要 Neo4j Manager 提供查询接口"
        )
        return RetrieveResult(items=[], total_count=0)

    # ---- Document result builder ----

    async def _build_document_result(
        self,
        document_id: str,
        include_content: bool,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> RetrieveResult:
        item = DocumentItem(
            document_id=document_id,
            score=1.0,
            metadata=dict(extra_metadata or {}),
        )

        # section_count：用 SectionDocumentRepository 即时聚合，
        # 让上层 Agent 能粗略判断文档规模。失败不致命。
        manager = self._get_mysql_manager()
        try:
            with manager.get_session() as session:
                section_rels = self._section_doc_repo.get_by_document_id(
                    session, document_id,
                )
                item.section_count = len(section_rels)
        except Exception:  # noqa: BLE001
            item.section_count = 0

        if include_content:
            doc_data = await self._document_data_repo.get_by_id(document_id)
            if doc_data:
                item.summary = doc_data.summary_zh or doc_data.summary_en
                if doc_data.metadata:
                    item.title = doc_data.metadata.get("title")
                    # 从 metadata 透传若存在的 source_type / file_name 等可读字段，
                    # 给 Agent 一个直观的"这是 PDF / Markdown / 文件名"信号。
                    src_type = doc_data.metadata.get("source_type") or doc_data.metadata.get("file_type")
                    if src_type:
                        item.source_type = src_type
                    file_name = doc_data.metadata.get("file_name") or doc_data.metadata.get("name")
                    if file_name and "file_name" not in item.metadata:
                        item.metadata["file_name"] = file_name

        return RetrieveResult(items=[item], total_count=1)

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="roll_up",
            display_name="跨粒度上溯",
            description=(
                "从低粒度向高粒度回溯（Element→Chunk→Section→Document），"
                "用于追踪信息来源、事实核查。"
                "Link→Chunk 路径待 Neo4j 完善后实现。"
            ),
            input_schema={
                "anchor_id": "str - 锚点 ID（element_id / chunk_id / section_id）",
                "anchor_type": "GranularityLevel - ELEMENT/CHUNK/SECTION/LINK",
                "target_granularity": "GranularityLevel - 目标粒度",
                "include_content": "bool - 是否获取全文，默认 True",
            },
            output_type="RetrieveResult[ChunkItem | SectionItem | DocumentItem]",
        )
