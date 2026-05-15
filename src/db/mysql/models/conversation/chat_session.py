#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chat_session.py
@Author  : caixiongjiang
@Date    : 2026/05/09
@Function:
    ChatSession Schema 定义

    对话会话元信息表（轻量、强一致），与 MongoDB 中的 ``ChatMessage``
    通过 ``session_id`` 关联：

    - MySQL.chat_session  : 会话设置 / 计数 / 标题，CRUD 频率低，强一致 ✅
    - MongoDB.chat_message: 消息正文 / 思考 / tool_calls / citations，
                             高频追加 + 长文本，半结构化 ✅

    与 ``BaseModel`` / ``AgentMixin`` 的关系
    -----------------------------------------
    - 直接继承 ``BaseModel``（拿到 status / creator / create_time / updater /
      update_time / deleted 6 个标准审计字段）
    - **不**直接继承 ``AgentMixin``：因为本表的 ``session_id`` 主键为 String 64
      （UUID 风格），与 ``AgentMixin.session_id``（``BigInteger``）类型冲突；
      但语义对齐，user_id 字段使用相同的命名约定
@Modify History:
    2026-05-09 - 首版（Phase 1）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
)

from src.db.mysql.models.base_model import BaseModel


class ChatSession(BaseModel):
    """
    对话会话元信息表

    每个用户在 Chat 模块中创建的对话都有一条记录；消息正文走 MongoDB，
    会话设置 / 标题 / 模型偏好 / 消息计数 / 最近活跃时间留在 MySQL。

    字段说明
    --------
    主键
        - ``session_id``: UUID 风格字符串，与 MongoDB 端 ``ChatMessage.session_id``
          一一对应

    归属
        - ``user_id``: 必填，会话所有者；权限校验入口
        - ``title``: 会话标题（首条用户消息后由 LLM 异步生成，前端可改）

    上下文绑定
        - ``knowledge_base_ids``: JSON list，本会话允许检索的知识库 ID
          （多 KB 场景下 ChatService 会按此过滤；空列表表示用户全量 KB）

    模型与策略
        - ``model_preset``: 引用 ``[llm.presets.<name>]``，默认 ``fast``
        - ``agent_mode``: 是否启用 Agent 工具循环（``True`` 默认）；为 ``False``
          时走 RAG 单轮快路径
        - ``enable_thinking``: 是否启用思考链（``deepseek-reasoner`` 等）
        - ``max_tool_rounds``: Agent 模式下含工具批次的调整轮数上限
        - ``system_prompt``: 用户可覆盖的自定义 system prompt

    运行计数
        - ``message_count``: 已落 MongoDB 的消息总数（user + assistant + tool 全计）
        - ``last_message_at``: 最近一条消息的产生时间（用于会话列表排序）

    复合索引
        - ``idx_user_lastmsg(user_id, last_message_at)``: "我的会话列表"按活跃度倒序
        - ``idx_user_deleted(user_id, deleted)``: 软删除过滤
    """

    __tablename__ = "chat_session"

    __table_args__ = (
        Index("idx_user_lastmsg", "user_id", "last_message_at"),
        Index("idx_user_deleted", "user_id", "deleted"),
    )

    # ========== 主键 ==========
    session_id = Column(
        String(64),
        primary_key=True,
        comment="会话ID（UUID 风格字符串，与 MongoDB.chat_message.session_id 关联）",
    )

    # ========== 归属 ==========
    user_id = Column(
        String(64),
        nullable=False,
        comment="所属用户ID（权限校验入口）",
    )

    title = Column(
        String(255),
        nullable=False,
        default="新会话",
        comment="会话标题（首条用户消息后可由 LLM 异步生成）",
    )

    # ========== 上下文绑定 ==========
    knowledge_base_ids = Column(
        JSON,
        nullable=True,
        comment="本会话允许检索的知识库 ID 列表（JSON array of str；空表示用户全量 KB）",
    )

    # ========== 模型与策略 ==========
    model_preset = Column(
        String(64),
        nullable=False,
        default="fast",
        comment="LLM preset 名称，引用 config.toml [llm.presets.*]",
    )

    agent_mode = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用 Agent 工具循环（False 时走 RAG 单轮快路径）",
    )

    enable_thinking = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否启用思考链（仅 reasoning 类模型生效）",
    )

    max_tool_rounds = Column(
        SmallInteger,
        nullable=False,
        default=5,
        comment="Agent 模式下含工具批次的调整轮数上限",
    )

    system_prompt = Column(
        Text,
        nullable=True,
        comment="用户自定义 system prompt（覆盖默认问答规范），NULL 表示用模块默认值",
    )

    # ========== 运行计数 ==========
    message_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="本会话已落 MongoDB 的消息总数（含 user / assistant / tool）",
    )

    last_message_at = Column(
        DateTime,
        nullable=True,
        comment="最近一条消息的产生时间（用于会话列表按活跃度倒序）",
    )

    # BaseModel 字段会自动继承：
    # - status, creator, create_time, updater, update_time, deleted
