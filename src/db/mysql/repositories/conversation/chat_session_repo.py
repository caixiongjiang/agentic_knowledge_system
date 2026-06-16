#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chat_session_repo.py
@Author  : caixiongjiang
@Date    : 2026/05/09
@Function:
    ChatSession Repository

    在 ``BaseRepository`` 通用 CRUD 之上，针对 Chat 模块的高频访问模式
    提供专用查询：

    - ``list_by_user``: "我的会话列表"，按 last_message_at 倒序、分页
    - ``get_by_id_and_user``: 含权限校验的单会话查询（user_id 必须匹配）
    - ``touch``: 在收到新消息时一次性增加 ``message_count`` 并刷新
      ``last_message_at``，避免业务侧两次 query
    - ``rename``: 标题重命名
    - ``soft_delete_by_user``: 含权限校验的软删除
@Modify History:
    2026-05-09 - 首版（Phase 1）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime
from typing import List, Optional, Tuple

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.db.mysql.models.conversation.chat_session import ChatSession
from src.db.mysql.repositories.base_repository import BaseRepository


class ChatSessionRepository(BaseRepository[ChatSession]):
    """ChatSession Repository（在 BaseRepository CRUD 之上扩展业务方法）"""

    def __init__(self) -> None:
        super().__init__(ChatSession)

    # ==================== 列表 ====================

    def list_by_user(
        self,
        session: Session,
        user_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[ChatSession], int]:
        """
        分页拉取用户的会话列表（按 last_message_at 倒序，未活跃的退到最后）

        Returns:
            ``(items, total)``：当前分片的记录 + 该用户的会话总数
        """
        try:
            base_q = (
                session.query(self.model)
                .filter(
                    self.model.user_id == user_id,
                    self.model.deleted == 0,
                )
            )
            total = base_q.count()

            # 注意：MySQL 不支持 NULLS LAST 语法。
            # 在 MySQL 中 ORDER BY <col> DESC 会把 NULL 排在最后，正符合
            # "未活跃会话沉到底部"的语义；同时 SQLite 行为也兼容。
            items = (
                base_q.order_by(
                    self.model.last_message_at.desc(),
                    self.model.create_time.desc(),
                )
                .limit(limit)
                .offset(offset)
                .all()
            )
            return items, total
        except SQLAlchemyError as e:
            logger.error(f"查询用户会话列表失败: {e}")
            return [], 0

    # ==================== 单条（带权限） ====================

    def get_by_id_and_user(
        self,
        session: Session,
        session_id: str,
        user_id: str,
    ) -> Optional[ChatSession]:
        """按 session_id + user_id 查询，权限不匹配时返回 None"""
        try:
            return (
                session.query(self.model)
                .filter(
                    self.model.session_id == session_id,
                    self.model.user_id == user_id,
                    self.model.deleted == 0,
                )
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"查询会话失败: {e}")
            return None

    # ==================== 计数刷新 ====================

    def touch(
        self,
        session: Session,
        session_id: str,
        *,
        delta: int = 1,
        when: Optional[datetime] = None,
    ) -> bool:
        """
        在 MongoDB 写入新消息后，原子更新会话的 ``message_count`` 和
        ``last_message_at``。

        Args:
            session_id: 会话 ID
            delta: 本次新增的消息条数（user + assistant + tool 都计数）
            when: 时间戳；不传则用 ``datetime.now()``

        Returns:
            是否找到并更新了记录
        """
        try:
            ts = when or datetime.now()
            updated = (
                session.query(self.model)
                .filter(
                    self.model.session_id == session_id,
                    self.model.deleted == 0,
                )
                .update(
                    {
                        self.model.message_count: self.model.message_count + delta,
                        self.model.last_message_at: ts,
                    },
                    synchronize_session=False,
                )
            )
            session.commit()
            return updated > 0
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"刷新会话计数失败: {e}")
            return False

    # ==================== 模式锁定 ====================

    def update_mode(
        self,
        session: Session,
        session_id: str,
        *,
        agent_mode: Optional[bool] = None,
        enable_thinking: Optional[bool] = None,
        enable_multimodal: Optional[bool] = None,
        max_tool_rounds: Optional[int] = None,
        updater: str = "",
    ) -> bool:
        """首条消息发出后，把用户选择的运行参数回写到 session。"""
        try:
            updates: dict = {}
            if agent_mode is not None:
                updates[self.model.agent_mode] = agent_mode
            if enable_thinking is not None:
                updates[self.model.enable_thinking] = enable_thinking
            if enable_multimodal is not None:
                updates[self.model.enable_multimodal] = enable_multimodal
            if max_tool_rounds is not None:
                updates[self.model.max_tool_rounds] = max_tool_rounds
            if not updates:
                return True
            if updater:
                updates[self.model.updater] = updater
            updated = (
                session.query(self.model)
                .filter(
                    self.model.session_id == session_id,
                    self.model.deleted == 0,
                )
                .update(updates, synchronize_session=False)
            )
            session.commit()
            return updated > 0
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新会话模式失败: {e}")
            return False

    # ==================== 偏好回写（model / preset / thinking） ====================

    def update_settings(
        self,
        session: Session,
        session_id: str,
        *,
        model: Optional[str] = None,
        model_preset: Optional[str] = None,
        enable_thinking: Optional[bool] = None,
        enable_multimodal: Optional[bool] = None,
        updater: str = "",
    ) -> bool:
        """轻量偏好回写：``model`` / ``model_preset`` / ``enable_thinking`` / ``enable_multimodal``。

        与 ``update_mode`` 的分工：``update_mode`` 是"会话首条消息后锁定"的
        模式参数（``agent_mode`` / ``max_tool_rounds``）；本方法是"用户每轮
        可调整的偏好"——选了哪个模型、是否开思考链等，每次都允许改。

        所有参数都是 ``Optional``：``None`` 表示"不动这一项"。返回 ``True``
        表示找到记录（即便 updates 为空也算成功）。
        """
        try:
            updates: dict = {}
            if model is not None:
                # 允许传空字符串 → NULL 来清除前端的模型选择，回退到 preset
                updates[self.model.model] = model or None
            if model_preset is not None:
                updates[self.model.model_preset] = model_preset
            if enable_thinking is not None:
                updates[self.model.enable_thinking] = enable_thinking
            if enable_multimodal is not None:
                updates[self.model.enable_multimodal] = enable_multimodal
            if not updates:
                return True
            if updater:
                updates[self.model.updater] = updater
            updated = (
                session.query(self.model)
                .filter(
                    self.model.session_id == session_id,
                    self.model.deleted == 0,
                )
                .update(updates, synchronize_session=False)
            )
            session.commit()
            return updated > 0
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新会话偏好失败: {e}")
            return False

    # ==================== 重命名 ====================

    def rename(
        self,
        session: Session,
        session_id: str,
        user_id: str,
        title: str,
        *,
        updater: str = "",
    ) -> Optional[ChatSession]:
        """重命名会话（含权限校验）"""
        obj = self.get_by_id_and_user(session, session_id, user_id)
        if obj is None:
            return None
        try:
            obj.title = title
            obj.updater = updater or user_id
            session.commit()
            session.refresh(obj)
            return obj
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"重命名会话失败: {e}")
            return None

    # ==================== 删除（含权限） ====================

    def soft_delete_by_user(
        self,
        session: Session,
        session_id: str,
        user_id: str,
        *,
        updater: str = "",
    ) -> bool:
        """软删除会话（仅本人可删；MongoDB 端消息不在此处级联，由上层批处理处理）"""
        obj = self.get_by_id_and_user(session, session_id, user_id)
        if obj is None:
            return False
        try:
            obj.deleted = 1
            obj.updater = updater or user_id
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"软删除会话失败: {e}")
            return False


# 全局实例（与 business/* 风格一致）
chat_session_repo = ChatSessionRepository()
