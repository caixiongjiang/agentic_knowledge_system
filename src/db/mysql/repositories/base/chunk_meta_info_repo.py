#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_meta_info_repo.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    ChunkMetaInfo Repository
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.base.chunk_meta_info import ChunkMetaInfo
from src.db.mysql.repositories.base_repository import BaseRepository


class ChunkMetaInfoRepository(BaseRepository[ChunkMetaInfo]):
    """ChunkMetaInfo Repository"""
    
    def __init__(self):
        super().__init__(ChunkMetaInfo)
    
    def get_by_chunk_type(
        self, 
        session: Session,
        chunk_type: str
    ) -> List[ChunkMetaInfo]:
        """
        根据 chunk_type 查询所有 ChunkMetaInfo
        
        Args:
            session: 数据库会话
            chunk_type: Chunk 类型（text, image, table）
        
        Returns:
            ChunkMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.chunk_type == chunk_type,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个ChunkMetaInfo: chunk_type={chunk_type}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据chunk_type查询失败: {e}")
            return []
    
    def get_by_page_index(
        self, 
        session: Session,
        page_index: int
    ) -> List[ChunkMetaInfo]:
        """
        根据 page_index 查询所有 ChunkMetaInfo
        
        Args:
            session: 数据库会话
            page_index: 页码索引
        
        Returns:
            ChunkMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.page_index == page_index,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个ChunkMetaInfo: page_index={page_index}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据page_index查询失败: {e}")
            return []


# 全局实例
chunk_meta_info_repo = ChunkMetaInfoRepository()
