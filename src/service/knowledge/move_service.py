#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : move_service.py
@Author  : caixiongjiang
@Date    : 2026/03/18
@Function: 
    Knowledge 文件移动服务
    提供文件移动相关的业务逻辑：单文件移动、批量移动、目标文件夹校验、知识库一致性校验
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from dataclasses import dataclass, field
from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.db.mysql.models.business.workspace_folder import WorkspaceFolder
from src.db.mysql.repositories.business.workspace_file_system_repo import (
    workspace_file_system_repo,
)


@dataclass
class SkippedFile:
    """被跳过的文件信息"""
    file_id: str
    reason: str


@dataclass
class MoveResult:
    """文件移动操作的结果"""
    moved_count: int = 0
    total_requested: int = 0
    skipped_files: List[SkippedFile] = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        return self.moved_count == self.total_requested


class KnowledgeMoveService:
    """Knowledge 文件移动服务

    提供文件级别的移动能力，包含：
    - 目标文件夹存在性与权限校验
    - 同一知识库内移动校验
    - 单文件移动与批量移动
    """

    def validate_target_folder(
        self,
        session: Session,
        user_id: str,
        target_folder_id: str | None,
        expected_knowledge_base_id: str | None = None,
    ) -> Optional[WorkspaceFolder]:
        """校验目标文件夹，返回文件夹对象

        Args:
            session: 数据库会话
            user_id: 用户ID
            target_folder_id: 目标文件夹ID（None 表示根目录，跳过校验）
            expected_knowledge_base_id: 期望的知识库ID，用于校验跨知识库移动

        Returns:
            WorkspaceFolder 对象，target_folder_id 为 None 时返回 None

        Raises:
            ValueError: 文件夹不存在、无权限或跨知识库
        """
        if target_folder_id is None:
            return None

        folder = session.query(WorkspaceFolder).filter(
            WorkspaceFolder.folder_id == target_folder_id,
            WorkspaceFolder.user_id == user_id,
            WorkspaceFolder.deleted == 0,
        ).first()

        if not folder:
            raise ValueError("目标文件夹不存在或无权限")

        if (
            expected_knowledge_base_id is not None
            and folder.knowledge_base_id != expected_knowledge_base_id
        ):
            raise ValueError(
                f"不允许跨知识库移动文件: "
                f"文件属于知识库 {expected_knowledge_base_id}, "
                f"目标文件夹属于知识库 {folder.knowledge_base_id}"
            )

        return folder

    def move_file(
        self,
        session: Session,
        user_id: str,
        file_id: str,
        target_folder_id: str | None,
    ) -> str:
        """移动单个文件到目标文件夹

        Args:
            session: 数据库会话
            user_id: 用户ID
            file_id: 文件ID
            target_folder_id: 目标文件夹ID（None 表示移到知识库根目录）

        Returns:
            移动后的文件名

        Raises:
            FileNotFoundError: 文件不存在或无权限
            ValueError: 目标文件夹无效、跨知识库、或文件已在目标文件夹
            SQLAlchemyError: 数据库操作失败
        """
        file_record = workspace_file_system_repo.get_by_user_and_file(
            session, user_id, file_id
        )
        if not file_record:
            raise FileNotFoundError(f"文件不存在或无权限: file_id={file_id}")

        if file_record.folder_id == target_folder_id:
            raise ValueError("文件已在目标文件夹中")

        self.validate_target_folder(
            session, user_id, target_folder_id,
            expected_knowledge_base_id=file_record.knowledge_base_id,
        )

        file_record.folder_id = target_folder_id
        file_record.updater = user_id
        session.commit()

        logger.info(
            f"文件移动成功: user_id={user_id}, file_id={file_id}, "
            f"target_folder_id={target_folder_id}"
        )
        return file_record.file_name

    def batch_move_files(
        self,
        session: Session,
        user_id: str,
        file_ids: List[str],
        target_folder_id: str | None,
    ) -> MoveResult:
        """批量移动文件到目标文件夹

        对每个文件独立校验，跳过不满足条件的文件并记录原因，
        成功的文件在同一事务中提交。

        Args:
            session: 数据库会话
            user_id: 用户ID
            file_ids: 文件ID列表
            target_folder_id: 目标文件夹ID（None 表示移到知识库根目录）

        Returns:
            MoveResult 包含成功数量和跳过的文件详情

        Raises:
            ValueError: 目标文件夹不存在或无权限
            SQLAlchemyError: 数据库操作失败
        """
        result = MoveResult(total_requested=len(file_ids))

        target_folder = self.validate_target_folder(
            session, user_id, target_folder_id
        )
        target_kb_id = target_folder.knowledge_base_id if target_folder else None

        try:
            for file_id in file_ids:
                file_record = workspace_file_system_repo.get_by_user_and_file(
                    session, user_id, file_id
                )
                if not file_record:
                    result.skipped_files.append(
                        SkippedFile(file_id=file_id, reason="文件不存在或无权限")
                    )
                    continue

                if file_record.folder_id == target_folder_id:
                    result.skipped_files.append(
                        SkippedFile(file_id=file_id, reason="文件已在目标文件夹中")
                    )
                    continue

                if (
                    target_kb_id is not None
                    and file_record.knowledge_base_id != target_kb_id
                ):
                    result.skipped_files.append(
                        SkippedFile(
                            file_id=file_id,
                            reason=f"不允许跨知识库移动: 文件属于 {file_record.knowledge_base_id}",
                        )
                    )
                    continue

                file_record.folder_id = target_folder_id
                file_record.updater = user_id
                result.moved_count += 1

            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"批量移动文件失败: {e}")
            raise

        logger.info(
            f"批量移动文件完成: user_id={user_id}, "
            f"moved={result.moved_count}/{result.total_requested}, "
            f"skipped={len(result.skipped_files)}, "
            f"target_folder_id={target_folder_id}"
        )
        return result


knowledge_move_service = KnowledgeMoveService()
