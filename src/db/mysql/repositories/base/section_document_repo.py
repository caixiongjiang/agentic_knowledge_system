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

from typing import List, Optional
from loguru import logger
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


# 全局实例
section_document_repo = SectionDocumentRepository()
