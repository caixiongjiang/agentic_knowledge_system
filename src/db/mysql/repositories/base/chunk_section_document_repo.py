#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_section_document_repo.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    ChunkSectionDocument Repository
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.base.chunk_section_document import ChunkSectionDocument
from src.db.mysql.repositories.base_repository import BaseRepository


class ChunkSectionDocumentRepository(BaseRepository[ChunkSectionDocument]):
    """ChunkSectionDocument Repository"""
    
    def __init__(self):
        super().__init__(ChunkSectionDocument)
    
    def get_by_section_id(
        self, 
        session: Session,
        section_id: str
    ) -> List[ChunkSectionDocument]:
        """
        根据 section_id 查询所有 Chunk
        
        Args:
            session: 数据库会话
            section_id: Section ID
        
        Returns:
            ChunkSectionDocument 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.section_id == section_id,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个Chunk: section_id={section_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据section_id查询失败: {e}")
            return []
    
    def get_by_document_id(
        self, 
        session: Session,
        document_id: str
    ) -> List[ChunkSectionDocument]:
        """
        根据 document_id 查询所有 Chunk
        
        Args:
            session: 数据库会话
            document_id: Document ID
        
        Returns:
            ChunkSectionDocument 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.document_id == document_id,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个Chunk: document_id={document_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据document_id查询失败: {e}")
            return []
    
    def get_children(
        self, 
        session: Session,
        parent_chunk_id: str
    ) -> List[ChunkSectionDocument]:
        """
        查询子 Chunk（根据 parent_chunk_id）
        
        Args:
            session: 数据库会话
            parent_chunk_id: 父 Chunk ID
        
        Returns:
            子 ChunkSectionDocument 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.parent_chunk_id == parent_chunk_id,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个子Chunk: parent_chunk_id={parent_chunk_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"查询子Chunk失败: {e}")
            return []


# 全局实例
chunk_section_document_repo = ChunkSectionDocumentRepository()
