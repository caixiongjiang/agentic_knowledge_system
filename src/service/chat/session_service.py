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
        folder_id: Optional[str] = None,
        include_subfolders: bool = True,
        model_preset: str = "fast",
        model: Optional[str] = None,
        mode: str = "agent",
        enable_thinking: bool = False,
        enable_multimodal: bool = False,
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
            folder_id: 可选，会话绑定的文件夹 ID。传入后启用 folder scope，
                每轮检索范围限定在该文件夹下文档。会校验：
                - folder 必须属于该 ``user_id``；
                - folder 所属 KB 必须 ∈ ``knowledge_base_ids``（非空时）；
                - 若 ``knowledge_base_ids`` 为空，会自动用 folder 所属 KB 填上一份；
                校验失败抛 ``ValueError`` 让调用方转 422。
            include_subfolders: folder scope 是否含子文件夹，默认 True
            model_preset: ``[llm.presets.*]`` 名称（后台 agent 仍走 preset）
            model: LiteLLM 模型字符串；``None`` 表示由 ``model_preset`` 决定。
                与 ``model_preset`` 并存：``model`` 非空时优先用它选模型，
                ``model_preset`` 仍作为 temperature / max_tokens / thinking_budget
                等采样参数模板（详见 ``ChatService._get_llm_client``）。
            enable_thinking: 默认是否启用思考链
            enable_multimodal: 默认是否启用多模态读图
            max_tool_rounds: Agent 模式默认工具批次上限
            system_prompt: 用户自定义 system_prompt（``None`` 表示用模块默认）
        """
        kb_ids = list(knowledge_base_ids or [])

        # ===== folder_id 跨 KB 一致性校验 =====
        if folder_id:
            kb_ids = self._validate_folder_against_kb(
                user_id=user_id,
                folder_id=folder_id,
                knowledge_base_ids=kb_ids,
            )

        sess_id = generate_session_id()
        manager = get_mysql_manager()
        with manager.get_session() as db:
            obj = self._session_repo.create(
                db,
                session_id=sess_id,
                user_id=user_id,
                title=title,
                knowledge_base_ids=kb_ids,
                folder_id=folder_id,
                include_subfolders=include_subfolders,
                model_preset=model_preset,
                model=model,
                mode=mode,
                enable_thinking=enable_thinking,
                enable_multimodal=enable_multimodal,
                max_tool_rounds=max_tool_rounds,
                system_prompt=system_prompt,
                creator=user_id,
            )
            if obj is None:
                logger.warning(f"创建会话失败: user={user_id}")
                return None
            logger.info(
                f"创建会话: session_id={sess_id}, user={user_id}, "
                f"model_preset={model_preset}, model={model or '-'}, "
                f"scope={'folder=' + folder_id if folder_id else 'kb'}"
            )
            return obj

    # ============================================================
    # folder scope 校验辅助
    # ============================================================

    def _validate_folder_against_kb(
        self,
        *,
        user_id: str,
        folder_id: str,
        knowledge_base_ids: List[str],
    ) -> List[str]:
        """校验 folder_id 与 knowledge_base_ids 的一致性。

        校验规则（must_match）：

        1. folder_id 必须存在且属于 ``user_id``；
        2. folder 所属 KB 必须 ∈ ``knowledge_base_ids``（非空时）；
        3. 若 ``knowledge_base_ids`` 为空 → 自动用 folder 所属 KB 填上一份。

        Returns:
            校验后的 knowledge_base_ids（必要时已自动填充 folder 的 KB）

        Raises:
            ValueError: 校验失败时抛出，建议上游转 422
        """
        from src.db.mysql.repositories.business.workspace_folder_repo import (
            workspace_folder_repo,
        )

        manager = get_mysql_manager()
        with manager.get_session() as db:
            folder = db.query(workspace_folder_repo.model).filter(
                workspace_folder_repo.model.folder_id == folder_id,
                workspace_folder_repo.model.user_id == user_id,
                workspace_folder_repo.model.deleted == 0,
            ).first()
            if not folder:
                raise ValueError(
                    f"folder_id={folder_id} 不存在或不属于当前用户"
                )
            folder_kb = folder.knowledge_base_id
            if not folder_kb:
                # 数据脏：folder 没绑定 KB；保守起见允许通过但记录 warning
                logger.warning(
                    f"folder_id={folder_id} 没有绑定 knowledge_base_id；"
                    "跳过跨 KB 校验"
                )
                return knowledge_base_ids

            if not knowledge_base_ids:
                logger.info(
                    f"create_session 自动填充 KB：folder_id={folder_id} → "
                    f"knowledge_base_ids=[{folder_kb}]"
                )
                return [folder_kb]

            if folder_kb not in knowledge_base_ids:
                raise ValueError(
                    f"folder_id={folder_id} 所属 knowledge_base_id={folder_kb} "
                    f"不在请求的 knowledge_base_ids={knowledge_base_ids} 中"
                )
            return knowledge_base_ids

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

    def update_session_mode(
        self,
        *,
        session_id: str,
        user_id: str,
        mode: Optional[str] = None,
        enable_thinking: Optional[bool] = None,
        max_tool_rounds: Optional[int] = None,
    ) -> bool:
        """首条消息发出后，把用户选择的运行参数回写到 session。"""
        manager = get_mysql_manager()
        with manager.get_session() as db:
            return self._session_repo.update_mode(
                db,
                session_id,
                mode=mode,
                enable_thinking=enable_thinking,
                max_tool_rounds=max_tool_rounds,
                updater=user_id,
            )

    def update_session_settings(
        self,
        *,
        session_id: str,
        user_id: str,
        model: Optional[str] = None,
        model_preset: Optional[str] = None,
        enable_thinking: Optional[bool] = None,
    ) -> bool:
        """把"会话级偏好"回写到 session（用户每轮可改的项）。

        与 ``update_session_mode`` 的分工：

        - ``update_session_mode``：首条消息后**锁定** ``mode`` /
          ``max_tool_rounds`` 等"会话定型"项；UI 上对应的 chip 在有消息后
          就是 disabled 的，不能再变。
        - ``update_session_settings``：随时可改的"轻偏好"——前端选了哪个
          ``model``、是否开思考链、用哪个 preset 模板，只要每轮请求带上
          就持久化，下次进同一会话时 UI 默认选项跟随。

        所有参数都是 ``Optional``：``None`` 表示"不动这一项"。
        """
        manager = get_mysql_manager()
        with manager.get_session() as db:
            return self._session_repo.update_settings(
                db,
                session_id,
                model=model,
                model_preset=model_preset,
                enable_thinking=enable_thinking,
                updater=user_id,
            )

    # ============================================================
    # 清空消息
    # ============================================================

    async def clear_messages(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> bool:
        """清空会话内的所有消息（保留会话本身）

        权限：仅 ``user_id`` 匹配的本人可操作。

        Args:
            session_id: 会话 ID
            user_id: 当前用户 ID（用于权限校验）

        Returns:
            True 表示清空成功，False 表示会话不存在或无权限
        """
        # 1. 权限校验：检查会话是否存在且属于当前用户
        manager = get_mysql_manager()
        with manager.get_session() as db:
            session = self._session_repo.get_by_id_and_user(db, session_id, user_id)
            if session is None:
                return False

        # 2. 软删除 MongoDB 中的所有消息
        try:
            cnt = await self._message_repo.soft_delete_by_session(
                session_id, updater=user_id,
            )
            logger.info(
                f"清空会话消息: session_id={session_id}, user={user_id}, "
                f"软删消息 {cnt} 条"
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"清空会话消息失败: session={session_id}, err={e}")
            return False

        # 3. 重置会话的 message_count 和 last_message_at
        with manager.get_session() as db:
            self._session_repo.reset_message_count(db, session_id)

        return True

    async def summarize_context(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> Optional[str]:
        """总结当前对话上下文，生成摘要并标记旧消息

        流程：
        1. 加载会话的 user/assistant 消息（跳过 tool/thinking 轮次）
        2. 调用 LLM 生成摘要
        3. 存储为 role="summary" 的消息
        4. 标记之前所有消息的 metadata.summarized = true

        Args:
            session_id: 会话 ID
            user_id: 当前用户 ID（用于权限校验）

        Returns:
            生成的摘要文本，失败返回 None
        """
        # 1. 权限校验
        manager = get_mysql_manager()
        with manager.get_session() as db:
            session = self._session_repo.get_by_id_and_user(db, session_id, user_id)
            if session is None:
                return None

        # 2. 加载会话所有消息（排除已软删和已总结的）
        all_messages = await self._message_repo.list_by_session(
            session_id, limit=1000, ascending=True,
        )
        # 过滤掉已总结的消息和 summary 消息
        all_messages = [
            m for m in all_messages
            if not m.metadata.get("summarized", False) and m.role != "summary"
        ]

        if not all_messages:
            return None

        # 3. 只保留 user/assistant 消息用于总结（跳过 tool/thinking 轮次）
        messages_for_summary = [
            m for m in all_messages
            if m.role in ("user", "assistant")
        ]

        if not messages_for_summary:
            return None

        # 4. 构建对话历史文本
        history_text = []
        for msg in messages_for_summary:
            if msg.role == "user":
                history_text.append(f"用户: {msg.content}")
            elif msg.role == "assistant":
                # 截断避免过长，保留核心内容
                content = msg.content[:500] if len(msg.content) > 500 else msg.content
                history_text.append(f"助手: {content}")

        conversation = "\n".join(history_text)

        # 5. 调用 LLM 生成摘要（使用独立的总结提示词）
        try:
            from src.client.llm import LLMClient, LLMClientConfig
            from src.prompts.chat.summary_prompt import SUMMARY_SYSTEM_PROMPT

            config = LLMClientConfig(
                model=session.model or "fast",
                temperature=0.3,
                max_tokens=800,
            )
            client = LLMClient(config)

            response = await client.agenerate(
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": f"请总结以下对话：\n\n{conversation}"},
                ]
            )
            summary_content = response.content

        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
            return None

        # 6. 存储 summary 消息
        from datetime import datetime

        summary_msg = ChatMessage(
            id=generate_message_id(),
            session_id=session_id,
            user_id=user_id,
            role="summary",
            content=summary_content,
            metadata={"summary_type": "context_compression"},
            create_time=datetime.now(),
            update_time=datetime.now(),
        )
        await summary_msg.insert()

        # 7. 标记所有消息为已总结（包括 tool/thinking 等中间轮次）
        all_msg_ids = [m.id for m in all_messages]
        if all_msg_ids:
            await self._message_repo.mark_as_summarized(all_msg_ids, updater=user_id)

        logger.info(
            f"上下文总结完成: session_id={session_id}, "
            f"总结了 {len(messages_for_summary)} 条对话消息，"
            f"标记了 {len(all_msg_ids)} 条消息（含工具调用）"
        )

        return summary_content

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

        Chat 主流程（``skip=0``）取**最近** ``limit`` 条，而非最早 ``limit`` 条。
        Agent 模式一轮常含多条 assistant/tool 消息；若从头部截断会在
        ``tool_calls`` 与 ``role=tool`` 之间切开，导致下一轮 LLM 400。

        Args:
            session_id: 会话 ID（外层应已通过 ``get_session`` 完成权限校验）
            limit: 单次加载上限（默认 200）
            skip: 跳过条数。仅在前端「加载更早」分页时使用；``skip>0`` 时
                仍按时间正序分页（从最早消息起算），与 ``limit`` 组合。
        """
        if skip > 0:
            return await self._message_repo.list_by_session(
                session_id, limit=limit, skip=skip, ascending=True,
            )
        return await self._message_repo.list_recent_by_session(
            session_id, limit=limit,
        )


__all__ = [
    "ChatSessionService",
    "generate_session_id",
    "generate_message_id",
]
