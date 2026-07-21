#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : qa_summarizer.py
@Function:
    Atomic QA 抽取的 LLM 调用封装层（v1.1 section 级 + chunk_map 溯源）。

    对应 section_summarizer.py 的角色：具体的算法组件，由 Service 层编排调用。
    封装 LLM 调用细节（prompt 构造、分批、重试、JSON 解析、占位符回填），
    不碰 Kafka / DB / 业务编排。

    - extract_section_qa：对单个 section 调 LLM 抽取 atomic_qa。
      超长 section（chunk 数 > N）自动分批，每批一次 LLM 调用；批次内
      chunk 用 [Cn] 占位符，LLM 在 source_chunks 里引用 [Cn]，本层后处理
      替换为真实 chunk_id（chunk_map 溯源），实现 chunk 级精准定位。

    设计原则：
    - 单批失败不阻断整 section：记录日志、跳过该批，保留已成功批次
    - LLM 输出 JSON 数组，本层解析 + 容错（解析失败丢弃该批，不臆造）
    - 并发由 Service 层通过 semaphore 控制，本层只负责单 section 的串行分批
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from loguru import logger

from src.index.common_file_extract.extract.models import QASection
from src.index.common_file_extract.extract.qa_context import (
    build_qa_batch_text,
    split_into_batches,
)
from src.prompts.background.text_analyzer import build_atomic_qa_messages
from src.types.models.text_analyzer_result import AtomicQAItem


# QA 类型白名单（与 prompt SYSTEM_PROMPT 一致；非白名单值回退 factual）
_QA_TYPE_WHITESHEET = {"factual", "procedural", "conceptual", "comparative"}

# [Cn] 占位符匹配（C 后跟数字），用于把 LLM 输出的占位符替换为真实 chunk_id
_CHUNK_CODE_PATTERN = re.compile(r"C(\d+)")


class QASummarizer:
    """
    Atomic QA LLM 抽取器（section 级 + 分批 + chunk_map 溯源）。

    由 TextAnalyzerService 构造并注入 LLM 客户端；Service 层负责跨 section
    并发编排，本类只做单 section 的分批 LLM 调用 + 重试 + JSON 解析 + 占位符回填。

    Args:
        llm_client: LLM 客户端（必须实现 agenerate(messages=...)）
        max_retries: 单批 LLM 调用失败时的重试次数（1 次正常 + max_retries 次重试）
        chunk_batch_size: 单次 LLM 调用覆盖的 chunk 数 N（默认 6）
    """

    def __init__(
        self,
        llm_client,
        max_retries: int = 2,
        chunk_batch_size: int = 6,
    ) -> None:
        self._llm_client = llm_client
        self._max_retries = max_retries
        self._chunk_batch_size = chunk_batch_size

    async def extract_section_qa(
        self,
        section: QASection,
        document_id: str,
        file_summary: str,
        knowledge_base_id: Optional[str],
        knowledge_base_name: Optional[str],
        semaphore: asyncio.Semaphore,
    ) -> List[AtomicQAItem]:
        """
        对单个 section 分批调 LLM 抽取 atomic_qa。

        流程：
        1. 按 chunk_batch_size 将 section.chunks 切成多个批次
        2. 每批构造 [Cn] 占位符文本 → 调 LLM → 解析 JSON 数组
        3. 把每条 QA 的 source_chunks 占位符 ([Cn]) 替换为真实 chunk_id
        4. 单批失败跳过（不阻断整 section），返回已成功批次的所有 QA
        5. 无 per-section QA 总数上限：超长 section 全量分批抽取，不提前停止

        Args:
            section: QASection
            document_id: 文档 ID
            file_summary: 文档全局摘要（主题锚点，来自消息体）
            knowledge_base_id / knowledge_base_name: 知识库归属
            semaphore: 并发信号量（由 Service 层掌管，跨 section 并发；
                单 section 内批次串行，避免同 section 多批打爆上下文）

        Returns:
            AtomicQAItem 列表（可能为空，表示该 section 无 QA 产出）
        """
        batches = split_into_batches(section.chunk_count, self._chunk_batch_size)
        if not batches:
            return []

        if len(batches) > 1:
            logger.debug(
                f"TextAnalyzer: section chunk 数超过单批容量，拆分多批抽取: "
                f"section_id={section.section_id}, "
                f"chunk_count={section.chunk_count}, "
                f"batch_size={self._chunk_batch_size}, batches={len(batches)}"
            )

        items: List[AtomicQAItem] = []
        async with semaphore:
            for start_index, _n in batches:
                batch_text, chunk_code_map = build_qa_batch_text(
                    section, start_index, self._chunk_batch_size
                )
                if not batch_text:
                    continue

                # 单批 QA 不超过 chunk 数（粗略上界，避免 LLM 臆造过多 QA）
                batch_max_qa = self._chunk_batch_size

                batch_items = await self._extract_one_batch(
                    section=section,
                    batch_text=batch_text,
                    chunk_code_map=chunk_code_map,
                    document_id=document_id,
                    file_summary=file_summary,
                    knowledge_base_id=knowledge_base_id,
                    knowledge_base_name=knowledge_base_name,
                    max_qa=batch_max_qa,
                    start_index=start_index,
                )
                items.extend(batch_items)

        logger.info(
            f"TextAnalyzer: section QA 抽取完成: "
            f"section_id={section.section_id}, "
            f"chunks={section.chunk_count}, batches={len(batches)}, "
            f"qa={len(items)}"
        )
        return items

    async def _extract_one_batch(
        self,
        section: QASection,
        batch_text: str,
        chunk_code_map: Dict[str, str],
        document_id: str,
        file_summary: str,
        knowledge_base_id: Optional[str],
        knowledge_base_name: Optional[str],
        max_qa: int,
        start_index: int,
    ) -> List[AtomicQAItem]:
        """对单个批次调 LLM（含重试）+ 解析 JSON + 占位符回填。"""
        messages = build_atomic_qa_messages(
            section_title=section.title,
            batch_chunks_text=batch_text,
            file_summary=file_summary,
            max_qa=max_qa,
        )

        last_error: Optional[str] = None
        for attempt in range(1, self._max_retries + 2):  # 1 次正常 + max_retries 次重试
            try:
                resp = await self._llm_client.agenerate(messages=messages)
                content = (resp.content or "").strip()
                if not content:
                    raise ValueError("LLM 返回空内容")
                qa_raw_list = self._parse_qa_json(content)
                if qa_raw_list is None:
                    raise ValueError("LLM 输出 JSON 解析失败")
                items = self._build_qa_items(
                    qa_raw_list=qa_raw_list,
                    section_id=section.section_id,
                    document_id=document_id,
                    chunk_code_map=chunk_code_map,
                    knowledge_base_id=knowledge_base_id,
                    knowledge_base_name=knowledge_base_name,
                )
                logger.debug(
                    f"TextAnalyzer: 批次抽取成功: "
                    f"section_id={section.section_id}, "
                    f"start={start_index}, qa={len(items)}, attempt={attempt}"
                )
                return items
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"TextAnalyzer: 批次抽取失败重试: "
                    f"section_id={section.section_id}, start={start_index}, "
                    f"attempt={attempt}, error={e}"
                )
                if attempt <= self._max_retries:
                    await asyncio.sleep(min(2 ** attempt, 8))

        logger.error(
            f"TextAnalyzer: 批次抽取最终失败（跳过该批）: "
            f"section_id={section.section_id}, start={start_index}, "
            f"error={last_error}"
        )
        return []

    @staticmethod
    def _parse_qa_json(content: str) -> Optional[List[Dict[str, Any]]]:
        """
        解析 LLM 输出的 JSON 数组。

        容错策略：
        1. 尝试直接 json.loads
        2. 失败则提取第一个 [...] 块再解析（兼容 markdown 代码块包裹）
        3. 仍失败返回 None（上层重试）

        Returns:
            QA dict 列表 或 None
        """
        # 尝试 1：直接解析
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "qa" in data:
                # 兼容 LLM 偶尔输出 {"qa": [...]}
                inner = data.get("qa")
                if isinstance(inner, list):
                    return inner
        except json.JSONDecodeError:
            pass

        # 尝试 2：提取第一个 [...] 块
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(content[start:end + 1])
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

        return None

    def _build_qa_items(
        self,
        qa_raw_list: List[Dict[str, Any]],
        section_id: str,
        document_id: str,
        chunk_code_map: Dict[str, str],
        knowledge_base_id: Optional[str],
        knowledge_base_name: Optional[str],
    ) -> List[AtomicQAItem]:
        """把 LLM 输出的 raw QA dict 列表转成 AtomicQAItem（含占位符回填）。"""
        items: List[AtomicQAItem] = []
        for raw in qa_raw_list:
            question = (str(raw.get("question") or "").strip())
            answer = (str(raw.get("answer") or "").strip())
            if not question or not answer:
                continue
            source_chunks_raw = raw.get("source_chunks") or []
            if isinstance(source_chunks_raw, str):
                source_chunks_raw = [source_chunks_raw]
            source_chunk_ids = self._resolve_chunk_codes(
                source_chunks_raw, chunk_code_map
            )
            qa_type = str(raw.get("qa_type") or "factual").strip().lower()
            if qa_type not in _QA_TYPE_WHITESHEET:
                qa_type = "factual"
            try:
                relevance = float(raw.get("relevance") or 0.8)
                relevance = max(0.0, min(1.0, relevance))
            except (TypeError, ValueError):
                relevance = 0.8

            items.append(AtomicQAItem(
                section_id=section_id,
                document_id=document_id,
                question=question,
                answer=answer,
                source_chunk_ids=source_chunk_ids,
                qa_type=qa_type,
                relevance=relevance,
                knowledge_base_id=knowledge_base_id,
                knowledge_base_name=knowledge_base_name,
            ))
        return items

    @staticmethod
    def _resolve_chunk_codes(
        source_chunks_raw: List[Any],
        chunk_code_map: Dict[str, str],
    ) -> List[str]:
        """
        把 LLM 输出的 source_chunks 占位符（[Cn] 或 Cn）替换为真实 chunk_id。

        - 仅保留能匹配到 chunk_code_map 的代号（丢弃 LLM 臆造的无效引用）
        - 去重保序
        - 若全部无法匹配，回退为本批全部 chunk_id（保守溯源，避免空 source）
        """
        resolved: List[str] = []
        seen = set()
        for raw in source_chunks_raw:
            token = str(raw or "").strip()
            if not token:
                continue
            # 提取 Cn 形式（兼容 "[C1]" / "C1" / "片段C1" 等）
            m = _CHUNK_CODE_PATTERN.search(token)
            code = f"C{m.group(1)}" if m else token
            chunk_id = chunk_code_map.get(code)
            if chunk_id and chunk_id not in seen:
                resolved.append(chunk_id)
                seen.add(chunk_id)

        if not resolved:
            # 回退：本批全部 chunk（保守溯源，保证 QA 有来源）
            for chunk_id in chunk_code_map.values():
                if chunk_id not in seen:
                    resolved.append(chunk_id)
                    seen.add(chunk_id)
        return resolved
