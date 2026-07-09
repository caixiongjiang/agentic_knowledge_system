#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_chat_prompts.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    src/prompts/chat/ 三件套单元测试

    覆盖目标
    --------
    1. **system_prompt**
       - 不传 enabled_tools / tools_description 时模板能渲染（不抛 KeyError）；
       - 传 enabled_tools=("context_window","drill_down","skeleton") 时自动生成简版
         工具说明，且 3 个工具名都出现在文本里；
       - custom_addendum 非空时，会被作为 "## 自定义规范" 拼到文本末尾。

    2. **context_builder.format_retrieved_chunks_for_context**
       - 空列表 → "(本轮未命中相关片段)"；
       - 非空列表 → 按 "### [i] chunk_id=..., document_id=..., score=..."
         逐条渲染，正文超长被截断。

    3. **context_builder.rebuild_messages_from_history**
       - 多种 role 反序列化为 OpenAI/LiteLLM messages，结构与字段全对；
       - assistant.tool_calls 的 ``function.arguments`` 必须是 JSON 字符串
         （含中文不转义），key 顺序稳定。

    4. **context_builder.compose_chat_messages**
       - 总装出的 messages 顺序：[system, ...history(去 system), 参考片段?, user]；
       - inject_chunks_before_user=False 时不注入参考片段；
       - retrieved_chunks 为空时不注入参考片段（即便 inject=True）。

    5. **history_compressor.apply_history_window**
       - max_turns 控制按 user 起点裁切；keep_system=True 保留首条 system；
       - 一轮内的 assistant.tool_calls + 对应 tool 消息整体保留或整体丢弃，
         不会出现"留下 tool 但 assistant 被裁掉"的情况。

    6. **history_compressor.drop_assistant_tool_dangling**
       - 孤儿 ``role=tool``（没有匹配 assistant.tool_calls.id）被丢弃；
       - 合法序列原样保留。

    7. **history_compressor.count_message_tokens / estimate_history_tokens**
       - LiteLLM 在常见模型下能给出非零、单调（越多消息越大）的估算；
       - 未知模型下不抛错（走 LiteLLM 内置回退或我们的经验回退）；
       - 加 tools schema 后 token 数严格增加。

    8. **history_compressor.apply_token_window**
       - 给一个超低 max_tokens，仅留 min_recent_turns 轮（保最后一轮）；
       - 给一个超高 max_tokens，全量保留；
       - 中等预算时按"对话轮"整轮回退，且 assistant.tool_calls + 对应 tool
         整轮保留或整轮丢弃。

    9. **history_compressor.summarize_history / compress_history_to_summary**
       - 注入 mock summarize_fn，返回"FAKE SUMMARY"；
       - 历史 <= keep_recent_turns 时返回 (None, history)，不调用回调；
       - 历史 > keep_recent_turns 时返回合成 system 消息 + 最近 N 轮原始切片；
       - summarize_fn 抛异常时退化为 (None, recent_part) 不影响主流程。

    运行::
        uv run python test/prompts/chat/test_chat_prompts.py

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import json
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Sequence

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def _hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


# ==================== ChatMessage 替身（避免引入 MongoDB 依赖） ====================
# 仅暴露 rebuild / window / dangling 需要的字段属性，与 ChatMessage 字段名一致。


@dataclass
class _FakeToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class _FakeMsg:
    role: str
    content: str = ""
    tool_calls: List[_FakeToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None


# ==================== Test 1: system_prompt ====================


def test_system_prompt() -> bool:
    _hr("Test 1 · build_chat_system_prompt（含工具白名单 / 自定义追加）")
    from src.prompts.chat import DEFAULT_CHAT_SYSTEM, build_chat_system_prompt

    # 不传任何槽位，模板要能渲染
    base = build_chat_system_prompt()
    if (
        "{tools_description}" in base
        or "{custom_addendum}" in base
        or "{explicit_skills_override}" in base
    ):
        _fail("槽位未替换")
        return False
    if "(本会话未启用导航工具)" not in base:
        _fail("空工具集时未输出占位")
        return False
    _ok("空槽位渲染正常（含占位文本）")

    # 传 enabled_tools 自动生成简版工具说明
    text = build_chat_system_prompt(
        enabled_tools=("context_window", "drill_down", "skeleton"),
    )
    for name in ("context_window", "drill_down", "skeleton"):
        if name not in text:
            _fail(f"工具名 {name!r} 未出现在 system prompt 中")
            return False
    _ok("自动生成的简版说明包含全部 3 个工具名")

    # custom_addendum
    text2 = build_chat_system_prompt(
        enabled_tools=("skeleton",),
        custom_addendum="回答仅限金融领域。",
    )
    if "## 自定义规范" not in text2 or "金融领域" not in text2:
        _fail("custom_addendum 未拼接到 system prompt")
        return False
    _ok("custom_addendum 被插入到 '## 自定义规范' 段")

    # 显式 tools_description 覆盖 enabled_tools
    text3 = build_chat_system_prompt(
        tools_description="（这是手动写的工具说明）",
        enabled_tools=("context_window",),
    )
    if "（这是手动写的工具说明）" not in text3:
        _fail("tools_description 显式覆盖未生效")
        return False
    if "context_window" in text3 and "拿到同一 section" in text3:
        _fail("显式 tools_description 时不应再用 enabled_tools 自动文本")
        return False
    _ok("显式 tools_description 优先于 enabled_tools 自动生成")

    assert isinstance(DEFAULT_CHAT_SYSTEM, str) and len(DEFAULT_CHAT_SYSTEM) > 100
    return True


# ==================== Test 2: format_retrieved_chunks_for_context ====================


def test_format_retrieved_chunks() -> bool:
    _hr("Test 2 · format_retrieved_chunks_for_context")
    from src.prompts.chat import format_retrieved_chunks_for_context
    from src.retrieve.types.result import ChunkItem

    # 空列表
    empty = format_retrieved_chunks_for_context([])
    if "(本轮未命中相关片段)" not in empty:
        _fail(f"空列表渲染异常：{empty!r}")
        return False
    _ok("空列表 → 占位文本")

    long_text = "这是一段很长的文本。" * 100
    chunks = [
        ChunkItem(
            chunk_id="ck_a", score=0.91, document_id="doc_x", text="片段 A",
        ),
        ChunkItem(
            chunk_id="ck_b", score=0.88, document_id="doc_x", text=long_text,
        ),
    ]
    rendered = format_retrieved_chunks_for_context(chunks, max_preview=40)
    if "ck_a" not in rendered or "ck_b" not in rendered:
        _fail("渲染未包含 chunk_id")
        return False
    if "### [1]" not in rendered or "### [2]" not in rendered:
        _fail("编号缺失")
        return False
    # long_text 被截断
    if long_text in rendered:
        _fail("max_preview 截断未生效")
        return False
    if "..." not in rendered:
        _fail("截断尾部应附加省略号")
        return False
    _ok("2 条片段编号正常，第 2 条被 max_preview=40 截断 + 省略号")
    return True


# ==================== Test 3: rebuild_messages_from_history ====================


def test_rebuild_messages_from_history() -> bool:
    _hr("Test 3 · rebuild_messages_from_history（OpenAI 协议字段全对齐）")
    from src.prompts.chat import rebuild_messages_from_history

    history = [
        _FakeMsg(role="system", content="sys"),
        _FakeMsg(role="user", content="hi"),
        _FakeMsg(
            role="assistant",
            content="",
            tool_calls=[
                _FakeToolCall(
                    id="call_1", name="get_weather",
                    arguments={"city": "上海", "unit": "celsius"},
                ),
            ],
        ),
        _FakeMsg(role="tool", content='{"temp":"22°C"}', tool_call_id="call_1"),
        _FakeMsg(role="assistant", content="上海现在 22°C。"),
    ]

    msgs = rebuild_messages_from_history(history)
    if len(msgs) != 5:
        _fail(f"messages 数量={len(msgs)}, want=5")
        return False

    if msgs[0] != {"role": "system", "content": "sys"}:
        _fail(f"[0] 不一致：{msgs[0]}")
        return False
    if msgs[1] != {"role": "user", "content": "hi"}:
        _fail(f"[1] 不一致：{msgs[1]}")
        return False

    asst = msgs[2]
    if asst["role"] != "assistant" or asst["content"] != "":
        _fail(f"assistant role/content 异常：{asst}")
        return False
    tcs = asst.get("tool_calls")
    if not tcs or len(tcs) != 1:
        _fail(f"tool_calls 缺失或数量错：{asst}")
        return False
    tc = tcs[0]
    if tc["id"] != "call_1" or tc["type"] != "function":
        _fail(f"tool_calls 结构错：{tc}")
        return False
    if tc["function"]["name"] != "get_weather":
        _fail(f"tool_calls.function.name 错：{tc}")
        return False
    # arguments 必须是 JSON 字符串、含中文不转义、key 稳定
    args_str = tc["function"]["arguments"]
    if not isinstance(args_str, str):
        _fail(f"arguments 应为 JSON 字符串，实际 {type(args_str)}")
        return False
    if "上海" not in args_str:
        _fail(f"中文应保留原文，不应被转义：{args_str!r}")
        return False
    parsed = json.loads(args_str)
    if parsed != {"city": "上海", "unit": "celsius"}:
        _fail(f"arguments 解析后内容错：{parsed}")
        return False
    _ok("assistant.tool_calls 结构完整、arguments 是 JSON 字符串、中文不转义")

    if msgs[3] != {
        "role": "tool", "tool_call_id": "call_1", "content": '{"temp":"22°C"}',
    }:
        _fail(f"tool message 异常：{msgs[3]}")
        return False
    _ok("tool 消息 tool_call_id / content 准确")

    if msgs[4] != {"role": "assistant", "content": "上海现在 22°C。"}:
        _fail(f"final assistant 异常：{msgs[4]}")
        return False
    _ok("纯文本 assistant 消息正常")
    return True


# ==================== Test 4: compose_chat_messages ====================


def test_compose_chat_messages() -> bool:
    _hr("Test 4 · compose_chat_messages 总装顺序")
    from src.prompts.chat import compose_chat_messages
    from src.retrieve.types.result import ChunkItem

    history = [
        _FakeMsg(role="system", content="OLD SYS（应被新 system 覆盖、不重复）"),
        _FakeMsg(role="user", content="第一轮问"),
        _FakeMsg(role="assistant", content="第一轮答"),
    ]
    chunks = [
        ChunkItem(chunk_id="ck_1", score=0.9, document_id="doc_a", text="片段一"),
    ]

    msgs = compose_chat_messages(
        system_prompt="NEW SYS",
        history=history,
        user_message="第二轮问",
        retrieved_chunks=chunks,
    )

    # 顺序断言
    roles = [m["role"] for m in msgs]
    if roles != ["system", "user", "assistant", "user", "user"]:
        _fail(f"role 序列错：{roles}")
        return False
    _ok(f"role 序列正确：{roles}")

    if msgs[0]["content"] != "NEW SYS":
        _fail("新 system_prompt 未生效")
        return False
    if "OLD SYS" in "\n".join(m["content"] for m in msgs):
        _fail("history 中的旧 system 未被去掉")
        return False
    _ok("system 槽位由调用方提供，history 里的旧 system 被去重")

    # 参考片段紧贴最新 user 之前
    if "ck_1" not in msgs[-2]["content"] or "片段一" not in msgs[-2]["content"]:
        _fail("参考片段未注入到最新 user 之前")
        return False
    if msgs[-1]["content"] != "第二轮问":
        _fail("最新 user 不在末尾")
        return False
    _ok("参考片段 = messages[-2]，最新 user = messages[-1]")

    # inject_chunks_before_user=False
    msgs2 = compose_chat_messages(
        system_prompt="NEW SYS",
        history=[],
        user_message="只问无片段",
        retrieved_chunks=chunks,
        inject_chunks_before_user=False,
    )
    if [m["role"] for m in msgs2] != ["system", "user"]:
        _fail(f"禁用注入时序列错：{[m['role'] for m in msgs2]}")
        return False
    _ok("inject_chunks_before_user=False → 不注入参考片段")

    # retrieved_chunks 为空时也不注入
    msgs3 = compose_chat_messages(
        system_prompt="S", history=[], user_message="x", retrieved_chunks=[],
    )
    if [m["role"] for m in msgs3] != ["system", "user"]:
        _fail("空 chunks 时仍注入了参考片段")
        return False
    _ok("空 retrieved_chunks → 不注入")
    return True


# ==================== Test 5: apply_history_window ====================


def test_apply_history_window() -> bool:
    _hr("Test 5 · apply_history_window 按对话轮裁切")
    from src.prompts.chat import apply_history_window

    # 6 轮（每轮 user + assistant）
    history = [
        _FakeMsg(role="system", content="sys"),
        _FakeMsg(role="user", content="U1"),
        _FakeMsg(role="assistant", content="A1"),
        _FakeMsg(role="user", content="U2"),
        _FakeMsg(role="assistant", content="A2"),
        _FakeMsg(role="user", content="U3"),
        _FakeMsg(
            role="assistant", content="",
            tool_calls=[_FakeToolCall(id="call_x", name="t", arguments={})],
        ),
        _FakeMsg(role="tool", content="r", tool_call_id="call_x"),
        _FakeMsg(role="assistant", content="A3"),
        _FakeMsg(role="user", content="U4"),
        _FakeMsg(role="assistant", content="A4"),
    ]

    kept = apply_history_window(history, max_turns=2)
    roles = [m.role for m in kept]
    contents = [m.content for m in kept if m.role in ("user", "assistant")]
    # 期望：[system, U3 起到最后 U4] —— 保留最近 2 个 user 起点
    if "system" not in roles:
        _fail("system 应保留")
        return False
    if "U1" in contents or "U2" in contents:
        _fail(f"U1/U2 应被裁掉：{contents}")
        return False
    if "U3" not in contents or "U4" not in contents:
        _fail(f"U3/U4 应保留：{contents}")
        return False
    # tool_call & 对应 tool 整轮保留
    if "call_x" not in {
        getattr(tc, "id", None)
        for m in kept if m.role == "assistant"
        for tc in (m.tool_calls or [])
    }:
        _fail("U3 轮内的 assistant.tool_calls 应保留")
        return False
    if not any(m.role == "tool" and m.tool_call_id == "call_x" for m in kept):
        _fail("U3 轮内的 role=tool 消息应保留")
        return False
    _ok(f"max_turns=2 → 裁切后 user={['U3','U4']}, "
        f"assistant.tool_calls/tool 整轮完整保留")

    # max_turns=1 → 只留最后一轮
    kept2 = apply_history_window(history, max_turns=1)
    contents2 = [m.content for m in kept2 if m.role == "user"]
    if contents2 != ["U4"]:
        _fail(f"max_turns=1 应只剩 U4：{contents2}")
        return False
    _ok("max_turns=1 → 仅剩最后一轮")

    # keep_system=False
    kept3 = apply_history_window(history, max_turns=1, keep_system=False)
    if any(m.role == "system" for m in kept3):
        _fail("keep_system=False 时 system 不应保留")
        return False
    _ok("keep_system=False → system 被丢弃")

    # 空历史
    if apply_history_window([], max_turns=3) != []:
        _fail("空历史应返回空列表")
        return False
    _ok("空历史 → 空列表")
    return True


# ==================== Test 6: drop_assistant_tool_dangling ====================


def test_drop_dangling() -> bool:
    _hr("Test 6 · drop_assistant_tool_dangling 孤儿丢弃")
    from src.prompts.chat import drop_assistant_tool_dangling

    history = [
        _FakeMsg(role="user", content="U1"),
        _FakeMsg(
            role="assistant", content="",
            tool_calls=[_FakeToolCall(id="call_ok", name="t", arguments={})],
        ),
        _FakeMsg(role="tool", content="r-ok", tool_call_id="call_ok"),
        # 孤儿：没有 assistant 配对
        _FakeMsg(role="tool", content="orphan", tool_call_id="call_missing"),
        _FakeMsg(role="assistant", content="answer"),
    ]
    cleaned = drop_assistant_tool_dangling(history)
    roles_and_ids = [
        (m.role, getattr(m, "tool_call_id", None)) for m in cleaned
    ]
    # 期望孤儿 (tool, call_missing) 被剔除
    if ("tool", "call_missing") in roles_and_ids:
        _fail(f"孤儿 tool 未被剔除：{roles_and_ids}")
        return False
    if ("tool", "call_ok") not in roles_and_ids:
        _fail("合法 tool 被误删")
        return False
    if len(cleaned) != len(history) - 1:
        _fail(f"清理后长度={len(cleaned)}, want={len(history) - 1}")
        return False
    _ok(f"孤儿 (tool, call_missing) 被剔除；合法 tool 保留；"
        f"len(history): {len(history)} → {len(cleaned)}")
    return True


# ==================== Test 7: count_message_tokens / estimate_history_tokens ====================


def _build_long_history(n_turns: int = 4) -> List[_FakeMsg]:
    """构造可控长度的多轮对话历史，每轮 user + assistant。"""
    msgs: List[_FakeMsg] = [_FakeMsg(role="system", content="系统设定：知识库问答助手")]
    for i in range(1, n_turns + 1):
        msgs.append(_FakeMsg(role="user", content=f"第 {i} 轮的问题：" + "Q" * 30))
        msgs.append(
            _FakeMsg(role="assistant", content=f"第 {i} 轮的回答：" + "A" * 60),
        )
    return msgs


def test_token_counters() -> bool:
    _hr("Test 7 · count_message_tokens / estimate_history_tokens")
    from src.prompts.chat import count_message_tokens, estimate_history_tokens

    base_msgs = [
        {"role": "system", "content": "你是知识库问答助手。"},
        {"role": "user", "content": "上海明天天气如何？"},
    ]
    bigger_msgs = base_msgs + [
        {"role": "assistant", "content": "我先查询一下。" * 5},
        {
            "role": "assistant", "content": "",
            "tool_calls": [{
                "id": "c1", "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"city": "上海"}',
                },
            }],
        },
        {"role": "tool", "tool_call_id": "c1",
         "content": '{"temp": "22", "weather": "多云"}'},
        {"role": "assistant", "content": "上海明天约 22°C，多云。"},
    ]

    # 空 messages → 0
    if count_message_tokens([], model="deepseek/deepseek-chat") != 0:
        _fail("空 messages 应返回 0")
        return False
    _ok("空 messages → 0 tokens")

    # 非空且非负
    t_base = count_message_tokens(base_msgs, model="deepseek/deepseek-chat")
    t_big = count_message_tokens(bigger_msgs, model="deepseek/deepseek-chat")
    if t_base <= 0 or t_big <= 0:
        _fail(f"token 估算非正：base={t_base}, big={t_big}")
        return False
    _ok(f"base={t_base} tokens, big={t_big} tokens（非空非负）")

    # 单调性：消息更多 → token 更大
    if t_big <= t_base:
        _fail(f"单调性失败：t_big({t_big}) <= t_base({t_base})")
        return False
    _ok(f"单调性成立：{t_base} < {t_big}")

    # tools schema 进一步增加 token
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the weather of a given city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }]
    t_with_tools = count_message_tokens(
        bigger_msgs, model="deepseek/deepseek-chat", tools=tools,
    )
    if t_with_tools <= t_big:
        _fail(f"加 tools 后 token 未增加：{t_with_tools} <= {t_big}")
        return False
    _ok(f"加 tools schema → {t_big} → {t_with_tools}（严格增加）")

    # 未知模型不抛错
    t_unknown = count_message_tokens(
        bigger_msgs, model="this-provider/this-model-does-not-exist",
    )
    if t_unknown <= 0:
        _fail(f"未知模型估算非正：{t_unknown}")
        return False
    _ok(f"未知模型不抛错，回退估算 = {t_unknown} tokens")

    # estimate_history_tokens 应能跑通 ChatMessage 鸭子对象
    history = _build_long_history(3)
    t_history = estimate_history_tokens(history, model="deepseek/deepseek-chat")
    if t_history <= 0:
        _fail(f"history token 估算非正：{t_history}")
        return False
    _ok(f"estimate_history_tokens(3 轮 fake history) = {t_history} tokens")
    return True


# ==================== Test 8: apply_token_window ====================


def test_apply_token_window() -> bool:
    _hr("Test 8 · apply_token_window 按 token 预算尾部滑窗")
    from src.prompts.chat import (
        apply_token_window,
        estimate_history_tokens,
    )

    # 6 轮（含一轮 tool_call）
    history = [
        _FakeMsg(role="system", content="sys"),
        _FakeMsg(role="user", content="U1 " + "x" * 80),
        _FakeMsg(role="assistant", content="A1 " + "y" * 80),
        _FakeMsg(role="user", content="U2 " + "x" * 80),
        _FakeMsg(role="assistant", content="A2 " + "y" * 80),
        _FakeMsg(role="user", content="U3 " + "x" * 80),
        _FakeMsg(
            role="assistant", content="",
            tool_calls=[
                _FakeToolCall(
                    id="call_x", name="get_x", arguments={"q": "value"},
                ),
            ],
        ),
        _FakeMsg(role="tool", content="r-x " + "z" * 50, tool_call_id="call_x"),
        _FakeMsg(role="assistant", content="A3 " + "y" * 80),
        _FakeMsg(role="user", content="U4 " + "x" * 80),
        _FakeMsg(role="assistant", content="A4 " + "y" * 80),
    ]
    model = "deepseek/deepseek-chat"
    full_tokens = estimate_history_tokens(history, model=model)
    _ok(f"完整 history 估算 ≈ {full_tokens} tokens")

    # 1) 超高预算 → 全保留（含 system）
    kept_full = apply_token_window(
        history, max_tokens=full_tokens * 10, model=model,
    )
    if len(kept_full) != len(history):
        _fail(f"超高预算应全保留，实际 {len(kept_full)} / {len(history)}")
        return False
    _ok(f"max_tokens 远大于实际 → 全量保留（{len(kept_full)} 条）")

    # 2) 极低预算（< 一轮的 token）→ 仍保留至少 min_recent_turns=1 轮
    kept_min = apply_token_window(history, max_tokens=1, model=model)
    if not kept_min:
        _fail("min_recent_turns=1 应至少保留一轮，结果为空")
        return False
    u_in_min = [m.content for m in kept_min if m.role == "user"]
    if u_in_min != [history[-2].content]:  # 最后一轮 user = U4
        _fail(f"超低预算应只剩最后一轮 user，实际 user={u_in_min}")
        return False
    _ok(f"max_tokens=1 → 至少留最后一轮，user={u_in_min}")

    # 3) 中等预算：能容纳一部分轮，不能全部
    mid_budget = full_tokens // 2
    kept_mid = apply_token_window(history, max_tokens=mid_budget, model=model)
    mid_tokens = estimate_history_tokens(kept_mid, model=model)
    if mid_tokens > mid_budget and len(kept_mid) > 2:
        _fail(f"中等预算回退失败：估算 {mid_tokens} > 预算 {mid_budget}")
        return False
    if len(kept_mid) >= len(history):
        _fail("中等预算不应全保留")
        return False
    _ok(f"中等预算 {mid_budget} tokens → 窗口估算 {mid_tokens} tokens, "
        f"保留 {len(kept_mid)}/{len(history)} 条")

    # 4) tool_calls 完整性：若 U3 轮被保留，对应 tool 也必须保留；
    #    若 U3 轮被裁，则 assistant.tool_calls + tool 一起被裁
    has_tool_call = any(
        getattr(tc, "id", None) == "call_x"
        for m in kept_mid if m.role == "assistant"
        for tc in (m.tool_calls or [])
    )
    has_tool_msg = any(
        m.role == "tool" and m.tool_call_id == "call_x" for m in kept_mid
    )
    if has_tool_call != has_tool_msg:
        _fail(
            f"tool_call / tool 整轮性被破坏：has_call={has_tool_call}, "
            f"has_tool={has_tool_msg}"
        )
        return False
    _ok(f"tool_calls 整轮性 OK：has_call={has_tool_call}, has_tool={has_tool_msg}")

    # 5) min_recent_turns=2 时即使预算极低也保 2 轮
    kept_min2 = apply_token_window(
        history, max_tokens=1, model=model, min_recent_turns=2,
    )
    u_in_min2 = [m.content for m in kept_min2 if m.role == "user"]
    if len(u_in_min2) < 2:
        _fail(f"min_recent_turns=2 应保 2 轮 user，实际 {u_in_min2}")
        return False
    _ok(f"min_recent_turns=2 + 预算 1 tokens → user 轮数={len(u_in_min2)}")

    # 6) keep_system=False
    kept_no_sys = apply_token_window(
        history, max_tokens=full_tokens * 10, model=model, keep_system=False,
    )
    if any(m.role == "system" for m in kept_no_sys):
        _fail("keep_system=False 时 system 应被丢弃")
        return False
    _ok("keep_system=False → 不保留 system")
    return True


# ==================== Test 9: summarize_history / compress_history_to_summary ====================


def test_summary_compression() -> bool:
    _hr("Test 9 · summarize_history / compress_history_to_summary")
    from src.prompts.chat import (
        compress_history_to_summary,
        summarize_history,
    )

    captured_arg: List[Any] = []

    async def fake_summarize(early: Sequence[Any]) -> str:
        captured_arg.append(list(early))
        return "FAKE SUMMARY: 用户问了 A/B/C 三件事，助手都给出了答复。"

    async def failing_summarize(early: Sequence[Any]) -> str:
        raise RuntimeError("LLM down")

    history = _build_long_history(5)  # 5 轮 user + 1 system

    # 1) 历史 < keep_recent_turns → 不压缩，不调 fn
    summary_dict, recent = asyncio.run(
        compress_history_to_summary(
            history, summarize_fn=fake_summarize, keep_recent_turns=10,
        ),
    )
    if summary_dict is not None:
        _fail("总轮数 <= keep_recent_turns 时不应返回 summary_dict")
        return False
    if len(recent) != len(history):
        _fail(f"不压缩时 kept 应等同原历史：{len(recent)} vs {len(history)}")
        return False
    if captured_arg:
        _fail("不需压缩时 summarize_fn 不应被调用")
        return False
    _ok("总轮数 <= keep_recent_turns → 不调 summarize_fn, kept=原历史")

    # 2) 历史 > keep_recent_turns → 调 fn, 返回合成 system + 最近 N 轮
    captured_arg.clear()
    summary_dict, recent = asyncio.run(
        compress_history_to_summary(
            history, summarize_fn=fake_summarize, keep_recent_turns=2,
        ),
    )
    if summary_dict is None:
        _fail("应当压缩，summary_dict 不应为 None")
        return False
    if summary_dict["role"] != "system":
        _fail(f"summary role 默认应为 system：{summary_dict['role']}")
        return False
    if "FAKE SUMMARY" not in summary_dict["content"]:
        _fail(f"summary content 未含回调返回值：{summary_dict['content']!r}")
        return False
    if "早期对话的摘要" not in summary_dict["content"]:
        _fail("summary 前缀缺失")
        return False
    # recent 应为最近 2 轮（U4..A4 + U5..A5）
    recent_users = [m.content for m in recent if m.role == "user"]
    if len(recent_users) != 2:
        _fail(f"recent user 轮数应为 2，实际 {len(recent_users)}")
        return False
    if not all(c.startswith(("第 4 轮", "第 5 轮")) for c in recent_users):
        _fail(f"recent user 应是第 4/5 轮：{recent_users}")
        return False
    # 早期片段被喂给 fn（包含 system + 第 1~3 轮）
    if not captured_arg:
        _fail("summarize_fn 未被调用")
        return False
    early_passed = captured_arg[0]
    early_users = [m.content for m in early_passed if getattr(m, "role", None) == "user"]
    if len(early_users) != 3:
        _fail(f"喂给 fn 的早期 user 轮数应为 3，实际 {len(early_users)}")
        return False
    _ok(
        f"压缩成功：summary 注入 system，recent={len(recent_users)} 轮 user，"
        f"early 喂给 fn 共 {len(early_users)} 轮 user"
    )

    # 3) summary_role="user" 自定义
    summary_dict2, _ = asyncio.run(
        compress_history_to_summary(
            history, summarize_fn=fake_summarize,
            keep_recent_turns=2, summary_role="user",
        ),
    )
    if summary_dict2["role"] != "user":
        _fail(f"自定义 summary_role 未生效：{summary_dict2['role']}")
        return False
    _ok("自定义 summary_role='user' 生效")

    # 4) summarize_fn 抛异常 → 退化为 (None, recent_part)，不影响主流程
    summary_dict3, recent3 = asyncio.run(
        compress_history_to_summary(
            history, summarize_fn=failing_summarize, keep_recent_turns=2,
        ),
    )
    if summary_dict3 is not None:
        _fail("summarize_fn 抛异常时应退化为 None")
        return False
    if not recent3:
        _fail("退化时 recent 不应为空")
        return False
    _ok("summarize_fn 抛异常 → 退化为 (None, recent_part)")

    # 5) summarize_history 单独：空 history → ""
    res_empty = asyncio.run(summarize_history([], summarize_fn=fake_summarize))
    if res_empty != "":
        _fail(f"空 history 应返回 ''，实际 {res_empty!r}")
        return False
    _ok("summarize_history(空 history) → ''")
    return True


# ==================== 主入口 ====================


def main() -> int:
    print("=" * 70)
    print("  src/prompts/chat/ 单元测试（Phase 2）")
    print("=" * 70)

    tests = [
        ("system_prompt", test_system_prompt),
        ("format_retrieved_chunks", test_format_retrieved_chunks),
        ("rebuild_messages_from_history", test_rebuild_messages_from_history),
        ("compose_chat_messages", test_compose_chat_messages),
        ("apply_history_window", test_apply_history_window),
        ("drop_assistant_tool_dangling", test_drop_dangling),
        ("token_counters", test_token_counters),
        ("apply_token_window", test_apply_token_window),
        ("summary_compression", test_summary_compression),
    ]
    results = []
    for name, fn in tests:
        try:
            ok = fn()
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
