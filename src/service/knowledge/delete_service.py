#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : delete_service.py
@Author  : caixiongjiang
@Date    : 2026/01/21 10:00
@Function: 
    Knowledge 删除服务
    提供删除相关的业务逻辑：软删除（标记删除）、硬删除（永久删除）、批量删除、删除验证、级联删除处理
@Modify History:
    2026/03/09 - 实现完整删除服务：软删除、永久删除、跨数据库级联删除
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from dataclasses import dataclass, field
from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.db.mysql.repositories.base.chunk_meta_info_repo import chunk_meta_info_repo
from src.db.mysql.repositories.base.chunk_section_document_repo import chunk_section_document_repo
from src.db.mysql.repositories.base.element_meta_info_repo import element_meta_info_repo
from src.db.mysql.repositories.base.section_document_repo import section_document_repo
from src.db.mysql.repositories.base.section_meta_info_repo import section_meta_info_repo
from src.db.mysql.repositories.extract.chunk_atomic_qa_repo import chunk_atomic_qa_repo
from src.db.mysql.repositories.extract.chunk_summary_repo import chunk_summary_repo
from src.db.mysql.repositories.extract.document_summary_repo import document_summary_repo
from src.db.mysql.repositories.business.workspace_file_system_repo import workspace_file_system_repo

from src.db.mongodb.repositories import (
    document_data_repository,
    section_data_repository,
    chunk_data_repository,
    element_data_repository,
)

from src.db.milvus.repositories.base import ChunkRepository, SectionRepository
from src.db.milvus.repositories.enhanced import EnhancedChunkRepository
from src.db.milvus.repositories.extract import (
    AtomicQARepository,
    FileSummaryRepository,
    SectionSummaryRepository,
)
from src.db.milvus.repositories.kg import SPORepository, TagRepository

from src.db.storage.manager import StorageManager


@dataclass
class DeleteResult:
    """删除操作的结果统计"""
    mysql_deleted: int = 0
    mongodb_deleted: int = 0
    milvus_deleted: int = 0
    storage_deleted: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def total_deleted(self) -> int:
        return self.mysql_deleted + self.mongodb_deleted + self.milvus_deleted + self.storage_deleted

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


class KnowledgeDeleteService:
    """Knowledge 删除服务

    提供文件级别的软删除和永久删除能力，永久删除时级联清理所有数据库中的关联数据。

    数据库覆盖范围：
    - MySQL: 元数据表（chunk_meta_info, section_document, element_meta_info 等）
    - MongoDB: 数据表（document_data, section_data, chunk_data, element_data）
    - Milvus: 向量表（chunk, section, enhanced_chunk, summary, atomic_qa, tag, spo）
    - Storage: 对象存储（原始文件、解析产物）
    """

    def soft_delete_file(
        self,
        session: Session,
        user_id: str,
        file_id: str,
    ) -> bool:
        """软删除单个文件（移入回收站）

        Args:
            session: MySQL 数据库会话
            user_id: 用户ID
            file_id: 文件ID

        Returns:
            是否成功
        """
        try:
            success = workspace_file_system_repo.delete_by_user_and_file(
                session, user_id, file_id, updater=user_id
            )
            if success:
                logger.info(f"文件已移入回收站: user_id={user_id}, file_id={file_id}")
            else:
                logger.warning(f"文件不存在或已删除: user_id={user_id}, file_id={file_id}")
            return success
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"软删除文件失败: {e}")
            return False

    def batch_soft_delete_files(
        self,
        session: Session,
        user_id: str,
        file_ids: List[str],
    ) -> int:
        """批量软删除文件（移入回收站）

        Args:
            session: MySQL 数据库会话
            user_id: 用户ID
            file_ids: 文件ID列表

        Returns:
            成功删除的文件数量
        """
        deleted_count = 0
        for file_id in file_ids:
            if self.soft_delete_file(session, user_id, file_id):
                deleted_count += 1
        return deleted_count

    async def permanent_delete_file(
        self,
        session: Session,
        user_id: str,
        file_id: str,
        storage_manager: Optional[StorageManager] = None,
    ) -> DeleteResult:
        """永久删除文件及其所有关联数据

        流程：
        1. 查询文件的 document_id
        2. 检查是否有其他文件引用同一 document_id（内容去重）
        3. 若无其他引用，级联删除该 document 在所有数据库中的数据
        4. 删除对象存储中的文件
        5. 硬删除文件记录

        Args:
            session: MySQL 数据库会话
            user_id: 用户ID
            file_id: 文件ID
            storage_manager: 对象存储管理器（可选）

        Returns:
            DeleteResult 包含各数据库删除统计和错误信息
        """
        result = DeleteResult()

        file_obj = workspace_file_system_repo.get_by_user_and_file(session, user_id, file_id)
        if not file_obj:
            file_obj = session.query(
                workspace_file_system_repo.model
            ).filter(
                workspace_file_system_repo.model.user_id == user_id,
                workspace_file_system_repo.model.file_id == file_id,
                workspace_file_system_repo.model.deleted.in_([1, 2]),
            ).first()

        if not file_obj:
            result.errors.append(f"文件不存在: file_id={file_id}")
            return result

        document_id = file_obj.document_id
        storage_path = file_obj.storage_path

        if document_id:
            other_refs = workspace_file_system_repo.get_by_document_id(session, document_id)
            other_refs = [
                f for f in other_refs
                if not (f.user_id == user_id and f.file_id == file_id)
            ]

            if not other_refs:
                cascade_result = await self._cascade_delete_document(
                    session, document_id, user_id
                )
                result.mysql_deleted += cascade_result.mysql_deleted
                result.mongodb_deleted += cascade_result.mongodb_deleted
                result.milvus_deleted += cascade_result.milvus_deleted
                result.errors.extend(cascade_result.errors)
            else:
                logger.info(
                    f"document_id={document_id} 仍被 {len(other_refs)} 个文件引用，跳过级联删除"
                )

        if storage_manager and storage_path:
            try:
                deleted = await storage_manager.delete_file(storage_path)
                if deleted:
                    result.storage_deleted += 1
                    logger.info(f"已删除存储文件: {storage_path}")
            except Exception as e:
                error_msg = f"删除存储文件失败: {storage_path}, {e}"
                result.errors.append(error_msg)
                logger.error(error_msg)

        try:
            count = session.query(workspace_file_system_repo.model).filter(
                workspace_file_system_repo.model.user_id == user_id,
                workspace_file_system_repo.model.file_id == file_id,
            ).delete(synchronize_session='fetch')
            if count > 0:
                result.mysql_deleted += 1
        except SQLAlchemyError as e:
            error_msg = f"硬删除文件记录失败: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        logger.info(
            f"永久删除文件完成: file_id={file_id}, "
            f"mysql={result.mysql_deleted}, mongodb={result.mongodb_deleted}, "
            f"milvus={result.milvus_deleted}, storage={result.storage_deleted}, "
            f"errors={len(result.errors)}"
        )
        return result

    async def batch_permanent_delete_files(
        self,
        session: Session,
        user_id: str,
        file_ids: List[str],
        storage_manager: Optional[StorageManager] = None,
    ) -> DeleteResult:
        """批量永久删除文件及其关联数据

        Args:
            session: MySQL 数据库会话
            user_id: 用户ID
            file_ids: 文件ID列表
            storage_manager: 对象存储管理器（可选）

        Returns:
            DeleteResult 汇总结果
        """
        total_result = DeleteResult()

        for file_id in file_ids:
            file_result = await self.permanent_delete_file(
                session, user_id, file_id, storage_manager
            )
            total_result.mysql_deleted += file_result.mysql_deleted
            total_result.mongodb_deleted += file_result.mongodb_deleted
            total_result.milvus_deleted += file_result.milvus_deleted
            total_result.storage_deleted += file_result.storage_deleted
            total_result.errors.extend(file_result.errors)

        logger.info(
            f"批量永久删除完成: {len(file_ids)} 个文件, "
            f"mysql={total_result.mysql_deleted}, mongodb={total_result.mongodb_deleted}, "
            f"milvus={total_result.milvus_deleted}, storage={total_result.storage_deleted}, "
            f"errors={len(total_result.errors)}"
        )
        return total_result

    async def _cascade_delete_document(
        self,
        session: Session,
        document_id: str,
        updater: str = "",
    ) -> DeleteResult:
        """级联删除文档的所有关联数据（跨所有数据库）

        删除顺序：Milvus（向量） → MongoDB（数据） → MySQL（元数据）

        Args:
            session: MySQL 数据库会话
            document_id: 文档ID
            updater: 操作者ID

        Returns:
            DeleteResult 删除统计
        """
        result = DeleteResult()

        sections = section_document_repo.get_by_document_id(session, document_id)
        section_ids = [s.section_id for s in sections]

        chunks = chunk_section_document_repo.get_by_document_id(session, document_id)
        chunk_ids = [c.chunk_id for c in chunks]

        elements = element_meta_info_repo.get_by_document_id(session, document_id)
        element_ids = [e.element_id for e in elements]

        logger.info(
            f"级联删除 document_id={document_id}: "
            f"sections={len(section_ids)}, chunks={len(chunk_ids)}, elements={len(element_ids)}"
        )

        milvus_count = self._delete_milvus_data(document_id, result)
        result.milvus_deleted += milvus_count

        mongodb_count = await self._delete_mongodb_data(
            document_id, section_ids, chunk_ids, element_ids, updater, result
        )
        result.mongodb_deleted += mongodb_count

        mysql_count = self._delete_mysql_metadata(
            session, document_id, section_ids, chunk_ids, element_ids, updater, result
        )
        result.mysql_deleted += mysql_count

        return result

    def _delete_milvus_data(self, document_id: str, result: DeleteResult) -> int:
        """删除 Milvus 中的向量数据（硬删除）

        Args:
            document_id: 文档ID
            result: 用于记录错误的 DeleteResult

        Returns:
            成功删除的 collection 数量
        """
        deleted_count = 0
        milvus_deletions = [
            ("chunk", lambda: ChunkRepository().delete_by_document(document_id)),
            ("section", lambda: SectionRepository().delete_by_document(document_id)),
            ("enhanced_chunk", lambda: EnhancedChunkRepository().delete_by_document(document_id)),
            ("file_summary", lambda: FileSummaryRepository().delete_by_document(document_id)),
            ("section_summary", lambda: SectionSummaryRepository().delete_by_document(document_id)),
            ("atomic_qa", lambda: AtomicQARepository().delete_by_document(document_id)),
            ("tag", lambda: TagRepository().delete_by_document(document_id)),
            ("spo", lambda: SPORepository().delete_by_document(document_id)),
        ]

        for name, delete_fn in milvus_deletions:
            try:
                delete_fn()
                deleted_count += 1
                logger.debug(f"Milvus {name} 删除成功: document_id={document_id}")
            except Exception as e:
                error_msg = f"Milvus {name} 删除失败: {e}"
                result.errors.append(error_msg)
                logger.error(error_msg)

        return deleted_count

    async def _delete_mongodb_data(
        self,
        document_id: str,
        section_ids: List[str],
        chunk_ids: List[str],
        element_ids: List[str],
        updater: str,
        result: DeleteResult,
    ) -> int:
        """删除 MongoDB 中的文档数据（软删除）

        Args:
            document_id: 文档ID
            section_ids: 章节ID列表
            chunk_ids: 分块ID列表
            element_ids: 元素ID列表
            updater: 操作者
            result: 用于记录错误的 DeleteResult

        Returns:
            成功删除的记录数量
        """
        deleted_count = 0

        try:
            if await document_data_repository.delete(document_id, updater=updater):
                deleted_count += 1
        except Exception as e:
            result.errors.append(f"MongoDB document_data 删除失败: {e}")
            logger.error(f"MongoDB document_data 删除失败: {e}")

        if section_ids:
            try:
                count = await section_data_repository.bulk_delete_by_ids(section_ids, updater=updater)
                deleted_count += count
            except Exception as e:
                result.errors.append(f"MongoDB section_data 删除失败: {e}")
                logger.error(f"MongoDB section_data 删除失败: {e}")

        if chunk_ids:
            try:
                count = await chunk_data_repository.bulk_delete_by_ids(chunk_ids, updater=updater)
                deleted_count += count
            except Exception as e:
                result.errors.append(f"MongoDB chunk_data 删除失败: {e}")
                logger.error(f"MongoDB chunk_data 删除失败: {e}")

        if element_ids:
            try:
                count = await element_data_repository.delete_elements_by_ids(element_ids, updater=updater)
                deleted_count += count
            except Exception as e:
                result.errors.append(f"MongoDB element_data 删除失败: {e}")
                logger.error(f"MongoDB element_data 删除失败: {e}")

        return deleted_count

    def _delete_mysql_metadata(
        self,
        session: Session,
        document_id: str,
        section_ids: List[str],
        chunk_ids: List[str],
        element_ids: List[str],
        updater: str,
        result: DeleteResult,
    ) -> int:
        """删除 MySQL 中的元数据（软删除）

        Args:
            session: 数据库会话
            document_id: 文档ID
            section_ids: 章节ID列表
            chunk_ids: 分块ID列表
            element_ids: 元素ID列表
            updater: 操作者
            result: 用于记录错误的 DeleteResult

        Returns:
            成功执行的软删除操作数量
        """
        deleted_count = 0

        mysql_operations = [
            (
                "chunk_section_document",
                lambda: chunk_section_document_repo.bulk_delete_by_ids(session, chunk_ids, updater=updater),
                bool(chunk_ids),
            ),
            (
                "chunk_meta_info",
                lambda: chunk_meta_info_repo.bulk_delete_by_ids(session, chunk_ids, updater=updater),
                bool(chunk_ids),
            ),
            (
                "section_document",
                lambda: section_document_repo.bulk_delete_by_ids(session, section_ids, updater=updater),
                bool(section_ids),
            ),
            (
                "section_meta_info",
                lambda: section_meta_info_repo.bulk_delete_by_ids(session, section_ids, updater=updater),
                bool(section_ids),
            ),
            (
                "element_meta_info",
                lambda: element_meta_info_repo.bulk_delete_by_ids(session, element_ids, updater=updater),
                bool(element_ids),
            ),
            (
                "chunk_atomic_qa",
                lambda: chunk_atomic_qa_repo.bulk_delete_by_ids(session, chunk_ids, updater=updater),
                bool(chunk_ids),
            ),
            (
                "chunk_summary",
                lambda: chunk_summary_repo.bulk_delete_by_ids(session, chunk_ids, updater=updater),
                bool(chunk_ids),
            ),
            (
                "document_summary",
                lambda: document_summary_repo.delete(session, document_id, updater=updater),
                True,
            ),
        ]

        for name, delete_fn, should_execute in mysql_operations:
            if not should_execute:
                continue
            try:
                delete_fn()
                deleted_count += 1
                logger.debug(f"MySQL {name} 软删除成功: document_id={document_id}")
            except SQLAlchemyError as e:
                error_msg = f"MySQL {name} 软删除失败: {e}"
                result.errors.append(error_msg)
                logger.error(error_msg)

        return deleted_count


knowledge_delete_service = KnowledgeDeleteService()
