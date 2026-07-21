#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_atomic_qa_repo.py
@Author  : agentic
@Date    : 2026/07/14
@Function:
    SectionAtomicQA Repository

    提供 SectionAtomicQA 的专用查询方法（按 section_id / document_id 批量查询）。
    QA 正文与向量分别存 MongoDB section_data.atomic_qa 与 Milvus atomic_qa_store，
    本表仅关系层。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.extract.section_atomic_qa import SectionAtomicQA
from src.db.mysql.repositories.base_repository import BaseRepository


class SectionAtomicQARepository(BaseRepository[SectionAtomicQA]):
    """SectionAtomicQA Repository"""

    def __init__(self):
        super().__init__(SectionAtomicQA)

    def get_by_qa_id(
        self,
        session: Session,
        qa_id: str
    ) -> Optional[SectionAtomicQA]:
        """根据 qa_id 查询 SectionAtomicQA。"""
        try:
            result = session.query(self.model).filter(
                self.model.qa_id == qa_id,
                self.model.deleted == 0
            ).first()
            if not result:
                logger.debug(f"未找到SectionAtomicQA: qa_id={qa_id}")
            return result
        except SQLAlchemyError as e:
            logger.error(f"根据qa_id查询失败: {e}")
            return None

    def get_by_section_id(
        self,
        session: Session,
        section_id: str
    ) -> List[SectionAtomicQA]:
        """根据 section_id 查询该 section 所有 QA 关联。"""
        try:
            results = session.query(self.model).filter(
                self.model.section_id == section_id,
                self.model.deleted == 0
            ).all()
            logger.debug(
                f"查询到{len(results)}个SectionAtomicQA: section_id={section_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据section_id查询失败: {e}")
            return []

    def get_by_document_id(
        self,
        session: Session,
        document_id: str
    ) -> List[SectionAtomicQA]:
        """根据 document_id 查询该文档所有 QA 关联。"""
        try:
            results = session.query(self.model).filter(
                self.model.document_id == document_id,
                self.model.deleted == 0
            ).all()
            logger.debug(
                f"查询到{len(results)}个SectionAtomicQA: document_id={document_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据document_id查询失败: {e}")
            return []

    def delete_by_document_id(
        self,
        session: Session,
        document_id: str,
        updater: str = ""
    ) -> int:
        """按 document_id 软删除该文档所有 QA 关联（级联删除用）。

        Returns:
            删除行数
        """
        try:
            updated_count = session.query(self.model).filter(
                self.model.document_id == document_id,
                self.model.deleted == 0
            ).update({
                'deleted': 1,
                'updater': updater
            }, synchronize_session='fetch')
            session.commit()
            logger.debug(
                f"软删除SectionAtomicQA: document_id={document_id}, {updated_count}条"
            )
            return int(updated_count)
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"按document_id软删除SectionAtomicQA失败: {e}")
            return 0


# 全局实例
section_atomic_qa_repo = SectionAtomicQARepository()
