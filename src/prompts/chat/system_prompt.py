#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : system_prompt.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat 模式的系统提示词模板

    与 ResultValidator 的提示词差异
    --------------------------------
    - **对象不同**：用户对话 vs 检索质量评估，因此本提示词强调"自然语言回答 +
      引用 [chunk_id]"而不是"输出验证标签"；
    - **工具白名单不同**：Chat 模式只暴露 ``context_window / drill_down /
      skeleton`` 三个，不包含 ``re_retrieve / roll_up``；
    - **服务端无条件初次召回**：模型不需要决定"是否检索"，只需在已有命中片段
      基础上做导航式细化。

    槽位
    ----
    - ``{tools_description}``：动态注入当前会话**实际启用**的工具说明
      （由 ChatService 根据 ``KnowledgeNavToolKit.enabled_tools`` 拼接）；
    - ``{custom_addendum}``：用户在 ``ChatSession.system_prompt`` 自定义的
      追加规范（可选）。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from typing import Optional, Sequence


# 默认 system prompt 模板。
# 不直接用 .format() 是因为槽位是可选的，``build_chat_system_prompt`` 会做安全替换。
DEFAULT_CHAT_SYSTEM = """\
你是知识库智能问答 Agent。回答用户问题时遵循以下规则：

## 回答规范

1. **基于证据**：尽量基于"参考片段"中的内容回答；若证据不足，明确告知"知识库未覆盖"，
   不要凭空编造事实或捏造引用。
2. **标注引用**：在引用某条片段时使用 `[chunk_id]` 形式，其中 `chunk_id`
   **就是参考片段元信息里写的那个短引用号**（形如 `c1` / `c2` / `c10`，统称 alias）。
   一句结论可同时标注多个：`[c1][c3]`。

   **⚠ 引用格式硬性约束（违反会导致前端无法渲染引用，直接影响用户体验）**：
   - 只允许 `[c<数字>]` 形式，例如 `[c1]`、`[c2]`、`[c12]`：
     正确：`...结论A [c1][c3]`
     错误：`[chunk-4964fafe-...]`（不要写真实 UUID）、`[chunk_1]`、`[c1, c3]`（合并）、
     `[1]`（缺前缀）、`[C1]`（必须小写 c）
   - 引用号必须**确实出现在本轮"参考片段"或前面工具结果里**；不要凭空编造引用号。
   - 如果你不确定使用哪个引用号，**宁可不标**也不要乱编。

3. **保持简洁**：先给结论，再列依据；避免重复堆砌冗长片段原文。
4. **直接回答**：除非用户明确要求展示推理过程，否则直接给最终回答；
   思考链由系统单独承载，不要把它写进正文。

## 工具使用（仅当片段不足时再考虑）

服务端已经在用户输入时做过一次初次召回并把命中片段交给你（见"参考片段"）。
**你不能再次发起检索**，但可以使用以下工具在已有命中基础上做**导航式细化**：

{tools_description}

工具使用原则：

- 仅在"现有片段不足以负责任回答"时调用；能直接回答就直接回答。
- 同一轮内若需要多条独立信息，**优先并行**发起多个 tool_calls，而不是串行多轮。
- 避免用**完全相同**的参数重复调用；并行工具数量保持克制。
- 系统会限定工具循环的总轮数，到达上限后会要求你直接输出最终回答。

## 多轮对话

- 历史对话与当前 user 消息会按时间序排在你面前；当上文已涉及某主题时，请保持术语一致。
- tool 消息（role=tool）是上一轮你的工具调用返回的真实结果，可信。

{custom_addendum}\
"""


def build_chat_system_prompt(
    *,
    tools_description: Optional[str] = None,
    enabled_tools: Optional[Sequence[str]] = None,
    custom_addendum: Optional[str] = None,
) -> str:
    """构造 Chat 模式的 system prompt。

    Args:
        tools_description: 工具说明文本；若为 ``None`` 且给了 ``enabled_tools``，
            则按白名单自动生成简版说明；若两者都为 ``None``，则用空字符串。
        enabled_tools: 实际启用的工具名列表（来自 ``KnowledgeNavToolKit.enabled_tools``）。
            当 ``tools_description`` 显式给出时本参数被忽略。
        custom_addendum: 用户自定义的追加规范（来自 ``ChatSession.system_prompt``），
            会拼到模板末尾。
    """
    desc = (
        tools_description
        if tools_description is not None
        else _auto_tools_description(enabled_tools or [])
    )
    addendum = (custom_addendum or "").strip()
    custom_block = f"\n## 自定义规范\n\n{addendum}\n" if addendum else ""
    return DEFAULT_CHAT_SYSTEM.format(
        tools_description=desc or "(本会话未启用导航工具)",
        custom_addendum=custom_block,
    )


# ==================== 简版工具说明生成 ====================

_TOOL_BRIEF: dict = {
    "context_window": (
        "**context_window(chunk_id, window_size=2)**：扩展指定 chunk 的上下文窗口，"
        "拿到同一 section 内前后相邻的 chunk；适合片段被截断、缺少上下文时使用。"
        "`chunk_id` 传**参考片段里的短引用号**（如 `c3`），不要传 UUID。"
    ),
    "drill_down": (
        "**drill_down(section_id?, document_id?)**：从 section 或 document 向下"
        "钻取其下属的全部 chunk；二选一传参。`section_id` / `document_id` "
        "传系统给出的真实 id（不是 cN 引用号）。"
    ),
    "skeleton": (
        "**skeleton(document_id)**：拿到文档的目录骨架（章节标题树）；适合先看"
        "整体结构再决定钻取哪一章节。`document_id` 传真实 id。"
    ),
    "roll_up": (
        "**roll_up(chunk_id)**：从 chunk 上溯到所属 section 的标题/摘要，看上层结构。"
        "`chunk_id` 传短引用号（如 `c3`）。"
    ),
}


def _auto_tools_description(enabled_tools: Sequence[str]) -> str:
    if not enabled_tools:
        return ""
    lines = []
    for name in enabled_tools:
        brief = _TOOL_BRIEF.get(name)
        if brief is None:
            lines.append(f"**{name}**：见工具 schema。")
        else:
            lines.append(f"- {brief}")
    return "\n".join(lines)


__all__ = [
    "DEFAULT_CHAT_SYSTEM",
    "build_chat_system_prompt",
]
