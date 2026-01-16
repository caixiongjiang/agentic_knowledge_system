#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : document_meta_info_repo.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    DocumentMetaInfo Repository
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.base.document_meta_info import DocumentMetaInfo
from src.db.mysql.repositories.base_repository import BaseRepository


class DocumentMetaInfoRepository(BaseRepository[DocumentMetaInfo]):
    """DocumentMetaInfo Repository"""
    
    def __init__(self):
        super().__init__(DocumentMetaInfo)
    
    def get_by_file_name(
        self, 
        session: Session,
        file_name: str
    ) -> List[DocumentMetaInfo]:
        """
        根据 file_name 查询所有 DocumentMetaInfo
        
        Args:
            session: 数据库会话
            file_name: 文件名
        
        Returns:
            DocumentMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.file_name == file_name,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个DocumentMetaInfo: file_name={file_name}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据file_name查询失败: {e}")
            return []
    
    def get_by_file_type(
        self, 
        session: Session,
        file_type: str
    ) -> List[DocumentMetaInfo]:
        """
        根据 file_type 查询所有 DocumentMetaInfo
        
        Args:
            session: 数据库会话
            file_type: 文件类型
        
        Returns:
            DocumentMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.file_type == file_type,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个DocumentMetaInfo: file_type={file_type}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据file_type查询失败: {e}")
            return []


# 全局实例
document_meta_info_repo = DocumentMetaInfoRepository()
