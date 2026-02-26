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
    2026/02/16 - 适配新结构：新增按 folder_id、knowledge_base_id 查询方法
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
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
    
    def get_by_folder_id(
        self,
        session: Session,
        user_id: str,
        folder_id: Optional[str]
    ) -> List[WorkspaceFileSystem]:
        """
        根据文件夹ID查询该文件夹下的所有文件
        
        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_id: 文件夹ID（None 表示根目录下的文件）
        
        Returns:
            WorkspaceFileSystem 列表
        """
        try:
            query = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.deleted == 0
            )
            
            if folder_id is None:
                query = query.filter(self.model.folder_id.is_(None))
            else:
                query = query.filter(self.model.folder_id == folder_id)
            
            results = query.all()
            
            logger.debug(
                f"查询到{len(results)}个WorkspaceFileSystem: "
                f"user_id={user_id}, folder_id={folder_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据folder_id查询失败: {e}")
            return []
    
    def get_by_knowledge_base_id(
        self,
        session: Session,
        user_id: str,
        knowledge_base_id: str
    ) -> List[WorkspaceFileSystem]:
        """
        根据知识库ID查询所有文件
        
        Args:
            session: 数据库会话
            user_id: 用户ID
            knowledge_base_id: 知识库ID
        
        Returns:
            WorkspaceFileSystem 列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.knowledge_base_id == knowledge_base_id,
                self.model.deleted == 0
            ).all()
            
            logger.debug(
                f"查询到{len(results)}个WorkspaceFileSystem: "
                f"user_id={user_id}, knowledge_base_id={knowledge_base_id}"
            )
            return results
        except SQLAlchemyError as e:
            logger.error(f"根据knowledge_base_id查询失败: {e}")
            return []
    
    def get_by_sha256(
        self,
        session: Session,
        file_sha256: bytes
    ) -> Optional[WorkspaceFileSystem]:
        """
        根据 SHA256 哈希值查询已有文件（用于内容去重，复用 document_id）
        
        Args:
            session: 数据库会话
            file_sha256: 文件 SHA256 哈希值（32字节二进制）
        
        Returns:
            第一个匹配的 WorkspaceFileSystem 实例，未找到返回 None
        """
        try:
            result = session.query(self.model).filter(
                self.model.file_sha256 == file_sha256,
                self.model.document_id.isnot(None),
                self.model.deleted == 0
            ).first()
            return result
        except SQLAlchemyError as e:
            logger.error(f"根据SHA256查询失败: {e}")
            return None
    
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
        根据联合主键软删除
        
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
    
    def delete_by_folder_id(
        self,
        session: Session,
        user_id: str,
        folder_id: str,
        updater: str = ""
    ) -> bool:
        """
        根据文件夹ID批量软删除该文件夹下的所有文件
        
        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_id: 文件夹ID
            updater: 更新者
        
        Returns:
            删除成功返回 True，否则返回 False
        """
        try:
            updated_count = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.folder_id == folder_id,
                self.model.deleted == 0
            ).update({
                'deleted': 1,
                'updater': updater
            }, synchronize_session='fetch')
            
            session.commit()
            logger.debug(
                f"成功批量删除{updated_count}个文件: "
                f"user_id={user_id}, folder_id={folder_id}"
            )
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"根据folder_id批量删除文件失败: {e}")
            return False

    # ==================== 回收站相关 ====================

    def cascade_soft_delete_by_folder_ids(
        self,
        session: Session,
        user_id: str,
        folder_ids: List[str],
        updater: str = "",
    ) -> int:
        """
        按文件夹ID列表级联软删除文件（deleted=2，回收站不可见）。
        **不会 commit**，由调用方统一提交事务。

        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_ids: 需要级联删除文件的文件夹ID列表
            updater: 更新者

        Returns:
            被删除的文件数量
        """
        if not folder_ids:
            return 0
        count = session.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.folder_id.in_(folder_ids),
            self.model.deleted == 0,
        ).update(
            {'deleted': 2, 'updater': updater},
            synchronize_session='fetch',
        )
        logger.debug(f"级联软删除{count}个文件: folder_ids count={len(folder_ids)}")
        return count

    def restore_by_folder_ids(
        self,
        session: Session,
        user_id: str,
        folder_ids: List[str],
    ) -> int:
        """
        按文件夹ID列表恢复级联删除的文件（deleted=2 -> 0）。
        **不会 commit**。

        Returns:
            被恢复的文件数量
        """
        if not folder_ids:
            return 0
        count = session.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.folder_id.in_(folder_ids),
            self.model.deleted == 2,
        ).update({'deleted': 0}, synchronize_session='fetch')
        logger.debug(f"恢复{count}个文件: folder_ids count={len(folder_ids)}")
        return count

    def get_deleted_files(
        self,
        session: Session,
        user_id: str,
        knowledge_base_id: Optional[str] = None,
    ) -> List[WorkspaceFileSystem]:
        """
        获取回收站中的文件（仅 deleted=1，即用户直接删除的文件）

        Args:
            session: 数据库会话
            user_id: 用户ID
            knowledge_base_id: 可选，按知识库筛选

        Returns:
            WorkspaceFileSystem 列表，按删除时间倒序
        """
        try:
            query = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.deleted == 1,
            )
            if knowledge_base_id:
                query = query.filter(
                    self.model.knowledge_base_id == knowledge_base_id
                )
            return query.order_by(self.model.update_time.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"查询回收站文件失败: {e}")
            return []

    def get_deleted_files_by_folder(
        self,
        session: Session,
        user_id: str,
        folder_id: str,
    ) -> List[WorkspaceFileSystem]:
        """
        获取回收站中某文件夹下的直接子文件（deleted=1 或 deleted=2）。
        用于在回收站内浏览文件夹内容。

        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_id: 文件夹ID

        Returns:
            WorkspaceFileSystem 列表
        """
        try:
            return session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.folder_id == folder_id,
                self.model.deleted.in_([1, 2]),
            ).order_by(self.model.file_name).all()
        except SQLAlchemyError as e:
            logger.error(f"查询回收站文件夹内文件失败: {e}")
            return []

    def hard_delete_by_folder_ids(
        self,
        session: Session,
        user_id: str,
        folder_ids: List[str],
    ) -> int:
        """
        按文件夹ID列表永久删除文件（物理删除）。
        **不会 commit**。

        Returns:
            被删除的文件数量
        """
        if not folder_ids:
            return 0
        count = session.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.folder_id.in_(folder_ids),
            self.model.deleted.in_([1, 2]),
        ).delete(synchronize_session='fetch')
        logger.debug(
            f"永久删除{count}个文件: folder_ids count={len(folder_ids)}"
        )
        return count

    def hard_delete_by_file_id(
        self,
        session: Session,
        user_id: str,
        file_id: str,
    ) -> bool:
        """
        按文件ID永久删除单个文件（物理删除）。
        **不会 commit**。

        Returns:
            是否找到并删除
        """
        count = session.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.file_id == file_id,
            self.model.deleted.in_([1, 2]),
        ).delete(synchronize_session='fetch')
        return count > 0

    def hard_delete_all_trash(
        self,
        session: Session,
        user_id: str,
    ) -> int:
        """
        清空回收站：永久删除用户所有已删除的文件。
        **不会 commit**。

        Returns:
            被删除的文件数量
        """
        count = session.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.deleted.in_([1, 2]),
        ).delete(synchronize_session='fetch')
        logger.info(f"清空回收站文件: user_id={user_id}, 删除{count}个文件")
        return count


# 全局实例
workspace_file_system_repo = WorkspaceFileSystemRepository()
