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

    输出：JSON 数组，每项 {question, answer, source_chunks, qa_type}

    设计原则（对齐「文档抽取提示词设计原则」）：
    - 清晰：明确任务、输入结构、输出 schema，给示例。
    - 自包含：file_summary 作为全局锚点直接喂入，不要求模型读外部上下文。
    - 类型白名单：qa_type 仅允许 factual / procedural / conceptual / comparative。
    - 数量控制：明确上限 max_qa，宁缺毋滥，禁止为凑数编造。
    - JSON 输出：只输出 JSON 数组，无前后缀/解释/markdown 包裹。
    - LLM 局限：忠实于 chunk 正文，不得臆造、不得补充正文之外的信息；
      答案若需跨多个 chunk，source_chunks 列出全部相关代号。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Dict


SYSTEM_PROMPT = (
    "你是一位严谨的技术文档问答对抽取助手。"
    "你的任务是从给定的「章节片段」中抽取原子问答（Atomic QA），"
    "用于后续基于问题的精准召回。\n"
    "要求：\n"
    "1. 忠实于输入正文，不得臆造、不得补充正文之外的信息；"
    "答案必须能由输入正文直接支撑。\n"
    "2. 每个 QA 聚焦一个「原子事实/概念/步骤」，问题清晰可独立理解，"
    "答案凝练完整（不只是一句话引用，但也不展开正文外的推理）。\n"
    "3. 答案若依据多个 chunk，必须在 source_chunks 中列出全部相关代号。\n"
    "4. qa_type 只能取以下四者之一：\n"
    "   - factual：事实型（是什么/有哪些）\n"
    "   - procedural：流程型（怎么做/步骤）\n"
    "   - conceptual：概念型（为什么/含义/原理）\n"
    "   - comparative：对比型（A 与 B 的区别/优劣）\n"
    "5. 数量控制：最多 {max_qa} 条，宁缺毋滥；"
    "若正文不足以支撑高质量 QA，可以少给甚至不给，禁止为凑数编造。\n"
    "6. QA 主题应与给定的「文档全局摘要」对齐，不抽取与文档主题无关的边角细节。\n"
    "7. QA 正文语言与输入正文主导语言一致。\n"
    "8. 只输出一个 JSON 数组，不要输出任何前缀、标签、解释或 markdown 代码块包裹。"
)


# 输出 schema 示例（注入 system prompt，约束 LLM 输出结构）
_OUTPUT_EXAMPLE = (
    "输出格式示例（仅示意结构，内容随输入而定）：\n"
    "[\n"
    "  {\"question\": \"...\", \"answer\": \"...\", "
    "\"source_chunks\": [\"C1\"], \"qa_type\": \"factual\"},\n"
    "  {\"question\": \"...\", \"answer\": \"...\", "
    "\"source_chunks\": [\"C1\", \"C3\"], \"qa_type\": \"comparative\"}\n"
    "]"
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
        f"请从上述章节片段中抽取最多 {max_qa} 条原子问答，按指定 JSON 数组格式输出。"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
