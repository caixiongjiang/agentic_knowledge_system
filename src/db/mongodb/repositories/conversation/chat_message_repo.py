#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chat_message_repo.py
@Author  : caixiongjiang
@Date    : 2026/05/09
@Function:
    ChatMessage Repository（MongoDB）

    在 ``BaseRepository`` 通用 CRUD 之上提供 Chat 模块专属访问：

    - ``list_by_session``: 拉某会话历史（按 create_time 正序，可分页）
    - ``count_by_session``: 会话内消息总数（用于会话计数刷新）
    - ``count_by_user``: 用户全部历史消息数（审计用）
    - ``soft_delete_by_session``: 软删除某会话所有消息（清理上层 ChatService 调用）
    - ``find_last_assistant``: 最近一条 assistant 消息（regenerate 用）
@Modify History:
    2026-05-09 - 首版（Phase 1）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime
from typing import List, Optional

from loguru import logger

from src.db.mongodb.models.conversation.chat_message import ChatMessage
from src.db.mongodb.repositories.base_repository import BaseRepository


class ChatMessageRepository(BaseRepository[ChatMessage]):
    """ChatMessage Repository（异步）"""

    def __init__(self) -> None:
        super().__init__(ChatMessage)

    # ==================== 列表 ====================

    async def list_by_session(
        self,
        session_id: str,
        *,
        limit: int = 50,
        skip: int = 0,
        ascending: bool = True,
        include_deleted: bool = False,
    ) -> List[ChatMessage]:
        """
        拉取会话内的消息（默认按 create_time 正序，便于直接拼回 messages 列表）

        Args:
            session_id: 会话 ID
            limit: 每页数量
            skip: 跳过数量（前端从尾部分页时用）
            ascending: True=按时间正序（默认，符合对话语义），False=倒序
            include_deleted: 是否包含已软删除消息
        """
        try:
            sort_dir = 1 if ascending else -1
            return await self.find(
                limit=limit,
                skip=skip,
                include_deleted=include_deleted,
                sort=[("create_time", sort_dir)],
                session_id=session_id,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"拉取会话历史失败: {e}", exc_info=True)
            return []

    async def list_recent_by_session(
        self,
        session_id: str,
        *,
        limit: int = 50,
        include_deleted: bool = False,
    ) -> List[ChatMessage]:
        """拉取会话内**最近** ``limit`` 条消息（按 create_time 正序返回）。

        Chat 主流程应使用本方法而非 ``list_by_session(skip=0)``：
        Agent 一轮可能产生 user + 多组 (assistant/tool_calls + tool×N)，
        若只取**最早**的 N 条，会在工具链中间截断，导致 LLM 报
        "insufficient tool messages following tool_calls"。
        """
        if limit <= 0:
            return []
        try:
            total = await self.count_by_session(session_id)
            if total <= 0:
                return []
            skip = max(0, total - limit)
            return await self.list_by_session(
                session_id,
                limit=limit,
                skip=skip,
                ascending=True,
                include_deleted=include_deleted,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"拉取会话最近历史失败: {e}", exc_info=True)
            return []

    # ==================== 计数 ====================

    async def count_by_session(self, session_id: str) -> int:
        """会话内活跃消息数（用于刷新 chat_session.message_count 兜底）"""
        return await self.count(session_id=session_id)

    async def count_by_user(self, user_id: str) -> int:
        """用户全量活跃消息数（审计用）"""
        return await self.count(user_id=user_id)

    # ==================== 工具消息 ====================

    async def find_last_assistant(self, session_id: str) -> Optional[ChatMessage]:
        """
        会话内最近一条 assistant 消息（regenerate 入口要先把它清理掉）。
        """
        try:
            results = await self.find(
                limit=1,
                skip=0,
                sort=[("create_time", -1)],
                session_id=session_id,
                role="assistant",
            )
            return results[0] if results else None
        except Exception as e:  # noqa: BLE001
            logger.error(f"查询最近 assistant 消息失败: {e}", exc_info=True)
            return None

    # ==================== 删除 ====================

    async def soft_delete_by_session(
        self,
        session_id: str,
        *,
        updater: str = "",
    ) -> int:
        """
        软删除某会话内所有未删除消息。

        通常由上层 ChatSessionService 在删除 session 后调用，避免遗留孤儿消息。
        Returns:
            被软删的消息条数
        """
        try:
            result = await self.model.find(
                {"session_id": session_id, "deleted": 0}
            ).update(
                {
                    "$set": {
                        "deleted": 1,
                        "updater": updater,
                        "update_time": datetime.now(),
                    }
                }
            )
            modified = result.modified_count if result else 0
            logger.debug(
                f"软删除会话 {session_id} 下的消息 {modified} 条"
            )
            return modified
        except Exception as e:  # noqa: BLE001
            logger.error(f"批量软删除会话消息失败: {e}", exc_info=True)
            return 0

    async def mark_as_summarized(
        self,
        message_ids: List[str],
        *,
        updater: str = "",
    ) -> int:
        """标记指定消息为已总结（metadata.summarized = true）

        用于上下文压缩：总结后标记旧消息，后续构建 LLM 上下文时跳过。

        Args:
            message_ids: 要标记的消息 ID 列表
            updater: 操作者

        Returns:
            被标记的消息条数
        """
        try:
            result = await self.model.find(
                {"_id": {"$in": message_ids}, "deleted": 0}
            ).update(
                {
                    "$set": {
                        "metadata.summarized": True,
                        "updater": updater,
                        "update_time": datetime.now(),
                    }
                }
            )
            modified = result.modified_count if result else 0
            logger.debug(f"标记 {modified} 条消息为已总结")
            return modified
        except Exception as e:  # noqa: BLE001
            logger.error(f"标记消息为已总结失败: {e}", exc_info=True)
            return 0


# 全局实例
chat_message_repo = ChatMessageRepository()
