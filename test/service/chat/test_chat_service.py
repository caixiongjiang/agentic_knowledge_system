#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_chat_service.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    ChatService 单元测试（mock LLM + mock repo + mock RetrieveService）

    覆盖目标
    --------
    1. **RAG 单轮成功路径**
       - SESSION_READY / RETRIEVAL_STARTED / RETRIEVAL_DONE /
         CONTENT_DELTA* / MESSAGE_DONE / TURN_DONE 事件顺序齐全；
       - 检索结果作为 citations 持久化到 assistant；
       - chat_message_repo.create 被调用 2 次（user + assistant）；
       - touch_session(delta=2)；非首轮不触发起标题。

    2. **Agent 一轮 tool_call + 收尾**
       - 第 1 轮 LLM 流式给出 tool_call_started + args_delta 事件；
       - 工具执行后产出 TOOL_CALL_COMPLETED + TOOL_ROUND_DONE；
       - 第 2 轮 LLM 给纯文本回复 + MESSAGE_DONE；
       - 持久化 2 条 assistant + 1 条 tool；
       - tool_calls_count=1, tool_rounds=1, citations 合并初始 hits + 新增 chunk。

    3. **Agent 工具循环 → 模型自主停止**
       - 第 1 轮模型发 tool_call，工具执行后进入下一轮；
       - 第 2 轮模型自主不再调用工具，给纯文本回复；
       - assistant_msg_ids 长度=2（工具轮 + 纯文本轮），无强制收尾轮。

    4. **session 不存在 → ERROR**
       - get_session 返回 None；只产出 1 个 ChatEvent(ERROR)；不写消息。

    5. **检索失败 → ERROR 但继续 RAG**
       - retrieve_service.retrieve 抛异常；产生 ERROR(phase=retrieve)；
       - 主流程继续，RAG 单轮仍能完成。

    6. **首轮异步起标题**
       - message_count=0 → 首轮；title_service.schedule_in_background 被调用 1 次；
       - 非首轮 → 不调用。

    运行::
        uv run python test/service/chat/test_chat_service.py

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.client.llm.types import (  # noqa: E402
    StreamChunk,
    ThinkingContent,
    TokenUsage,
    ToolCall,
    ToolCallDelta,
)
from src.retrieve.types.result import ChunkItem  # noqa: E402
from src.service.chat.chat_service import ChatService, ChatServiceConfig  # noqa: E402
from src.service.chat.types import (  # noqa: E402
    ChatEvent,
    ChatEventType,
    ChatRequest,
)


# ============================================================
# 输出辅助
# ============================================================


def _hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


# ============================================================
# Mock 基础设施
# ============================================================


@dataclass
class _FakeSession:
    """伪 ChatSession，匹配 ChatService 实际读取的字段"""

    session_id: str = "sess_test"
    user_id: str = "u_test"
    title: str = "新会话"
    knowledge_base_ids: List[str] = field(default_factory=list)
    model_preset: str = "fast"
    model: Optional[str] = None
    agent_mode: bool = False
    enable_thinking: bool = False
    max_tool_rounds: int = 3
    system_prompt: Optional[str] = None
    message_count: int = 0
    last_message_at: Any = None


class _FakeSessionService:
    """伪 ChatSessionService"""

    def __init__(self, session: Optional[_FakeSession] = None) -> None:
        self.session = session
        self.touch_calls: List[int] = []
        self.rename_calls: List[Dict[str, Any]] = []
        self.load_history_returns: List[Any] = []

    def get_session(self, *, session_id: str, user_id: str):
        if self.session is None:
            return None
        if self.session.user_id != user_id or self.session.session_id != session_id:
            return None
        return self.session

    async def load_history(self, *, session_id: str, limit: int = 200, skip: int = 0):
        return list(self.load_history_returns)

    def touch_session(self, *, session_id: str, delta: int = 1) -> bool:
        self.touch_calls.append(delta)
        return True

    def rename_session(self, *, session_id: str, user_id: str, title: str):
        self.rename_calls.append({"session_id": session_id, "title": title})
        return object()


class _FakeTitleService:
    def __init__(self) -> None:
        self.schedule_count = 0
        self.last_query = ""
        self.last_reply = ""

    def schedule_in_background(
        self,
        *,
        session_id: str,
        user_id: str,
        user_query: str,
        assistant_reply: str,
        session_service,
        max_chars: int = 20,
    ):
        self.schedule_count += 1
        self.last_query = user_query
        self.last_reply = assistant_reply
        # 立即完成的"假 task"
        async def _noop():
            return "fake_title"
        return asyncio.ensure_future(_noop())


class _FakeRetrieveService:
    def __init__(
        self,
        hits: Optional[List[ChunkItem]] = None,
        raise_exc: Optional[Exception] = None,
    ) -> None:
        self.hits = hits or []
        self.raise_exc = raise_exc
        self.calls: List[Any] = []

    async def retrieve(self, request):
        self.calls.append(request)
        if self.raise_exc:
            raise self.raise_exc

        class _Resp:
            items = self.hits
            total_count = len(self.hits)

        return _Resp()


@dataclass
class _Scripted:
    """单次 astream 的脚本：要发出的 StreamChunk 列表"""
    chunks: List[StreamChunk]


class _FakeLLMClient:
    """伪 LLMClient：按调用顺序消费 scripts 中预录的 chunk 序列"""

    def __init__(self, scripts: List[_Scripted], model: str = "fake/fake-model") -> None:
        self._scripts = list(scripts)
        self.model = model
        self.preset_name = "fast"
        self.calls: List[Dict[str, Any]] = []

    def astream(self, messages, *, tools=None, tool_choice=None,
                temperature=None, max_tokens=None, thinking_budget=None,
                **kwargs):
        self.calls.append({
            "messages": list(messages),
            "tools": tools,
            "tool_choice": tool_choice,
            "thinking_budget": thinking_budget,
        })
        if not self._scripts:
            raise AssertionError(
                f"FakeLLMClient 脚本耗尽，但又被调用了第 {len(self.calls)} 次",
            )
        script = self._scripts.pop(0)

        async def _agen():
            for ch in script.chunks:
                yield ch

        return _agen()

    async def agenerate(self, messages, **kwargs):
        # 摘要回调可能用到；这里直接返回空回应
        from src.client.llm.types import LLMResponse
        return LLMResponse(
            content="", thinking=None, tool_calls=[], usage=TokenUsage(),
            model=self.model, finish_reason="stop",
        )


# ============================================================
# Mock chat_message_repo（monkeypatch chat_service 模块属性）
# ============================================================


class _FakeChatMessageRepo:
    """记录每次 create 调用 + 提供 get_by_id"""

    def __init__(self) -> None:
        self.records: Dict[str, Dict[str, Any]] = {}

    async def create(self, *, creator: str = "", **kwargs):
        msg_id = kwargs.get("_id") or kwargs.get("id")
        self.records[msg_id] = {"creator": creator, **kwargs}

    async def get_by_id(self, doc_id, include_deleted: bool = False):
        rec = self.records.get(doc_id)
        if rec is None:
            return None

        class _FakeObj:
            def __init__(self, d: Dict[str, Any]) -> None:
                self.id = d.get("_id")
                self.content = d.get("content", "")
                self.role = d.get("role", "")

        return _FakeObj(rec)


# ============================================================
# 脚本构造工具
# ============================================================


def _content_chunks(deltas: List[str], finish: str = "stop",
                    model: str = "fake/fake-model") -> List[StreamChunk]:
    out: List[StreamChunk] = []
    for d in deltas:
        out.append(StreamChunk(delta=d, is_thought=False, model=model))
    out.append(StreamChunk(delta="", finish_reason=finish, model=model))
    return out


def _tool_call_chunks(
    *,
    tool_id: str,
    name: str,
    args_str: str,
    model: str = "fake/fake-model",
    chunks_split: int = 2,
) -> List[StreamChunk]:
    """生成一组 tool_call 流式分块：
    - 第 0 块：仅 id+name（无 args）
    - 后续：把 args_str 拆成 chunks_split 段
    """
    out: List[StreamChunk] = [
        StreamChunk(
            delta="", is_thought=False, model=model,
            tool_call_delta=ToolCallDelta(
                index=0, id=tool_id, name=name, arguments_delta=None,
            ),
        ),
    ]
    step = max(1, len(args_str) // chunks_split)
    parts = [args_str[i:i + step] for i in range(0, len(args_str), step)]
    for part in parts:
        out.append(StreamChunk(
            delta="", is_thought=False, model=model,
            tool_call_delta=ToolCallDelta(
                index=0, id=None, name=None, arguments_delta=part,
            ),
        ))
    out.append(StreamChunk(delta="", finish_reason="tool_calls", model=model))
    return out


# ============================================================
# 通用：把 chat_stream 全部消费成 list[ChatEvent]
# ============================================================


async def _consume(stream: AsyncIterator[ChatEvent]) -> List[ChatEvent]:
    events: List[ChatEvent] = []
    async for ev in stream:
        events.append(ev)
    return events


def _types_seq(events: List[ChatEvent]) -> List[str]:
    return [ev.type.value for ev in events]


# ============================================================
# 公共装配
# ============================================================


def _patch_message_repo(monkey_repo: _FakeChatMessageRepo) -> None:
    """把 chat_service 模块里 import 的 chat_message_repo 替换为 mock。"""
    import src.service.chat.chat_service as cs_mod
    cs_mod.chat_message_repo = monkey_repo


def _build_service(
    *,
    session: Optional[_FakeSession],
    llm_scripts: List[_Scripted],
    hits: Optional[List[ChunkItem]] = None,
    retrieve_exc: Optional[Exception] = None,
    history: Optional[List[Any]] = None,
) -> tuple:
    """组装一个最小可用的 ChatService（全 mock 依赖）"""
    sess_svc = _FakeSessionService(session=session)
    sess_svc.load_history_returns = history or []
    title_svc = _FakeTitleService()
    retrieve_svc = _FakeRetrieveService(hits=hits, raise_exc=retrieve_exc)
    fake_llm = _FakeLLMClient(scripts=llm_scripts)
    repo = _FakeChatMessageRepo()
    _patch_message_repo(repo)

    service = ChatService(
        session_service=sess_svc,
        retrieve_service=retrieve_svc,
        title_service=title_svc,
        config=ChatServiceConfig(),
    )
    # 注入 fake client
    service._client_cache["fast"] = fake_llm  # noqa: SLF001
    return service, sess_svc, title_svc, retrieve_svc, fake_llm, repo


# ============================================================
# Test 1: RAG 单轮成功路径
# ============================================================


async def test_rag_single_turn_happy() -> bool:
    _hr("Test 1 · RAG 单轮成功路径（agent_mode=False）")

    sess = _FakeSession(
        session_id="sess_1", user_id="u_1", agent_mode=False, message_count=2,
    )
    hits = [
        ChunkItem(chunk_id="ck_a", score=0.9, document_id="doc_x", text="片段 A"),
        ChunkItem(chunk_id="ck_b", score=0.7, document_id="doc_y", text="片段 B"),
    ]
    scripts = [
        _Scripted(_content_chunks(["你", "好", "！", "上海", "天气", "23°C"])),
    ]

    service, sess_svc, title_svc, retrieve_svc, llm, repo = _build_service(
        session=sess, llm_scripts=scripts, hits=hits,
    )
    req = ChatRequest(
        session_id="sess_1", user_id="u_1", query="上海天气怎么样？",
    )
    events = await _consume(service.chat_stream(req))
    types = _types_seq(events)

    expected_subseq = [
        "session.ready",
        "retrieval.started",
        "retrieval.done",
        "content.delta",
        "message.done",
        "turn.done",
    ]
    if not all(t in types for t in expected_subseq):
        _fail(f"事件序列不完整：{types}")
        return False
    if types[0] != "session.ready" or types[-1] != "turn.done":
        _fail(f"首尾事件错：{types[0]} / {types[-1]}")
        return False
    _ok(f"事件序列正确（{len(events)} 个），包含 {expected_subseq}")

    # CONTENT_DELTA 至少 6 个
    content_count = sum(1 for t in types if t == "content.delta")
    if content_count < 6:
        _fail(f"CONTENT_DELTA 太少：{content_count}")
        return False
    _ok(f"CONTENT_DELTA = {content_count}")

    # message.done 数据正确
    msg_done = [ev for ev in events if ev.type == ChatEventType.MESSAGE_DONE][0]
    if msg_done.data.get("finish_reason") != "stop":
        _fail(f"message.done finish_reason 错：{msg_done.data}")
        return False
    if msg_done.data.get("tool_calls_count") != 0:
        _fail("RAG 路径不应有 tool_calls")
        return False
    if msg_done.data.get("citations_count") != 2:
        _fail(f"citations_count 应为 2，实际 {msg_done.data.get('citations_count')}")
        return False
    _ok("message.done 的 citations_count=2（含本轮 2 个种子 hits）")

    # turn.done 数据
    turn_done = [ev for ev in events if ev.type == ChatEventType.TURN_DONE][0]
    if turn_done.data.get("rounds") != 1:
        _fail(f"rounds 应为 1：{turn_done.data}")
        return False
    if turn_done.data.get("tool_calls_count") != 0:
        _fail("tool_calls_count 应为 0")
        return False
    if turn_done.data.get("citations_count") != 2:
        _fail(f"citations_count 应为 2：{turn_done.data}")
        return False
    _ok(f"turn.done: rounds={turn_done.data['rounds']}, "
        f"citations={turn_done.data['citations_count']}, "
        f"time={turn_done.data['total_time_ms']:.1f}ms")

    # 持久化：user + assistant = 2 条
    if len(repo.records) != 2:
        _fail(f"应写 2 条消息（user + assistant），实际 {len(repo.records)}")
        return False
    roles = sorted(rec["role"] for rec in repo.records.values())
    if roles != ["assistant", "user"]:
        _fail(f"持久化角色不对：{roles}")
        return False
    _ok("持久化：1 条 user + 1 条 assistant")

    # touch session
    if sess_svc.touch_calls != [2]:
        _fail(f"touch_session 应调用一次 delta=2，实际 {sess_svc.touch_calls}")
        return False
    _ok(f"touch_session(delta=2) 正确")

    # 非首轮 → 不起标题
    if title_svc.schedule_count != 0:
        _fail("非首轮不应触发起标题")
        return False
    _ok("非首轮（message_count>0）不触发标题")
    return True


# ============================================================
# Test 2: Agent 一轮 tool_call + 收尾
# ============================================================


async def test_agent_one_tool_round() -> bool:
    _hr("Test 2 · Agent: 1 轮 tool_call + 1 轮纯文本收尾")

    sess = _FakeSession(
        session_id="sess_2", user_id="u_2", agent_mode=True,
        max_tool_rounds=3, message_count=2,
    )
    hits = [
        ChunkItem(chunk_id="ck_init", score=0.8, document_id="doc_1", text="种子片段"),
    ]
    # 第 1 轮：发出 1 个 tool_call(context_window, chunk_id=ck_init)
    # 第 2 轮：纯文本回复
    args_json = '{"chunk_id": "ck_init", "window_size": 1}'
    scripts = [
        _Scripted(_tool_call_chunks(
            tool_id="call_1", name="context_window", args_str=args_json,
        )),
        _Scripted(_content_chunks(
            ["根据", "工具", "结果", "：", "片段", "已确认"], finish="stop",
        )),
    ]

    # Monkeypatch KnowledgeNavToolKit.call → 返回固定文本 + 注入 supplemented
    import src.service.chat.chat_service as cs_mod
    from src.service.chat.tools import KnowledgeNavToolKit

    original_call = KnowledgeNavToolKit.call

    async def fake_call(self, name, args=None):
        if name == "context_window":
            extra = ChunkItem(
                chunk_id="ck_ctx_a", score=0.65, document_id="doc_1",
                text="补充片段 A",
            )
            self._supplemented.append(extra)
            return f"found chunk: {extra.chunk_id}"
        return await original_call(self, name, args)

    KnowledgeNavToolKit.call = fake_call

    try:
        service, sess_svc, title_svc, retrieve_svc, llm, repo = _build_service(
            session=sess, llm_scripts=scripts, hits=hits,
        )
        req = ChatRequest(
            session_id="sess_2", user_id="u_2", query="解释一下 ck_init",
        )
        events = await _consume(service.chat_stream(req))
        types = _types_seq(events)
    finally:
        KnowledgeNavToolKit.call = original_call

    if "tool_call.started" not in types:
        _fail("缺 tool_call.started")
        return False
    if "tool_call.args_delta" not in types:
        _fail("缺 tool_call.args_delta")
        return False
    if "tool_call.completed" not in types:
        _fail("缺 tool_call.completed")
        return False
    if "tool_round.done" not in types:
        _fail("缺 tool_round.done")
        return False
    _ok("tool_call.started / args_delta / completed / tool_round.done 全部出现")

    msg_dones = [ev for ev in events if ev.type == ChatEventType.MESSAGE_DONE]
    if len(msg_dones) != 2:
        _fail(f"应有 2 个 MESSAGE_DONE（含工具轮 + 纯文本轮），实际 {len(msg_dones)}")
        return False
    if msg_dones[0].data["tool_calls_count"] != 1:
        _fail(f"第 1 个 MESSAGE_DONE tool_calls_count 应为 1：{msg_dones[0].data}")
        return False
    if msg_dones[1].data["tool_calls_count"] != 0:
        _fail(f"第 2 个 MESSAGE_DONE tool_calls_count 应为 0：{msg_dones[1].data}")
        return False
    _ok("2 个 MESSAGE_DONE：[第 1 轮 tool, 第 2 轮 final-text]")

    # tool_call.completed 数据
    tc_completed = [
        ev for ev in events if ev.type == ChatEventType.TOOL_CALL_COMPLETED
    ][0]
    if tc_completed.data["name"] != "context_window":
        _fail(f"tool_call.completed name 错：{tc_completed.data}")
        return False
    if tc_completed.data["items_added"] != 1:
        _fail(f"items_added 应为 1：{tc_completed.data}")
        return False
    _ok(f"tool_call.completed: name={tc_completed.data['name']}, "
        f"items_added={tc_completed.data['items_added']}")

    # turn.done 汇总
    turn = [ev for ev in events if ev.type == ChatEventType.TURN_DONE][0]
    if turn.data["rounds"] != 2:
        _fail(f"rounds 应为 2：{turn.data}")
        return False
    if turn.data["tool_calls_count"] != 1 or turn.data["tool_rounds"] != 1:
        _fail(
            f"tool_calls={turn.data['tool_calls_count']}, "
            f"tool_rounds={turn.data['tool_rounds']}, 期望 1/1",
        )
        return False
    if turn.data["citations_count"] != 2:
        _fail(
            f"citations_count 应为 2（init + supplemented），实际"
            f" {turn.data['citations_count']}",
        )
        return False
    _ok(f"turn.done: rounds=2, tool_rounds=1, tool_calls=1, "
        f"citations=2（init + 工具补充）")

    # 持久化：1 user + 2 assistant + 1 tool = 4
    roles_count: Dict[str, int] = {}
    for rec in repo.records.values():
        roles_count[rec["role"]] = roles_count.get(rec["role"], 0) + 1
    if roles_count != {"user": 1, "assistant": 2, "tool": 1}:
        _fail(f"持久化角色分布异常：{roles_count}")
        return False
    _ok(f"持久化分布：{roles_count}")
    return True


# ============================================================
# Test 3: Agent 工具循环 → 模型自主停止（不设轮数上限）
# ============================================================


async def test_agent_loop_until_no_tool_calls() -> bool:
    _hr("Test 3 · Agent: 工具循环直到模型自主不再调用工具")

    sess = _FakeSession(
        session_id="sess_3", user_id="u_3", agent_mode=True,
        max_tool_rounds=1, message_count=5,
    )
    args_json = '{"chunk_id": "ck_a"}'
    scripts = [
        _Scripted(_tool_call_chunks(
            tool_id="call_a", name="context_window", args_str=args_json,
        )),
        # 第二轮：模型自主决定不再调用工具，直接给纯文本
        _Scripted(_content_chunks(
            ["已拿到足够证据", "，", "基于已有信息回答"], finish="stop",
        )),
    ]
    from src.service.chat.tools import KnowledgeNavToolKit

    original_call = KnowledgeNavToolKit.call

    async def fake_call(self, name, args=None):
        if name == "context_window":
            return "tool ok"
        return await original_call(self, name, args)

    KnowledgeNavToolKit.call = fake_call
    try:
        service, _sess, _title, _retr, llm, repo = _build_service(
            session=sess, llm_scripts=scripts, hits=[],
        )
        req = ChatRequest(
            session_id="sess_3", user_id="u_3", query="试试 agent 循环",
        )
        events = await _consume(service.chat_stream(req))
    finally:
        KnowledgeNavToolKit.call = original_call

    msg_dones = [ev for ev in events if ev.type == ChatEventType.MESSAGE_DONE]
    if len(msg_dones) != 2:
        _fail(f"应有 2 个 MESSAGE_DONE（round=0 工具轮 + round=1 纯文本），"
              f"实际 {len(msg_dones)}")
        return False
    if msg_dones[-1].data.get("round") != 1:
        _fail(f"最后 MESSAGE_DONE.round 应为 1（纯文本收尾轮）：{msg_dones[-1].data}")
        return False
    _ok("第二轮 MESSAGE_DONE.round=1（模型自主停止）✓")

    # 第二轮流式调用仍带 tools_schema（不再有"强制 tools=None 的收尾轮"）
    if llm.calls[-1].get("tools") is None:
        _fail(f"第二轮 tools 不应为 None（不再强制收尾），实际：{llm.calls[-1].get('tools')}")
        return False
    _ok("第二轮 astream(tools=schema) ✓（无强制收尾轮）")

    turn = [ev for ev in events if ev.type == ChatEventType.TURN_DONE][0]
    if turn.data["rounds"] != 2:
        _fail(f"rounds 应为 2（首轮 tool + 第二轮纯文本），实际 {turn.data['rounds']}")
        return False
    _ok(f"turn.done.rounds=2")
    return True


# ============================================================
# Test 4: session 不存在 → ERROR + 立即返回
# ============================================================


async def test_session_not_found() -> bool:
    _hr("Test 4 · session 不存在 → ERROR + 立即返回")

    service, _sess, _title, _retr, _llm, repo = _build_service(
        session=None, llm_scripts=[],
    )
    req = ChatRequest(
        session_id="missing", user_id="u_x", query="hi",
    )
    events = await _consume(service.chat_stream(req))
    types = _types_seq(events)
    if types != ["error"]:
        _fail(f"应只产出 1 个 ERROR，实际 {types}")
        return False
    if events[0].data.get("phase") != "load_session":
        _fail(f"phase 应为 load_session：{events[0].data}")
        return False
    if len(repo.records) != 0:
        _fail("session 不存在时不应写任何消息")
        return False
    _ok("error.phase=load_session, 未写任何消息 ✓")
    return True


# ============================================================
# Test 5: 检索失败但 RAG 仍能跑完
# ============================================================


async def test_retrieval_failure_resilient() -> bool:
    _hr("Test 5 · 检索失败 → ERROR 但 RAG 单轮仍完成")

    sess = _FakeSession(
        session_id="sess_5", user_id="u_5", agent_mode=False, message_count=2,
    )
    scripts = [_Scripted(_content_chunks(["即使", "检索", "挂了"]))]
    service, _sess, _title, _retr, _llm, repo = _build_service(
        session=sess, llm_scripts=scripts, hits=[],
        retrieve_exc=RuntimeError("milvus down"),
    )
    req = ChatRequest(session_id="sess_5", user_id="u_5", query="ping?")
    events = await _consume(service.chat_stream(req))
    types = _types_seq(events)

    if "error" not in types:
        _fail("缺 ERROR 事件")
        return False
    err_ev = [ev for ev in events if ev.type == ChatEventType.ERROR][0]
    if err_ev.data.get("phase") != "retrieve":
        _fail(f"phase 应为 retrieve：{err_ev.data}")
        return False
    if "turn.done" not in types:
        _fail("RAG 应继续到 turn.done")
        return False
    if "message.done" not in types:
        _fail("RAG 应至少写出一条 message.done")
        return False
    _ok("检索失败时仍能完成 RAG 主流程（含 error + message.done + turn.done）")
    return True


# ============================================================
# Test 6: 首轮触发异步起标题
# ============================================================


async def test_first_turn_triggers_title() -> bool:
    _hr("Test 6 · 首轮（message_count=0）触发异步起标题")

    sess = _FakeSession(
        session_id="sess_6", user_id="u_6",
        agent_mode=False, message_count=0,   # 首轮
    )
    scripts = [_Scripted(_content_chunks(["上海", "天气", "23°C"]))]
    service, _sess, title_svc, _retr, _llm, repo = _build_service(
        session=sess, llm_scripts=scripts, hits=[],
    )
    req = ChatRequest(session_id="sess_6", user_id="u_6", query="上海天气")
    await _consume(service.chat_stream(req))

    if title_svc.schedule_count != 1:
        _fail(f"应调度起标题 1 次，实际 {title_svc.schedule_count}")
        return False
    if title_svc.last_query != "上海天气":
        _fail(f"标题入参 query 不对：{title_svc.last_query!r}")
        return False
    if "上海" not in title_svc.last_reply or "23°C" not in title_svc.last_reply:
        _fail(f"标题入参 reply 不对：{title_svc.last_reply!r}")
        return False
    _ok(f"起标题已调度 1 次；query={title_svc.last_query!r}，"
        f"reply={title_svc.last_reply!r}")
    return True


# ============================================================
# 主入口
# ============================================================


def main() -> int:
    print("=" * 70)
    print("  ChatService 单元测试（Phase 3）")
    print("=" * 70)

    tests = [
        ("rag_single_turn", test_rag_single_turn_happy),
        ("agent_one_tool_round", test_agent_one_tool_round),
        ("agent_loop_until_no_tool_calls", test_agent_loop_until_no_tool_calls),
        ("session_not_found", test_session_not_found),
        ("retrieval_failure_resilient", test_retrieval_failure_resilient),
        ("first_turn_triggers_title", test_first_turn_triggers_title),
    ]
    results: List[tuple] = []
    for name, fn in tests:
        try:
            ok = asyncio.run(fn())
            results.append((name, ok))
        except Exception as e:  # noqa: BLE001
            print(f"\n❌ {name} 异常：{e}")
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 70)
    passed = sum(1 for _, ok in results if ok)
    print(f"  汇总: {passed}/{len(results)} 通过")
    for name, ok in results:
        print(f"    {'✅' if ok else '❌'} {name}")
    print("=" * 70)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
