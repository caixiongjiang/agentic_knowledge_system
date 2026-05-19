#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : types.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat 模块核心数据类型

    本模块定义 ChatService 的入口请求、产出事件、轮次结果三类核心数据：

    - **ChatRequest**：单轮对话请求；既包含会话身份信息（``session_id`` /
      ``user_id`` / ``query``），也允许在请求级别覆盖会话默认参数
      （``agent_mode`` / ``enable_thinking`` / ``retrieve_top_k`` 等），
      方便客户端做"试一下不开 agent"之类的临时切换。
    - **ChatEvent / ChatEventType**：服务端 → 客户端的语义事件序列。
      与 ``src/chat/stream_buffer.py::StreamEvent`` 的差异：
        * ``StreamEvent`` 是"LLM 流式底层事件"；
        * ``ChatEvent`` 是"业务语义事件"——既包含 LLM 流的转译事件，也包含
          检索阶段、工具执行阶段、消息收尾等业务时间线节点。
      Phase 4 的 WS / SSE 端点会再做一次"业务事件 → 传输协议帧"的映射，
      因此本模块**不耦合**任何传输协议（无 WebSocket / JSON 字段约束）。
    - **ChatTurnResult**：一次完整对话轮次（用户问一次 → assistant 答完）
      的结构化总结，包含产生的消息 ID、工具调用次数、模型轮数、耗时、
      finish_reason 等可观测信息，便于上层日志、限流、计费统计消费。

    设计要点
    --------
    - ``ChatEvent.data`` 用宽松的 ``Dict[str, Any]`` 而非严格 Pydantic 子类，
      在产品迭代期保留灵活性；后续 Phase 4 WS schema 再用 Pydantic 严格化。
    - ``ChatRequest`` 提供 ``inherit_from_session()`` 帮助方法：把请求级覆盖
      与 ``ChatSession`` 默认值合并成一份"本轮有效配置"。
    - ``EVENT_TYPES_FROM_STREAM`` 记录了哪些 ChatEventType 由 StreamEvent
      转译而来，便于 Phase 4 WS 协议设计时一眼看清"实时"与"边界"事件。
@Modify History:
    2026-05-11 - 首版（Phase 3）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 事件枚举
# ============================================================


class ChatEventType(str, Enum):
    """Chat 业务事件类型

    分类
    ----
    - **会话级**：``SESSION_READY`` / ``TURN_DONE`` / ``ERROR``
    - **检索阶段**：``RETRIEVAL_STARTED`` / ``RETRIEVAL_DONE``
    - **LLM 流式（来自 StreamAccumulator）**：``THINKING_DELTA`` /
      ``CONTENT_DELTA`` / ``TOOL_CALL_STARTED`` / ``TOOL_CALL_ARGS_DELTA``
    - **工具执行（Agent 模式独有）**：``TOOL_CALL_COMPLETED`` /
      ``TOOL_ROUND_DONE``
    - **轮内边界**：``MESSAGE_DONE``（一次 assistant 落 MongoDB 完毕）
    """

    # 会话级
    SESSION_READY = "session.ready"
    TURN_DONE = "turn.done"
    ERROR = "error"

    # 检索阶段
    RETRIEVAL_STARTED = "retrieval.started"
    RETRIEVAL_PROGRESS = "retrieval.progress"
    RETRIEVAL_DONE = "retrieval.done"

    # LLM 流式
    THINKING_DELTA = "thinking.delta"
    CONTENT_DELTA = "content.delta"
    TOOL_CALL_STARTED = "tool_call.started"
    TOOL_CALL_ARGS_DELTA = "tool_call.args_delta"

    # 工具执行
    TOOL_CALL_COMPLETED = "tool_call.completed"
    TOOL_ROUND_DONE = "tool_round.done"

    # 轮内边界
    MESSAGE_DONE = "message.done"


# 由 StreamAccumulator 直接转译的事件类型（与 src/chat/stream_buffer.py 对齐）
EVENT_TYPES_FROM_STREAM = frozenset({
    ChatEventType.THINKING_DELTA,
    ChatEventType.CONTENT_DELTA,
    ChatEventType.TOOL_CALL_STARTED,
    ChatEventType.TOOL_CALL_ARGS_DELTA,
})


@dataclass
class ChatEvent:
    """ChatService 产出的业务事件

    Attributes
    ----------
    type : ChatEventType
        事件类型。
    data : Dict[str, Any]
        事件附属数据；按事件类型不同载荷不同，典型字段：

        - ``SESSION_READY``: ``{"session_id", "user_message_id"}``
        - ``RETRIEVAL_DONE``: ``{"hit_count", "time_ms", "chunks": [...]}``
        - ``CONTENT_DELTA`` / ``THINKING_DELTA``: ``{"text"}``
        - ``TOOL_CALL_STARTED``: ``{"index", "id", "name"}``
        - ``TOOL_CALL_ARGS_DELTA``: ``{"index", "text"}``
        - ``TOOL_CALL_COMPLETED``: ``{"id", "name", "args", "result_brief",
          "items_added", "time_ms"}``
        - ``MESSAGE_DONE``: ``{"message_id", "role", "round", "finish_reason",
          "tool_calls_count", "citations_count", "usage": {...}}``
        - ``TOOL_ROUND_DONE``: ``{"round", "tool_calls": [...]}``
        - ``TURN_DONE``: ``{"rounds", "tool_calls_count", "time_ms",
          "user_message_id", "assistant_message_ids": [...]}``
        - ``ERROR``: ``{"phase", "error": str}``
    """

    type: ChatEventType
    data: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# 请求模型
# ============================================================


class ChatRequest(BaseModel):
    """单轮对话请求

    ``session_id`` / ``user_id`` / ``query`` 必填；其余字段为 ``None`` 时
    继承 ``ChatSession`` 的默认配置（``ChatService`` 内部通过
    :meth:`inherit_from_session` 完成合并）。
    """

    session_id: str = Field(..., description="会话 ID（必须已存在）")
    user_id: str = Field(..., description="发起请求的用户 ID（权限校验）")
    query: str = Field(..., min_length=1, description="本轮用户输入")

    # 请求级覆盖（None → 用 ChatSession 默认）
    agent_mode: Optional[bool] = Field(
        None, description="是否启用 Agent 工具循环；None 表示沿用 session 默认",
    )
    enable_thinking: Optional[bool] = Field(
        None, description="是否启用思考链；None 表示沿用 session 默认",
    )
    model_preset: Optional[str] = Field(
        None, description="LLM preset 名称；None 表示沿用 session 默认",
    )
    max_tool_rounds: Optional[int] = Field(
        None, ge=1, description="Agent 模式工具循环上限；None 表示沿用 session 默认",
    )
    retrieve_top_k: Optional[int] = Field(
        None, ge=1, description="本轮初始检索 top_k；None 表示用 ChatServiceConfig 默认",
    )
    custom_system_prompt: Optional[str] = Field(
        None,
        description=(
            "本轮临时覆盖 system_prompt；None 表示用 ``ChatSession.system_prompt``"
            " 或模块默认 ``DEFAULT_CHAT_SYSTEM``"
        ),
    )
    skip_retrieval: bool = Field(
        False,
        description=(
            "是否跳过初始服务端检索（仅 Agent 模式有意义，用于纯导航工具"
            "驱动的探索式对话）"
        ),
    )

    model_config = ConfigDict(extra="ignore")


class ChatTurnContext(BaseModel):
    """ChatService 内部使用的"本轮有效配置"

    由 ``ChatRequest.inherit_from_session(...)`` 产出。把"用户层覆盖 +
    会话默认 + 模块默认"三段配置合并后，下游主循环只需读一份。
    """

    session_id: str
    user_id: str
    query: str

    agent_mode: bool
    enable_thinking: bool
    model_preset: str
    max_tool_rounds: int
    retrieve_top_k: int
    system_prompt: str
    knowledge_base_ids: List[str] = Field(default_factory=list)
    skip_retrieval: bool = False

    model_config = ConfigDict(extra="ignore")


# ============================================================
# 轮次结果
# ============================================================


@dataclass
class ChatTurnResult:
    """一次完整对话轮次的结构化总结

    "一轮"的定义：用户发起一次 ``query`` 起，到 ``ChatService`` 决定不再
    继续工具循环为止；可能产生多条 assistant 消息（每个 LLM 调用产出一条），
    以及多条 ``role=tool`` 消息（每次工具执行产出一条）。
    """

    session_id: str
    user_message_id: str
    assistant_message_ids: List[str] = field(default_factory=list)
    tool_message_ids: List[str] = field(default_factory=list)

    rounds: int = 0                          # 实际 LLM 调用次数
    tool_calls_count: int = 0                # 工具被调用的总次数
    tool_rounds: int = 0                     # 含工具调用的"批次"数
    citations_count: int = 0                 # 最终引用的 chunk 数
    final_finish_reason: str = "stop"
    error: Optional[str] = None

    total_time_ms: float = 0.0
    retrieval_time_ms: float = 0.0
    llm_time_ms: float = 0.0
    tool_time_ms: float = 0.0


__all__ = [
    "ChatEventType",
    "ChatEvent",
    "EVENT_TYPES_FROM_STREAM",
    "ChatRequest",
    "ChatTurnContext",
    "ChatTurnResult",
]
