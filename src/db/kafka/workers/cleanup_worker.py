#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : cleanup_worker.py
@Author  : caixiongjiang
@Date    : 2026/09/01
@Function:
    删除清理 Worker
    消费 knowledge_base.cleanup.start，清理已删除文件的全部关联数据：
    Milvus 向量 → MongoDB 文档 → MySQL 元数据 → 对象存储 → 物理删除墓碑行
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from loguru import logger

from src.db.kafka.topics import KafkaTopics
from src.db.kafka.workers.base_worker import BaseWorker
from src.db.mysql.connection.factory import get_mysql_manager
from src.db.storage.manager import StorageManager
from src.service.knowledge.delete_service import knowledge_delete_service
from src.types.messages.cleanup import CleanupMessage


class CleanupWorker(BaseWorker):
    """
    Cleanup Worker

    职责:
    - 消费 Kafka 消息 (knowledge_base.cleanup.start)
    - 级联清理文件在 Milvus / MongoDB / MySQL / 对象存储中的关联数据
    - 清理完成后物理删除 workspace_file_system 墓碑行

    这一步之所以放在 worker 里：单个文件的清理要打 8 个 Milvus collection
    （每个 load + delete + flush）、4 个 Mongo 集合和 9 张 MySQL 表，全程串行，
    放在 HTTP 请求里会把 API 唯一的事件循环占住。

    失败处理沿用 BaseWorker 的重试 + DLQ。清理本身是幂等的：
    墓碑行已被清掉时会按消息里带的 document_id / storage_path 补完剩余步骤。
    """

    def get_original_topic(self) -> str:
        return KafkaTopics.CLEANUP_START

    def _get_failure_stage(self) -> str:
        return "cleanup"

    async def _fail_file_progress(self, file_id: str, stage: str, error_message: str) -> None:
        """清理与索引进度无关，文件已经不存在了，不写 Redis 失败态"""
        return

    async def process_message_impl(self, message: CleanupMessage) -> bool:
        """
        清理单个文件的关联数据。

        Args:
            message: CleanupMessage

        Returns:
            bool: 处理是否成功；返回 False 会触发重试
        """
        session_factory = get_mysql_manager().SessionLocal
        session = session_factory()

        try:
            async with StorageManager() as storage_manager:
                result = await knowledge_delete_service.purge_file(
                    session=session,
                    user_id=message.user_id,
                    file_id=message.file_id,
                    document_id=message.document_id,
                    storage_path=message.storage_path,
                    storage_manager=storage_manager,
                )
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"清理文件失败: file_id={message.file_id}, error={e}")
            raise
        finally:
            session.close()

        if result.has_errors:
            # 部分存储清理失败：墓碑行还在，重试会从头再跑一遍（各步骤均幂等）
            logger.warning(
                f"清理文件存在失败项，将重试: file_id={message.file_id}, "
                f"errors={result.errors}"
            )
            return False

        logger.info(
            f"清理文件完成: file_id={message.file_id}, "
            f"document_id={message.document_id}, "
            f"knowledge_base_id={message.knowledge_base_id}"
        )
        return True
