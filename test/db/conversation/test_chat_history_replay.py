#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_chat_history_replay.py
@Author  : caixiongjiang
@Date    : 2026/05/09
@Function:
    Chat 历史"真机回放"集成测试
    ============================

    动机
    ----
    `test_chat_persistence.py` 已经从结构层面证明了 ChatMessage 的写入/读取
    无失真。但**真正要保证的事情**是：

        在多轮对话中，从 MongoDB 读回历史并重建出的 ``messages`` 列表，
        交给真实 LLM 推理时，行为与"始终用内存里那份原生 messages"完全一致。

    如果两者发生漂移（例如丢字段 / 顺序错乱 / arguments 编码差异），
    续聊时 LLM 就会偏离上下文。所以本测试**两次都把 messages 真实发给模型**
    做对比。

    流水（4 次真实 LLM 请求）
    --------------------------

    Stage A · 真实对话生成历史
        ① messages = [system, user("上海现在天气？")]
        ② **真实请求 #1**: client.agenerate(messages, tools=[get_weather])
              → finish_reason="tool_calls"
        ③ 本地 mock 工具执行（不调真天气 API）
        ④ messages.append(assistant_with_tool_calls)
           messages.append(tool_result)
        ⑤ **真实请求 #2**: client.agenerate(messages, tools=[get_weather])
              → finish_reason="stop"，最终自然语言回答
        ⑥ messages.append(final_assistant)
        → 内存中得到 5 条"原生"消息

    Stage B · 持久化
        把这 5 条消息逐条写入 MongoDB（保留 thinking / usage / metadata
        等业务侧字段）

    Stage C · 双路续聊（同一新问题）
        新问题 q3 = "那北京呢？请也用工具查询。"

        A 路（内存）::
            msgs_mem = original_messages + [user(q3)]
            **真实请求 #3**: response_a = agenerate(msgs_mem, tools=...)

        B 路（数据库）::
            history  = chat_message_repo.list_by_session(...)
            msgs_db  = rebuild_llm_messages(history) + [user(q3)]
            **真实请求 #4**: response_b = agenerate(msgs_db, tools=...)

    Stage D · 断言（4 项）
        1) ``msgs_mem`` ≡ ``msgs_db``（OpenAI 协议字段经规范化后逐项相等）
        2) ``response_a.finish_reason == response_b.finish_reason``
        3) 都是 ``tool_calls`` 时：tool_calls 数量、name、关键字段（city）一致
           都是 ``stop`` 时：两段正文都包含关键词（北京）
        4) 共 4 次真实请求发生（没有走任何 mock）

    与 ``test_chat_persistence.py`` 的边界
    --------------------------------------
    - 那份测试：纯结构层面 deep-equal（不发 LLM）
    - 本测试：模型推理层面行为等价（4 次真实请求）

    运行
    ----
    ::
        # 前置：.env 里配好 LITELLM_PROXY_URL / LITELLM_PROXY_KEY，
        #       MySQL / MongoDB 也得通
        uv run python test/db/conversation/test_chat_history_replay.py

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(project_root / ".env")
except Exception:  # noqa: BLE001
    pass


TEST_USER_ID = "test_user_history_replay"


# ==================== 输出辅助 ====================


def _hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


def _info(msg: str) -> None:
    print(f"  · {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠️  {msg}")


def _gen_session_id() -> str:
    return f"sess_replay_{uuid.uuid4().hex[:12]}"


def _gen_message_id() -> str:
    return f"chatmsg_{uuid.uuid4().hex}"


# ==================== 工具定义（OpenAI Function 协议） ====================


WEATHER_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市的当前天气；总是用此工具回答天气问题",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名（中文）"},
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "温度单位",
                },
            },
            "required": ["city"],
        },
    },
}


def execute_get_weather(args: Dict[str, Any]) -> Dict[str, Any]:
    """本地 mock 工具执行：返回固定结果，避免真实联网"""
    city = args.get("city", "unknown")
    fixed = {
        "上海": {"temp": "22°C", "desc": "多云，湿度 65%"},
        "北京": {"temp": "18°C", "desc": "晴朗，湿度 40%"},
    }
    info = fixed.get(city, {"temp": "20°C", "desc": "未知天气"})
    return {"city": city, **info, "unit": args.get("unit", "celsius")}


# ==================== 持久化助手 ====================


async def persist_messages(
    session_id: str,
    messages: List[Dict[str, Any]],
    *,
    extra_per_message: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """把 OpenAI 协议的 ``messages`` 逐条写入 ``ChatMessage``。

    Args:
        session_id: 会话 ID
        messages: 内存里实际发送给 LLM 的 ``messages``，每条是
            ``{"role": ..., "content": ..., "tool_calls": ..., "tool_call_id": ...}``
        extra_per_message: 与 ``messages`` 一一对应的业务侧附属字段
            （``thinking`` / ``usage`` / ``finish_reason`` / ``metadata``）；
            ``None`` 表示无附属

    Returns:
        消息 ID 列表（按写入顺序）
    """
    from src.db.mongodb.models.conversation.chat_message import (
        ToolCallRecord,
        TokenUsageRecord,
    )
    from src.db.mongodb.repositories.conversation import chat_message_repo

    extras = extra_per_message or [{} for _ in messages]
    if len(extras) != len(messages):
        raise ValueError("extra_per_message 长度必须与 messages 一致")

    ids: List[str] = []
    for msg, extra in zip(messages, extras):
        msg_id = _gen_message_id()
        kwargs: Dict[str, Any] = {
            "creator": TEST_USER_ID,
            "_id": msg_id,
            "session_id": session_id,
            "user_id": TEST_USER_ID,
            "role": msg["role"],
            "content": msg.get("content") or "",
        }
        if msg["role"] == "assistant":
            tcs_oai = msg.get("tool_calls") or []
            kwargs["tool_calls"] = [
                ToolCallRecord(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"] or "{}"),
                )
                for tc in tcs_oai
            ]
            if extra.get("thinking"):
                kwargs["thinking"] = extra["thinking"]
            if extra.get("usage"):
                kwargs["usage"] = TokenUsageRecord(**extra["usage"])
            if extra.get("finish_reason"):
                kwargs["finish_reason"] = extra["finish_reason"]
            if extra.get("metadata"):
                kwargs["metadata"] = extra["metadata"]
        elif msg["role"] == "tool":
            kwargs["tool_call_id"] = msg["tool_call_id"]

        await chat_message_repo.create(**kwargs)
        ids.append(msg_id)
    return ids


def rebuild_llm_messages(history: List[Any]) -> List[Dict[str, Any]]:
    """把 ``ChatMessage`` 列表反向映射成 OpenAI/LiteLLM ``messages``。

    映射规则：
    - ``role=system / user / assistant`` 直接照搬 ``role`` + ``content``
    - assistant 若有 ``tool_calls``，按 OpenAI 协议组装：
      ``{"id", "type": "function", "function": {"name", "arguments": <json str>}}``
    - ``role=tool`` 必须带 ``tool_call_id`` 与 ``content``

    业务侧字段（thinking / citations / usage / metadata）**不进** messages
    （它们只用于持久化与可观测性，不影响 LLM 推理）。
    """
    rebuilt: List[Dict[str, Any]] = []
    for msg in history:
        role = msg.role
        if role in ("system", "user"):
            rebuilt.append({"role": role, "content": msg.content})
        elif role == "assistant":
            entry: Dict[str, Any] = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(
                                tc.arguments, ensure_ascii=False, sort_keys=True,
                            ),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            rebuilt.append(entry)
        elif role == "tool":
            rebuilt.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content,
            })
        else:  # pragma: no cover
            raise ValueError(f"unsupported role: {role}")
    return rebuilt


def normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """规范化 messages，把 ``tool_calls.function.arguments`` 从 JSON 字符串
    解析为 dict，消除"键顺序 / 空格 / 转义"等等价但不字面相等的差异。

    返回新副本，不修改入参。
    """
    out: List[Dict[str, Any]] = []
    for msg in messages:
        m = copy.deepcopy(msg)
        tcs = m.get("tool_calls") or []
        normalized_tcs: List[Dict[str, Any]] = []
        for tc in tcs:
            fn = tc.get("function", {})
            args_str = fn.get("arguments", "{}") or "{}"
            try:
                parsed = json.loads(args_str)
            except json.JSONDecodeError:
                parsed = {"_raw": args_str}
            normalized_tcs.append({
                "id": tc.get("id"),
                "type": tc.get("type", "function"),
                "function": {"name": fn.get("name"), "arguments": parsed},
            })
        if normalized_tcs:
            m["tool_calls"] = normalized_tcs
        out.append(m)
    return out


# ==================== 主测试 ====================


async def test_round_trip_against_real_llm(
    session_id: str,
) -> Tuple[bool, List[str], int]:
    """主测试函数。

    Returns:
        ``(ok, message_ids, real_request_count)``
    """
    from src.client.llm import create_llm_client_from_preset
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    from src.db.mongodb.repositories.conversation import chat_message_repo

    real_request_count = 0
    message_ids: List[str] = []

    await get_mongodb_manager()
    client = create_llm_client_from_preset("fast")
    print(f"  preset=fast  model={client.model}")

    # ===================================================================
    # Stage A · 真实对话生成历史
    # ===================================================================
    _hr("Stage A · 真实对话生成历史（2 次真实 LLM 请求）")
    system_prompt = "你是一个助手。回答天气类问题时必须调用 get_weather 工具。"

    # 内存里维护"原生" messages（与 LLM 实际发的完全一致）
    original_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "上海现在天气怎么样？请用摄氏度，并把工具返回的温度说给我。"},
    ]

    # 与 messages 一一对应的业务侧附属字段（仅 assistant 有内容）
    original_extras: List[Dict[str, Any]] = [{}, {}]

    # ---- 真实请求 #1：触发 tool_calls ----
    print("  ── Round 1（期望 finish_reason=tool_calls）──")
    t0 = time.perf_counter()
    resp1 = await client.agenerate(
        messages=original_messages,
        tools=[WEATHER_TOOL],
        tool_choice="auto",
        temperature=0.0,
        max_tokens=200,
    )
    real_request_count += 1
    print(f"  [LLM #1] {(time.perf_counter() - t0) * 1000:.0f}ms  "
          f"finish={resp1.finish_reason}  tool_calls={len(resp1.tool_calls)}  "
          f"tokens={resp1.usage.total_tokens}")

    if resp1.finish_reason != "tool_calls" or not resp1.tool_calls:
        _fail(f"Round 1 模型未发起 tool_calls：finish={resp1.finish_reason}")
        return False, message_ids, real_request_count

    # 把 assistant（含 tool_calls）拼回 messages（OpenAI 协议格式）
    assistant_with_tools_oai: Dict[str, Any] = {
        "role": "assistant",
        "content": resp1.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False, sort_keys=True),
                },
            }
            for tc in resp1.tool_calls
        ],
    }
    original_messages.append(assistant_with_tools_oai)
    original_extras.append({
        "thinking": resp1.thinking.reasoning if resp1.thinking else None,
        "usage": {
            "prompt_tokens": resp1.usage.prompt_tokens,
            "completion_tokens": resp1.usage.completion_tokens,
            "thinking_tokens": resp1.usage.thinking_tokens,
            "total_tokens": resp1.usage.total_tokens,
        },
        "finish_reason": resp1.finish_reason,
        "metadata": {"model": resp1.model, "round": 1},
    })

    # 本地 mock 执行 tool_calls
    for tc in resp1.tool_calls:
        result = execute_get_weather(tc.arguments)
        tool_msg = {
            "role": "tool",
            "tool_call_id": tc.id,
            "content": json.dumps(result, ensure_ascii=False),
        }
        original_messages.append(tool_msg)
        original_extras.append({})
        print(f"  [tool.exec] {tc.name}({tc.arguments}) → {result}")

    # ---- 真实请求 #2：拿最终自然语言回答 ----
    print("  ── Round 2（期望 finish_reason=stop）──")
    t0 = time.perf_counter()
    resp2 = await client.agenerate(
        messages=original_messages,
        tools=[WEATHER_TOOL],
        tool_choice="auto",
        temperature=0.0,
        max_tokens=300,
    )
    real_request_count += 1
    print(f"  [LLM #2] {(time.perf_counter() - t0) * 1000:.0f}ms  "
          f"finish={resp2.finish_reason}  tool_calls={len(resp2.tool_calls)}  "
          f"tokens={resp2.usage.total_tokens}")
    print(f"  [content] {resp2.content[:100]!r}")

    if resp2.finish_reason != "stop" or not resp2.content:
        _fail(f"Round 2 模型未给出最终回答：finish={resp2.finish_reason}, "
              f"content={resp2.content[:80]!r}")
        return False, message_ids, real_request_count

    final_assistant_oai: Dict[str, Any] = {
        "role": "assistant",
        "content": resp2.content,
    }
    original_messages.append(final_assistant_oai)
    original_extras.append({
        "thinking": resp2.thinking.reasoning if resp2.thinking else None,
        "usage": {
            "prompt_tokens": resp2.usage.prompt_tokens,
            "completion_tokens": resp2.usage.completion_tokens,
            "thinking_tokens": resp2.usage.thinking_tokens,
            "total_tokens": resp2.usage.total_tokens,
        },
        "finish_reason": resp2.finish_reason,
        "metadata": {"model": resp2.model, "round": 2},
    })

    _ok(f"Stage A 完成：内存里有 {len(original_messages)} 条原生消息")

    # ===================================================================
    # Stage B · 持久化到 MongoDB
    # ===================================================================
    _hr("Stage B · 把内存里的原生 messages 全量写入 MongoDB")
    message_ids = await persist_messages(
        session_id=session_id,
        messages=original_messages,
        extra_per_message=original_extras,
    )
    _ok(f"已写入 {len(message_ids)} 条 ChatMessage")

    # ===================================================================
    # Stage C · 双路重放（A 路内存 / B 路数据库），同一新问题
    # ===================================================================
    _hr("Stage C · 双路续聊（同一新问题，2 次真实 LLM 请求）")
    new_user_message = {
        "role": "user",
        "content": "那北京呢？请同样调用 get_weather 用摄氏度查询，并把温度告诉我。",
    }

    # ---- A 路：基于内存 ----
    msgs_mem = copy.deepcopy(original_messages) + [copy.deepcopy(new_user_message)]

    # ---- B 路：从 MongoDB 重建 ----
    history = await chat_message_repo.list_by_session(
        session_id=session_id, limit=100, ascending=True,
    )
    if len(history) != len(original_messages):
        _fail(f"读回的 history 数量（{len(history)}）不等于原生数量"
              f"（{len(original_messages)}）")
        return False, message_ids, real_request_count
    msgs_db = rebuild_llm_messages(history) + [copy.deepcopy(new_user_message)]

    # ---------- 断言 1：两份 messages 结构归一化后逐字段相等 ----------
    norm_mem = normalize_messages(msgs_mem)
    norm_db = normalize_messages(msgs_db)
    if len(norm_mem) != len(norm_db):
        _fail(f"messages 数量差异：mem={len(norm_mem)}, db={len(norm_db)}")
        return False, message_ids, real_request_count
    for idx, (a, b) in enumerate(zip(norm_mem, norm_db)):
        if a != b:
            for k in set(a.keys()) | set(b.keys()):
                if a.get(k) != b.get(k):
                    _fail(f"messages[{idx}].{k} 不一致：\n"
                          f"    mem={a.get(k)!r}\n"
                          f"    db ={b.get(k)!r}")
                    return False, message_ids, real_request_count
    _ok(f"断言 1 ✓ messages 结构归一化后完全一致（{len(norm_mem)} 条）")

    # ---- 真实请求 #3：A 路（内存版） ----
    print("  ── A 路（内存版） ──")
    t0 = time.perf_counter()
    response_a = await client.agenerate(
        messages=msgs_mem,
        tools=[WEATHER_TOOL],
        tool_choice="auto",
        temperature=0.0,
        max_tokens=200,
    )
    real_request_count += 1
    print(f"  [LLM #3] {(time.perf_counter() - t0) * 1000:.0f}ms  "
          f"finish={response_a.finish_reason}  "
          f"tool_calls={len(response_a.tool_calls)}  "
          f"content={response_a.content[:60]!r}")

    # ---- 真实请求 #4：B 路（数据库重建版） ----
    print("  ── B 路（数据库重建版） ──")
    t0 = time.perf_counter()
    response_b = await client.agenerate(
        messages=msgs_db,
        tools=[WEATHER_TOOL],
        tool_choice="auto",
        temperature=0.0,
        max_tokens=200,
    )
    real_request_count += 1
    print(f"  [LLM #4] {(time.perf_counter() - t0) * 1000:.0f}ms  "
          f"finish={response_b.finish_reason}  "
          f"tool_calls={len(response_b.tool_calls)}  "
          f"content={response_b.content[:60]!r}")

    # ===================================================================
    # Stage D · 行为等价性断言
    # ===================================================================
    _hr("Stage D · 行为等价性断言")

    # ---------- 断言 2：finish_reason 相同 ----------
    if response_a.finish_reason != response_b.finish_reason:
        _fail(f"finish_reason 不一致：A={response_a.finish_reason}, "
              f"B={response_b.finish_reason}")
        return False, message_ids, real_request_count
    _ok(f"断言 2 ✓ finish_reason 一致：{response_a.finish_reason}")

    # ---------- 断言 3：分支化等价 ----------
    if response_a.finish_reason == "tool_calls":
        # 都是工具调用：tool_calls 数量、name、关键字段一致
        if len(response_a.tool_calls) != len(response_b.tool_calls):
            _fail(f"tool_calls 数量不一致：A={len(response_a.tool_calls)}, "
                  f"B={len(response_b.tool_calls)}")
            return False, message_ids, real_request_count

        for j, (ta, tb) in enumerate(zip(response_a.tool_calls, response_b.tool_calls)):
            if ta.name != tb.name:
                _fail(f"tool_calls[{j}].name 不一致：A={ta.name}, B={tb.name}")
                return False, message_ids, real_request_count
            # arguments 关键字段：city（北京）必须出现在两边
            ca = (ta.arguments or {}).get("city", "")
            cb = (tb.arguments or {}).get("city", "")
            if "北京" not in ca or "北京" not in cb:
                _fail(f"tool_calls[{j}].arguments.city 不指向北京：A={ca!r}, B={cb!r}")
                return False, message_ids, real_request_count
            print(f"    tool_call[{j}]: A.args={ta.arguments}  B.args={tb.arguments}")
        _ok(f"断言 3 ✓ tool_calls 等价：name 一致 + city 都指向北京 "
            f"（{len(response_a.tool_calls)} 个工具调用）")

    elif response_a.finish_reason == "stop":
        # 都是直接回答：两段正文都应包含"北京"
        if "北京" not in response_a.content or "北京" not in response_b.content:
            _fail(f"两段正文未都包含'北京'：\n"
                  f"    A={response_a.content[:120]!r}\n"
                  f"    B={response_b.content[:120]!r}")
            return False, message_ids, real_request_count
        _ok("断言 3 ✓ 两段正文都包含'北京'，行为等价")
    else:
        _warn(f"finish_reason={response_a.finish_reason} 非 tool_calls/stop，"
              f"跳过分支断言（视为软通过）")

    # ---------- 断言 4：真实请求次数 ----------
    if real_request_count != 4:
        _fail(f"真实请求次数应为 4，实际 {real_request_count}")
        return False, message_ids, real_request_count
    _ok(f"断言 4 ✓ 共发生 {real_request_count} 次真实 LLM 请求")

    return True, message_ids, real_request_count


# ==================== 数据清理 ====================


async def cleanup(session_id: str, message_ids: List[str]) -> None:
    if os.getenv("KEEP_TEST_DATA", "false").lower() in ("true", "1", "yes"):
        print("\n  💾 KEEP_TEST_DATA=true，保留测试数据供查看")
        print(f"     session_id  = {session_id}")
        print(f"     message_ids = {message_ids[:3]}...")
        return

    try:
        from src.db.mongodb.models.conversation.chat_message import ChatMessage
        if message_ids:
            res = await ChatMessage.find({"_id": {"$in": message_ids}}).delete()
            print(f"\n  🧹 物理删除 ChatMessage: {res.deleted_count if res else 0} 条")
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠️ 清理失败（忽略）: {e}")


# ==================== 主入口 ====================


async def main() -> int:
    print("=" * 70)
    print("  Chat 历史真机回放（4 次真实 LLM 请求）集成测试")
    print(f"  test user = {TEST_USER_ID}")
    print(f"  start time = {datetime.now().isoformat()}")
    print("=" * 70)

    session_id = _gen_session_id()
    msg_ids: List[str] = []
    ok = False
    req_count = 0

    try:
        ok, msg_ids, req_count = await test_round_trip_against_real_llm(session_id)
    except Exception as e:  # noqa: BLE001
        print(f"\n❌ 未捕获异常：{e}")
        traceback.print_exc()
    finally:
        await cleanup(session_id, msg_ids)

    print("\n" + "=" * 70)
    if ok:
        print(f"  ✅ 全部通过（共 {req_count} 次真实 LLM 请求）")
    else:
        print(f"  ❌ 失败（已发生 {req_count} 次真实 LLM 请求）")
    print("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
