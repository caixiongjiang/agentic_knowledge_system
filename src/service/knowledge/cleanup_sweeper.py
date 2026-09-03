#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : cleanup_sweeper.py
@Author  : caixiongjiang
@Date    : 2026/09/01
@Function:
    清理兜底扫描：重新投递迟迟没被清掉的墓碑
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import asyncio
from datetime import datetime, timedelta
from typing import List

from loguru import logger

from src.db.kafka.producer import KafkaProducer
from src.db.mysql.connection.factory import get_mysql_manager
from src.db.mysql.models.business.workspace_file_system import WorkspaceFileSystem
from src.db.kafka.topics import KafkaTopics
from src.types.messages.cleanup import CleanupMessage

# 正常清理是秒级的，超过这个时长还留着就说明消息丢了或者清理反复失败
_STALE_AFTER = timedelta(minutes=10)
_SWEEP_INTERVAL_SECONDS = 300
_BATCH_LIMIT = 200


def _find_stale_tombstones(cutoff: datetime) -> List[CleanupMessage]:
    """捞出超时未清理的墓碑行"""
    manager = get_mysql_manager()
    with manager.get_session() as session:
        rows = (
            session.query(WorkspaceFileSystem)
            .filter(
                WorkspaceFileSystem.deleted != 0,
                WorkspaceFileSystem.update_time < cutoff,
            )
            .limit(_BATCH_LIMIT)
            .all()
        )
        return [
            CleanupMessage(
                user_id=r.user_id,
                file_id=r.file_id,
                document_id=r.document_id,
                storage_path=r.storage_path,
                knowledge_base_id=r.knowledge_base_id,
            )
            for r in rows
        ]


async def sweep_once(producer: KafkaProducer) -> int:
    """扫描一轮并重投

    Returns:
        重新投递的墓碑数量
    """
    cutoff = datetime.now() - _STALE_AFTER

    try:
        messages = await asyncio.to_thread(_find_stale_tombstones, cutoff)
    except Exception as e:
        logger.error(f"扫描待清理墓碑失败: {e}")
        return 0

    if not messages:
        return 0

    sent = 0
    for message in messages:
        try:
            await producer.send_and_flush(
                topic=KafkaTopics.CLEANUP_START,
                message=message,
            )
            sent += 1
        except Exception as e:
            logger.error(f"重投清理任务失败: file_id={message.file_id}, error={e}")

    logger.warning(f"兜底扫描重投 {sent}/{len(messages)} 个待清理文件")
    return sent


async def run_forever(producer: KafkaProducer) -> None:
    """周期性兜底扫描

    Worker 侧没有接 retry / DLQ 管理器，消费失败的消息 offset 照样会提交，
    所以这个扫描就是清理链路实际的重试机制，不能省。
    """
    logger.info(
        f"清理兜底扫描已启动: 每 {_SWEEP_INTERVAL_SECONDS}s 扫一次，"
        f"重投超过 {_STALE_AFTER} 未清理的墓碑"
    )
    while True:
        try:
            await asyncio.sleep(_SWEEP_INTERVAL_SECONDS)
            await sweep_once(producer)
        except asyncio.CancelledError:
            logger.info("清理兜底扫描已停止")
            raise
        except Exception as e:
            logger.error(f"清理兜底扫描异常（继续下一轮）: {e}")
