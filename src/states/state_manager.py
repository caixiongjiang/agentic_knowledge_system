#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : state_manager.py
@Author  : caixiongjiang
@Date    : 2025/12/30 15:33
@Function: 
    文件索引进度管理器，基于 Redis Hash 实现细粒度进度追踪
@Modify History:
    2026/02/18 - 重写：删除旧 StateManager，新建基于 Redis 的 FileProgressManager
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from loguru import logger

from src.db.redis.connection.base import BaseRedisManager
from src.db.redis.keys import RedisKeys
from src.db.redis.namespace import RedisNamespace
from src.states.states import (
    FileIndexProgress,
    IndexStage,
    IndexStatus,
    stage_to_progress,
)

_KEY_DEF = RedisKeys.PROGRESS.FILE_PROGRESS
_PROGRESS_TTL = _KEY_DEF.ttl or 86400

# 从 "progress:file:{file_id}" 中截取 "progress:file" 作为 RedisNamespace 前缀
_NS_PREFIX = _KEY_DEF.get_full_pattern().rsplit(":{", 1)[0]


class FileProgressManager:
    """
    文件索引进度管理器

    使用 Redis Hash 存储每个文件的索引进度，提供：
    - init_progress:   索引构建 API 触发时创建初始进度
    - update_progress: Kafka Worker / StatusManager 更新进度
    - get_progress:    API 查询单个文件进度
    - get_batch_progress: API 批量查询进度
    - delete_progress: 清理进度记录

    Redis Key 格式由 RedisKeys.PROGRESS.FILE_PROGRESS 统一定义
    """

    def __init__(self, redis_manager: BaseRedisManager) -> None:
        self._ns = RedisNamespace(redis_manager, _NS_PREFIX)

    async def init_progress(
        self,
        file_id: str,
        user_id: str,
        file_name: str,
    ) -> FileIndexProgress:
        """
        创建初始索引进度（index_start 阶段，10%）

        Args:
            file_id: 文件 ID
            user_id: 用户 ID
            file_name: 文件名

        Returns:
            初始化后的 FileIndexProgress
        """
        progress = FileIndexProgress(
            file_id=file_id,
            user_id=user_id,
            file_name=file_name,
            progress=stage_to_progress(IndexStage.INDEX_START),
            status=IndexStatus.PROCESSING,
            stage=IndexStage.INDEX_START,
            message="索引构建已提交",
        )

        await self._ns.hset(file_id, mapping=progress.to_redis_dict())
        await self._ns.expire(file_id, _PROGRESS_TTL)

        logger.debug(f"初始化索引进度: file_id={file_id}, progress=0.10")
        return progress

    async def update_progress(
        self,
        file_id: str,
        stage: str,
        status: IndexStatus,
        message: Optional[str] = None,
    ) -> Optional[FileIndexProgress]:
        """
        更新文件索引进度

        根据 stage 自动计算 progress 数值，写回 Redis Hash。

        Args:
            file_id: 文件 ID
            stage: 当前阶段（IndexStage 的值）
            status: 当前状态
            message: 描述信息

        Returns:
            更新后的 FileIndexProgress，若 key 不存在返回 None
        """
        exists = await self._ns.exists(file_id)
        if not exists:
            logger.warning(f"更新进度失败，key 不存在: file_id={file_id}")
            return None

        now = datetime.now(timezone.utc).isoformat()
        computed_progress = stage_to_progress(stage)

        update_fields: Dict[str, str] = {
            "progress": str(computed_progress),
            "status": status.value,
            "stage": stage,
            "updated_at": now,
        }
        if message is not None:
            update_fields["message"] = message

        await self._ns.hset(file_id, mapping=update_fields)
        await self._ns.expire(file_id, _PROGRESS_TTL)

        logger.debug(
            f"更新索引进度: file_id={file_id}, stage={stage}, "
            f"progress={computed_progress}, status={status.value}"
        )

        return await self.get_progress(file_id)

    async def get_progress(self, file_id: str) -> Optional[FileIndexProgress]:
        """
        查询单个文件索引进度

        Args:
            file_id: 文件 ID

        Returns:
            FileIndexProgress，Redis 中无数据返回 None
        """
        data: Dict[str, str] = await self._ns.hgetall(file_id)
        if not data:
            return None

        try:
            return FileIndexProgress.from_redis_dict(data)
        except Exception as e:
            logger.error(f"反序列化进度数据失败: file_id={file_id}, error={e}")
            return None

    async def get_batch_progress(
        self, file_ids: List[str]
    ) -> List[Optional[FileIndexProgress]]:
        """
        批量查询文件索引进度

        对每个 file_id 执行 HGETALL，返回与 file_ids 等长的列表。

        Args:
            file_ids: 文件 ID 列表

        Returns:
            与 file_ids 同序的进度列表，无数据的位置为 None
        """
        results: List[Optional[FileIndexProgress]] = []
        for fid in file_ids:
            results.append(await self.get_progress(fid))
        return results

    async def delete_progress(self, file_id: str) -> bool:
        """
        删除文件索引进度记录

        Args:
            file_id: 文件 ID

        Returns:
            是否删除成功
        """
        count = await self._ns.delete(file_id)
        deleted = count > 0
        if deleted:
            logger.debug(f"删除索引进度: file_id={file_id}")
        return deleted
