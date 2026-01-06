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


# 全局实例
section_meta_info_repo = SectionMetaInfoRepository()
