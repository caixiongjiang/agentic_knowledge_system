#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : history_compressor.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    长会话历史压缩工具

    模块职责
    --------
    在 ChatService 把 ``ChatMessage`` 历史交给 LLM 之前做"够用就好"的瘦身：

    1. **轮次滑窗** ``apply_history_window``
       按"对话轮（user → assistant ± tool）"做尾部截尾，保证 ``assistant.tool_calls``
       与对应 ``role=tool`` 消息**永远不会被拆开**。

    2. **孤儿清理** ``drop_assistant_tool_dangling``
       兜底——把没有匹配 ``assistant.tool_calls.id`` 的 ``role=tool`` 丢掉，
       避免 LiteLLM 报 "tool_call_id 找不到对应 assistant" 错。

    3. **Token 估算** ``count_message_tokens`` / ``estimate_history_tokens``
       基于 LiteLLM ``token_counter`` 做精确估算，失败回退到经验值
       （中文≈1.6 chars/token、英文≈4 chars/token）；面向"上下文预算"判断。

    4. **Token 滑窗** ``apply_token_window``
       在轮次滑窗基础上叠加 token 上限约束：从尾部贪心累加，达到 ``max_tokens``
       即停止，但**至少保留 ``min_recent_turns`` 轮**（防止极端长输入导致空 history）。

    5. **摘要压缩** ``summarize_history`` / ``compress_history_to_summary``
       把"超出 ``keep_recent_turns`` 的早期消息"喂给注入的 ``summarize_fn``
       生成一段文本摘要，封装为合成 ``messages dict``（默认 ``role=system``，
       **不持久化** 到 MongoDB），由调用方 ``messages.insert(1, summary_dict)`` 接入。

    设计约定
    --------
    - 入参 ``history`` 是按 ``create_time`` 正序排列的 ``ChatMessage``（或具备
      相同字段属性的鸭子对象）列表；
    - 轮次/token 滑窗系列函数返回**同类型**的列表，方便下游直接调用
      ``rebuild_messages_from_history``；
    - 摘要压缩返回 ``(summary_dict_or_None, kept_history)``，summary 是 OpenAI
      协议 messages dict，由调用方拼接到 ``messages`` 头部；
    - Token 估算与摘要压缩**不强制**对 ``ChatMessage`` 做反射，只读取
      ``role / content / tool_calls / tool_call_id`` 等少量字段。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import json
import logging
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
)

from src.prompts.chat.context_builder import rebuild_messages_from_history

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 类型别名：摘要回调函数。入参是要被压缩的历史片段（与 history 同类型），
# 出参是一段自然语言摘要文本。一般由 ChatService 注入：内部用"fast" preset 的
# LLMClient 拼一段 "请把下列对话压缩成 200 字以内的要点..." prompt 执行 agenerate。
SummarizeFn = Callable[[Sequence[Any]], Awaitable[str]]


# ============================================================
# 1) 轮次滑窗
# ============================================================


def apply_history_window(
    history: Sequence[T],
    *,
    max_turns: int = 10,
    keep_system: bool = True,
) -> List[T]:
    """对历史按"对话轮"做尾部滑窗。

    一"轮"的定义：以 ``role=user`` 起、到下一条 ``role=user`` 之前结束。
    也就是说，一轮可以包含 1 条 user + 多条 assistant + 多条 tool，确保
    ``assistant.tool_calls`` 和它对应的 ``role=tool`` 消息**永远不会被拆开**。

    Args:
        history: 按 create_time 正序的消息列表
        max_turns: 保留的最近轮数（>=1）；本函数不会越界裁切
        keep_system: 是否在窗口顶部保留首条 ``role=system``（默认 True）；
            ChatService 通常会用最新的 system_prompt 重新拼接，
            不依赖历史里的 system，可设 ``False``

    Returns:
        裁切后的新列表（不修改入参）

    Examples
    --------
    >>> # history = [system, user1, asst1, user2, asst2, tool, asst3, user3, asst4]
    >>> # max_turns=2 后保留：[system, user2, asst2, tool, asst3, user3, asst4]
    """
    if not history:
        return []
    if max_turns < 1:
        max_turns = 1

    user_indices: List[int] = [
        i for i, m in enumerate(history) if getattr(m, "role", None) == "user"
    ]
    if not user_indices:
        return list(history)

    kept_user_starts = user_indices[-max_turns:]
    start_idx = kept_user_starts[0]

    kept: List[T] = []
    if keep_system:
        for m in history:
            if getattr(m, "role", None) == "system":
                kept.append(m)
                break

    kept.extend(history[start_idx:])
    return kept


# ============================================================
# 2) 孤儿清理
# ============================================================


def drop_assistant_tool_dangling(history: Sequence[T]) -> List[T]:
    """兜底清理：把没有匹配 ``assistant.tool_calls`` 的孤儿 ``role=tool`` 消息丢弃。

    场景：当上层对历史做过激进 trim、或 MongoDB 软删除导致中间 assistant 消失
    时，可能出现 "role=tool 找不到对应 tool_call_id" 的非法序列，LiteLLM 会
    直接报错。本函数做一次线性扫描，把这类孤儿丢掉。

    Args:
        history: 已经按时间序排好的消息列表

    Returns:
        清理后的列表（不修改入参）。

    注：未对 ``assistant.tool_calls`` 的 ``id`` 与 ``tool.tool_call_id`` 做严格
    一对一校验——只做最小够用的"孤儿丢弃"，避免过度删消息。
    """
    valid_ids: set = set()
    cleaned: List[T] = []
    for msg in history:
        role = getattr(msg, "role", None)
        if role == "assistant":
            tcs = getattr(msg, "tool_calls", None) or []
            for tc in tcs:
                tc_id = getattr(tc, "id", None)
                if tc_id:
                    valid_ids.add(tc_id)
            cleaned.append(msg)
        elif role == "tool":
            tool_call_id = getattr(msg, "tool_call_id", None)
            if tool_call_id and tool_call_id in valid_ids:
                cleaned.append(msg)
        else:
            cleaned.append(msg)
    return cleaned


# ============================================================
# 3) Token 估算
# ============================================================


def _heuristic_count(text: str) -> int:
    """无 LiteLLM 时的经验回退：按中英文字符比估算 token。

    经验值：
    - 中文（含 CJK 字符）：约 ``1 token / 1.6 字符``
    - 英文/符号：约 ``1 token / 4 字符``

    本函数不追求精确，只在 ``litellm.token_counter`` 抛错时兜底，
    保证 ChatService 不会因 token 估算失败而崩。
    """
    if not text:
        return 0
    cjk_count = 0
    other_count = 0
    for ch in text:
        codepoint = ord(ch)
        if (
            0x4E00 <= codepoint <= 0x9FFF
            or 0x3400 <= codepoint <= 0x4DBF
            or 0x20000 <= codepoint <= 0x2A6DF
            or 0x3040 <= codepoint <= 0x30FF  # 日文
            or 0xAC00 <= codepoint <= 0xD7AF  # 韩文
        ):
            cjk_count += 1
        else:
            other_count += 1
    return max(1, int(cjk_count / 1.6) + int(other_count / 4))


def _serialize_message_for_count(msg: Dict[str, Any]) -> str:
    """把一条 OpenAI messages dict 序列化成估算 token 用的纯文本。

    回退路径专用——把 role / content / tool_calls / tool_call_id 拼成
    单段字符串。
    """
    parts: List[str] = [msg.get("role", "")]
    content = msg.get("content")
    if content:
        parts.append(str(content))
    tcs = msg.get("tool_calls") or []
    for tc in tcs:
        try:
            fn = tc.get("function") or {}
            parts.append(fn.get("name", ""))
            parts.append(str(fn.get("arguments", "")))
        except AttributeError:
            parts.append(str(tc))
    if msg.get("tool_call_id"):
        parts.append(str(msg["tool_call_id"]))
    return "\n".join(p for p in parts if p)


def count_message_tokens(
    messages: Sequence[Dict[str, Any]],
    *,
    model: str,
    tools: Optional[Sequence[Dict[str, Any]]] = None,
) -> int:
    """估算 OpenAI/LiteLLM 协议 ``messages``（+ ``tools`` schema）的 token 总数。

    优先调用 ``litellm.token_counter``（自动按 ``model`` 选 tokenizer），失败时
    回退到 ``_heuristic_count`` 经验估算，保证不抛异常。

    Args:
        messages: OpenAI/LiteLLM 协议 messages 列表（典型来自
            ``rebuild_messages_from_history`` 或 ``compose_chat_messages``）。
        model: 模型 ID，例如 ``"deepseek/deepseek-chat"``。LiteLLM 会按此选 tokenizer。
        tools: 可选——本轮要带给 LLM 的 tool schemas（OpenAI 格式）；
            tool schema 本身也吃 tokens，长会话场景必须计入。

    Returns:
        非负整数 token 数。即使输入为空也返回 ``0``。
    """
    if not messages:
        return 0

    try:
        import litellm

        kwargs: Dict[str, Any] = {"model": model, "messages": list(messages)}
        if tools:
            kwargs["tools"] = list(tools)
        return int(litellm.token_counter(**kwargs))
    except Exception as e:  # noqa: BLE001
        logger.debug(
            "litellm.token_counter failed (model=%s, msgs=%d), fallback to heuristic: %s",
            model, len(messages), e,
        )
        total = 0
        for m in messages:
            total += _heuristic_count(_serialize_message_for_count(m))
        if tools:
            total += _heuristic_count(json.dumps(list(tools), ensure_ascii=False))
        return total


def estimate_history_tokens(
    history: Sequence[T],
    *,
    model: str,
    tools: Optional[Sequence[Dict[str, Any]]] = None,
) -> int:
    """以 ``history`` 为入参的便捷 token 估算：内部先 rebuild 再调用 ``count_message_tokens``。

    适用于 ChatService 在压缩前快速判断"是否超预算"。
    """
    if not history:
        return 0
    msgs = rebuild_messages_from_history(history)
    return count_message_tokens(msgs, model=model, tools=tools)


# ============================================================
# 4) Token 滑窗
# ============================================================


def apply_token_window(
    history: Sequence[T],
    *,
    max_tokens: int,
    model: str,
    keep_system: bool = True,
    min_recent_turns: int = 1,
    tools: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[T]:
    """按 token 预算做尾部滑窗（仍以"对话轮"为最小粒度，保证 tool_calls 完整）。

    算法
    ----
    1. 找出所有 ``user`` 起点；
    2. 从最后一轮起点开始向前扩张窗口，每加入一轮就重新估算 token；
    3. 若当前窗口 token 超 ``max_tokens``，**回退到上一轮**（即不再扩张），
       但若已扩张轮数 < ``min_recent_turns``，则继续保留（避免空 history）；
    4. 可选在窗口顶部保留首条 ``role=system``。

    Args:
        history: 按 create_time 正序的消息列表
        max_tokens: token 上限（含 system + history + tools schema）。
            通常由 ChatService 用"模型 context_length - 预留给 system_prompt
            - 预留给本轮 user - 预留给输出"算出。
        model: 模型 ID，用于选 tokenizer。
        keep_system: 是否保留首条 system（默认 True）。
        min_recent_turns: 最少保留几轮（默认 1，即至少保最后一轮 user → assistant）。
            即使最后一轮自身就超 ``max_tokens``，本函数也不会丢——上游应另行截
            content。
        tools: 透传给 ``count_message_tokens``，把 tool schema 的 token 也算上。

    Returns:
        裁切后的新列表；与 ``apply_history_window`` 同语义保证："assistant.tool_calls
        + 对应 tool" 永远整轮保留或整轮丢弃。
    """
    if not history:
        return []
    if max_tokens <= 0:
        return []
    if min_recent_turns < 1:
        min_recent_turns = 1

    user_indices: List[int] = [
        i for i, m in enumerate(history) if getattr(m, "role", None) == "user"
    ]
    if not user_indices:
        return list(history)

    # system 槽位的 token 占用（独立计入以便复用）
    system_msg: Optional[T] = None
    if keep_system:
        for m in history:
            if getattr(m, "role", None) == "system":
                system_msg = m
                break

    # 从最后一轮起点开始，逐步向前扩张
    # turn_idx 从 len(user_indices)-1 倒推
    best_kept: List[T] = []
    last_turn_pos = len(user_indices) - 1
    while last_turn_pos >= 0:
        turns_taken = (len(user_indices) - 1) - last_turn_pos + 1
        start_idx = user_indices[last_turn_pos]

        candidate: List[T] = []
        if system_msg is not None:
            candidate.append(system_msg)
        candidate.extend(history[start_idx:])

        tokens = estimate_history_tokens(candidate, model=model, tools=tools)
        if tokens <= max_tokens or turns_taken <= min_recent_turns:
            best_kept = candidate
            last_turn_pos -= 1
            continue
        # 超预算且已满足最少轮数，停止扩张
        break

    return best_kept


# ============================================================
# 5) 摘要压缩
# ============================================================


async def summarize_history(
    history: Sequence[T],
    *,
    summarize_fn: SummarizeFn,
) -> str:
    """调用注入的 ``summarize_fn`` 把 ``history`` 摘成一段文本。

    本函数只做最薄的包装：
    - history 为空 → 直接返回 ``""``，避免无意义 LLM 调用；
    - 异常 → 记 warning 并返回 ``""``，不影响 ChatService 主流程
      （摘要失败时退化为"无摘要 + 仅最近 N 轮"也能跑）。
    """
    if not history:
        return ""
    try:
        summary = await summarize_fn(history)
        return (summary or "").strip()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "summarize_fn raised, fallback to empty summary (n_msgs=%d): %s",
            len(history), e,
        )
        return ""


async def compress_history_to_summary(
    history: Sequence[T],
    *,
    summarize_fn: SummarizeFn,
    keep_recent_turns: int = 3,
    keep_system: bool = True,
    summary_role: str = "system",
    summary_prefix: str = "以下是早期对话的摘要，仅供你回顾上下文，请勿照抄：\n",
) -> Tuple[Optional[Dict[str, Any]], List[T]]:
    """把"超出 ``keep_recent_turns`` 的早期消息"归并为一段摘要。

    流程
    ----
    1. 用"对话轮"切分 ``history``；
    2. 若总轮数 <= ``keep_recent_turns``，无需压缩，返回 ``(None, list(history))``；
    3. 否则取**早期片段**（含可选首条 system 之外的所有早于"最近 N 轮"的消息）
       喂给 ``summarize_fn`` 生成摘要文本；
    4. 把摘要包装成合成 ``messages dict``（role=``summary_role`` 默认 ``system``），
       同最近 ``keep_recent_turns`` 轮的**原始消息**一并返回。

    Args:
        history: 按 create_time 正序的消息列表（``ChatMessage`` 或鸭子对象）
        summarize_fn: 异步可调用对象，签名 ``(early_history) -> str``，
            由 ChatService 注入（典型用 "fast" preset 的 LLMClient.agenerate
            执行一段"压缩对话"prompt）。
        keep_recent_turns: 不压缩的最近轮数（默认 3）。
        keep_system: 早期片段是否包含首条 ``role=system`` 消息（默认 True，
            首条 system 通常是历史快照，归入摘要更合理；若 ChatService 已用
            新 system_prompt，差异可忽略）。
        summary_role: 合成摘要消息的 role，默认 ``"system"``；某些模型不接受
            多个 system，可改成 ``"user"``。
        summary_prefix: 摘要正文前缀，提示 LLM "这是早期摘要，别当真话照抄"。

    Returns:
        ``(summary_message_dict | None, kept_history)``

        - ``summary_message_dict``: 若不需要压缩则为 ``None``；否则形如
          ``{"role": "system", "content": "<前缀><摘要文本>"}``，调用方可
          ``messages.insert(1, summary_message_dict)`` 把它接到 system_prompt
          之后、history 之前。**该字段不持久化**。
        - ``kept_history``: ``history`` 的**原始切片**（同类型对象，未做任何转换），
          长度等同最近 ``keep_recent_turns`` 轮覆盖的消息条数；ChatService 直接
          交给 ``rebuild_messages_from_history`` / ``compose_chat_messages``。
    """
    if not history:
        return None, []
    if keep_recent_turns < 1:
        keep_recent_turns = 1

    user_indices: List[int] = [
        i for i, m in enumerate(history) if getattr(m, "role", None) == "user"
    ]
    if not user_indices:
        return None, list(history)

    total_turns = len(user_indices)
    if total_turns <= keep_recent_turns:
        return None, list(history)

    recent_start_user = user_indices[-keep_recent_turns]
    early_part = list(history[:recent_start_user])
    recent_part = list(history[recent_start_user:])

    if not keep_system:
        early_part = [
            m for m in early_part if getattr(m, "role", None) != "system"
        ]

    if not early_part:
        return None, recent_part

    summary_text = await summarize_history(early_part, summarize_fn=summarize_fn)
    if not summary_text:
        # 摘要失败 → 退化为"不压缩、仅截断"
        return None, recent_part

    summary_dict: Dict[str, Any] = {
        "role": summary_role,
        "content": f"{summary_prefix}{summary_text}",
    }
    return summary_dict, recent_part


__all__ = [
    "SummarizeFn",
    "apply_history_window",
    "drop_assistant_tool_dangling",
    "count_message_tokens",
    "estimate_history_tokens",
    "apply_token_window",
    "summarize_history",
    "compress_history_to_summary",
]
