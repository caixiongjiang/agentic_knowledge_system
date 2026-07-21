#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_document_repo.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    SectionDocument Repository
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Dict, List, Optional
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.base.section_document import SectionDocument
from src.db.mysql.repositories.base_repository import BaseRepository


class SectionDocumentRepository(BaseRepository[SectionDocument]):
    """SectionDocument Repository"""

    def __init__(self):
        super().__init__(SectionDocument)

    def get_by_document_id(
        self,
        session: Session,
        document_id: str
    ) -> List[SectionDocument]:
        """
        根据 document_id 查询所有 Section

        Args:
            session: 数据库会话
            document_id: Document ID

        Returns:
            SectionDocument 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.document_id == document_id,
                self.model.deleted == 0
            ).all()

            logger.debug(
                f"查询到{len(results)}个Section: document_id={document_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据document_id查询失败: {e}")
            return []

    def get_children(
        self,
        session: Session,
        parent_section_id: str
    ) -> List[SectionDocument]:
        """
        查询子 Section（根据 parent_section_id）

        Args:
            session: 数据库会话
            parent_section_id: 父 Section ID

        Returns:
            子 SectionDocument 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.parent_section_id == parent_section_id,
                self.model.deleted == 0
            ).all()

            logger.debug(
                f"查询到{len(results)}个子Section: parent_section_id={parent_section_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"查询子Section失败: {e}")
            return []

    def get_sections_with_order(
        self,
        session: Session,
        document_id: str,
    ) -> List[Dict[str, Any]]:
        """
        单次 JOIN 取一个文档所有 section 的拓扑 + 排序键（消除 N+1）。

        骨架树重建原先对每个 section 分别查 section_meta_info / element_meta_info
        （2N 次查询）。本方法用一次三表 LEFT JOIN 拿齐：
            section_document  → section_id / parent_section_id / is_leaf
            section_meta_info → element_id
            element_meta_info → page_index / element_index（阅读顺序排序键）

        Args:
            session: 数据库会话
            document_id: Document ID

        Returns:
            dict 列表，每项：
            {section_id, parent_section_id, is_leaf, page_index, element_index}
            page_index / element_index 缺失时为 None，由调用方兜底排序。
        """
        sql = text(
            """
            SELECT
                sd.section_id        AS section_id,
                sd.parent_section_id AS parent_section_id,
                sd.is_leaf           AS is_leaf,
                em.page_index        AS page_index,
                em.element_index    AS element_index
            FROM section_document sd
            LEFT JOIN section_meta_info sm
                ON sm.section_id = sd.section_id AND sm.deleted = 0
            LEFT JOIN element_meta_info em
                ON em.element_id = sm.element_id AND em.deleted = 0
            WHERE sd.document_id = :doc_id
              AND sd.deleted = 0
            """
        )
        try:
            rows = session.execute(sql, {"doc_id": document_id}).mappings().all()
            result = [dict(r) for r in rows]
            logger.debug(
                f"get_sections_with_order 命中 {len(result)} 个 section: "
                f"document_id={document_id}"
            )
            return result
        except SQLAlchemyError as e:
            logger.error(f"get_sections_with_order 查询失败: {e}")
            return []

    def get_leaf_section_ids_by_document_id(
        self,
        session: Session,
        document_id: str,
    ) -> List[str]:
        """
        取一个文档下所有叶子 section（is_leaf=True）的 section_id。

        供 TextAnalyzer 等只需在叶子 section 抽取的组件使用，走 idx_doc_leaf 索引。

        Args:
            session: 数据库会话
            document_id: Document ID

        Returns:
            叶子 section_id 列表（未保序，调用方按需重排）
        """
        try:
            rows = session.query(self.model.section_id).filter(
                self.model.document_id == document_id,
                self.model.is_leaf.is_(True),
                self.model.deleted == 0,
            ).all()
            section_ids = [r[0] for r in rows if r[0]]
            logger.debug(
                f"查询到{len(section_ids)}个叶子Section: document_id={document_id}"
            )
            return section_ids
        except SQLAlchemyError as e:
            logger.error(f"查询叶子Section失败: {e}")
            return []


# 全局实例
section_document_repo = SectionDocumentRepository()
