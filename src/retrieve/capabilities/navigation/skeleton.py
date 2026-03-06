#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : skeleton.py
@Author  : caixiongjiang
@Date    : 2026/03/05
@Function: 
    文档骨架/目录树提取原子能力
    给定 document_id，提取文档的层级结构目录
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from src.db.mongodb.repositories.document_data_repository import (
    DocumentDataRepository,
)
from src.db.mongodb.repositories.section_data_repository import SectionDataRepository
from src.db.mysql.connection.base import BaseMySQLManager
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
from src.retrieve.types.query import NavigationQuery
from src.retrieve.types.result import RetrieveResult, SkeletonItem, SkeletonNode


class Skeleton(BaseCapability):
    """文档骨架/目录树提取

    给定一个 document_id，提取该文档的层级结构目录（仅标题，不含正文），
    帮助 Agent 快速了解文档的整体结构。

    Section 的阅读顺序通过 section_meta_info.element_id 指向的标题 Element
    的 (page_index, element_index) 推导，而非显式的 section_index 字段。
    """

    def __init__(
        self,
        mysql_manager: Optional[BaseMySQLManager] = None,
        section_doc_repo: Optional[SectionDocumentRepository] = None,
        section_meta_repo: Optional[SectionMetaInfoRepository] = None,
        element_meta_repo: Optional[ElementMetaInfoRepository] = None,
        chunk_rel_repo: Optional[ChunkSectionDocumentRepository] = None,
        section_data_repo: Optional[SectionDataRepository] = None,
        document_data_repo: Optional[DocumentDataRepository] = None,
    ) -> None:
        super().__init__()
        self._mysql_manager = mysql_manager
        self._section_doc_repo = section_doc_repo or SectionDocumentRepository()
        self._section_meta_repo = section_meta_repo or SectionMetaInfoRepository()
        self._element_meta_repo = element_meta_repo or ElementMetaInfoRepository()
        self._chunk_rel_repo = chunk_rel_repo or ChunkSectionDocumentRepository()
        self._section_data_repo = section_data_repo or SectionDataRepository()
        self._document_data_repo = document_data_repo or DocumentDataRepository()

    def _get_mysql_manager(self) -> BaseMySQLManager:
        if self._mysql_manager is None:
            from src.db.mysql.connection.factory import get_mysql_manager
            self._mysql_manager = get_mysql_manager()
        return self._mysql_manager

    async def _do_execute(self, **kwargs: Any) -> RetrieveResult:
        query: NavigationQuery = kwargs["query"]
        document_id = query.anchor_id
        max_depth = query.max_depth

        manager = self._get_mysql_manager()
        with manager.get_session() as session:
            section_rels = self._section_doc_repo.get_by_document_id(
                session, document_id,
            )
            if not section_rels:
                item = SkeletonItem(
                    document_id=document_id,
                    score=1.0,
                    outline_tree=[],
                    total_sections=0,
                    total_chunks=0,
                )
                await self._enrich_document_title(item)
                return RetrieveResult(items=[item], total_count=1)

            section_rels = self._sort_section_rels(session, section_rels)
            section_ids = [rel.section_id for rel in section_rels]

            meta_map: Dict[str, Any] = {}
            for sid in section_ids:
                meta = self._section_meta_repo.get_by_id(session, sid)
                if meta:
                    meta_map[sid] = meta

            title_map = await self._get_section_titles(section_ids)

            chunk_count_map = self._count_chunks_per_section(session, section_ids)

            outline_tree = self._build_outline_tree(
                section_rels, meta_map, title_map, chunk_count_map, max_depth,
            )

            total_chunks = sum(chunk_count_map.values())

            item = SkeletonItem(
                document_id=document_id,
                score=1.0,
                outline_tree=outline_tree,
                total_sections=len(section_ids),
                total_chunks=total_chunks,
            )
            await self._enrich_document_title(item)

        return RetrieveResult(items=[item], total_count=1)

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

    def _sort_section_rels(
        self, session: Session, section_rels: list,
    ) -> list:
        """按 section_meta_info.element_id 指向的标题 Element 位置排序"""
        keyed: List[Tuple[Tuple[int, int], Any]] = []
        for rel in section_rels:
            meta = self._section_meta_repo.get_by_id(session, rel.section_id)
            eid = meta.element_id if meta else None
            sort_key = self._get_element_sort_key(session, eid)
            keyed.append((sort_key, rel))
        keyed.sort(key=lambda x: x[0])
        return [rel for _, rel in keyed]

    # ---- 数据获取辅助方法 ----

    async def _get_section_titles(
        self, section_ids: List[str],
    ) -> Dict[str, str]:
        section_data_list = await self._section_data_repo.get_by_ids(section_ids)
        return {
            str(sd.id): (sd.text or "[未命名章节]")
            for sd in section_data_list
        }

    def _count_chunks_per_section(
        self, session: Session, section_ids: List[str],
    ) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for sid in section_ids:
            chunks = self._chunk_rel_repo.get_by_section_id(session, sid)
            counts[sid] = len(chunks)
        return counts

    def _build_outline_tree(
        self,
        section_rels: list,
        meta_map: Dict[str, Any],
        title_map: Dict[str, str],
        chunk_count_map: Dict[str, int],
        max_depth: int,
    ) -> List[SkeletonNode]:
        """将扁平的 Section 列表构建为树状结构

        基于 parent_section_id 建立父子关系，
        使用 text_level 确定层级深度。
        section_rels 已按 element 位置排好序，保留阅读顺序。
        """
        children_map: Dict[Optional[str], List[str]] = {}
        order_map: Dict[str, int] = {}

        for i, rel in enumerate(section_rels):
            parent_id = rel.parent_section_id
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(rel.section_id)
            order_map[rel.section_id] = i

        visited: Set[str] = set()

        def build_node(section_id: str, depth: int) -> Optional[SkeletonNode]:
            if section_id in visited:
                self.logger.warning(f"检测到 Section 环路，跳过: {section_id}")
                return None
            visited.add(section_id)

            meta = meta_map.get(section_id)
            level = meta.text_level if meta and meta.text_level else depth

            node = SkeletonNode(
                section_id=section_id,
                title=title_map.get(section_id, "[未命名章节]"),
                level=level,
                chunk_count=chunk_count_map.get(section_id, 0),
                children=[],
            )

            if depth < max_depth:
                child_ids = children_map.get(section_id, [])
                child_ids.sort(key=lambda sid: order_map.get(sid, 0))
                for child_id in child_ids:
                    child_node = build_node(child_id, depth + 1)
                    if child_node:
                        node.children.append(child_node)

            return node

        root_ids = children_map.get(None, [])
        root_ids.sort(key=lambda sid: order_map.get(sid, 0))

        tree: List[SkeletonNode] = []
        for root_id in root_ids:
            node = build_node(root_id, 1)
            if node:
                tree.append(node)

        remaining = set(order_map.keys()) - visited
        if remaining:
            remaining_sorted = sorted(remaining, key=lambda sid: order_map.get(sid, 0))
            for sid in remaining_sorted:
                node = build_node(sid, 1)
                if node:
                    tree.append(node)

        return tree

    async def _enrich_document_title(self, item: SkeletonItem) -> None:
        doc_data = await self._document_data_repo.get_by_id(item.document_id)
        if doc_data and doc_data.metadata:
            item.title = doc_data.metadata.get("title")

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="skeleton",
            display_name="文档骨架/目录树提取",
            description=(
                "给定 document_id，提取文档的层级结构目录树（仅标题，不含正文）。"
                "适用于文档概览、检索策略规划。"
            ),
            input_schema={
                "anchor_id": "str - 文档 ID (document_id)",
                "anchor_type": "GranularityLevel.DOCUMENT",
                "max_depth": "int - 最大展开深度，默认 3",
            },
            output_type="RetrieveResult[SkeletonItem]",
        )
