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

import uuid
from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.db.mysql.models.business.workspace_folder import WorkspaceFolder
from src.db.mysql.repositories.base_repository import BaseRepository

_DEFAULT_FOLDER_NAME = "user_uploads"
_DEFAULT_FOLDER_PATH = f"/{_DEFAULT_FOLDER_NAME}/"


class WorkspaceFolderRepository(BaseRepository[WorkspaceFolder]):
    """WorkspaceFolder Repository"""
    
    def __init__(self):
        super().__init__(WorkspaceFolder)
    
    def get_or_create_default(
        self,
        session: Session,
        user_id: str,
        knowledge_base_id: str,
    ) -> WorkspaceFolder:
        """
        获取或创建用户在指定知识库下的默认文件夹

        同一 (user_id, knowledge_base_id) 下最多一个 is_default=1 的文件夹。
        首次调用时自动创建，后续直接返回已有记录。
        知识库名称从 knowledge_base 表自动查询，无需外部传入。

        Args:
            session: 数据库会话
            user_id: 用户 ID
            knowledge_base_id: 知识库 ID

        Returns:
            默认文件夹的 WorkspaceFolder 实例

        Raises:
            RuntimeError: 创建默认文件夹失败时抛出
        """
        try:
            existing = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.knowledge_base_id == knowledge_base_id,
                self.model.is_default == 1,
                self.model.deleted == 0,
            ).first()

            if existing:
                return existing

            from src.db.mysql.models.business.knowledge_base import KnowledgeBase
            kb = session.query(KnowledgeBase).filter(
                KnowledgeBase.knowledge_base_id == knowledge_base_id,
            ).first()
            kb_name = kb.knowledge_base_name if kb else ""

            folder = self.model(
                folder_id=str(uuid.uuid4()),
                user_id=user_id,
                folder_name=_DEFAULT_FOLDER_NAME,
                parent_folder_id=None,
                full_path=_DEFAULT_FOLDER_PATH,
                depth=0,
                sort_order=0,
                is_default=1,
                knowledge_base_id=knowledge_base_id,
                knowledge_base_name=kb_name,
                creator=user_id,
            )
            session.add(folder)
            session.flush()

            logger.info(
                f"创建默认文件夹: user_id={user_id}, "
                f"kb_id={knowledge_base_id}, folder_id={folder.folder_id}"
            )
            return folder

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"获取/创建默认文件夹失败: {e}")
            raise RuntimeError(f"获取默认文件夹失败: {e}") from e

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
        updater: str = "",
    ) -> List[str]:
        """
        软删除文件夹及其所有后代文件夹。

        目标文件夹标记 deleted=1（回收站可见），
        后代文件夹标记 deleted=2（级联删除，回收站不可见）。
        **不会 commit**，由调用方统一提交事务。

        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_id: 文件夹ID
            full_path_prefix: 该文件夹的完整路径前缀
            updater: 更新者

        Returns:
            所有被删除的 folder_id 列表（含目标自身）

        Raises:
            SQLAlchemyError: 数据库操作失败
        """
        session.query(self.model).filter(
            self.model.folder_id == folder_id,
            self.model.user_id == user_id,
            self.model.deleted == 0,
        ).update({'deleted': 1, 'updater': updater}, synchronize_session='fetch')

        descendant_rows = session.query(self.model.folder_id).filter(
            self.model.user_id == user_id,
            self.model.full_path.like(f"{full_path_prefix}%"),
            self.model.folder_id != folder_id,
            self.model.deleted == 0,
        ).all()
        descendant_ids = [row[0] for row in descendant_rows]

        if descendant_ids:
            session.query(self.model).filter(
                self.model.folder_id.in_(descendant_ids),
            ).update(
                {'deleted': 2, 'updater': updater},
                synchronize_session='fetch',
            )

        all_ids = [folder_id] + descendant_ids
        logger.debug(
            f"软删除{len(all_ids)}个文件夹: "
            f"folder_id={folder_id}, prefix={full_path_prefix}"
        )
        return all_ids

    # ==================== 回收站相关 ====================

    def get_deleted_folders(
        self,
        session: Session,
        user_id: str,
        knowledge_base_id: Optional[str] = None,
    ) -> List[WorkspaceFolder]:
        """
        获取回收站中的文件夹（仅 deleted=1，即用户直接删除的顶层文件夹）

        Args:
            session: 数据库会话
            user_id: 用户ID
            knowledge_base_id: 可选，按知识库筛选

        Returns:
            WorkspaceFolder 列表，按删除时间倒序
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
            logger.error(f"查询回收站文件夹失败: {e}")
            return []

    def get_deleted_children(
        self,
        session: Session,
        user_id: str,
        parent_folder_id: str,
    ) -> List[WorkspaceFolder]:
        """
        获取回收站中某文件夹的直接子文件夹（deleted=1 或 deleted=2）。
        用于在回收站内浏览文件夹层级。

        Args:
            session: 数据库会话
            user_id: 用户ID
            parent_folder_id: 父文件夹ID

        Returns:
            直接子文件夹列表
        """
        try:
            return session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.parent_folder_id == parent_folder_id,
                self.model.deleted.in_([1, 2]),
            ).order_by(self.model.folder_name).all()
        except SQLAlchemyError as e:
            logger.error(f"查询回收站子文件夹失败: {e}")
            return []

    def restore_with_descendants(
        self,
        session: Session,
        user_id: str,
        folder_id: str,
    ) -> List[str]:
        """
        恢复文件夹及其所有级联删除的后代。
        如果原父文件夹已被删除或不存在，则移到根目录。
        **不会 commit**，由调用方统一提交事务。

        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_id: 文件夹ID（必须是 deleted=1 的）

        Returns:
            所有被恢复的 folder_id 列表

        Raises:
            ValueError: 文件夹不存在
        """
        folder = session.query(self.model).filter(
            self.model.folder_id == folder_id,
            self.model.user_id == user_id,
            self.model.deleted == 1,
        ).first()
        if not folder:
            raise ValueError("回收站中未找到该文件夹")

        old_path: str = folder.full_path
        old_depth: int = folder.depth
        need_relocate = False

        if folder.parent_folder_id:
            parent = session.query(self.model).filter(
                self.model.folder_id == folder.parent_folder_id,
                self.model.user_id == user_id,
                self.model.deleted == 0,
            ).first()
            if not parent:
                need_relocate = True
                folder.parent_folder_id = None
                folder.full_path = f"/{folder.folder_name}/"
                folder.depth = 0

        folder.deleted = 0

        descendants = session.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.full_path.like(f"{old_path}%"),
            self.model.folder_id != folder_id,
            self.model.deleted == 2,
        ).all()

        descendant_ids: List[str] = []
        if need_relocate:
            new_path = folder.full_path
            depth_delta = folder.depth - old_depth
            for d in descendants:
                d.full_path = new_path + d.full_path[len(old_path):]
                d.depth = d.depth + depth_delta
                d.deleted = 0
                descendant_ids.append(d.folder_id)
        else:
            for d in descendants:
                d.deleted = 0
                descendant_ids.append(d.folder_id)

        all_ids = [folder_id] + descendant_ids
        logger.info(f"恢复{len(all_ids)}个文件夹: folder_id={folder_id}")
        return all_ids

    def hard_delete_with_descendants(
        self,
        session: Session,
        user_id: str,
        folder_id: str,
    ) -> tuple[List[str], int]:
        """
        永久删除文件夹及其后代（物理删除）。
        **不会 commit**，由调用方统一提交事务。

        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_id: 文件夹ID（必须是 deleted=1 的）

        Returns:
            (被删除的 folder_id 列表, 删除数量)

        Raises:
            ValueError: 文件夹不存在
        """
        folder = session.query(self.model).filter(
            self.model.folder_id == folder_id,
            self.model.user_id == user_id,
            self.model.deleted == 1,
        ).first()
        if not folder:
            raise ValueError("回收站中未找到该文件夹")

        all_rows = session.query(self.model.folder_id).filter(
            self.model.user_id == user_id,
            self.model.full_path.like(f"{folder.full_path}%"),
            self.model.deleted.in_([1, 2]),
        ).all()
        all_ids = [row[0] for row in all_rows]

        count = session.query(self.model).filter(
            self.model.folder_id.in_(all_ids),
        ).delete(synchronize_session='fetch')

        logger.info(f"永久删除{count}个文件夹: folder_id={folder_id}")
        return all_ids, count

    def hard_delete_all_trash(
        self,
        session: Session,
        user_id: str,
    ) -> tuple[List[str], int]:
        """
        清空回收站：永久删除用户所有已删除的文件夹。
        **不会 commit**。

        Returns:
            (被删除的 folder_id 列表, 删除数量)
        """
        all_rows = session.query(self.model.folder_id).filter(
            self.model.user_id == user_id,
            self.model.deleted.in_([1, 2]),
        ).all()
        all_ids = [row[0] for row in all_rows]

        count = 0
        if all_ids:
            count = session.query(self.model).filter(
                self.model.folder_id.in_(all_ids),
            ).delete(synchronize_session='fetch')

        logger.info(f"清空回收站: user_id={user_id}, 删除{count}个文件夹")
        return all_ids, count

    def restore_ancestors_chain(
        self,
        session: Session,
        user_id: str,
        start_folder_id: str,
    ) -> List[str]:
        """
        从指定文件夹开始向上遍历，恢复整条祖先链路。
        将所有 deleted!=0 的祖先文件夹设为 deleted=0。
        如果最顶层祖先的父文件夹不存在或仍被删除，则将其移到根目录。
        **不会 commit**。

        Args:
            session: 数据库会话
            user_id: 用户ID
            start_folder_id: 起始文件夹ID（向上查找其祖先）

        Returns:
            被恢复的祖先文件夹 ID 列表（不含 start_folder_id 自身）
        """
        restored_ancestor_ids: List[str] = []
        current_id = start_folder_id

        while current_id:
            folder = session.query(self.model).filter(
                self.model.folder_id == current_id,
                self.model.user_id == user_id,
            ).first()
            if not folder:
                break

            if folder.deleted != 0:
                folder.deleted = 0
                if current_id != start_folder_id:
                    restored_ancestor_ids.append(current_id)

            if folder.parent_folder_id:
                parent = session.query(self.model).filter(
                    self.model.folder_id == folder.parent_folder_id,
                    self.model.user_id == user_id,
                ).first()
                if not parent or parent.deleted != 0:
                    if parent and parent.deleted != 0:
                        current_id = folder.parent_folder_id
                        continue
                    folder.parent_folder_id = None
                    folder.full_path = f"/{folder.folder_name}/"
                    folder.depth = 0
                    break
                break
            else:
                break

        logger.debug(
            f"恢复祖先链: start={start_folder_id}, "
            f"restored_ancestors={len(restored_ancestor_ids)}"
        )
        return restored_ancestor_ids

    def restore_subfolder_with_ancestors(
        self,
        session: Session,
        user_id: str,
        folder_id: str,
    ) -> tuple[List[str], List[str]]:
        """
        从回收站恢复一个子文件夹（deleted=1 或 deleted=2），
        同时恢复其所有后代（文件夹），并自动重建祖先链路。
        **不会 commit**。

        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_id: 要恢复的子文件夹ID

        Returns:
            (restored_folder_ids, restored_ancestor_ids) 元组
            - restored_folder_ids: 被恢复的文件夹ID列表（含自身和后代）
            - restored_ancestor_ids: 被恢复的祖先文件夹ID列表

        Raises:
            ValueError: 文件夹不存在
        """
        folder = session.query(self.model).filter(
            self.model.folder_id == folder_id,
            self.model.user_id == user_id,
            self.model.deleted.in_([1, 2]),
        ).first()
        if not folder:
            raise ValueError("回收站中未找到该文件夹")

        folder.deleted = 0

        descendants = session.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.full_path.like(f"{folder.full_path}%"),
            self.model.folder_id != folder_id,
            self.model.deleted.in_([1, 2]),
        ).all()

        descendant_ids: List[str] = []
        for d in descendants:
            d.deleted = 0
            descendant_ids.append(d.folder_id)

        all_restored = [folder_id] + descendant_ids

        restored_ancestor_ids: List[str] = []
        if folder.parent_folder_id:
            restored_ancestor_ids = self.restore_ancestors_chain(
                session, user_id, folder.parent_folder_id
            )

        logger.info(
            f"恢复子文件夹: folder_id={folder_id}, "
            f"descendants={len(descendant_ids)}, ancestors={len(restored_ancestor_ids)}"
        )
        return all_restored, restored_ancestor_ids

    def hard_delete_subfolder(
        self,
        session: Session,
        user_id: str,
        folder_id: str,
    ) -> tuple[List[str], int]:
        """
        永久删除回收站中的子文件夹及其所有后代（物理删除）。
        支持 deleted=1 和 deleted=2 的文件夹。
        **不会 commit**。

        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_id: 文件夹ID

        Returns:
            (被删除的 folder_id 列表, 删除数量)

        Raises:
            ValueError: 文件夹不存在
        """
        folder = session.query(self.model).filter(
            self.model.folder_id == folder_id,
            self.model.user_id == user_id,
            self.model.deleted.in_([1, 2]),
        ).first()
        if not folder:
            raise ValueError("回收站中未找到该文件夹")

        all_rows = session.query(self.model.folder_id).filter(
            self.model.user_id == user_id,
            self.model.full_path.like(f"{folder.full_path}%"),
            self.model.deleted.in_([1, 2]),
        ).all()
        all_ids = [row[0] for row in all_rows]

        count = session.query(self.model).filter(
            self.model.folder_id.in_(all_ids),
        ).delete(synchronize_session='fetch')

        logger.info(f"永久删除子文件夹: folder_id={folder_id}, count={count}")
        return all_ids, count

    def rename(
        self,
        session: Session,
        user_id: str,
        folder_id: str,
        new_name: str,
        updater: str = "",
    ) -> Optional[WorkspaceFolder]:
        """
        重命名文件夹，并级联更新所有后代的 full_path

        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_id: 文件夹ID
            new_name: 新名称
            updater: 更新者

        Returns:
            重命名后的 WorkspaceFolder，失败返回 None
        """
        try:
            folder = session.query(self.model).filter(
                self.model.folder_id == folder_id,
                self.model.user_id == user_id,
                self.model.deleted == 0,
            ).first()
            if not folder:
                return None

            old_path: str = folder.full_path
            parent_path = old_path.rsplit(folder.folder_name + "/", 1)[0]
            new_path = f"{parent_path}{new_name}/"

            dup = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.full_path == new_path,
                self.model.deleted == 0,
                self.model.folder_id != folder_id,
            ).first()
            if dup:
                raise ValueError(f"同级已存在同名文件夹: {new_path}")

            folder.folder_name = new_name
            folder.full_path = new_path
            folder.updater = updater

            descendants = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.full_path.like(f"{old_path}%"),
                self.model.folder_id != folder_id,
                self.model.deleted == 0,
            ).all()
            for d in descendants:
                d.full_path = new_path + d.full_path[len(old_path):]
                d.updater = updater

            session.commit()
            session.refresh(folder)
            logger.info(
                f"重命名文件夹: folder_id={folder_id}, "
                f"{old_path} -> {new_path}, 级联更新{len(descendants)}个后代"
            )
            return folder

        except ValueError:
            session.rollback()
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"重命名文件夹失败: {e}")
            return None

    def move(
        self,
        session: Session,
        user_id: str,
        folder_id: str,
        target_parent_folder_id: Optional[str],
        updater: str = "",
    ) -> Optional[WorkspaceFolder]:
        """
        移动文件夹到新的父文件夹，级联更新后代的 full_path 和 depth

        Args:
            session: 数据库会话
            user_id: 用户ID
            folder_id: 文件夹ID
            target_parent_folder_id: 目标父文件夹ID，None 表示移到根目录
            updater: 更新者

        Returns:
            移动后的 WorkspaceFolder，失败返回 None
        """
        try:
            folder = session.query(self.model).filter(
                self.model.folder_id == folder_id,
                self.model.user_id == user_id,
                self.model.deleted == 0,
            ).first()
            if not folder:
                return None

            old_path: str = folder.full_path
            old_depth: int = folder.depth

            new_parent_path = "/"
            new_depth = 0

            if target_parent_folder_id is not None:
                parent = session.query(self.model).filter(
                    self.model.folder_id == target_parent_folder_id,
                    self.model.user_id == user_id,
                    self.model.deleted == 0,
                ).first()
                if not parent:
                    raise ValueError("目标父文件夹不存在或无权限")

                if parent.full_path.startswith(old_path):
                    raise ValueError("不能将文件夹移动到自身的子目录下")

                new_parent_path = parent.full_path
                new_depth = parent.depth + 1

            new_path = f"{new_parent_path}{folder.folder_name}/"

            dup = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.full_path == new_path,
                self.model.deleted == 0,
                self.model.folder_id != folder_id,
            ).first()
            if dup:
                raise ValueError(f"目标位置已存在同名文件夹: {new_path}")

            depth_delta = new_depth - old_depth
            folder.parent_folder_id = target_parent_folder_id
            folder.full_path = new_path
            folder.depth = new_depth
            folder.updater = updater

            descendants = session.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.full_path.like(f"{old_path}%"),
                self.model.folder_id != folder_id,
                self.model.deleted == 0,
            ).all()
            for d in descendants:
                d.full_path = new_path + d.full_path[len(old_path):]
                d.depth = d.depth + depth_delta
                d.updater = updater

            session.commit()
            session.refresh(folder)
            logger.info(
                f"移动文件夹: folder_id={folder_id}, "
                f"{old_path} -> {new_path}, 级联更新{len(descendants)}个后代"
            )
            return folder

        except ValueError:
            session.rollback()
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"移动文件夹失败: {e}")
            return None


# 全局实例
workspace_folder_repo = WorkspaceFolderRepository()
