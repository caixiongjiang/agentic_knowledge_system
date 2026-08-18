#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : text_analyzer.py
@Author  : agentic
@Date    : 2026/07/14
@Function:
    Atomic QA 抽取 Prompt 构造（v1.1 section 级抽取）。

    build_atomic_qa_messages：对一个 section 的一批 chunk（≤ N 个，N=chunk_batch_size）
    调 LLM 抽取原子问答（Atomic QA），LLM 用 [Cn] 占位符标注每条 QA 的来源 chunk，
    后处理（qa_summarizer）再把 [Cn] 替换为真实 chunk_id，实现 chunk 级溯源。

    输入：
    - section_title：section 标题
    - batch_chunks_text：本批 chunk 拼接文本，每个 chunk 前缀 [Cn] 代号
      （由 qa_context.build_qa_batch_text 构造）
    - file_summary：全局主题锚点（来自 SummaryEndMessage 消息体），约束 QA 与文档主题对齐
    - max_qa：本批 QA 数量上限

    输出：JSON 数组，每项 {question, answer, source_chunks, qa_type}；无价值则 []。

    设计原则：
    - 先判断本节对文档主题有无召回价值，再抽取；目录/对照表等无实质知识则空数组。
    - 忠实于正文，不臆造；通识背景须落到本文任务，否则不抽。
    - qa_type 白名单：factual / procedural / conceptual / comparative。
    - 上限 max_qa，宁缺毋滥，不必凑满。
    - 只输出 JSON 数组。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Dict


SYSTEM_PROMPT = (
    "从章节片段抽取原子问答，供按问题召回。"
    "先看本节对文档主题有无召回价值：没有就输出 []。"
    "目录、术语对照、页码版式直接 []；"
    "通识定义若不体现本文用法也不要抽。\n"
    "答案须能由正文直接支撑，不编造。"
    "一条一事，问题自含；选题和问法自行判断，不必凑满。\n"
    "最多 {max_qa} 条。"
    "qa_type 仅限 factual / procedural / conceptual / comparative。"
    "语言跟正文主导语言走。"
    "source_chunks 写所依据的 Cn。"
    "只输出 JSON 数组。"
)


_OUTPUT_EXAMPLE = (
    "格式：[{\"question\":\"...\",\"answer\":\"...\","
    "\"source_chunks\":[\"C1\"],\"qa_type\":\"factual\"}] 或 []"
)


def build_atomic_qa_messages(
    section_title: str,
    batch_chunks_text: str,
    file_summary: str,
    max_qa: int,
) -> List[Dict[str, str]]:
    """
    构造 atomic_qa 抽取的 LLM 消息列表（OpenAI 风格）。

    Args:
        section_title: Section 标题文本（无标题时传空字符串）
        batch_chunks_text: 本批 chunk 拼接文本，每个 chunk 前缀 [Cn] 代号
            （由 qa_context.build_qa_batch_text 构造，n 从 1 开始）
        file_summary: 文档全局摘要（主题锚点，来自 SummaryEndMessage 消息体）
        max_qa: 本批 QA 数量上限

    Returns:
        [{"role": "system", ...}, {"role": "user", ...}]
    """
    title_line = section_title.strip() if section_title else "（无标题）"
    file_summary_line = (file_summary or "").strip() or "（无文档级摘要，按 section 正文主题抽取）"

    system_prompt = SYSTEM_PROMPT.format(max_qa=max_qa) + "\n\n" + _OUTPUT_EXAMPLE

    user_prompt = (
        f"章节标题：{title_line}\n\n"
        f"文档全局摘要（主题锚点）：\n{file_summary_line}\n\n"
        f"章节片段（每个 chunk 前缀 [Cn] 代号）：\n{batch_chunks_text}\n\n"
        f"按文档主题判断本节是否值得抽取。有则最多 {max_qa} 条，无则输出 []。"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
