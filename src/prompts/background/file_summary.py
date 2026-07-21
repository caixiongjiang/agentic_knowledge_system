#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : file_summary.py
@Function:
    文件级摘要 Prompt 构造。

    输入：各 section 的（标题 + 摘要正文）列表
    输出：一段文件级摘要 + 关键词 + 主题标签 + 文档类型分类

    设计原则：
    - 忠实于子章节摘要，不臆造、不补充输入外的信息
    - 摘要 3-6 句连贯文字，覆盖文档整体主题与各 section 要点分布
    - keywords：5-10 个核心关键词
    - topics：2-5 个主题标签（比 keywords 更高层的主题分类）
    - document_type：从预设分类中选一个最贴近的
    - 输出 JSON 便于解析（避免额外标记/解释）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import json
from typing import Dict, List, Tuple


SYSTEM_PROMPT = (
    "你是一位严谨的技术文档摘要助手。"
    "当前需要为一个整篇文档生成文件级摘要，输入是该文档下属若干「章节」的标题与已生成摘要，"
    "而不是原文正文。请把这些章节摘要综合成一段连贯的文件级摘要，并提取关键词、主题标签、文档类型。\n"
    "要求：\n"
    "1. 忠实于给定的章节摘要，不得臆造、不得补充这些摘要之外的信息；\n"
    "2. summary 为 3-6 句连贯文字，覆盖文档整体主题及各章节要点分布；"
    "不要罗列成 bullet 或分行输出，输出一段连贯段落；不要复述文档标题作为开头；\n"
    "3. keywords 为 5-10 个核心关键词（短语或词，反映文档核心概念、技术、方法）；\n"
    "4. topics 为 2-5 个主题标签（比 keywords 更高层的主题分类，如「机器学习」「系统设计」「操作教程」）；\n"
    "5. document_type 从以下分类中选最贴近的一个："
    "research_paper / tutorial / manual / technical_report / blog / specification / book / other；"
    "若无法判断则填 other；\n"
    "6. 使用与章节摘要一致的主导语言（若为中文则用中文，若为英文则用英文），"
    "若混合以字符数多者为准；\n"
    "7. 只输出一个 JSON 对象，不要输出任何前缀、标签、解释或额外说明。"
)


def build_file_summary_messages(
    section_summaries: List[Tuple[str, str]],
    document_title: str = "",
) -> List[Dict[str, str]]:
    """
    构造文件级摘要的 LLM 消息列表（OpenAI 风格）。

    Args:
        section_summaries: 各 section 的 (标题, 摘要正文) 列表，按文档顺序传入。
            标题为空的 section 会记为「（无标题）」。
        document_title: 文档标题（可选，从消息体或文件名获取）

    Returns:
        [{"role": "system", ...}, {"role": "user", ...}]
    """
    title_line = (document_title or "").strip() or "（无文档标题）"

    lines: List[str] = []
    for idx, (section_title, section_summary) in enumerate(section_summaries, start=1):
        s_title = (section_title or "").strip() or "（无标题）"
        s_summary = (section_summary or "").strip()
        if not s_summary:
            continue
        lines.append(f"章节 {idx}【{s_title}】：{s_summary}")

    combined = "\n\n".join(lines) if lines else "（无有效章节摘要）"

    user_prompt = (
        f"文档标题：{title_line}\n\n"
        f"下属各章节摘要如下（按文档顺序）：\n{combined}\n\n"
        f"请综合上述章节摘要，生成该文档的文件级摘要，并提取关键词、主题标签、文档类型。\n"
        f"输出 JSON 格式：\n"
        f"{json.dumps({'summary': '...', 'keywords': ['...'], 'topics': ['...'], 'document_type': '...'}, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
