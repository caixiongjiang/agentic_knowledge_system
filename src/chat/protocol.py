#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : protocol.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat WebSocket 传输协议 schema

    本模块定义"业务事件 ↔ WS 网络帧"之间的转换规则。Phase 3 的
    ``ChatService`` 产出 ``ChatEvent``（业务语义）；本模块负责把它包装成
    可序列化的 WS 帧（``ServerFrame``），同时定义客户端可以发回服务端的
    控制帧（``ClientFrame``）。

    协议子版本
    ----------
    - ``aks-chat-v1``: 当前版本。``ClientFrame.type`` 仅支持 ``start`` /
      ``stop`` / ``ping``；``ServerFrame.type`` 与 ``ChatEventType`` 一一
      对应，再附加 ``pong`` / ``ready`` 两个连接级帧。

    设计要点
    --------
    - **JSON 友好**：所有 Pydantic 模型用 ``str`` enum 序列化，不传入二进制；
    - **解耦传输与编排**：``ChatService`` 不感知 WS；``protocol`` 不感知数据库；
    - **客户端控制最小化**：v1 只支持 ``start`` / ``stop`` / ``ping``，更复杂的
      regenerate / branch 等放 v2 再迭代。
@Modify History:
    2026-05-11 - 首版（Phase 4）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from src.service.chat.types import ChatEvent, ChatEventType


# ============================================================
# 子协议常量
# ============================================================

WS_SUBPROTOCOL = "aks-chat-v1"


# ============================================================
# 客户端 → 服务端 控制帧
# ============================================================


class ClientFrameType(str, Enum):
    """客户端可以发回服务端的控制帧类型"""

    START = "start"   # 开始一轮对话；data 必填 ``ChatRequestPayload``
    STOP = "stop"     # 中断当前轮（如果有的话）
    PING = "ping"     # 心跳保活；服务端回 ``pong``


class ChatRequestPayload(BaseModel):
    """``ClientFrame(type=start)`` 携带的请求体

    本 schema 是 ``src.service.chat.types.ChatRequest`` 的传输层映射，
    字段语义完全对齐。
    """

    session_id: str = Field(..., description="会话 ID（必须已存在）")
    query: str = Field(..., min_length=1, description="本轮用户输入")
    agent_mode: Optional[bool] = Field(
        None, description="是否启用 Agent 工具循环；None 表示沿用 session 默认",
    )
    enable_thinking: Optional[bool] = Field(
        None, description="是否启用思考链；None 表示沿用 session 默认",
    )
    model_preset: Optional[str] = Field(None, description="LLM preset 名称")
    max_tool_rounds: Optional[int] = Field(
        None, ge=1, description="Agent 工具循环上限",
    )
    retrieve_top_k: Optional[int] = Field(
        None, ge=1, description="本轮初始检索 top_k",
    )
    custom_system_prompt: Optional[str] = Field(
        None, description="本轮临时覆盖 system_prompt",
    )
    skip_retrieval: bool = Field(False, description="是否跳过初始检索")

    model_config = ConfigDict(extra="ignore")


class ClientFrame(BaseModel):
    """客户端 → 服务端的统一帧格式

    Examples
    --------
    >>> # 客户端发起一轮：
    >>> ClientFrame(type=ClientFrameType.START,
    ...             data=ChatRequestPayload(
    ...                 session_id="sess_xxx", query="你好").model_dump())
    >>> # 客户端中断当前轮：
    >>> ClientFrame(type=ClientFrameType.STOP)
    """

    type: ClientFrameType = Field(..., description="帧类型")
    data: Dict[str, Any] = Field(default_factory=dict, description="帧附属数据")

    model_config = ConfigDict(extra="ignore", use_enum_values=False)

    def as_start_payload(self) -> ChatRequestPayload:
        """把 ``type=start`` 帧的 ``data`` 解析为 ``ChatRequestPayload``"""
        if self.type != ClientFrameType.START:
            raise ValueError(
                f"as_start_payload() 仅适用于 START 帧；当前 type={self.type}",
            )
        return ChatRequestPayload(**self.data)


# ============================================================
# 服务端 → 客户端 帧
# ============================================================


class ServerFrameKind(str, Enum):
    """服务端帧的"种类标签"

    与 ``ChatEventType`` 一一对应；外加两个连接级帧：

    - ``ready``: 握手完成（鉴权 OK）后立即下发；
    - ``pong``:  对 ``ClientFrame(ping)`` 的回应。
    """

    # 连接级
    READY = "ready"
    PONG = "pong"

    # 来自 ChatEventType（值与之保持一致）
    SESSION_READY = "session.ready"
    RETRIEVAL_STARTED = "retrieval.started"
    RETRIEVAL_DONE = "retrieval.done"
    THINKING_DELTA = "thinking.delta"
    CONTENT_DELTA = "content.delta"
    TOOL_CALL_STARTED = "tool_call.started"
    TOOL_CALL_ARGS_DELTA = "tool_call.args_delta"
    TOOL_CALL_COMPLETED = "tool_call.completed"
    TOOL_ROUND_DONE = "tool_round.done"
    MESSAGE_DONE = "message.done"
    TURN_DONE = "turn.done"
    ERROR = "error"


class ServerFrame(BaseModel):
    """服务端 → 客户端帧"""

    type: ServerFrameKind = Field(..., description="帧类型")
    data: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


# ============================================================
# 翻译：ChatEvent → ServerFrame
# ============================================================


# ``ChatEventType.value`` 与 ``ServerFrameKind.value`` 严格一致，因此可以直接
# 取 value 反查 ServerFrameKind；这里做一份显式映射方便后续协议扩展时一眼看
# 出对齐关系。
_CHAT_EVENT_TO_FRAME: Dict[ChatEventType, ServerFrameKind] = {
    ChatEventType.SESSION_READY: ServerFrameKind.SESSION_READY,
    ChatEventType.RETRIEVAL_STARTED: ServerFrameKind.RETRIEVAL_STARTED,
    ChatEventType.RETRIEVAL_DONE: ServerFrameKind.RETRIEVAL_DONE,
    ChatEventType.THINKING_DELTA: ServerFrameKind.THINKING_DELTA,
    ChatEventType.CONTENT_DELTA: ServerFrameKind.CONTENT_DELTA,
    ChatEventType.TOOL_CALL_STARTED: ServerFrameKind.TOOL_CALL_STARTED,
    ChatEventType.TOOL_CALL_ARGS_DELTA: ServerFrameKind.TOOL_CALL_ARGS_DELTA,
    ChatEventType.TOOL_CALL_COMPLETED: ServerFrameKind.TOOL_CALL_COMPLETED,
    ChatEventType.TOOL_ROUND_DONE: ServerFrameKind.TOOL_ROUND_DONE,
    ChatEventType.MESSAGE_DONE: ServerFrameKind.MESSAGE_DONE,
    ChatEventType.TURN_DONE: ServerFrameKind.TURN_DONE,
    ChatEventType.ERROR: ServerFrameKind.ERROR,
}


def chat_event_to_server_frame(event: ChatEvent) -> ServerFrame:
    """把 ``ChatEvent`` 转成可序列化的 ``ServerFrame``。

    Args:
        event: ``ChatService.chat_stream`` 产出的业务事件

    Returns:
        可直接 ``.model_dump()`` 后通过 WebSocket 发送的服务端帧
    """
    kind = _CHAT_EVENT_TO_FRAME.get(event.type)
    if kind is None:
        # 防御：未来如果 ChatEventType 新增成员而本模块未更新映射，
        # 退化为按字符串原样下发，避免端点崩溃。
        return ServerFrame(
            type=ServerFrameKind.ERROR,
            data={
                "phase": "protocol",
                "error": f"unmapped ChatEvent type: {event.type.value}",
                "raw": event.data,
            },
        )
    return ServerFrame(type=kind, data=event.data)


def make_ready_frame(user_id: str) -> ServerFrame:
    """握手成功后下发的连接级帧"""
    return ServerFrame(
        type=ServerFrameKind.READY,
        data={"subprotocol": WS_SUBPROTOCOL, "user_id": user_id},
    )


def make_pong_frame() -> ServerFrame:
    """对 ``ping`` 的简单回应"""
    return ServerFrame(type=ServerFrameKind.PONG, data={})


def make_error_frame(phase: str, error: str,
                     extra: Optional[Dict[str, Any]] = None) -> ServerFrame:
    """构造一个 ``type=error`` 的服务端帧"""
    data: Dict[str, Any] = {"phase": phase, "error": error}
    if extra:
        data.update(extra)
    return ServerFrame(type=ServerFrameKind.ERROR, data=data)


# ============================================================
# 解析：dict → ClientFrame
# ============================================================


def parse_client_frame(raw: Union[str, bytes, Dict[str, Any]]) -> ClientFrame:
    """把客户端发来的原始 JSON / dict 解析为 ``ClientFrame``，含输入校验

    Raises:
        ValueError: 当 type 缺失 / 不是已知类型时
    """
    import json as _json

    if isinstance(raw, (str, bytes)):
        try:
            data = _json.loads(raw)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"非合法 JSON 帧: {e}") from e
    else:
        data = dict(raw)

    if "type" not in data:
        raise ValueError("帧缺少 type 字段")
    try:
        return ClientFrame(**data)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"帧解析失败: {e}") from e


__all__ = [
    "WS_SUBPROTOCOL",
    "ClientFrameType",
    "ClientFrame",
    "ChatRequestPayload",
    "ServerFrameKind",
    "ServerFrame",
    "chat_event_to_server_frame",
    "make_ready_frame",
    "make_pong_frame",
    "make_error_frame",
    "parse_client_frame",
]
