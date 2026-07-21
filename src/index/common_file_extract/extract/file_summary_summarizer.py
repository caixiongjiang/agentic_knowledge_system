#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : file_summary_summarizer.py
@Function:
    文件级摘要的 LLM 调用封装层。

    对应 section_summarizer.py 的角色：具体的算法组件，
    由 Service 层编排调用。封装 LLM 调用细节（prompt 构造、
    重试、JSON 解析），不碰 Kafka / DB / 业务编排。

    - summarize_document：对整文档的 section 摘要列表调 LLM 汇总，
      产出 FileSummaryItem（含 summary_text / keywords / topics / document_type）

    设计原则：
    - LLM 输出 JSON，本层负责解析 + 容错（解析失败时降级为纯摘要文本）
    - 单次调用失败重试 max_retries 次
    - 最终失败返回 None，由 Service 层决定如何处理
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import asyncio
import json
from typing import List, Optional, Tuple

from loguru import logger

from src.index.common_file_extract.extract.file_summary_context import (
    SectionSummaryInput,
    aggregate_chunk_count,
)
from src.prompts.background.file_summary import build_file_summary_messages
from src.types.models.file_summary_result import FileSummaryItem
from src.utils.language_detector import detect_language


class FileSummarizer:
    """
    文件级摘要 LLM 抽取器。

    由 FileSummaryService 构造并注入 LLM 客户端；Service 层负责编排，
    本类只做单次 LLM 调用 + 重试 + JSON 解析。

    Args:
        llm_client: LLM 客户端（必须实现 agenerate(messages=...)）
        max_retries: LLM 调用失败时的重试次数（1 次正常 + max_retries 次重试）
    """

    def __init__(self, llm_client, max_retries: int = 3) -> None:
        self._llm_client = llm_client
        self._max_retries = max_retries

    async def summarize_document(
        self,
        section_summaries: List[SectionSummaryInput],
        document_id: str,
        document_title: str = "",
        knowledge_base_id: Optional[str] = None,
        knowledge_base_name: Optional[str] = None,
        language: str = "unknown",
    ) -> Optional[FileSummaryItem]:
        """
        对整文档的 section 摘要列表调 LLM 汇总，生成文件级摘要。

        Args:
            section_summaries: SectionSummaryInput 列表（已过滤空摘要、按树顺序排序）
            document_id: 文档 ID
            document_title: 文档标题（可选）
            knowledge_base_id / knowledge_base_name: 知识库归属
            language: 文档级语言（作为 section 级检测失败时的回退）

        Returns:
            FileSummaryItem 或 None（失败 / 空输入时）
        """
        if not section_summaries:
            logger.info(
                f"FileSummary: 无 section 摘要可用，跳过 file 摘要生成: "
                f"document_id={document_id}"
            )
            return None

        # 拼装 LLM 输入：(title, summary_text) 列表
        section_pairs: List[Tuple[str, str]] = [
            (s.title, s.summary_text) for s in section_summaries
        ]
        messages = build_file_summary_messages(section_pairs, document_title)

        last_error: Optional[str] = None
        for attempt in range(1, self._max_retries + 2):  # 1 次正常 + max_retries 次重试
            try:
                resp = await self._llm_client.agenerate(messages=messages)
                content = (resp.content or "").strip()
                if not content:
                    raise ValueError("LLM 返回空内容")

                summary_text, keywords, topics, document_type = self._parse_llm_output(content)

                if not summary_text:
                    raise ValueError("LLM 输出 JSON 缺少 summary 字段")

                # 语言检测：对最终摘要正文跑 detect_language
                summary_language = detect_language(summary_text, fallback=language or "unknown")

                chunk_count = aggregate_chunk_count(section_summaries)

                item = FileSummaryItem(
                    document_id=document_id,
                    summary_text=summary_text,
                    keywords=keywords,
                    topics=topics,
                    document_type=document_type,
                    section_count=len(section_summaries),
                    chunk_count=chunk_count,
                    language=summary_language,
                    knowledge_base_id=knowledge_base_id,
                    knowledge_base_name=knowledge_base_name,
                )
                logger.info(
                    f"FileSummary: 文件摘要生成成功: "
                    f"document_id={document_id}, "
                    f"section_count={len(section_summaries)}, "
                    f"chunk_count={chunk_count}, language={summary_language}, "
                    f"document_type={document_type}, "
                    f"keywords={len(keywords)}, topics={len(topics)}, "
                    f"attempt={attempt}"
                )
                return item

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"FileSummary: 文件摘要失败重试: "
                    f"document_id={document_id}, attempt={attempt}, error={e}"
                )
                if attempt <= self._max_retries:
                    await asyncio.sleep(min(2 ** attempt, 8))

        logger.error(
            f"FileSummary: 文件摘要最终失败（返回 None）: "
            f"document_id={document_id}, error={last_error}"
        )
        return None

    @staticmethod
    def _parse_llm_output(content: str) -> Tuple[str, List[str], List[str], Optional[str]]:
        """
        解析 LLM 输出的 JSON，提取 summary / keywords / topics / document_type。

        容错策略：
        1. 尝试直接 json.loads
        2. 失败则尝试提取第一个 {...} 块再解析（LLM 可能包了 markdown 代码块）
        3. 仍失败则把整个 content 当作 summary 文本，keywords/topics/type 留空

        Returns:
            (summary_text, keywords, topics, document_type)
        """
        # 尝试 1：直接解析
        try:
            data = json.loads(content)
            return FileSummarizer._extract_fields(data)
        except json.JSONDecodeError:
            pass

        # 尝试 2：提取第一个 {... } 块（兼容 ```json ... ``` 包裹）
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(content[start:end + 1])
                return FileSummarizer._extract_fields(data)
            except json.JSONDecodeError:
                pass

        # 尝试 3：降级，整个 content 当作 summary
        logger.warning(
            f"FileSummary: LLM 输出 JSON 解析失败，降级为纯摘要文本: "
            f"content_prefix={content[:80]!r}"
        )
        return content.strip(), [], [], None

    @staticmethod
    def _extract_fields(data: dict) -> Tuple[str, List[str], List[str], Optional[str]]:
        """从解析后的 dict 提取四个字段，做类型容错。"""
        summary_text = (data.get("summary") or "").strip()
        keywords_raw = data.get("keywords") or []
        topics_raw = data.get("topics") or []
        document_type = data.get("document_type")

        # 类型容错：keywords/topics 可能是 str（LLM 偶尔输出逗号分隔字符串）
        if isinstance(keywords_raw, str):
            keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        else:
            keywords = [str(k).strip() for k in keywords_raw if k]

        if isinstance(topics_raw, str):
            topics = [t.strip() for t in topics_raw.split(",") if t.strip()]
        else:
            topics = [str(t).strip() for t in topics_raw if t]

        if document_type is not None:
            document_type = str(document_type).strip() or None

        return summary_text, keywords, topics, document_type
