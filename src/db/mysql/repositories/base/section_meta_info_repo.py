#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_meta_info_repo.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    SectionMetaInfo Repository
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.base.section_meta_info import SectionMetaInfo
from src.db.mysql.repositories.base_repository import BaseRepository


class SectionMetaInfoRepository(BaseRepository[SectionMetaInfo]):
    """SectionMetaInfo Repository"""
    
    def __init__(self):
        super().__init__(SectionMetaInfo)
    
    def get_by_level(
        self, 
        session: Session,
        level: int
    ) -> List[SectionMetaInfo]:
        """
        根据 level 查询所有 SectionMetaInfo
        
        Args:
            session: 数据库会话
            level: 层级深度
        
        Returns:
            SectionMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.level == level,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个SectionMetaInfo: level={level}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据level查询失败: {e}")
            return []
    
    def get_by_page_range(
        self, 
        session: Session,
        start_page: int,
        end_page: int
    ) -> List[SectionMetaInfo]:
        """
        根据页面范围查询 SectionMetaInfo
        
        Args:
            session: 数据库会话
            start_page: 起始页码
            end_page: 结束页码
        
        Returns:
            SectionMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.start_page_index >= start_page,
                self.model.end_page_index <= end_page,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个SectionMetaInfo: "
                f"page_range=[{start_page}, {end_page}]"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据页面范围查询失败: {e}")
            return []
    
    def get_by_element_id(
        self,
        session: Session,
        element_id: str
    ) -> Optional[SectionMetaInfo]:
        """
        根据 element_id 查询 SectionMetaInfo（用于 pipeline）
        
        Args:
            session: 数据库会话
            element_id: 关联的 Element ID
        
        Returns:
            SectionMetaInfo 实例，未找到返回 None
        """
        try:
            result = session.query(self.model).filter(
                self.model.element_id == element_id,
                self.model.deleted == 0
            ).first()
            
            if result:
                logger.debug(f"找到SectionMetaInfo: element_id={element_id}")
            else:
                logger.debug(f"未找到SectionMetaInfo: element_id={element_id}")
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"根据element_id查询失败: {e}")
            return None
    
    def update_element_id(
        self,
        session: Session,
        section_id: str,
        element_id: str
    ) -> bool:
        """
        更新 Section 的 element_id（用于 pipeline）
        
        Args:
            session: 数据库会话
            section_id: Section ID
            element_id: 要关联的 Element ID
        
        Returns:
            更新成功返回 True，失败返回 False
        """
        try:
            section = self.get_by_id(session, section_id)
            if not section:
                logger.warning(f"Section 不存在: {section_id}")
                return False
            
            section.element_id = element_id
            session.commit()
            
            logger.debug(f"更新SectionMetaInfo element_id: {section_id} -> {element_id}")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新element_id失败: {e}")
            return False


# 全局实例
section_meta_info_repo = SectionMetaInfoRepository()
