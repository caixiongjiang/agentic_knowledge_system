#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : workspace_folder_repo.py
@Author  : caixiongjiang
@Date    : 2026/02/16
@Function: 
    WorkspaceFolder Repository
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.business.workspace_folder import WorkspaceFolder
from src.db.mysql.repositories.base_repository import BaseRepository


class WorkspaceFolderRepository(BaseRepository[WorkspaceFolder]):
    """WorkspaceFolder Repository"""
    
    def __init__(self):
        super().__init__(WorkspaceFolder)
    
    def get_by_user_id(
        self,
        session: Session,
        user_id: str
    ) -> List[WorkspaceFolder]:
        """
        根据 user_id 查询所有文件夹
        
        Args:
            session: 数据库会话
            user_id: 用户ID
        
        Returns:
            WorkspaceFolder 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个WorkspaceFolder: user_id={user_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据user_id查询WorkspaceFolder失败: {e}")
            return []
    
    def get_by_user_and_knowledge_base(
        self,
        session: Session,
        user_id: str,
        knowledge_base_id: str
    ) -> List[WorkspaceFolder]:
        """
        根据用户ID和知识库ID查询文件夹列表
        
        Args:
            session: 数据库会话
            user_id: 用户ID
            knowledge_base_id: 知识库ID
        
        Returns:
            WorkspaceFolder 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.knowledge_base_id == knowledge_base_id,
                self.model.deleted == 0
            ).order_by(self.model.depth, self.model.sort_order).all()
            
            logger.debug(
                f"查询到{len(results)}个WorkspaceFolder: "
                f"user_id={user_id}, knowledge_base_id={knowledge_base_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(
                f"根据user_id和knowledge_base_id查询WorkspaceFolder失败: {e}"
            )
            return []
    
    def get_children(
        self,
        session: Session,
        user_id: str,
        parent_folder_id: Optional[str]
    ) -> List[WorkspaceFolder]:
        """
        获取指定文件夹的直接子文件夹
        
        Args:
            session: 数据库会话
            user_id: 用户ID
            parent_folder_id: 父文件夹ID（None 表示查询根目录下的文件夹）
        
        Returns:
            WorkspaceFolder 列表
        """
        try:
            query = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.deleted == 0
            )
            
            if parent_folder_id is None:
                query = query.filter(self.model.parent_folder_id.is_(None))
            else:
                query = query.filter(
                    self.model.parent_folder_id == parent_folder_id
                )
            
            results = query.order_by(self.model.sort_order).all()
            
            logger.debug(
                f"查询到{len(results)}个子文件夹: "
                f"user_id={user_id}, parent_folder_id={parent_folder_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"查询子文件夹失败: {e}")
            return []
    
    def get_by_full_path(
        self,
        session: Session,
        user_id: str,
        full_path: str
    ) -> Optional[WorkspaceFolder]:
        """
        根据完整路径查询文件夹
        
        Args:
            session: 数据库会话
            user_id: 用户ID
            full_path: 完整路径
        
        Returns:
            WorkspaceFolder 实例，未找到返回 None
        """
        try:
            result = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.full_path == full_path,
                self.model.deleted == 0
            ).first()
            
            if not result:
                logger.debug(
                    f"未找到WorkspaceFolder: "
                    f"user_id={user_id}, full_path={full_path}"
                )
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"根据full_path查询WorkspaceFolder失败: {e}")
            return None
    
    def get_descendants(
        self,
        session: Session,
        user_id: str,
        full_path_prefix: str
    ) -> List[WorkspaceFolder]:
        """
        获取指定路径前缀下的所有后代文件夹
        
        通过 full_path 的 LIKE 前缀匹配实现。
        
        Args:
            session: 数据库会话
            user_id: 用户ID
            full_path_prefix: 路径前缀（如 /项目A/文档/）
        
        Returns:
            WorkspaceFolder 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.full_path.like(f"{full_path_prefix}%"),
                self.model.deleted == 0
            ).order_by(self.model.depth).all()
            
            logger.debug(
                f"查询到{len(results)}个后代文件夹: "
                f"user_id={user_id}, prefix={full_path_prefix}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"查询后代文件夹失败: {e}")
            return []
    
    def soft_delete_with_descendants(
        self,
        session: Session,
        user_id: str,
        folder_id: str,
        full_path_prefix: str,
        updater: str = ""
    ) -> bool:
        """
        软删除文件夹及其所有后代文件夹
        
        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_id: 文件夹ID
            full_path_prefix: 该文件夹的完整路径前缀
            updater: 更新者
        
        Returns:
            删除成功返回 True，否则返回 False
        """
        try:
            updated_count = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.full_path.like(f"{full_path_prefix}%"),
                self.model.deleted == 0
            ).update({
                'deleted': 1,
                'updater': updater
            }, synchronize_session='fetch')
            
            session.commit()
            logger.debug(
                f"成功软删除{updated_count}个文件夹: "
                f"folder_id={folder_id}, prefix={full_path_prefix}"
            )
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"软删除文件夹及后代失败: {e}")
            return False


# 全局实例
workspace_folder_repo = WorkspaceFolderRepository()
