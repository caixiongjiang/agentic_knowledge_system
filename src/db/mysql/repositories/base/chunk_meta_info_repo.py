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
from sqlalchemy import func, cast, String
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
    
    def get_by_element_id(
        self,
        session: Session,
        element_id: str
    ) -> List[ChunkMetaInfo]:
        """
        查找包含指定 element_id 的所有 Chunk（用于 pipeline）
        
        Args:
            session: 数据库会话
            element_id: Element ID
        
        Returns:
            包含该 element_id 的 ChunkMetaInfo 列表
        """
        try:
            # 使用 JSON_CONTAINS 查询（MySQL 5.7+）
            results = session.query(self.model).filter(
                func.json_contains(
                    self.model.element_ids,
                    cast(f'"{element_id}"', String)
                ) == 1,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个包含element_id的ChunkMetaInfo: {element_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据element_id查询Chunk失败: {e}")
            return []
    
    def update_element_ids(
        self,
        session: Session,
        chunk_id: str,
        element_ids: List[str]
    ) -> bool:
        """
        更新 Chunk 的 element_ids（用于 pipeline）
        
        Args:
            session: 数据库会话
            chunk_id: Chunk ID
            element_ids: Element ID 列表
        
        Returns:
            更新成功返回 True，失败返回 False
        """
        try:
            chunk = self.get_by_id(session, chunk_id)
            if not chunk:
                logger.warning(f"Chunk 不存在: {chunk_id}")
                return False
            
            chunk.element_ids = element_ids
            session.commit()
            
            logger.debug(f"更新ChunkMetaInfo element_ids: {chunk_id} -> {element_ids}")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新element_ids失败: {e}")
            return False
    
    def add_element_id(
        self,
        session: Session,
        chunk_id: str,
        element_id: str
    ) -> bool:
        """
        向 Chunk 添加一个 element_id（用于 pipeline）
        
        Args:
            session: 数据库会话
            chunk_id: Chunk ID
            element_id: 要添加的 Element ID
        
        Returns:
            添加成功返回 True，失败返回 False
        """
        try:
            chunk = self.get_by_id(session, chunk_id)
            if not chunk:
                logger.warning(f"Chunk 不存在: {chunk_id}")
                return False
            
            # 初始化或添加
            if chunk.element_ids is None:
                chunk.element_ids = [element_id]
            elif element_id not in chunk.element_ids:
                chunk.element_ids.append(element_id)
            else:
                logger.debug(f"element_id 已存在，跳过: {element_id}")
                return True
            
            session.commit()
            
            logger.debug(f"向ChunkMetaInfo添加element_id: {chunk_id} + {element_id}")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"添加element_id失败: {e}")
            return False
    
    def remove_element_id(
        self,
        session: Session,
        chunk_id: str,
        element_id: str
    ) -> bool:
        """
        从 Chunk 移除一个 element_id（用于 pipeline）
        
        Args:
            session: 数据库会话
            chunk_id: Chunk ID
            element_id: 要移除的 Element ID
        
        Returns:
            移除成功返回 True，失败返回 False
        """
        try:
            chunk = self.get_by_id(session, chunk_id)
            if not chunk:
                logger.warning(f"Chunk 不存在: {chunk_id}")
                return False
            
            # 移除 element_id
            if chunk.element_ids and element_id in chunk.element_ids:
                chunk.element_ids.remove(element_id)
                session.commit()
                logger.debug(f"从ChunkMetaInfo移除element_id: {chunk_id} - {element_id}")
            else:
                logger.debug(f"element_id 不存在，跳过: {element_id}")
            
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"移除element_id失败: {e}")
            return False


# 全局实例
chunk_meta_info_repo = ChunkMetaInfoRepository()
