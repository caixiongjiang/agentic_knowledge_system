#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_summary.py
@Author  : agentic
@Date    : 2026/07/02
@Function:
    Section 级摘要 Prompt 构造。

    包含两类 prompt：
    1) build_section_summary_messages：叶子 section（有 chunk）→ 基于原文生成摘要
    2) build_section_rollup_messages：父 section（无 chunk，仅有子 section 摘要）
       → 基于子 section 摘要合成父 section 的连贯摘要（Bottom-up Rollup）

    Rollup 场景：MinerU 不给可靠层级，split 阶段把父/子 section 摊平成同级，
    父 section 挂不到 chunk。SectionSummaryService 通过标题编号推断真实层级、
    建树、后序遍历，先叶子 LLM 摘要，再父节点 rollup。父 rollup 的输入是
    「子标题 + 子 summary 列表」，输出是一段自然连贯的父级摘要，供 Milvus
    检索（命中父节点后 agent 可下钻）与前端骨架展示。

    设计原则：
    - 忠实于输入内容，不臆造、不补充输入外的信息。
    - 控制篇幅：3-6 句，覆盖核心主题与关键事实。
    - 摘要正文语言与输入内容主导语言一致。
    - 只输出摘要正文，不加前缀/标签/解释。
@Modify History:
    2026/07/03 - 增加 build_section_rollup_messages（父 section 自下而上摘要）

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Dict, Tuple


SYSTEM_PROMPT = (
    "你是一位严谨的技术文档摘要助手。"
    "你的任务是根据给定的「章节标题」与「章节正文」，"
    "生成该章节的精炼摘要。\n"
    "要求：\n"
    "1. 忠实于原文，不得臆造、不得补充原文之外的信息；\n"
    "2. 摘要为 3-6 句连贯的中文，覆盖该章节的核心主题与关键事实；\n"
    "3. 不要复述章节标题作为开头，直接给出摘要正文；\n"
    "4. 正文中可能出现「[图片]\\n标题：…\\n脚注：…」形式的图片占位符，"
    "不要把占位符字面内容当作事实复述；仅当其标题/脚注"
    "提供了真实语义信息时，才可凝练进摘要；\n"
    "5. 只输出摘要正文，不要输出任何前缀、标签、解释或额外说明。"
)


ROLLUP_SYSTEM_PROMPT = (
    "你是一位严谨的技术文档摘要助手。"
    "当前需要为一个「父章节」生成摘要，输入是它下属若干「子章节」的标题与已生成摘要，"
    "而不是原文正文。请把这些子章节摘要综合成一段连贯的父章节摘要。\n"
    "要求：\n"
    "1. 忠实于给定的子章节摘要，不得臆造、不得补充这些摘要之外的信息；\n"
    "2. 摘要为 3-6 句连贯文字，覆盖父章节整体主题及各子章节要点分布；\n"
    "3. 使用与子章节摘要一致的主导语言（若子章节为中文则用中文，"
    "若为英文则用英文），若混合以字符数多者为准；\n"
    "4. 不要罗列成 bullet 或分行输出，输出一段连贯段落；\n"
    "5. 不要复述父章节标题作为开头，直接给出摘要正文；\n"
    "6. 只输出摘要正文，不要输出任何前缀、标签、解释或额外说明。"
)


def build_section_summary_messages(
    section_title: str,
    combined_text: str,
) -> List[Dict[str, str]]:
    """
    构造叶子 section 摘要的 LLM 消息列表（OpenAI 风格）。

    Args:
        section_title: Section 标题文本（无标题时传空字符串）
        combined_text: 该 section 下所有 chunk 拼接后的组合正文
            （image chunk 已转为占位符）

    Returns:
        [{"role": "system", ...}, {"role": "user", ...}]
    """
    title_line = section_title.strip() if section_title else "（无标题）"
    user_prompt = (
        f"章节标题：{title_line}\n\n"
        f"章节正文：\n{combined_text}\n\n"
        f"请生成该章节的摘要。"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_section_rollup_messages(
    parent_title: str,
    child_summaries: List[Tuple[str, str]],
) -> List[Dict[str, str]]:
    """
    构造父 section 自下而上摘要（rollup）的 LLM 消息列表。

    Args:
        parent_title: 父 Section 标题文本（无标题时传空字符串）
        child_summaries: 子 section 的 (标题, 摘要) 列表，按文档顺序传入。
            标题为空的子节点会记为「（无标题）」。

    Returns:
        [{"role": "system", ...}, {"role": "user", ...}]
    """
    title_line = parent_title.strip() if parent_title else "（无标题）"

    lines: List[str] = []
    for idx, (child_title, child_summary) in enumerate(child_summaries, start=1):
        c_title = (child_title or "").strip() or "（无标题）"
        c_summary = (child_summary or "").strip()
        if not c_summary:
            continue
        lines.append(f"子章节 {idx}【{c_title}】：{c_summary}")

    combined = "\n\n".join(lines) if lines else "（无有效子章节摘要）"

    user_prompt = (
        f"父章节标题：{title_line}\n\n"
        f"下属子章节摘要如下（按文档顺序）：\n{combined}\n\n"
        f"请综合上述子章节摘要，生成该父章节的整体摘要。"
    )
    return [
        {"role": "system", "content": ROLLUP_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
