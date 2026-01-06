#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : document_summary_repo.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    DocumentSummary Repository
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.extract.document_summary import DocumentSummary
from src.db.mysql.repositories.base_repository import BaseRepository


class DocumentSummaryRepository(BaseRepository[DocumentSummary]):
    """DocumentSummary Repository"""
    
    def __init__(self):
        super().__init__(DocumentSummary)
    
    def get_by_summary_id(
        self, 
        session: Session,
        summary_id: str
    ) -> Optional[DocumentSummary]:
        """
        根据 summary_id 查询 DocumentSummary
        
        Args:
            session: 数据库会话
            summary_id: Summary ID
        
        Returns:
            DocumentSummary 实例，未找到返回 None
        """
        try:
            result = session.query(self.model).filter(
                self.model.summary_id == summary_id,
                self.model.deleted == 0
            ).first()
            
            if not result:
                logger.debug(f"未找到DocumentSummary: summary_id={summary_id}")
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"根据summary_id查询失败: {e}")
            return None


# 全局实例
document_summary_repo = DocumentSummaryRepository()
