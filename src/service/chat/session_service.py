#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : session_service.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    ChatSessionService ── 会话级业务封装

    职责定位
    --------
    把 ``ChatSessionRepository``（MySQL CRUD）和 ``ChatMessageRepository``
    （MongoDB CRUD）封装成"业务语义层"的会话管理 API，对外暴露：

    - ``create_session``：分配 UUID 风格 ``session_id`` 并落 MySQL。
    - ``get_session`` / ``list_sessions``：含 user_id 权限校验。
    - ``rename_session`` / ``soft_delete_session``：含权限校验；
      软删 session 时同步软删 MongoDB 端的消息（避免遗留孤儿）。
    - ``load_history``：从 MongoDB 拉取消息（按 create_time 正序），
      为 ChatService 主流程提供历史 ``ChatMessage`` 列表。

    Phase 3 设计取舍
    ----------------
    - 不接管 MySQL session 的生命周期（用 ``get_mysql_manager().get_session()``
      上下文管理器），保持与现有 business / extract 层一致；
    - 历史加载默认"全量按时间正序"，由 ChatService 自己决定是否做
      ``apply_token_window`` / ``compress_history_to_summary``；
    - 会话计数维护：``ChatService`` 在新消息落库后调用
      ``ChatSessionRepository.touch``，**不**在本服务集中维护——
      因为单轮可能落 N 条消息（user + 多轮 assistant/tool），
      把 touch 留给写消息的人控制更准确。
@Modify History:
    2026-05-11 - 首版（Phase 3）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import uuid
from typing import List, Optional, Tuple

from loguru import logger

from src.db.mongodb.models.conversation.chat_message import ChatMessage
from src.db.mongodb.repositories.conversation import chat_message_repo
from src.db.mysql.connection.factory import get_mysql_manager
from src.db.mysql.models.conversation.chat_session import ChatSession
from src.db.mysql.repositories.conversation import chat_session_repo


def generate_session_id() -> str:
    """生成与项目约定一致的会话 ID：``sess_<uuid_hex16>``"""
    return f"sess_{uuid.uuid4().hex[:16]}"


def generate_message_id() -> str:
    """生成与项目约定一致的消息 ID：``chatmsg_<uuid_hex32>``"""
    return f"chatmsg_{uuid.uuid4().hex}"


class ChatSessionService:
    """会话 CRUD + 历史加载

    本类是无状态的薄业务包装；可直接 ``ChatSessionService()`` 创建实例。
    传入的 ``session_repo`` / ``message_repo`` 默认走全局单例，便于测试时
    注入 mock。
    """

    def __init__(
        self,
        *,
        session_repo=chat_session_repo,
        message_repo=chat_message_repo,
    ) -> None:
        self._session_repo = session_repo
        self._message_repo = message_repo

    # ============================================================
    # 创建
    # ============================================================

    def create_session(
        self,
        *,
        user_id: str,
        title: str = "新会话",
        knowledge_base_ids: Optional[List[str]] = None,
        model_preset: str = "fast",
        agent_mode: bool = True,
        enable_thinking: bool = False,
        max_tool_rounds: int = 5,
        system_prompt: Optional[str] = None,
    ) -> Optional[ChatSession]:
        """创建新会话；返回完整记录对象，失败返回 None。

        Args:
            user_id: 创建者用户 ID
            title: 初始标题（一般用"新会话"占位；首条 user 消息后由
                ``TitleService`` 异步覆盖）
            knowledge_base_ids: 本会话允许检索的知识库 ID 列表；
                ``None`` / 空列表表示放开到用户全量 KB
            model_preset: ``[llm.presets.*]`` 名称
            agent_mode: 默认是否启用 Agent 工具循环
            enable_thinking: 默认是否启用思考链
            max_tool_rounds: Agent 模式默认工具批次上限
            system_prompt: 用户自定义 system_prompt（``None`` 表示用模块默认）
        """
        sess_id = generate_session_id()
        manager = get_mysql_manager()
        with manager.get_session() as db:
            obj = self._session_repo.create(
                db,
                session_id=sess_id,
                user_id=user_id,
                title=title,
                knowledge_base_ids=knowledge_base_ids or [],
                model_preset=model_preset,
                agent_mode=agent_mode,
                enable_thinking=enable_thinking,
                max_tool_rounds=max_tool_rounds,
                system_prompt=system_prompt,
                creator=user_id,
            )
            if obj is None:
                logger.warning(f"创建会话失败: user={user_id}")
                return None
            logger.info(
                f"创建会话: session_id={sess_id}, user={user_id}, "
                f"model_preset={model_preset}, agent_mode={agent_mode}"
            )
            return obj

    # ============================================================
    # 查询
    # ============================================================

    def get_session(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> Optional[ChatSession]:
        """按会话 ID + user_id 加载（含权限校验，跨用户返回 None）"""
        manager = get_mysql_manager()
        with manager.get_session() as db:
            return self._session_repo.get_by_id_and_user(db, session_id, user_id)

    def list_sessions(
        self,
        *,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[ChatSession], int]:
        """分页拉用户的会话列表（按 ``last_message_at`` 倒序）"""
        manager = get_mysql_manager()
        with manager.get_session() as db:
            return self._session_repo.list_by_user(
                db, user_id, limit=limit, offset=offset,
            )

    # ============================================================
    # 修改
    # ============================================================

    def rename_session(
        self,
        *,
        session_id: str,
        user_id: str,
        title: str,
    ) -> Optional[ChatSession]:
        """重命名会话（含权限校验）"""
        manager = get_mysql_manager()
        with manager.get_session() as db:
            return self._session_repo.rename(
                db, session_id, user_id, title, updater=user_id,
            )

    def touch_session(
        self,
        *,
        session_id: str,
        delta: int = 1,
    ) -> bool:
        """新消息落库后刷新 ``message_count`` + ``last_message_at``

        典型在 ``ChatService`` 一轮结束、累计 ``delta=`` 实际新增条数后一次性
        调用，避免每条消息触发一次 MySQL update。
        """
        if delta <= 0:
            return True
        manager = get_mysql_manager()
        with manager.get_session() as db:
            return self._session_repo.touch(db, session_id, delta=delta)

    # ============================================================
    # 删除
    # ============================================================

    async def soft_delete_session(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> bool:
        """软删除会话 + 级联软删该会话下所有消息

        权限：仅 ``user_id`` 匹配的本人可删。
        """
        manager = get_mysql_manager()
        with manager.get_session() as db:
            ok = self._session_repo.soft_delete_by_user(
                db, session_id, user_id, updater=user_id,
            )
        if not ok:
            return False
        # 级联软删 MongoDB 消息
        try:
            cnt = await self._message_repo.soft_delete_by_session(
                session_id, updater=user_id,
            )
            logger.info(
                f"软删会话: session_id={session_id}, user={user_id}, "
                f"级联软删消息 {cnt} 条"
            )
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"级联软删消息失败但 session 已软删: session={session_id}, err={e}"
            )
        return True

    # ============================================================
    # 历史加载
    # ============================================================

    async def load_history(
        self,
        *,
        session_id: str,
        limit: int = 200,
        skip: int = 0,
    ) -> List[ChatMessage]:
        """加载会话历史消息（按 create_time 正序，便于直接拼回 messages）

        Args:
            session_id: 会话 ID（外层应已通过 ``get_session`` 完成权限校验）
            limit: 单次加载上限（默认 200，覆盖典型 100 轮以内的会话）
            skip: 跳过条数（前端做"加载更早"分页时用）
        """
        return await self._message_repo.list_by_session(
            session_id, limit=limit, skip=skip, ascending=True,
        )


__all__ = [
    "ChatSessionService",
    "generate_session_id",
    "generate_message_id",
]
