#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_summary_repo.py
@Author  : agentic
@Date    : 2026/07/02
@Function:
    SectionSummary Repository
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.extract.section_summary import SectionSummary
from src.db.mysql.repositories.base_repository import BaseRepository


class SectionSummaryRepository(BaseRepository[SectionSummary]):
    """SectionSummary Repository"""

    def __init__(self):
        super().__init__(SectionSummary)

    def get_by_summary_id(
        self,
        session: Session,
        summary_id: str
    ) -> Optional[SectionSummary]:
        """根据 summary_id 查询 SectionSummary。"""
        try:
            result = session.query(self.model).filter(
                self.model.summary_id == summary_id,
                self.model.deleted == 0
            ).first()
            if not result:
                logger.debug(f"未找到SectionSummary: summary_id={summary_id}")
            return result
        except SQLAlchemyError as e:
            logger.error(f"根据summary_id查询失败: {e}")
            return None

    def get_by_document_id(
        self,
        session: Session,
        document_id: str
    ) -> List[SectionSummary]:
        """根据 document_id 查询该文档所有 section 摘要关联。"""
        try:
            results = session.query(self.model).filter(
                self.model.document_id == document_id,
                self.model.deleted == 0
            ).all()
            logger.debug(
                f"查询到{len(results)}个SectionSummary: document_id={document_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据document_id查询失败: {e}")
            return []


# 全局实例
section_summary_repo = SectionSummaryRepository()
