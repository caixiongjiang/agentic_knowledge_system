#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_chat_api.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat API 集成测试（REST + WebSocket，mock 掉数据库与 ChatService）

    覆盖目标
    --------
    REST
    ~~~~
    1. 创建会话: ``POST /api/chat/sessions``
    2. 我的会话列表: ``GET /api/chat/sessions``
    3. 单条会话详情 + 跨用户 404: ``GET /api/chat/sessions/{id}``
    4. 重命名: ``PATCH /api/chat/sessions/{id}``
    5. 软删除: ``DELETE /api/chat/sessions/{id}``
    6. 历史消息: ``GET /api/chat/sessions/{id}/messages``
    7. 缺失 X-User-Id 头 → 401

    WebSocket
    ~~~~~~~~~
    1. 缺 token → 直接关闭（code=1008）
    2. 握手 OK → 立刻收到 ``ready`` 帧
    3. ``ping`` → 收到 ``pong``
    4. ``start`` → 一组 ServerFrame，最后含 ``turn.done``
    5. 进行中重复 ``start`` → ``error(phase=start)``
    6. ``stop`` 中断 → cancel 当前任务，回 ``error(phase=stop, cancelled=true)``
    7. 非法 JSON / 缺 type → ``error(phase=parse_client_frame)``

    运行::
        uv run python test/api/chat/test_chat_api.py

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import json
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# 必须在 import 路由前禁用 ChatService 真实依赖；这里通过 monkeypatch 服务单例完成
from api.routers.chat import chat_router  # noqa: E402
import api.routers.chat.sessions as sessions_module  # noqa: E402
import api.routers.chat.ws as ws_module  # noqa: E402
from src.service.chat.types import ChatEvent, ChatEventType  # noqa: E402


# ============================================================
# 输出辅助
# ============================================================


def _hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


# ============================================================
# Fakes：ChatSessionService / chat_message_repo
# ============================================================


@dataclass
class _FakeSession:
    session_id: str
    user_id: str
    title: str = "新会话"
    knowledge_base_ids: List[str] = field(default_factory=list)
    model_preset: str = "fast"
    agent_mode: bool = True
    enable_thinking: bool = False
    max_tool_rounds: int = 5
    system_prompt: Optional[str] = None
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    create_time: Optional[datetime] = field(default_factory=datetime.now)
    update_time: Optional[datetime] = field(default_factory=datetime.now)


@dataclass
class _FakeChatMessage:
    """对齐 ChatMessage 的字段子集（仅用于 list_messages DTO 转换）"""
    id: str
    role: str
    content: str = ""
    thinking: Optional[str] = None
    tool_calls: List[Any] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    citations: List[Any] = field(default_factory=list)
    usage: Optional[Any] = None
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    create_time: Optional[datetime] = field(default_factory=datetime.now)


class _FakeSessionService:
    """覆盖 ChatSessionService 的 6 个对外方法"""

    def __init__(self) -> None:
        self.sessions: Dict[str, _FakeSession] = {}
        self.created_count = 0
        self.renamed_count = 0
        self.deleted_count = 0
        self._auto_seq = 0

    def _gen_id(self) -> str:
        self._auto_seq += 1
        return f"sess_test_{self._auto_seq:04d}"

    def create_session(self, *, user_id: str, title: str = "新会话",
                       knowledge_base_ids: Optional[List[str]] = None,
                       model_preset: str = "fast", agent_mode: bool = True,
                       enable_thinking: bool = False, max_tool_rounds: int = 5,
                       system_prompt: Optional[str] = None):
        sid = self._gen_id()
        s = _FakeSession(
            session_id=sid, user_id=user_id, title=title,
            knowledge_base_ids=list(knowledge_base_ids or []),
            model_preset=model_preset, agent_mode=agent_mode,
            enable_thinking=enable_thinking, max_tool_rounds=max_tool_rounds,
            system_prompt=system_prompt,
        )
        self.sessions[sid] = s
        self.created_count += 1
        return s

    def get_session(self, *, session_id: str, user_id: str):
        s = self.sessions.get(session_id)
        if s is None or s.user_id != user_id:
            return None
        return s

    def list_sessions(self, *, user_id: str, limit: int = 20, offset: int = 0):
        items = [s for s in self.sessions.values() if s.user_id == user_id]
        items.sort(key=lambda s: (s.last_message_at or s.create_time), reverse=True)
        return items[offset: offset + limit], len(items)

    def rename_session(self, *, session_id: str, user_id: str, title: str):
        s = self.get_session(session_id=session_id, user_id=user_id)
        if s is None:
            return None
        s.title = title
        s.update_time = datetime.now()
        self.renamed_count += 1
        return s

    async def soft_delete_session(self, *, session_id: str, user_id: str) -> bool:
        s = self.get_session(session_id=session_id, user_id=user_id)
        if s is None:
            return False
        del self.sessions[session_id]
        self.deleted_count += 1
        return True


class _FakeMessageRepo:
    """覆盖 chat_message_repo 在 sessions 路由中使用的方法"""

    def __init__(self) -> None:
        self.by_session: Dict[str, List[_FakeChatMessage]] = {}

    def seed(self, session_id: str, messages: List[_FakeChatMessage]) -> None:
        self.by_session[session_id] = list(messages)

    async def list_by_session(self, session_id: str, *,
                              limit: int = 50, skip: int = 0,
                              ascending: bool = True,
                              include_deleted: bool = False):
        items = list(self.by_session.get(session_id, []))
        if not ascending:
            items.reverse()
        return items[skip: skip + limit]

    async def count_by_session(self, session_id: str) -> int:
        return len(self.by_session.get(session_id, []))


# ============================================================
# Fakes: ChatService（仅 chat_stream 用于 WS 测试）
# ============================================================


class _ScriptedChatService:
    """按 session_id 回放预录的 ChatEvent 序列；支持人为"挂起"以测试 stop"""

    def __init__(self) -> None:
        # session_id -> List[ChatEvent]
        self.scripts: Dict[str, List[ChatEvent]] = {}
        # session_id -> 每个事件之间的延迟（秒）
        self.delays: Dict[str, float] = {}
        self.calls: List[Dict[str, Any]] = []

    def set_script(self, session_id: str, events: List[ChatEvent],
                   delay: float = 0.0) -> None:
        self.scripts[session_id] = list(events)
        self.delays[session_id] = delay

    async def chat_stream(self, request) -> AsyncIterator[ChatEvent]:
        self.calls.append({
            "session_id": request.session_id,
            "user_id": request.user_id,
            "query": request.query,
        })
        events = self.scripts.get(request.session_id, [
            ChatEvent(ChatEventType.SESSION_READY,
                      {"session_id": request.session_id}),
            ChatEvent(ChatEventType.TURN_DONE, {"rounds": 1}),
        ])
        delay = self.delays.get(request.session_id, 0.0)
        for ev in events:
            if delay:
                await asyncio.sleep(delay)
            yield ev


# ============================================================
# 测试夹具：构建 FastAPI app + 替换 sessions / ws 单例
# ============================================================


def _build_app(
    sess_service: _FakeSessionService,
    msg_repo: _FakeMessageRepo,
    chat_service: _ScriptedChatService,
) -> FastAPI:
    app = FastAPI()
    app.include_router(chat_router)
    # 替换 sessions 模块的服务单例
    sessions_module._session_service = sess_service
    sessions_module.chat_message_repo = msg_repo  # type: ignore[attr-defined]
    # 替换 ws 模块的 chat service 单例
    ws_module._chat_service = chat_service
    return app


# ============================================================
# REST 测试用例
# ============================================================


def test_rest_create_get_rename_delete() -> bool:
    _hr("REST · 创建 / 详情 / 重命名 / 软删除")
    sess = _FakeSessionService()
    msg = _FakeMessageRepo()
    chat = _ScriptedChatService()
    app = _build_app(sess, msg, chat)
    headers = {"X-User-Id": "u1"}

    with TestClient(app) as client:
        # 创建
        r = client.post(
            "/api/chat/sessions",
            headers=headers,
            json={
                "title": "T1", "agent_mode": True, "model_preset": "fast",
                "knowledge_base_ids": ["kb1"], "max_tool_rounds": 3,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == 200, body
        sid = body["data"]["session_id"]
        assert sid.startswith("sess_test_"), body
        assert body["data"]["title"] == "T1"
        assert body["data"]["knowledge_base_ids"] == ["kb1"]
        _ok(f"创建会话 OK: {sid}")

        # 详情
        r = client.get(f"/api/chat/sessions/{sid}", headers=headers)
        assert r.status_code == 200
        assert r.json()["data"]["session_id"] == sid
        _ok("详情查询 OK")

        # 跨用户访问应 404
        r = client.get(f"/api/chat/sessions/{sid}", headers={"X-User-Id": "u_other"})
        assert r.status_code == 404, r.text
        _ok("跨用户隔离 OK (404)")

        # 重命名
        r = client.patch(
            f"/api/chat/sessions/{sid}", headers=headers, json={"title": "T1-new"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["title"] == "T1-new"
        _ok("重命名 OK")

        # 软删除
        r = client.delete(f"/api/chat/sessions/{sid}", headers=headers)
        assert r.status_code == 200, r.text
        # 再 GET 应 404
        r = client.get(f"/api/chat/sessions/{sid}", headers=headers)
        assert r.status_code == 404
        _ok("软删除 + 后续 404 OK")

    return True


def test_rest_list_pagination() -> bool:
    _hr("REST · 列表 + 分页")
    sess = _FakeSessionService()
    msg = _FakeMessageRepo()
    chat = _ScriptedChatService()
    app = _build_app(sess, msg, chat)
    headers = {"X-User-Id": "u2"}

    with TestClient(app) as client:
        for i in range(5):
            r = client.post(
                "/api/chat/sessions", headers=headers,
                json={"title": f"S-{i}"},
            )
            assert r.status_code == 200, r.text

        r = client.get(
            "/api/chat/sessions", headers=headers,
            params={"page": 1, "page_size": 2},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 5
        assert data["page"] == 1 and data["page_size"] == 2
        assert len(data["items"]) == 2
        _ok(f"第 1 页 2 条 OK; total={data['total']}")

        r = client.get(
            "/api/chat/sessions", headers=headers,
            params={"page": 3, "page_size": 2},
        )
        data = r.json()["data"]
        assert len(data["items"]) == 1
        _ok("第 3 页 1 条 OK")

    return True


def test_rest_messages_endpoint() -> bool:
    _hr("REST · 会话消息历史")
    sess = _FakeSessionService()
    msg = _FakeMessageRepo()
    chat = _ScriptedChatService()
    app = _build_app(sess, msg, chat)
    headers = {"X-User-Id": "u3"}

    with TestClient(app) as client:
        r = client.post(
            "/api/chat/sessions", headers=headers, json={"title": "M-1"},
        )
        sid = r.json()["data"]["session_id"]

        msg.seed(sid, [
            _FakeChatMessage(id="m1", role="user", content="hi"),
            _FakeChatMessage(id="m2", role="assistant", content="hello"),
            _FakeChatMessage(id="m3", role="user", content="how are you"),
        ])

        r = client.get(
            f"/api/chat/sessions/{sid}/messages", headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["session_id"] == sid
        assert data["total"] == 3
        assert [m["message_id"] for m in data["items"]] == ["m1", "m2", "m3"]
        assert data["items"][1]["role"] == "assistant"
        _ok(f"消息历史 OK: total={data['total']}, 顺序={[m['role'] for m in data['items']]}")

        # 跨用户 404
        r = client.get(
            f"/api/chat/sessions/{sid}/messages",
            headers={"X-User-Id": "u_other"},
        )
        assert r.status_code == 404
        _ok("跨用户消息历史隔离 OK")

    return True


def test_rest_missing_user_header() -> bool:
    _hr("REST · 缺失 X-User-Id 头")
    sess = _FakeSessionService()
    msg = _FakeMessageRepo()
    chat = _ScriptedChatService()
    app = _build_app(sess, msg, chat)

    with TestClient(app) as client:
        r = client.post("/api/chat/sessions", json={"title": "X"})
        # FastAPI 强制 Header 缺失会 422；本路由对应 401 见 get_current_user_id
        assert r.status_code in (401, 422), r.text
        _ok(f"无 X-User-Id 头 → status={r.status_code}")
    return True


# ============================================================
# WS 测试用例
# ============================================================


def test_ws_missing_token_closes() -> bool:
    _hr("WS · 缺 token → 关闭")
    sess = _FakeSessionService()
    msg = _FakeMessageRepo()
    chat = _ScriptedChatService()
    app = _build_app(sess, msg, chat)

    from starlette.websockets import WebSocketDisconnect

    with TestClient(app) as client:
        try:
            with client.websocket_connect("/api/chat/ws"):
                _fail("应当被拒绝但未拒绝")
                return False
        except WebSocketDisconnect as e:
            assert e.code == 1008, f"期望 1008，实际 {e.code}"
            _ok(f"未鉴权连接被关闭 (code={e.code})")
    return True


def _recv_json(ws) -> Dict[str, Any]:
    return json.loads(ws.receive_text())


def test_ws_ready_and_ping() -> bool:
    _hr("WS · 握手 ready + ping/pong")
    sess = _FakeSessionService()
    msg = _FakeMessageRepo()
    chat = _ScriptedChatService()
    app = _build_app(sess, msg, chat)

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws?token=u_ws") as ws:
            ready = _recv_json(ws)
            assert ready["type"] == "ready", ready
            assert ready["data"]["user_id"] == "u_ws"
            _ok(f"ready 帧 OK: {ready['data']}")

            ws.send_text(json.dumps({"type": "ping"}))
            pong = _recv_json(ws)
            assert pong["type"] == "pong"
            _ok("ping → pong OK")
    return True


def test_ws_full_turn_flow() -> bool:
    _hr("WS · 完整一轮（start → events → turn.done）")
    sess = _FakeSessionService()
    msg = _FakeMessageRepo()
    chat = _ScriptedChatService()
    chat.set_script("sess_demo", [
        ChatEvent(ChatEventType.SESSION_READY, {"session_id": "sess_demo"}),
        ChatEvent(ChatEventType.CONTENT_DELTA, {"text": "你好"}),
        ChatEvent(ChatEventType.CONTENT_DELTA, {"text": "，世界"}),
        ChatEvent(ChatEventType.MESSAGE_DONE, {"round": 0, "finish_reason": "stop"}),
        ChatEvent(ChatEventType.TURN_DONE, {"rounds": 1, "tool_calls_count": 0}),
    ])
    app = _build_app(sess, msg, chat)

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws?token=u_ws") as ws:
            assert _recv_json(ws)["type"] == "ready"
            ws.send_text(json.dumps({
                "type": "start",
                "data": {"session_id": "sess_demo", "query": "你好"},
            }))
            kinds = []
            while True:
                msg_in = _recv_json(ws)
                kinds.append(msg_in["type"])
                if msg_in["type"] == "turn.done":
                    break
            assert kinds == [
                "session.ready", "content.delta", "content.delta",
                "message.done", "turn.done",
            ], kinds
            _ok(f"事件序列 OK: {kinds}")
            assert len(chat.calls) == 1
            assert chat.calls[0]["user_id"] == "u_ws"
            assert chat.calls[0]["query"] == "你好"
            _ok("ChatService 被调用 1 次，user/query 正确")
    return True


def test_ws_concurrent_start_rejected() -> bool:
    _hr("WS · 进行中 start 应当被拒绝")
    sess = _FakeSessionService()
    msg = _FakeMessageRepo()
    chat = _ScriptedChatService()
    chat.set_script("sess_slow", [
        ChatEvent(ChatEventType.SESSION_READY, {"session_id": "sess_slow"}),
        ChatEvent(ChatEventType.CONTENT_DELTA, {"text": "a"}),
        ChatEvent(ChatEventType.CONTENT_DELTA, {"text": "b"}),
        ChatEvent(ChatEventType.TURN_DONE, {"rounds": 1}),
    ], delay=0.1)  # 每个事件之间 100ms 间隔
    app = _build_app(sess, msg, chat)

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws?token=u_ws") as ws:
            assert _recv_json(ws)["type"] == "ready"
            ws.send_text(json.dumps({
                "type": "start",
                "data": {"session_id": "sess_slow", "query": "Q"},
            }))
            first = _recv_json(ws)  # session.ready
            assert first["type"] == "session.ready"
            # 在第一轮还没跑完前再次 start
            ws.send_text(json.dumps({
                "type": "start",
                "data": {"session_id": "sess_slow", "query": "Q2"},
            }))
            # 接下来该收到 error(phase=start) 帧；它在主循环里立刻 send
            # 但也可能先收到第二个 content.delta；因此循环等到 error 或 turn.done
            saw_error = False
            while True:
                f = _recv_json(ws)
                if f["type"] == "error" and f["data"].get("phase") == "start":
                    saw_error = True
                if f["type"] == "turn.done":
                    break
            assert saw_error, "应当收到 error(phase=start)"
            _ok("并发 start 被拒绝 (error.phase=start)")
            assert len(chat.calls) == 1, f"ChatService 应只被调用 1 次，实际 {len(chat.calls)}"
            _ok("ChatService 仅被调 1 次")
    return True


def test_ws_stop_cancels_turn() -> bool:
    _hr("WS · stop 中断当前轮")
    sess = _FakeSessionService()
    msg = _FakeMessageRepo()
    chat = _ScriptedChatService()
    # 故意造一个"长流"：100 个 delta，每个 50ms
    long_events = [
        ChatEvent(ChatEventType.SESSION_READY, {"session_id": "sess_long"}),
    ]
    for i in range(100):
        long_events.append(ChatEvent(ChatEventType.CONTENT_DELTA, {"text": f"d{i}"}))
    long_events.append(ChatEvent(ChatEventType.TURN_DONE, {"rounds": 1}))
    chat.set_script("sess_long", long_events, delay=0.05)
    app = _build_app(sess, msg, chat)

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws?token=u_ws") as ws:
            assert _recv_json(ws)["type"] == "ready"
            ws.send_text(json.dumps({
                "type": "start",
                "data": {"session_id": "sess_long", "query": "long"},
            }))
            # 收到 session.ready + 至少 1 个 delta 后立刻发 stop
            kinds = []
            for _ in range(3):
                kinds.append(_recv_json(ws)["type"])
            assert "session.ready" in kinds
            assert "content.delta" in kinds
            ws.send_text(json.dumps({"type": "stop"}))

            # 后续应当收到 error(phase=stop, cancelled=true)；可能前面还残留若干 delta
            saw_stop_ack = False
            for _ in range(120):
                f = _recv_json(ws)
                if f["type"] == "error" and f["data"].get("phase") == "stop":
                    assert f["data"].get("cancelled") is True
                    saw_stop_ack = True
                    break
            assert saw_stop_ack, "未收到 stop 确认 error 帧"
            _ok("stop 中断 OK，回 error(cancelled=true)")

            # 再发一次 stop 应当回 'no active turn'
            ws.send_text(json.dumps({"type": "stop"}))
            f = _recv_json(ws)
            assert f["type"] == "error", f
            assert f["data"]["phase"] == "stop"
            assert "no active turn" in f["data"]["error"]
            _ok("空闲 stop 回 'no active turn' OK")
    return True


def test_ws_invalid_frames() -> bool:
    _hr("WS · 非法帧")
    sess = _FakeSessionService()
    msg = _FakeMessageRepo()
    chat = _ScriptedChatService()
    app = _build_app(sess, msg, chat)

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws?token=u_ws") as ws:
            assert _recv_json(ws)["type"] == "ready"

            # 非法 JSON
            ws.send_text("not a json")
            f = _recv_json(ws)
            assert f["type"] == "error"
            assert f["data"]["phase"] == "parse_client_frame"
            _ok(f"非法 JSON → error.phase={f['data']['phase']}")

            # 缺 type
            ws.send_text(json.dumps({"data": {}}))
            f = _recv_json(ws)
            assert f["type"] == "error"
            assert f["data"]["phase"] == "parse_client_frame"
            _ok("缺 type → error 帧 OK")

            # 不支持的 type
            ws.send_text(json.dumps({"type": "regenerate"}))
            f = _recv_json(ws)
            assert f["type"] == "error"
            _ok("非法 type → error 帧 OK")
    return True


# ============================================================
# 入口
# ============================================================


TESTS = [
    test_rest_create_get_rename_delete,
    test_rest_list_pagination,
    test_rest_messages_endpoint,
    test_rest_missing_user_header,
    test_ws_missing_token_closes,
    test_ws_ready_and_ping,
    test_ws_full_turn_flow,
    test_ws_concurrent_start_rejected,
    test_ws_stop_cancels_turn,
    test_ws_invalid_frames,
]


def main() -> int:
    passed = 0
    failed = 0
    for fn in TESTS:
        try:
            ok = fn()
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception:
            failed += 1
            print("\n  Exception in test:", fn.__name__)
            traceback.print_exc()

    _hr("总结")
    print(f"  通过: {passed}/{len(TESTS)}")
    print(f"  失败: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
