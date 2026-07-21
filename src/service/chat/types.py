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
      （``mode`` / ``enable_thinking`` / ``retrieve_top_k`` 等），
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
from typing import Any, Dict, List, Literal, Optional

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
    TOOL_PROGRESS = "tool.progress"
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
        - ``TOOL_PROGRESS``: ``{"tool_call_id", "stage", "model"?}``
        - ``TOOL_CALL_COMPLETED``: ``{"id", "name", "args", "result_brief",
          "items_added", "time_ms", "execution_model"?}``
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


class ChatMention(BaseModel):
    """Cursor 式 @ 内联引用项（文件或目录）

    后端按 ``kind`` 把 ``id`` 解析为一组 document_id：
    - ``kind='file'``   → 该文件的单个 document_id（未索引则为空）
    - ``kind='folder'`` → 该目录（含子目录）下所有文档的 document_id
    """

    kind: Literal["file", "folder"] = Field(..., description="引用类型")
    id: str = Field(..., description="文件 ID 或目录 ID")

    model_config = ConfigDict(extra="ignore")


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
    mode: Optional[str] = Field(
        None,
        description=(
            "会话交互模式（agent / plan 等）；None 表示沿用 session 默认。"
        ),
    )
    enable_thinking: Optional[bool] = Field(
        None, description="是否启用思考链；None 表示沿用 session 默认",
    )
    enable_multimodal: Optional[bool] = Field(
        None, description="是否启用多模态读图；None 表示沿用 session 默认",
    )
    model_preset: Optional[str] = Field(
        None, description="LLM preset 名称；None 表示沿用 session 默认",
    )
    model: Optional[str] = Field(
        None,
        description=(
            "LiteLLM 模型字符串（如 'openai/gpt-4o-mini'），优先级高于 "
            "model_preset；None 表示沿用 session 默认"
        ),
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
    mentions: Optional[List[ChatMention]] = Field(
        None,
        description=(
            "Cursor 式 @ 内联引用（软引用，可多个，文件/目录混选）；None 表示无引用。"
            "后端解析为「引用资料」块注入 user prompt（不锁死 scope）；"
            "越界 / 不存在 / 未索引项软降级（丢弃或标注未索引），不报错。"
        ),
    )
    folder_id: Optional[str] = Field(
        None,
        description=(
            "请求级临时覆盖 folder scope；None 表示沿用 session.folder_id。"
            "传入后必须满足 folder 所属 KB ∈ session.knowledge_base_ids，"
            "否则在 _resolve_turn_context 处会报错。"
        ),
    )
    include_subfolders: Optional[bool] = Field(
        None,
        description=(
            "请求级临时覆盖 include_subfolders；None 表示沿用 session 默认。"
            "仅当 folder_id（请求或 session 级）非空时有意义。"
        ),
    )
    forced_skill_names: Optional[List[str]] = Field(
        None,
        description=(
            "Slash 显式召唤的技能名列表（如 ['/research-report'] 触发时传 ['research-report']）。"
            "被指定的技能正文会注入到 *当轮 user 消息尾部*（而非 system prompt），"
            "使 system prompt 保持稳定前缀、提升缓存命中率，模型必定遵循。"
            "停用或不存在的技能会被跳过。"
        ),
    )

    # 含 ``model`` 字段，需要解除 Pydantic v2 的保护命名空间
    model_config = ConfigDict(extra="ignore", protected_namespaces=())


class ChatTurnContext(BaseModel):
    """ChatService 内部使用的"本轮有效配置"

    由 ``ChatRequest.inherit_from_session(...)`` 产出。把"用户层覆盖 +
    会话默认 + 模块默认"三段配置合并后，下游主循环只需读一份。
    """

    session_id: str
    user_id: str
    query: str

    mode: str
    """会话交互模式（agent / plan 等）"""

    enable_thinking: bool
    model_preset: str
    model: Optional[str] = None
    """显式选定的 LiteLLM 模型字符串；为 ``None`` 时由 ``model_preset`` 决定模型"""
    max_tool_rounds: int
    retrieve_top_k: int
    system_prompt: str
    knowledge_base_ids: List[str] = Field(default_factory=list)
    skip_retrieval: bool = False

    # ===== scope 抽象（v0.8.0 引入）=====
    scope_kind: str = Field(
        "kb",
        description=(
            "本轮检索范围类型：'kb'=知识库全量；'folder'=文件夹内文档。"
        ),
    )
    folder_id: Optional[str] = Field(
        None,
        description="folder scope 时的目标文件夹 ID；'kb' 时为 None",
    )
    folder_label: Optional[str] = Field(
        None,
        description=(
            "folder scope 时给 LLM 看的可读名（如文件夹名 / 路径片段）；"
            "由 ChatService 在解析时填充"
        ),
    )
    include_subfolders: bool = Field(
        True,
        description="folder scope 时是否递归含子文件夹的文档",
    )
    scope_document_ids: List[str] = Field(
        default_factory=list,
        description=(
            "解析后产物：本轮检索 / 工具调用允许命中的 document_id 集合。"
            "scope_kind='kb' 时为空（不限制）；scope_kind='folder' 时为该 folder "
            "（含子目录，由 include_subfolders 决定）下所有文档去重后的 ID 列表。"
            "navigation 工具组依此做硬校验拒绝越界 document_id"
        ),
    )

    forced_skills_block: str = Field(
        "",
        description=(
            "Slash 显式召唤技能的正文块（已解析），注入到当轮 *给 LLM 的* user "
            "消息最末尾；无显式技能时为空串。由 ChatService._build_forced_skills_block 生成。"
        ),
    )
    forced_skill_names: List[str] = Field(
        default_factory=list,
        description=(
            "Slash 显式召唤且成功解析的技能名列表；供 build_index(exclude_names=…) "
            "与 system explicit_skills_override 使用。"
        ),
    )

    # 含 ``model`` 字段，需要解除 Pydantic v2 的保护命名空间
    model_config = ConfigDict(extra="ignore", protected_namespaces=())


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
