#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : context_builder.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat 模块上下文组装层：把"系统提示 / 历史 / 检索片段 / 用户当前问"
    四块原料组装为 LiteLLM 可消费的 ``messages`` 列表。

    与 Phase 1 测试 ``test_chat_history_replay.py`` 中 ``rebuild_llm_messages``
    的关系
    ----------------------------------------------------------------
    Phase 1 测试里那个工具函数已经验证过"持久化 → OpenAI 协议"反向映射的
    无失真性，本模块把它正式落到 src/，并叠加 Chat 模块独有的能力：

    1. ``format_retrieved_chunks_for_context``：把检索 ``ChunkItem`` 列表渲染
       成 LLM 看得懂的"参考片段"段落（带 chunk_id 便于模型自然引用）；
    2. ``rebuild_messages_from_history``：把 ``ChatMessage`` 历史反序列化回
       OpenAI 协议 messages（user / assistant w/ tool_calls / tool / system）；
    3. ``compose_chat_messages``：四块原料的总装入口，是 ChatService 主流程的
       唯一消费点。

    设计约定
    --------
    - 参考片段以 **role=user** 的形式放在 ``[system, ...history]`` 之后、
      最新 user 消息之前：现实里 LLM 对"最近的 user 内容"敏感度最高，把片段
      贴近问题能稳定模型行为；同时不污染 system 槽位，便于多轮叠加。
    - 历史里的 tool_calls 必须在内存协议中按 OpenAI 规范（``function.arguments``
      JSON 字符串）重建，否则 LiteLLM 会拒绝。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence

from src.retrieve.types.result import ChunkItem

if TYPE_CHECKING:
    # 仅类型注解使用；运行期不导入，避免 src.prompts.chat ↔ src.service.chat 循环
    from src.service.chat.chunk_alias_map import ChunkAliasMap

from src.prompts.chat.retrieval_hints import SEMANTIC_RECALL_LITERAL_HINT


# ==================== 检索片段渲染 ====================


def format_retrieved_chunks_for_context(
    chunks: Sequence[ChunkItem],
    *,
    max_preview: int = 400,
    header: str = "参考片段",
    alias_map: Optional[ChunkAliasMap] = None,
) -> str:
    """把 ChunkItem 列表渲染为人类/LLM 可读的"参考片段"段落。

    格式约定（与 system prompt 中"标注引用"规则联动）::

        ## 参考片段

        ### [1] chunk_id=c1, document_id=doc_yyy, score=0.91
        <片段正文，截断到 max_preview>

        ### [2] chunk_id=c2, ...
        ...

    Args:
        chunks: 命中的 ChunkItem 列表（已按业务侧排序/去重）
        max_preview: 单片段正文最大字符数，超出截断（默认 400 字）
        header: 段落顶部标题（默认"参考片段"）
        alias_map: 若提供，则把真实 chunk_id 替换为 session 级 alias
            （``c1``, ``c2`` ...），节省 token + 屏蔽内部 id；map 是
            in-place 增量分配，调用本函数后里面会多出新 alias。
            为 ``None`` 时回退到老行为（直接输出真实 chunk_id），便于
            单测和兼容历史调用。

    Returns:
        渲染后的 markdown 文本；若 ``chunks`` 为空返回 ``"## {header}\\n\\n(本轮未命中相关片段)"``。
    """
    if not chunks:
        return f"## {header}\n\n(本轮未命中相关片段)"

    lines: List[str] = [f"## {header}", ""]
    for i, c in enumerate(chunks, 1):
        text = (c.text or "").strip()
        if max_preview and len(text) > max_preview:
            text = text[:max_preview] + "..."
        doc = c.document_id or "N/A"
        cid_label = alias_map.alias_for(c.chunk_id) if alias_map and c.chunk_id else c.chunk_id
        lines.append(
            f"### [{i}] chunk_id={cid_label}, document_id={doc}, score={c.score:.4f}",
        )
        if text:
            lines.append(text)
        lines.append("")  # 空行分隔
    lines.append(SEMANTIC_RECALL_LITERAL_HINT)
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ==================== 历史反序列化 ====================


def rebuild_messages_from_history(history: Iterable[Any]) -> List[Dict[str, Any]]:
    """把 ``ChatMessage`` 列表反向映射成 OpenAI/LiteLLM ``messages``。

    映射规则
    --------
    - ``role=system / user / assistant`` 直接照搬 ``role`` + ``content``；
    - assistant 若有 ``tool_calls``，按 OpenAI 协议组装::

          {"id", "type": "function", "function": {"name", "arguments": <json str>}}

    - ``role=tool`` 必须带 ``tool_call_id`` 与 ``content``；
    - 业务侧附属字段（thinking / citations / usage / metadata）**不进** messages，
      它们只用于持久化与可观测性，不影响 LLM 推理。

    入参 ``history`` 接受任何具有 ``role / content / tool_calls / tool_call_id``
    属性的对象（典型即 ``ChatMessage``），便于单元测试使用轻量替身。
    """
    rebuilt: List[Dict[str, Any]] = []
    for msg in history:
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", "") or ""
        if role in ("system", "user"):
            rebuilt.append({"role": role, "content": content})
        elif role == "assistant":
            entry: Dict[str, Any] = {"role": "assistant", "content": content}
            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
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
                    for tc in tool_calls
                ]
            rebuilt.append(entry)
        elif role == "tool":
            rebuilt.append({
                "role": "tool",
                "tool_call_id": getattr(msg, "tool_call_id", None),
                "content": content,
            })
        elif role is None:
            continue
        else:
            raise ValueError(f"unsupported role in history: {role!r}")
    return rebuilt


# ==================== 总装入口 ====================


def compose_chat_messages(
    *,
    system_prompt: str,
    history: Iterable[Any],
    user_message: str,
    retrieved_chunks: Sequence[ChunkItem] = (),
    inject_chunks_before_user: bool = True,
    chunks_max_preview: int = 400,
    alias_map: Optional[ChunkAliasMap] = None,
) -> List[Dict[str, Any]]:
    """组装本轮发给 LLM 的完整 ``messages``。

    顺序::

        [system_prompt]
        + [...history(已反序列化)]                 # 不重复 system
        + [(optional) "参考片段" as role=user]      # inject_chunks_before_user=True
        + [user_message]

    Args:
        system_prompt: 已经构造好的 system 文本；本函数直接放在 messages[0]。
            若 history 中也含 system 消息，这里**不会**重复加，由调用方决定。
        history: ``ChatMessage`` 列表（按 create_time 正序）。
        user_message: 用户本轮新消息正文。
        retrieved_chunks: 服务端本轮命中的检索片段（已去重/排序）。
        inject_chunks_before_user: 是否把"参考片段"以 role=user 形式插在最新
            user 消息之前。设 ``False`` 则不注入（用于工具补轮等场景）。
        chunks_max_preview: 单片段最大字符数（透传给 ``format_retrieved_chunks_for_context``）。

    Returns:
        可以直接喂给 ``LLMClient.agenerate / astream`` 的 messages 列表。
    """
    msgs: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    history_msgs = rebuild_messages_from_history(history)
    # 去重：若 history 中已含 system，跳过那条避免重复
    for m in history_msgs:
        if m["role"] == "system":
            continue
        msgs.append(m)

    if inject_chunks_before_user and retrieved_chunks:
        msgs.append({
            "role": "user",
            "content": format_retrieved_chunks_for_context(
                retrieved_chunks,
                max_preview=chunks_max_preview,
                alias_map=alias_map,
            ),
        })

    msgs.append({"role": "user", "content": user_message})
    return msgs


__all__ = [
    "format_retrieved_chunks_for_context",
    "rebuild_messages_from_history",
    "compose_chat_messages",
]
