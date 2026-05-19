#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : system_prompt.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    Chat 模式的系统提示词模板

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
你是知识库智能问答 Agent。你拥有完整的工具集，可以根据需要自主决定如何获取信息来回答用户问题。

## 回答规范

1. **基于证据**：尽量基于检索到的片段或工具返回的内容回答；若证据不足，明确告知"知识库未覆盖"，
   不要凭空编造事实或捏造引用。
2. **标注引用**：在引用某条片段时使用 `[chunk_id]` 形式，其中 `chunk_id`
   **就是参考片段元信息里写的那个短引用号**（形如 `c1` / `c2` / `c10`，统称 alias）。
   一句结论可同时标注多个：`[c1][c3]`。

   **引用格式约束**（违反会导致前端无法渲染引用）：
   - 只允许 `[c<数字>]` 形式，例如 `[c1]`、`[c2]`、`[c12]`。
   - 引用号必须确实出现在工具返回的结果里；不要凭空编造。
   - 如果不确定使用哪个引用号，宁可不标也不要乱编。

3. **数学公式**：使用标准 LaTeX 语法，并用美元符号包裹（前端通过 remark-math + KaTeX 渲染）。

   **公式格式约束**（违反会导致前端无法渲染公式，直接以原始字符串显示）：
   - 行内公式用**单美元符号**包裹：`$\\lambda_1 = 0.5$`、`$q_i$`、`$\\sum_i q_i \\log p_i$`。
   - 块级公式用**双美元符号**包裹，且独占一行、前后各留一个空行，例如：

     ```
     $$
     \\mathcal{{L}}_{{\\text{{total}}}} = \\mathcal{{L}}_{{\\text{{CE}}}} + \\lambda_1 \\cdot \\mathcal{{L}}_{{\\text{{feat}}}}
     $$
     ```
   - **严禁**使用 `\\[ ... \\]`、`[ ... ]`、`\\( ... \\)`、`( ... )` 作为公式分隔符——这些写法前端不会识别为公式。
   - 下标必须用 `_`、上标必须用 `^`，**不能省略下划线 / 脱字符**。
     - 正确：`\\mathcal{{L}}_{{\\text{{CE}}}}`、`\\sum_{{i=1}}^{{N}}`、`q_i^t`。
     - 错误：`\\mathcal{{L}}{{\\text{{CE}}}}`、`\\sum{{i=1}}^{{N}}`、`q_i t`。

4. **保持简洁**：先给结论，再列依据；避免重复堆砌冗长片段原文。
5. **直接回答**：除非用户明确要求展示推理过程，否则直接给最终回答。

## 自主规划

你可以根据用户问题的特点自主决定回答策略：

- 如果问题比较简单或基于常识，可以直接回答，不必检索。
- 如果问题涉及知识库中的具体内容，可以调用检索工具获取相关片段。
- 如果已有片段不够充分，可以用不同的查询角度再次检索，或用导航工具深入探索。
- 如果需要了解某个片段的上下文或所属章节，可以使用导航工具。

{tools_description}

工具使用建议：

- 同一轮内若需要多条独立信息，可以并行发起多个 tool_calls。
- 避免用完全相同的参数重复调用同一工具。
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
        tools_description=desc or "(本会话未启用工具)",
        custom_addendum=custom_block,
    )


# ==================== 简版工具说明生成 ====================

_TOOL_BRIEF: dict = {
    "search_knowledge_base": (
        "- **search_knowledge_base(query_text, top_k=10)**：在知识库中检索相关文档片段。"
        "内部经过大模型路由规划、多路召回、融合精排。"
        "当已有信息不足以回答时，或需要查找更多相关内容时可以使用。"
        "可以用不同角度的查询多次调用。"
    ),
    "context_window": (
        "- **context_window(chunk_id, window_size=2)**：扩展指定片段的上下文，"
        "获取同一章节内前后相邻的片段。"
        "当某个片段内容被截断或需要更多上下文时适用。"
        "`chunk_id` 传引用号（如 `c3`）。"
    ),
    "drill_down": (
        "- **drill_down(section_id?, document_id?, target?)**：从文档或章节向下钻取。"
        "支持三条路径：document→section（返回章节列表）、document→chunk、section→chunk。"
        "`target` 可选 `section` 或 `chunk`，默认 `chunk`。"
        "返回的结果包含真实 id，可直接传给其他导航工具继续探索。"
    ),
    "skeleton": (
        "- **skeleton(document_id)**：获取文档的目录骨架（章节标题树）。"
        "想了解文档整体结构、定位相关章节时适用。`document_id` 传真实 id。"
    ),
    "roll_up": (
        "- **roll_up(chunk_id?, section_id?, target?)**：从片段或章节向上回溯。"
        "支持三条路径：chunk→section、chunk→document、section→document。"
        "`chunk_id` 传引用号（如 `c3`），`section_id` 传真实 id，二选一。"
        "`target` 可选 `section` 或 `document`，默认 `section`。"
        "返回的结果包含真实 id，可直接传给其他导航工具继续探索。"
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
            lines.append(brief)
    return "\n".join(lines)


__all__ = [
    "DEFAULT_CHAT_SYSTEM",
    "build_chat_system_prompt",
]
