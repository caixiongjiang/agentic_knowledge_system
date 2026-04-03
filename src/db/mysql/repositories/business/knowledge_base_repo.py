#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : knowledge_base_repo.py
@Author  : caixiongjiang
@Date    : 2026/02/19
@Function: 
    KnowledgeBase Repository
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.db.mysql.models.business.knowledge_base import KnowledgeBase
from src.db.mysql.models.business.workspace_file_system import WorkspaceFileSystem
from src.db.mysql.models.business.workspace_folder import WorkspaceFolder
from src.db.mysql.repositories.base_repository import BaseRepository


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """KnowledgeBase Repository"""

    def __init__(self) -> None:
        super().__init__(KnowledgeBase)

    def get_by_user_id(
        self,
        session: Session,
        user_id: str,
    ) -> List[KnowledgeBase]:
        """获取用户的所有知识库"""
        try:
            return (
                session.query(self.model)
                .filter(
                    self.model.user_id == user_id,
                    self.model.deleted == 0,
                )
                .order_by(self.model.create_time.desc())
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"查询用户知识库列表失败: {e}")
            return []

    def get_by_id_and_user(
        self,
        session: Session,
        knowledge_base_id: str,
        user_id: str,
    ) -> Optional[KnowledgeBase]:
        """按 ID + user_id 查询（含权限校验）"""
        try:
            return (
                session.query(self.model)
                .filter(
                    self.model.knowledge_base_id == knowledge_base_id,
                    self.model.user_id == user_id,
                    self.model.deleted == 0,
                )
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"查询知识库失败: {e}")
            return None

    def get_children(
        self,
        session: Session,
        user_id: str,
        parent_knowledge_base_id: Optional[str],
    ) -> List[KnowledgeBase]:
        """获取子知识库列表"""
        try:
            query = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.deleted == 0,
            )
            if parent_knowledge_base_id is None:
                query = query.filter(
                    self.model.parent_knowledge_base_id.is_(None)
                )
            else:
                query = query.filter(
                    self.model.parent_knowledge_base_id
                    == parent_knowledge_base_id
                )
            return query.order_by(self.model.create_time.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"查询子知识库失败: {e}")
            return []

    def check_has_files(
        self,
        session: Session,
        user_id: str,
        knowledge_base_id: str,
    ) -> int:
        """
        检查知识库下是否存在文件（包括活跃文件和回收站中的文件）。

        deleted IN (0, 1, 2) 即所有未被永久删除的文件都算在内。

        Returns:
            文件数量
        """
        try:
            return (
                session.query(WorkspaceFileSystem)
                .filter(
                    WorkspaceFileSystem.user_id == user_id,
                    WorkspaceFileSystem.knowledge_base_id == knowledge_base_id,
                    WorkspaceFileSystem.deleted.in_([0, 1, 2]),
                )
                .count()
            )
        except SQLAlchemyError as e:
            logger.error(f"检查知识库文件数量失败: {e}")
            return -1

    def get_all_descendants(
        self,
        session: Session,
        user_id: str,
        knowledge_base_id: str,
    ) -> List[str]:
        """BFS 收集所有后代知识库 ID（不含自身）"""
        result: List[str] = []
        queue = [knowledge_base_id]
        while queue:
            parent_id = queue.pop(0)
            children = self.get_children(session, user_id, parent_id)
            for child in children:
                result.append(child.knowledge_base_id)
                queue.append(child.knowledge_base_id)
        return result

    def check_tree_has_files(
        self,
        session: Session,
        user_id: str,
        kb_ids: List[str],
    ) -> int:
        """检查一组知识库下的总文件数（含回收站）"""
        if not kb_ids:
            return 0
        try:
            return (
                session.query(WorkspaceFileSystem)
                .filter(
                    WorkspaceFileSystem.user_id == user_id,
                    WorkspaceFileSystem.knowledge_base_id.in_(kb_ids),
                    WorkspaceFileSystem.deleted.in_([0, 1, 2]),
                )
                .count()
            )
        except SQLAlchemyError as e:
            logger.error(f"批量检查知识库文件数量失败: {e}")
            return -1

    def hard_delete(
        self,
        session: Session,
        user_id: str,
        knowledge_base_id: str,
    ) -> int:
        """
        物理删除知识库，同时清理其下的所有文件夹。
        **不会 commit**，由调用方统一提交事务。

        前置条件：知识库下不存在任何文件（由调用方保证）。

        Returns:
            被删除的文件夹数量
        """
        session.query(self.model).filter(
            self.model.knowledge_base_id == knowledge_base_id,
            self.model.user_id == user_id,
        ).delete(synchronize_session='fetch')

        folder_count = session.query(WorkspaceFolder).filter(
            WorkspaceFolder.user_id == user_id,
            WorkspaceFolder.knowledge_base_id == knowledge_base_id,
        ).delete(synchronize_session='fetch')

        logger.info(
            f"物理删除知识库: user_id={user_id}, "
            f"kb_id={knowledge_base_id}, 清理{folder_count}个文件夹"
        )
        return folder_count

    def name_exists(
        self,
        session: Session,
        user_id: str,
        name: str,
        exclude_id: Optional[str] = None,
    ) -> bool:
        """检查同一用户下是否存在同名知识库"""
        try:
            query = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.knowledge_base_name == name,
                self.model.deleted == 0,
            )
            if exclude_id:
                query = query.filter(
                    self.model.knowledge_base_id != exclude_id
                )
            return query.first() is not None
        except SQLAlchemyError as e:
            logger.error(f"检查知识库名称重复失败: {e}")
            return False


# 全局实例
knowledge_base_repo = KnowledgeBaseRepository()
