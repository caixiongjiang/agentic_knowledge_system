#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : ws.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat WebSocket 端点

    URL
    ----
        ws://<host>/api/chat/ws?token=<user_id>

    协议
    ----
    见 ``src.chat.protocol``：

    - 服务端 → 客户端: ``ServerFrame``，``type`` 与 ``ChatEventType`` 对齐，
      外加 ``ready`` / ``pong`` 两个连接级帧。
    - 客户端 → 服务端: ``ClientFrame``，``type ∈ {start, stop, ping}``。

    交互流程
    --------
    1. 握手: 服务端校验 ``token``；通过则 ``accept()`` 并下发 ``ready`` 帧。
    2. ``ClientFrame(start)`` ── 开始一轮对话。本端在另一个 ``asyncio.Task``
       里跑 ``ChatService.chat_stream``，每个事件翻译为 ``ServerFrame`` 下发。
       若上一轮还没结束，返回 ``error`` 帧并忽略本次 start。
    3. ``ClientFrame(stop)`` ── 取消当前轮（``Task.cancel()``）。
       ``ChatService`` 已经持久化的 user 消息保留；未完成的 assistant 不写
       MongoDB（因为持久化点在 round 末尾）。下发 ``error`` 帧告知"已中断"。
    4. ``ClientFrame(ping)`` ── 心跳；服务端回 ``pong``。
    5. WS disconnect 时自动取消未完成的轮任务。

    设计取舍
    --------
    - **一条 WS 一会话窗口**：每个连接最多有一个进行中的 chat 任务；并发
      场景由前端开新 WS 解决，避免后端复杂的"流多路复用"。
    - **STOP 即 cancel**：依赖 ``asyncio.CancelledError`` 透传；
      ``chat_service`` 内部所有 await 都尊重 cancel。中断后的"半个轮次"
      不入库——这与"用户主动中断不计费"语义匹配。
    - **强 schema**：每帧都过 ``parse_client_frame`` / ``ChatRequestPayload``
      校验，非法帧统一回 ``error``，不让脏数据进入 ChatService。
@Modify History:
    2026-05-11 - 首版（Phase 4）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from api.dependencies.auth import close_unauthorized, get_current_user_id_ws
from src.chat.protocol import (
    WS_SUBPROTOCOL,
    ClientFrame,
    ClientFrameType,
    ServerFrame,
    chat_event_to_server_frame,
    make_error_frame,
    make_pong_frame,
    make_ready_frame,
    parse_client_frame,
)
from src.service.chat.chat_service import ChatService, ChatServiceConfig
from src.service.chat.types import ChatRequest


router = APIRouter(tags=["Chat / WebSocket"])


# ============================================================
# 单例 ChatService
# ============================================================

_chat_service: Optional[ChatService] = None


def _get_chat_service() -> ChatService:
    """模块级单例。

    生产环境用 ``ChatServiceConfig.from_config_manager()`` 装配——运行参数与
    LLM 选型均走 ``config.toml [chat]`` 节（chat 不进 ``components.json``，
    后者只服务于 RAG 抽取 Pipeline）。如需热替换可走 DI 容器。
    """
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService(
            config=ChatServiceConfig.from_config_manager(),
        )
    return _chat_service


# ============================================================
# 单连接会话句柄
# ============================================================


class _WSSession:
    """封装单条 WS 连接的状态：当前正在运行的轮任务、互斥锁等。"""

    def __init__(self, websocket: WebSocket, user_id: str) -> None:
        self.ws = websocket
        self.user_id = user_id
        self.current_task: Optional[asyncio.Task] = None
        self._send_lock = asyncio.Lock()

    async def send_frame(self, frame: ServerFrame) -> None:
        """串行下发；FastAPI WebSocket 不允许并发 send_text"""
        async with self._send_lock:
            await self.ws.send_text(frame.model_dump_json())

    def has_running_task(self) -> bool:
        return self.current_task is not None and not self.current_task.done()

    async def cancel_running(self, reason: str = "stopped by client") -> None:
        """取消进行中的轮任务并等待其结束"""
        task = self.current_task
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        finally:
            self.current_task = None
        logger.info(
            f"WS cancel running task: user={self.user_id}, reason={reason}"
        )


# ============================================================
# 主循环
# ============================================================


async def _run_chat_turn(
    session: _WSSession,
    payload_dict: dict,
) -> None:
    """运行一次完整对话轮（START 帧的实际执行体）

    本协程被 ``asyncio.create_task`` 起在 _WSSession.current_task 中；
    STOP 帧 / WS 断开 / 异常 都通过 cancel 该 task 达到中断目的。
    """
    from src.chat.protocol import ChatRequestPayload

    try:
        payload = ChatRequestPayload(**payload_dict)
    except Exception as e:  # noqa: BLE001
        await session.send_frame(
            make_error_frame("parse_start", f"invalid start payload: {e}")
        )
        return

    request = ChatRequest(
        session_id=payload.session_id,
        user_id=session.user_id,
        query=payload.query,
        agent_mode=payload.agent_mode,
        enable_thinking=payload.enable_thinking,
        model_preset=payload.model_preset,
        max_tool_rounds=payload.max_tool_rounds,
        retrieve_top_k=payload.retrieve_top_k,
        custom_system_prompt=payload.custom_system_prompt,
        skip_retrieval=payload.skip_retrieval,
    )

    service = _get_chat_service()
    try:
        async for ev in service.chat_stream(request):
            await session.send_frame(chat_event_to_server_frame(ev))
    except asyncio.CancelledError:
        # STOP 或断连引发；上层已下发 cancelled 帧
        logger.info(
            f"WS chat task cancelled: user={session.user_id}, "
            f"session={payload.session_id}"
        )
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception(f"WS chat task crashed: {e}")
        try:
            await session.send_frame(
                make_error_frame("chat_stream", f"unhandled: {e}")
            )
        except Exception:  # noqa: BLE001
            pass


async def _handle_client_frame(
    session: _WSSession,
    frame: ClientFrame,
) -> None:
    """分发单条客户端帧到对应处理逻辑"""
    if frame.type == ClientFrameType.PING:
        await session.send_frame(make_pong_frame())
        return

    if frame.type == ClientFrameType.STOP:
        if not session.has_running_task():
            await session.send_frame(
                make_error_frame("stop", "no active turn to stop")
            )
            return
        await session.cancel_running(reason="stopped by client")
        await session.send_frame(
            make_error_frame(
                "stop", "turn cancelled by client", {"cancelled": True}
            )
        )
        return

    if frame.type == ClientFrameType.START:
        if session.has_running_task():
            await session.send_frame(
                make_error_frame(
                    "start", "a turn is already running; send stop first",
                )
            )
            return
        session.current_task = asyncio.create_task(
            _run_chat_turn(session, frame.data),
        )
        return

    # 防御：parse_client_frame 已限制 type，正常不会到达
    await session.send_frame(
        make_error_frame("client_frame", f"unsupported type: {frame.type}")
    )


# ============================================================
# WebSocket 端点
# ============================================================


@router.websocket("/ws")
async def chat_ws_endpoint(websocket: WebSocket) -> None:
    """流式对话 WebSocket 端点

    握手 query 必填:
        token: 用户 ID（开发期；生产替换为 JWT）
    """
    user_id = await get_current_user_id_ws(websocket)
    if not user_id:
        await close_unauthorized(websocket, reason="missing user token")
        return

    # 若客户端在 Sec-WebSocket-Protocol 里申请了 aks-chat-v1（含 .<token> 形式），
    # 必须在 accept 时回写同名子协议——否则浏览器会因 RFC 6455 子协议未协商而
    # 在 101 响应后立即关闭连接，导致后续 ready 帧发送失败。
    requested_subprotocols = websocket.scope.get("subprotocols") or []
    negotiated_subprotocol: Optional[str] = None
    for proto in requested_subprotocols:
        if proto == WS_SUBPROTOCOL or proto.startswith(f"{WS_SUBPROTOCOL}."):
            negotiated_subprotocol = proto
            break

    await websocket.accept(subprotocol=negotiated_subprotocol)
    session = _WSSession(websocket, user_id)
    try:
        await session.send_frame(make_ready_frame(user_id))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"WS send ready failed early: {e}")
        return

    logger.info(f"WS connected: user={user_id}")

    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            # 解析客户端帧
            try:
                frame = parse_client_frame(raw)
            except ValueError as e:
                await session.send_frame(
                    make_error_frame("parse_client_frame", str(e))
                )
                continue
            except Exception as e:  # noqa: BLE001
                await session.send_frame(
                    make_error_frame("parse_client_frame", f"unexpected: {e}")
                )
                continue

            try:
                await _handle_client_frame(session, frame)
            except Exception as e:  # noqa: BLE001
                logger.exception(f"WS handler crashed: {e}")
                try:
                    await session.send_frame(
                        make_error_frame("handler", f"unhandled: {e}")
                    )
                except Exception:  # noqa: BLE001
                    pass
    finally:
        # 连接关闭：取消进行中的轮任务（如有）
        await session.cancel_running(reason="ws disconnect")
        logger.info(f"WS disconnected: user={user_id}")
