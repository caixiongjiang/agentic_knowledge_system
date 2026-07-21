#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : text_analyzer_service.py
@Function:
    文本分析（atomic_qa 抽取）Service（业务编排层，v1.1 section 级抽取）。

    对应 file_summary_service.py 的角色：编排 extract 层组件 + 读 DB 取数。
    核心抽取逻辑（[Cn] 占位符 prompt、分批、JSON 解析、chunk_map 溯源）
    已下沉到 src/index/common_file_extract/extract/，本类只做：
    - 配置加载（components.json 的 text_analyzer 段）
    - LLM 客户端懒加载
    - DB + Message 混合取数（section/chunk 读 DB，file_summary 读消息体）
    - 主编排：DB 取数 → context → 跨 section 并发调 summarizer → 聚合结果

    设计原则（v1.1 决策）：
    - **混合取数**：section 正文 + chunk 列表读 DB（split→summary→file_summary
      串行链路末端，section/chunk 早已稳定入库，无竞态）；file_summary 读
      SummaryEndMessage 消息体（file_summary 刚发出，其自身落库走异步 Consumer，
      进度不保证先于本 Worker）。这是有意的边界突破，不是模式回归。
    - Service 不触碰 Kafka，仅返回 TextAnalyzerResult DTO。
    - 跨 section 并发（semaphore），单 section 内批次串行。
@Modify History:
    2026/07/14 - 初版（落实 TextAnalyzer v1.1 section 级 atomic_qa 抽取）

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import asyncio
import math
from typing import Any, Dict, List, Optional

from loguru import logger

from src.db.mongodb.repositories import (
    chunk_data_repository,
    section_data_repository,
)
from src.db.mysql.connection.factory import get_mysql_manager
from src.db.mysql.repositories.base.section_document_repo import section_document_repo
from src.index.common_file_extract.extract import (
    QASummarizer,
    build_qa_sections_from_db_data,
)
from src.types.models.text_analyzer_result import AtomicQAItem, TextAnalyzerResult
from src.utils.component_config_manager import get_component_config_manager


class TextAnalyzerService:
    """文本分析（atomic_qa 抽取）服务（编排层，DB+Message 混合取数 + LLM 调用）。"""

    COMPONENT_NAME = "text_analyzer"

    def __init__(self) -> None:
        self._config_manager = get_component_config_manager()
        cfg = self._config_manager.get_component_config(self.COMPONENT_NAME)
        self._max_retries: int = int(cfg.get("max_retries", 2))
        self._max_concurrency: int = int(cfg.get("max_concurrency", 4))
        self._chunk_batch_size: int = int(cfg.get("chunk_batch_size", 6))
        self._llm_client = None  # 懒加载
        self._summarizer: Optional[QASummarizer] = None  # 懒加载

    # ========== 依赖懒加载 ==========

    def _get_llm_client(self):
        """懒加载 LLM 客户端（基于 components.json 的 text_analyzer 配置）。"""
        if self._llm_client is None:
            self._llm_client = (
                self._config_manager.get_llm_client_for_component(self.COMPONENT_NAME)
            )
            logger.info(
                f"TextAnalyzerService LLM 客户端已创建: "
                f"model={self._llm_client.model_name}"
            )
        return self._llm_client

    def _get_summarizer(self) -> QASummarizer:
        """懒加载 QASummarizer（注入 LLM 客户端与抽取配置）。"""
        if self._summarizer is None:
            self._summarizer = QASummarizer(
                llm_client=self._get_llm_client(),
                max_retries=self._max_retries,
                chunk_batch_size=self._chunk_batch_size,
            )
        return self._summarizer

    # ========== DB + Message 混合取数 ==========

    def _load_section_ids(self, document_id: str) -> List[str]:
        """从 MySQL section_document 关系表取该文档所有 section_id。"""
        manager = get_mysql_manager()
        with manager.get_session() as session:
            rows = section_document_repo.get_by_document_id(session, document_id)
        section_ids = [r.section_id for r in rows if r.section_id]
        logger.info(
            f"TextAnalyzer: DB 取 section_ids: document_id={document_id}, "
            f"count={len(section_ids)}"
        )
        return section_ids

    def _load_leaf_section_ids(self, document_id: str) -> List[str]:
        """
        从 MySQL section_document 取该文档所有叶子 section（is_leaf=True）的 section_id。

        v1.1（2026/07/17）：is_leaf 已由 Mongo section_data 迁到 MySQL section_document，
        叶子过滤在 SQL 层完成（走 idx_doc_leaf 索引），减少 Mongo 取数范围。
        """
        manager = get_mysql_manager()
        with manager.get_session() as session:
            rows = section_document_repo.get_leaf_section_ids_by_document_id(
                session, document_id,
            )
        logger.info(
            f"TextAnalyzer: DB 取叶子 section_ids: document_id={document_id}, "
            f"count={len(rows)}"
        )
        return rows

    async def _load_section_docs(
        self, section_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        从 Mongo section_data 取 section 标题 + 有序 chunk_id_list。

        v1.1：is_leaf 已迁到 MySQL section_document，本方法不再返回 is_leaf
        （叶子过滤由调用方在 SQL 层完成）。返回 dict 列表：{section_id, text, chunk_id_list}
        """
        if not section_ids:
            return []
        sections = await section_data_repository.get_by_ids(section_ids)
        section_docs: List[Dict[str, Any]] = []
        for s in sections:
            section_docs.append({
                "section_id": s.id,
                "text": s.text or "",
                "chunk_id_list": list(s.chunk_id_list or []),
            })
        return section_docs

    async def _load_chunk_docs(
        self, chunk_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        从 Mongo chunk_data 取 chunk 检索正文（search_text）。

        返回 dict 列表：{chunk_id, search_text, type}
        """
        if not chunk_ids:
            return []
        chunks = await chunk_data_repository.get_by_ids(chunk_ids)
        chunk_docs: List[Dict[str, Any]] = []
        for c in chunks:
            chunk_docs.append({
                "chunk_id": c.id,
                "search_text": c.search_text or "",
                "type": c.chunk_type or "text",
            })
        return chunk_docs

    @staticmethod
    def _collect_chunk_ids(section_docs: List[Dict[str, Any]]) -> List[str]:
        """从 section_docs 收集去重的 chunk_id 列表。"""
        seen = set()
        chunk_ids: List[str] = []
        for s in section_docs:
            for cid in (s.get("chunk_id_list") or []):
                if cid and cid not in seen:
                    chunk_ids.append(cid)
                    seen.add(cid)
        return chunk_ids

    # ========== 主编排 ==========

    async def analyze_document(
        self,
        document_id: str,
        file_summary: str,
        language: str = "unknown",
        knowledge_base_id: Optional[str] = None,
        knowledge_base_name: Optional[str] = None,
    ) -> TextAnalyzerResult:
        """
        编排整文档的 section 级 atomic_qa 抽取。

        流程：
        1. DB 取数：section_document → 全量 section_ids + 叶子 section_ids（is_leaf=True）
           → section_data（title + chunk_id_list）→ chunk_data（search_text）
        2. build_qa_sections_from_db_data：构造 QASection 列表（仅叶子 section）
        3. 跨 section 并发（semaphore）调 QASummarizer.extract_section_qa
           （单 section 内分批串行，[Cn] 占位符 + chunk_map 溯源）
        4. 聚合 AtomicQAItem，统计 section_count / llm_call_count
        5. 包装成 TextAnalyzerResult 返回

        Args:
            document_id: 文档 ID
            file_summary: 文档全局摘要（来自 SummaryEndMessage 消息体，主题锚点）
            language: 文档级语言（来自 SummaryEndMessage）
            knowledge_base_id / knowledge_base_name: 知识库归属

        Returns:
            TextAnalyzerResult（items 为空表示无 QA 产出）
        """
        # Step 1: DB 取数（混合取数：section/chunk 读 DB，file_summary 走消息体）
        # v1.1：叶子过滤在 MySQL 层完成（is_leaf 已迁到 section_document，走 idx_doc_leaf 索引）。
        all_section_ids = self._load_section_ids(document_id)
        if not all_section_ids:
            logger.warning(
                f"TextAnalyzer: 文档无 section 关联，返回空结果: "
                f"document_id={document_id}"
            )
            return self._empty_result(
                document_id, knowledge_base_id, knowledge_base_name
            )

        leaf_section_ids = self._load_leaf_section_ids(document_id)
        skipped_non_leaf = len(all_section_ids) - len(leaf_section_ids)
        if skipped_non_leaf:
            logger.info(
                f"TextAnalyzer: 跳过 {skipped_non_leaf} 个非叶子 section（rollup，避免重复抽取）: "
                f"document_id={document_id}"
            )
        if not leaf_section_ids:
            logger.warning(
                f"TextAnalyzer: 文档无可 QA 抽取的叶子 section，返回空结果: "
                f"document_id={document_id}"
            )
            return self._empty_result(
                document_id, knowledge_base_id, knowledge_base_name
            )

        section_docs = await self._load_section_docs(leaf_section_ids)

        chunk_ids = self._collect_chunk_ids(section_docs)
        chunk_docs = await self._load_chunk_docs(chunk_ids)

        # Step 2: 构造 QA 上下文
        qa_sections = build_qa_sections_from_db_data(section_docs, chunk_docs)
        if not qa_sections:
            logger.warning(
                f"TextAnalyzer: 叶子 section 无 chunk 文本，返回空结果: "
                f"document_id={document_id}"
            )
            return self._empty_result(
                document_id, knowledge_base_id, knowledge_base_name
            )

        # Step 3: 跨 section 并发抽取
        summarizer = self._get_summarizer()
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def _run_one(section):
            return await summarizer.extract_section_qa(
                section=section,
                document_id=document_id,
                file_summary=file_summary,
                knowledge_base_id=knowledge_base_id,
                knowledge_base_name=knowledge_base_name,
                semaphore=semaphore,
            )

        section_results: List[List[AtomicQAItem]] = await asyncio.gather(
            *[_run_one(qs) for qs in qa_sections],
            return_exceptions=True,
        )

        # Step 4: 聚合（单 section 异常不阻断整文档）
        all_items: List[AtomicQAItem] = []
        for qs, res in zip(qa_sections, section_results):
            if isinstance(res, Exception):
                logger.error(
                    f"TextAnalyzer: section 抽取异常（跳过）: "
                    f"section_id={qs.section_id}, error={res}"
                )
                continue
            all_items.extend(res)

        # 统计：计划 LLM 调用次数 = 各 section 批次数之和（ceil(chunk_count/N)）
        llm_call_count = sum(
            math.ceil(qs.chunk_count / self._chunk_batch_size)
            for qs in qa_sections
        )

        llm_model = self._get_llm_client().model_name
        token_usage: Dict[str, int] = {"input": 0, "output": 0, "total": 0}

        logger.info(
            f"TextAnalyzer: 文档抽取完成 document_id={document_id}, "
            f"sections={len(qa_sections)}, llm_calls={llm_call_count}, "
            f"qa={len(all_items)}"
        )

        return TextAnalyzerResult(
            document_id=document_id,
            items=all_items,
            llm_model=llm_model,
            token_usage=token_usage,
            knowledge_base_id=knowledge_base_id,
            knowledge_base_name=knowledge_base_name,
            section_count=len(qa_sections),
            llm_call_count=llm_call_count,
        )

    def _empty_result(
        self,
        document_id: str,
        knowledge_base_id: Optional[str],
        knowledge_base_name: Optional[str],
    ) -> TextAnalyzerResult:
        llm_model = ""
        try:
            llm_model = self._get_llm_client().model_name
        except Exception:
            pass
        return TextAnalyzerResult(
            document_id=document_id,
            items=[],
            llm_model=llm_model,
            token_usage={"input": 0, "output": 0, "total": 0},
            knowledge_base_id=knowledge_base_id,
            knowledge_base_name=knowledge_base_name,
            section_count=0,
            llm_call_count=0,
        )
