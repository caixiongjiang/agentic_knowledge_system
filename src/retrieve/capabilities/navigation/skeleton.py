#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : skeleton.py
@Author  : caixiongjiang
@Date    : 2026/03/05
@Function: 
    文档骨架/目录树提取原子能力
    给定 document_id，提取文档的层级结构目录树。
    每个 section 节点携带 summary / is_leaf / chunk_id_list，
    便于 Agent 直接判断下钻目标。
@Modify History:
    2026/07/05 - 改用 MongoDB section_data 的 parent_section_id 建树
                 （编号解析推断，比 MinerU text_level 更准），
                 每个 node 带上 summary / is_leaf / chunk_id_list。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from src.db.mongodb.models.section_data import SectionData
from src.db.mongodb.repositories.document_data_repository import (
    DocumentDataRepository,
)
from src.db.mongodb.repositories.section_data_repository import SectionDataRepository
from src.db.mysql.connection.base import BaseMySQLManager
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

    给定一个 document_id，提取该文档的层级结构目录树。
    每个 section 节点携带 summary / is_leaf / chunk_id_list，
    帮助 Agent 快速了解文档结构并定位下钻目标。

    建树依据：MongoDB section_data.parent_section_id
    （由 SectionSummaryService 从标题编号推断，比 MinerU text_level 更准）。
    排序依据：MySQL section_meta_info.element_id → element_meta_info 的
    (page_index, element_index)，保留文档阅读顺序。
    """

    def __init__(
        self,
        mysql_manager: Optional[BaseMySQLManager] = None,
        section_doc_repo: Optional[SectionDocumentRepository] = None,
        section_meta_repo: Optional[SectionMetaInfoRepository] = None,
        element_meta_repo: Optional[ElementMetaInfoRepository] = None,
        section_data_repo: Optional[SectionDataRepository] = None,
        document_data_repo: Optional[DocumentDataRepository] = None,
    ) -> None:
        super().__init__()
        self._mysql_manager = mysql_manager
        self._section_doc_repo = section_doc_repo or SectionDocumentRepository()
        self._section_meta_repo = section_meta_repo or SectionMetaInfoRepository()
        self._element_meta_repo = element_meta_repo or ElementMetaInfoRepository()
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
            # 1. MySQL 获取该文档的所有 section_id（section_document 关系表）
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

            section_ids = [rel.section_id for rel in section_rels]

            # 2. MySQL 排序：按标题 element 的 (page_index, element_index)
            order_map = self._build_section_order_map(session, section_rels)

            # 3. MongoDB 批量取 section_data（title/summary/is_leaf/chunk_id_list/parent_id）
            section_data_map = await self._get_section_data_map(section_ids)

            # 4. 用 MongoDB parent_section_id 建树
            outline_tree = self._build_outline_tree(
                section_ids, section_data_map, order_map, max_depth,
            )

            # 5. 统计 total_chunks：所有 chunk_id_list 的并集
            all_chunk_ids: Set[str] = set()
            for sd in section_data_map.values():
                all_chunk_ids.update(sd.chunk_id_list or [])

            item = SkeletonItem(
                document_id=document_id,
                score=1.0,
                outline_tree=outline_tree,
                total_sections=len(section_ids),
                total_chunks=len(all_chunk_ids),
            )
            await self._enrich_document_title(item)

        return RetrieveResult(items=[item], total_count=1)

    # ---- 排序辅助 ----

    def _get_element_sort_key(
        self, session: Session, element_id: Optional[str],
    ) -> Tuple[int, int]:
        if not element_id:
            return (999999, 999999)
        meta = self._element_meta_repo.get_by_id(session, element_id)
        if not meta:
            return (999999, 999999)
        return (meta.page_index or 0, meta.element_index or 0)

    def _build_section_order_map(
        self, session: Session, section_rels: list,
    ) -> Dict[str, int]:
        """按标题 element 位置构建 section_id → 顺序序号 的映射"""
        keyed: List[Tuple[Tuple[int, int], str]] = []
        for rel in section_rels:
            meta = self._section_meta_repo.get_by_id(session, rel.section_id)
            eid = meta.element_id if meta else None
            sort_key = self._get_element_sort_key(session, eid)
            keyed.append((sort_key, rel.section_id))
        keyed.sort(key=lambda x: x[0])
        return {sid: i for i, (_, sid) in enumerate(keyed)}

    # ---- MongoDB 数据获取 ----

    async def _get_section_data_map(
        self, section_ids: List[str],
    ) -> Dict[str, SectionData]:
        """批量从 MongoDB section_data 取所有 section 的完整数据"""
        section_data_list = await self._section_data_repo.get_by_ids(section_ids)
        return {str(sd.id): sd for sd in section_data_list}

    # ---- 建树 ----

    def _build_outline_tree(
        self,
        section_ids: List[str],
        section_data_map: Dict[str, SectionData],
        order_map: Dict[str, int],
        max_depth: int,
    ) -> List[SkeletonNode]:
        """用 MongoDB parent_section_id 建树，每个 node 带 summary/is_leaf/chunk_id_list。

        - parent_section_id 来自编号解析推断（SectionSummaryService 写入）
        - 未在 section_data_map 中的 section（MongoDB 缺数据）视为 root 孤儿
        - 环路检测防止异常数据导致死循环
        """
        # section_id → 子 section_id 列表
        children_map: Dict[Optional[str], List[str]] = {}
        for sid in section_ids:
            sd = section_data_map.get(sid)
            parent_id = sd.parent_section_id if sd else None
            children_map.setdefault(parent_id, []).append(sid)

        # 每个父节点下的子节点按 element 位置排序
        for parent_id, child_ids in children_map.items():
            child_ids.sort(key=lambda cid: order_map.get(cid, 0))

        visited: Set[str] = set()

        def build_node(section_id: str, depth: int) -> Optional[SkeletonNode]:
            if section_id in visited:
                self.logger.warning(f"检测到 Section 环路，跳过: {section_id}")
                return None
            visited.add(section_id)

            sd = section_data_map.get(section_id)
            title = (sd.text or "[未命名章节]") if sd else "[未命名章节]"
            chunk_id_list = list(sd.chunk_id_list or []) if sd else []
            is_leaf = sd.is_leaf if sd else None
            summary_text = None
            if sd and sd.summary:
                summary_text = sd.summary.get("text")

            node = SkeletonNode(
                section_id=section_id,
                title=title,
                level=depth,
                chunk_count=len(chunk_id_list),
                summary=summary_text,
                is_leaf=is_leaf,
                chunk_id_list=chunk_id_list,
                children=[],
            )

            if depth < max_depth:
                child_ids = children_map.get(section_id, [])
                for child_id in child_ids:
                    child_node = build_node(child_id, depth + 1)
                    if child_node:
                        node.children.append(child_node)

            return node

        # root 节点：parent_section_id 为 None 或 MongoDB 中不存在该 section
        root_ids: List[str] = []
        for sid in section_ids:
            sd = section_data_map.get(sid)
            parent_id = sd.parent_section_id if sd else None
            if parent_id is None or parent_id not in section_data_map:
                root_ids.append(sid)

        # 去重 + 排序
        seen_root: Set[str] = set()
        root_ids_sorted: List[str] = []
        for sid in sorted(root_ids, key=lambda cid: order_map.get(cid, 0)):
            if sid not in seen_root:
                seen_root.add(sid)
                root_ids_sorted.append(sid)

        tree: List[SkeletonNode] = []
        for root_id in root_ids_sorted:
            node = build_node(root_id, 1)
            if node:
                tree.append(node)

        # 兜底：未被遍历到的 section（孤儿）挂到顶层
        remaining = set(section_ids) - visited
        if remaining:
            remaining_sorted = sorted(
                remaining, key=lambda cid: order_map.get(cid, 0),
            )
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
                "给定 document_id，提取文档的层级结构目录树。"
                "每个 section 节点携带 summary（摘要文本）、is_leaf（是否叶子）、"
                "chunk_id_list（子树 chunk 列表，可直接下钻）。"
                "适用于文档概览、检索策略规划、定位目标章节。"
            ),
            input_schema={
                "anchor_id": "str - 文档 ID (document_id)",
                "anchor_type": "GranularityLevel.DOCUMENT",
                "max_depth": "int - 最大展开深度，默认 3",
            },
            output_type="RetrieveResult[SkeletonItem]",
        )
