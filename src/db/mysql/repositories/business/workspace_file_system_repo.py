#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : workspace_file_system_repo.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    WorkspaceFileSystem Repository
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.business.workspace_file_system import WorkspaceFileSystem
from src.db.mysql.repositories.base_repository import BaseRepository


class WorkspaceFileSystemRepository(BaseRepository[WorkspaceFileSystem]):
    """WorkspaceFileSystem Repository（联合主键表）"""
    
    def __init__(self):
        super().__init__(WorkspaceFileSystem)
    
    def get_by_user_and_file(
        self,
        session: Session,
        user_id: str,
        file_id: str
    ) -> Optional[WorkspaceFileSystem]:
        """
        根据联合主键查询
        
        Args:
            session: 数据库会话
            user_id: 用户ID
            file_id: 文件ID
        
        Returns:
            WorkspaceFileSystem 实例，未找到返回 None
        """
        try:
            result = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.file_id == file_id,
                self.model.deleted == 0
            ).first()
            
            if not result:
                logger.debug(
                    f"未找到WorkspaceFileSystem: user_id={user_id}, file_id={file_id}"
                )
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"查询WorkspaceFileSystem失败: {e}")
            return None
    
    def get_by_user_id(
        self,
        session: Session,
        user_id: str
    ) -> List[WorkspaceFileSystem]:
        """
        根据 user_id 查询所有文件
        
        Args:
            session: 数据库会话
            user_id: 用户ID
        
        Returns:
            WorkspaceFileSystem 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个WorkspaceFileSystem: user_id={user_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据user_id查询失败: {e}")
            return []
    
    def get_by_document_id(
        self,
        session: Session,
        document_id: str
    ) -> List[WorkspaceFileSystem]:
        """
        根据 document_id 查询所有文件
        
        Args:
            session: 数据库会话
            document_id: Document ID
        
        Returns:
            WorkspaceFileSystem 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.document_id == document_id,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个WorkspaceFileSystem: document_id={document_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据document_id查询失败: {e}")
            return []
    
    def delete_by_user_and_file(
        self,
        session: Session,
        user_id: str,
        file_id: str,
        updater: str = ""
    ) -> bool:
        """
        根据联合主键删除
        
        Args:
            session: 数据库会话
            user_id: 用户ID
            file_id: 文件ID
            updater: 更新者
        
        Returns:
            删除成功返回 True，否则返回 False
        """
        try:
            obj = self.get_by_user_and_file(session, user_id, file_id)
            if obj:
                obj.deleted = 1
                obj.updater = updater
                # update_time 由数据库 onupdate 自动处理
                session.commit()
                logger.debug(
                    f"成功删除WorkspaceFileSystem: user_id={user_id}, file_id={file_id}"
                )
                return True
            
            logger.debug(
                f"未找到要删除的WorkspaceFileSystem: user_id={user_id}, file_id={file_id}"
            )
            return False
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"删除WorkspaceFileSystem失败: {e}")
            return False


# 全局实例
workspace_file_system_repo = WorkspaceFileSystemRepository()
