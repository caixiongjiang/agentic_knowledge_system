#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : file_summary_context.py
@Function:
    文件级摘要的上下文构造层。

    对应 section_context.py 的角色：把上游消息 payload 转成
    extract 层用的内存结构。纯函数，无 LLM / 无 DB 依赖。

    - build_section_summaries_from_payload：从 SectionSummaryEndMessage 的
      section_summaries_payload 字段构造 SectionSummaryInput 列表
      （过滤空摘要、按树顺序排序：叶子在前、父在后，便于 LLM 看到完整结构）
    - aggregate_chunk_count：聚合各 section 的 chunk_count 得到全文档总数
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Dict, List

from loguru import logger
from pydantic import BaseModel


class SectionSummaryInput(BaseModel):
    """
    单个 section 摘要的内存结构（来自 SectionSummaryEndMessage payload）。

    供 FileSummarizer 拼装 LLM 输入用。
    """

    section_id: str
    summary_id: str = ""
    title: str = ""
    summary_text: str
    is_leaf: bool = True
    parent_section_id: str = ""
    chunk_count: int = 0
    language: str = "unknown"


def build_section_summaries_from_payload(
    section_summaries_payload: List[Dict[str, Any]],
) -> List[SectionSummaryInput]:
    """
    从 SectionSummaryEndMessage 的 section_summaries_payload 构造
    SectionSummaryInput 列表。

    不访问任何数据库；输入完全来自消息体，消除写库竞态。

    排序策略：
    - 结构叶子（is_leaf=True）在前，父节点（is_leaf=False）在后，
      使 LLM 看到自底向上的内容流，更贴近自然阅读顺序。
    - 同类内保持原 payload 顺序（与 SectionSummary 后序遍历一致）。

    Args:
        section_summaries_payload: 各 section 摘要完整数据列表，
            每项含 {section_id, summary_id, title, summary_text,
                   is_leaf, parent_section_id, chunk_count, language}

    Returns:
        SectionSummaryInput 列表（过滤掉空 summary_text 的项）
    """
    if not section_summaries_payload:
        logger.info("FileSummary: payload 无 section 摘要，返回空列表")
        return []

    result: List[SectionSummaryInput] = []
    for s in section_summaries_payload:
        section_id = s.get("section_id")
        summary_text = (s.get("summary_text") or "").strip()
        if not section_id or not summary_text:
            continue
        result.append(SectionSummaryInput(
            section_id=section_id,
            summary_id=s.get("summary_id") or "",
            title=s.get("title") or "",
            summary_text=summary_text,
            is_leaf=bool(s.get("is_leaf", True)),
            parent_section_id=s.get("parent_section_id") or "",
            chunk_count=int(s.get("chunk_count") or 0),
            language=s.get("language") or "unknown",
        ))

    # 叶子在前、父在后（自底向上，更贴近自然阅读顺序）
    result.sort(key=lambda x: (0 if x.is_leaf else 1,))

    logger.info(
        f"FileSummary: 从 payload 构造上下文 section_summaries={len(result)}, "
        f"leaf={sum(1 for r in result if r.is_leaf)}, "
        f"parent={sum(1 for r in result if not r.is_leaf)}"
    )
    return result


def aggregate_chunk_count(section_summaries: List[SectionSummaryInput]) -> int:
    """
    聚合各 section 的 chunk_count 得到全文档 chunk 总数。

    注意：父 section 的 chunk_count 已包含后代叶子的 chunk_id
    （由 SectionSummaryService._collect_descendant_chunk_ids 递归合并），
    故只统计叶子 section 的 chunk_count，避免重复累加。

    Args:
        section_summaries: SectionSummaryInput 列表

    Returns:
        全文档 chunk 总数
    """
    return sum(s.chunk_count for s in section_summaries if s.is_leaf)
