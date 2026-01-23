#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : document_meta_info_repo.py
@Author  : caixiongjiang
@Date    : 2026/01/23
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
        根据文件名查询所有 DocumentMetaInfo
        
        Args:
            session: 数据库会话
            file_name: 文件名（不含路径）
        
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
        根据文件类型查询所有 DocumentMetaInfo
        
        Args:
            session: 数据库会话
            file_type: 文件类型（pdf, docx, txt等）
        
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
    
    def get_by_storage_id(
        self, 
        session: Session,
        storage_id: int
    ) -> List[DocumentMetaInfo]:
        """
        根据存储系统ID查询所有 DocumentMetaInfo
        
        Args:
            session: 数据库会话
            storage_id: 存储系统ID（-1=本地存储，其他值对应具体存储系统）
        
        Returns:
            DocumentMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.storage_id == storage_id,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个DocumentMetaInfo: storage_id={storage_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据storage_id查询失败: {e}")
            return []
    
    def get_by_sha256(
        self, 
        session: Session,
        file_sha256: bytes
    ) -> Optional[DocumentMetaInfo]:
        """
        根据文件SHA256哈希值查询 DocumentMetaInfo（通常唯一）
        
        Args:
            session: 数据库会话
            file_sha256: 文件SHA256哈希值（32字节二进制）
        
        Returns:
            DocumentMetaInfo 对象或 None
        """
        try:
            result = session.query(self.model).filter(
                self.model.file_sha256 == file_sha256,
                self.model.deleted == 0
            ).first()
            
            if result:
                logger.debug(f"找到DocumentMetaInfo: sha256={file_sha256.hex()}")
            else:
                logger.debug(f"未找到DocumentMetaInfo: sha256={file_sha256.hex()}")
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"根据file_sha256查询失败: {e}")
            return None
    
    def get_by_bucket_name(
        self, 
        session: Session,
        bucket_name: str
    ) -> List[DocumentMetaInfo]:
        """
        根据对象存储桶名称查询所有 DocumentMetaInfo
        
        Args:
            session: 数据库会话
            bucket_name: 对象存储桶名称
        
        Returns:
            DocumentMetaInfo 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.bucket_name == bucket_name,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个DocumentMetaInfo: bucket_name={bucket_name}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据bucket_name查询失败: {e}")
            return []
    
    def get_by_file_path(
        self, 
        session: Session,
        file_path: str
    ) -> Optional[DocumentMetaInfo]:
        """
        根据文件路径查询 DocumentMetaInfo
        
        Args:
            session: 数据库会话
            file_path: 文件路径（相对路径或完整路径）
        
        Returns:
            DocumentMetaInfo 对象或 None
        """
        try:
            result = session.query(self.model).filter(
                self.model.file_path == file_path,
                self.model.deleted == 0
            ).first()
            
            if result:
                logger.debug(f"找到DocumentMetaInfo: file_path={file_path}")
            else:
                logger.debug(f"未找到DocumentMetaInfo: file_path={file_path}")
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"根据file_path查询失败: {e}")
            return None


# 全局实例
document_meta_info_repo = DocumentMetaInfoRepository()
