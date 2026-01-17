#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : element_meta_info_repo.py
@Author  : caixiongjiang
@Date    : 2026/01/17
@Function: 
    ElementMetaInfo Repository
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.base.element_meta_info import ElementMetaInfo
from src.db.mysql.repositories.base_repository import BaseRepository


class ElementMetaInfoRepository(BaseRepository[ElementMetaInfo]):
    """ElementMetaInfo Repository"""
    
    def __init__(self):
        super().__init__(ElementMetaInfo)
    
    def get_by_element_type(
        self, 
        session: Session,
        element_type: str
    ) -> List[ElementMetaInfo]:
        """
        根据 element_type 查询所有 ElementMetaInfo
        
        Args:
            session: 数据库会话
            element_type: 元素类型（text, image, table, discarded）
        
        Returns:
            ElementMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.element_type == element_type,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个ElementMetaInfo: element_type={element_type}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据element_type查询失败: {e}")
            return []
    
    def get_by_page_index(
        self, 
        session: Session,
        page_index: int
    ) -> List[ElementMetaInfo]:
        """
        根据 page_index 查询所有 ElementMetaInfo
        
        Args:
            session: 数据库会话
            page_index: 页码索引
        
        Returns:
            ElementMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.page_index == page_index,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个ElementMetaInfo: page_index={page_index}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据page_index查询失败: {e}")
            return []
    
    def get_by_level(
        self, 
        session: Session,
        level: int
    ) -> List[ElementMetaInfo]:
        """
        根据 level 查询所有 ElementMetaInfo
        
        Args:
            session: 数据库会话
            level: 元素层级深度
        
        Returns:
            ElementMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.level == level,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个ElementMetaInfo: level={level}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据level查询失败: {e}")
            return []
    
    def get_images_by_page(
        self, 
        session: Session,
        page_index: int
    ) -> List[ElementMetaInfo]:
        """
        查询指定页面的所有图片元素
        
        Args:
            session: 数据库会话
            page_index: 页码索引
        
        Returns:
            图片类型的 ElementMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.page_index == page_index,
                self.model.element_type == "image",
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个图片元素: page_index={page_index}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"查询页面图片元素失败: {e}")
            return []


# 全局实例
element_meta_info_repo = ElementMetaInfoRepository()
