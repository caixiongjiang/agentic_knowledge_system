#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_summarizer.py
@Function:
    Section 摘要抽取的 LLM 调用封装层。

    对应 splitter/text_splitter.py + table_splitter.py 的角色：
    具体的算法组件，由 Service 层编排调用。封装 LLM 调用细节
    （prompt 构造、重试、降级），不碰 Kafka / DB / 业务编排。

    - summarize_leaf：对单个叶子 section 调 LLM 生成摘要（含重试）
    - rollup_parent：对父 section 做自下而上 rollup（LLM 压缩，
      失败降级为纯拼接，保证可用性）

    设计原则：
    - 单 section 失败不阻断整文档：记录日志、跳过该 section
    - LLM 失败时父 rollup 降级为纯拼接，叶子摘要则直接返回 None
    - 并发由 Service 层通过 semaphore 控制，本层只负责单次调用
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import asyncio
from typing import List, Optional, Tuple

from loguru import logger

from src.index.common_file_extract.extract.models import SectionNode, SectionWithChunks
from src.index.common_file_extract.extract.section_context import (
    build_section_combined_text,
)
from src.index.common_file_extract.extract.section_tree import (
    collect_descendant_chunk_ids,
)
from src.prompts.background.section_summary import (
    build_section_rollup_messages,
    build_section_summary_messages,
)
from src.types.models.section_summary_result import SectionSummaryItem
from src.utils.language_detector import detect_language


class SectionSummarizer:
    """
    Section 摘要 LLM 抽取器。

    由 SectionSummaryService 构造并注入 LLM 客户端；Service 层负责并发
    编排，本类只做单次 LLM 调用 + 重试 + 降级。

    Args:
        llm_client: LLM 客户端（必须实现 agenerate(messages=...)）
        max_retries: LLM 调用失败时的重试次数（1 次正常 + max_retries 次重试）
    """

    def __init__(self, llm_client, max_retries: int = 2) -> None:
        self._llm_client = llm_client
        self._max_retries = max_retries

    # ========== 叶子 section LLM 摘要 ==========

    async def summarize_leaf(
        self,
        section: SectionWithChunks,
        document_id: str,
        knowledge_base_id: Optional[str],
        knowledge_base_name: Optional[str],
        language: str,
        semaphore: asyncio.Semaphore,
    ) -> Optional[SectionSummaryItem]:
        """
        对单个 section 调用 LLM 生成摘要（含重试）。

        Args:
            section: SectionWithChunks
            document_id: 文档 ID
            knowledge_base_id / knowledge_base_name: 知识库归属
            language: 文档级语言（来自 SplitEndMessage.language），作为 section 级
                检测失败时的回退
            semaphore: 并发信号量（由 Service 层掌管）

        Returns:
            SectionSummaryItem 或 None（失败 / 空内容时）
        """
        combined_text = build_section_combined_text(section)
        chunk_count = len(section.chunks)

        # 空内容 section 直接跳过（无 chunk 或全部缺失文本）
        if not combined_text.strip():
            logger.info(
                f"SectionSummary: section 无有效内容跳过: "
                f"section_id={section.section_id}, chunk_count={chunk_count}"
            )
            return None

        # section 级语言：对该 section 的实际正文跑脚本统计检测，比文档级语言更贴近
        # section 真实语种（混合语言文档可区分到 section 级）。检测不到时回退文档级
        # language，再回退 "unknown"。供 Milvus 检索结果与 agent 执行做语言判断。
        # 注意：chunk.language 当前等于文档级语言（split 阶段从 document_language 赋值），
        # 不提供 per-chunk 精度，故不作为优先信号；以 combined_text 实测为准。
        section_language = detect_language(combined_text, fallback=language or "unknown")

        messages = build_section_summary_messages(section.title, combined_text)

        async with semaphore:
            last_error: Optional[str] = None
            for attempt in range(1, self._max_retries + 2):  # 1 次正常 + max_retries 次重试
                try:
                    resp = await self._llm_client.agenerate(messages=messages)
                    summary_text = (resp.content or "").strip()
                    if not summary_text:
                        raise ValueError("LLM 返回空摘要")
                    item = SectionSummaryItem(
                        section_id=section.section_id,
                        document_id=document_id,
                        summary_text=summary_text,
                        chunk_count=chunk_count,
                        chunk_id_list=list(section.chunk_id_list),
                        language=section_language,
                        knowledge_base_id=knowledge_base_id,
                        knowledge_base_name=knowledge_base_name,
                    )
                    logger.info(
                        f"SectionSummary: section 摘要生成成功: "
                        f"section_id={section.section_id}, "
                        f"chunk_count={chunk_count}, language={section_language}, "
                        f"attempt={attempt}"
                    )
                    return item
                except Exception as e:
                    last_error = str(e)
                    logger.warning(
                        f"SectionSummary: section 摘要失败重试: "
                        f"section_id={section.section_id}, attempt={attempt}, error={e}"
                    )
                    if attempt <= self._max_retries:
                        await asyncio.sleep(min(2 ** attempt, 8))

        logger.error(
            f"SectionSummary: section 摘要最终失败（跳过）: "
            f"section_id={section.section_id}, error={last_error}"
        )
        return None

    # ========== 父节点 Rollup ==========

    async def rollup_parent(
        self,
        node: SectionNode,
        document_id: str,
        knowledge_base_id: Optional[str],
        knowledge_base_name: Optional[str],
        language: str,
        semaphore: asyncio.Semaphore,
        own_llm_summary: Optional[str] = None,
    ) -> Optional[SectionSummaryItem]:
        """
        对父 section 做自下而上的 rollup 摘要（含 LLM 压缩 + 失败降级为纯拼接）。

        输入：
        - node.children 中已生成 summary_item 的子节点列表
          （按文档顺序，未成功生成 summary 的子节点会被跳过）
        - own_llm_summary（可选）：混合节点自身 chunk 的 LLM 摘要，作为「引言性质」
          伪子章节最先加入 rollup 输入。用于「自己有 chunk 又有子节点」的情况。

        流程：
        1. 收集子节点 (title, summary_text) 列表；全部为空则返回 None
        2. 调 LLM 压缩生成一段连贯的父摘要
        3. LLM 失败（超重试）→ 降级为纯拼接输出「子标题：子summary\\n\\n…」，
           不阻断整个文档流程

        父节点 chunk_count = 递归合并后代叶子的 chunk_id 总数；
        父节点 language = 对生成的最终摘要跑 detect_language；
        summary_id 与叶子一致自动生成。
        """
        child_summaries: List[Tuple[str, str]] = []
        # 混合节点：自身 chunk 的 LLM 摘要作为「引言」伪子章节，放在最前
        if own_llm_summary and own_llm_summary.strip():
            child_summaries.append(("（本节引言）", own_llm_summary.strip()))
        for child in node.children:
            if child.summary_item is None:
                continue
            child_summaries.append(
                (child.title, child.summary_item.summary_text)
            )

        if not child_summaries:
            logger.info(
                f"SectionSummary: 父 section 无有效子摘要跳过 rollup: "
                f"section_id={node.section_id}, title={node.title!r}"
            )
            return None

        descendant_chunk_ids = collect_descendant_chunk_ids(node)
        chunk_count = len(descendant_chunk_ids)

        messages = build_section_rollup_messages(node.title, child_summaries)

        summary_text: Optional[str] = None
        async with semaphore:
            last_error: Optional[str] = None
            for attempt in range(1, self._max_retries + 2):
                try:
                    resp = await self._llm_client.agenerate(messages=messages)
                    text = (resp.content or "").strip()
                    if not text:
                        raise ValueError("LLM 返回空 rollup 摘要")
                    summary_text = text
                    break
                except Exception as e:
                    last_error = str(e)
                    logger.warning(
                        f"SectionSummary: 父 section rollup 失败重试: "
                        f"section_id={node.section_id}, attempt={attempt}, error={e}"
                    )
                    if attempt <= self._max_retries:
                        await asyncio.sleep(min(2 ** attempt, 8))

        # LLM 全部失败 → 降级为纯拼接，保证父节点仍有 summary（可用性优先）
        if summary_text is None:
            logger.error(
                f"SectionSummary: 父 section rollup LLM 全部失败，降级为纯拼接: "
                f"section_id={node.section_id}, error={last_error}"
            )
            summary_text = "\n\n".join(
                f"{(t or '（无标题）').strip()}：{s.strip()}"
                for t, s in child_summaries
                if s and s.strip()
            )
            if not summary_text:
                # 极端兜底：无任何可用文本
                return None

        summary_language = detect_language(summary_text, fallback=language or "unknown")

        item = SectionSummaryItem(
            section_id=node.section_id,
            document_id=document_id,
            summary_text=summary_text,
            chunk_count=chunk_count,
            chunk_id_list=list(descendant_chunk_ids),
            language=summary_language,
            parent_section_id=node.parent.section_id if node.parent else None,
            is_leaf=False,
            knowledge_base_id=knowledge_base_id,
            knowledge_base_name=knowledge_base_name,
        )
        logger.info(
            f"SectionSummary: 父 section rollup 完成: "
            f"section_id={node.section_id}, title={node.title!r}, "
            f"child_summaries={len(child_summaries)}, chunk_count={chunk_count}, "
            f"language={summary_language}"
        )
        return item
