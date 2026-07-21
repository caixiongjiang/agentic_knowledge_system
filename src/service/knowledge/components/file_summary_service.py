#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : file_summary_service.py
@Function:
    文件级摘要抽取 Service（业务编排层，不含 Kafka / DB 读依赖）。

    对应 section_summary_service.py 的角色：编排 extract 层组件，
    不写具体算法。核心抽取逻辑（payload 解析、LLM 汇总、JSON 解析）
    已下沉到 src/index/common_file_extract/extract/，本类只做：
    - 配置加载（components.json 的 file_summary 段）
    - LLM 客户端懒加载
    - 主编排：payload → context → 调 summarizer → 返回 FileSummaryResult

    设计原则：
    - **不读数据库**：输入完全来自 SectionSummaryEndMessage 消息体
      （section_summaries_payload 字段），消除 section_summary 写库异步竞态。
    - 与 SectionSummaryService 一致：Service 不触碰 Kafka，仅返回结果 DTO。
    - 单文档单次 LLM 调用（与 SectionSummary 的多 section 并发不同）。
@Modify History:
    2026/07/09 - 初版（落实两级摘要的第二级，对齐 SectionSummary 分层模式）

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Dict, List, Optional

from loguru import logger

from src.index.common_file_extract.extract import (
    FileSummarizer,
    build_section_summaries_from_payload,
)
from src.types.models.file_summary_result import FileSummaryResult
from src.utils.component_config_manager import get_component_config_manager


class FileSummaryService:
    """文件级摘要抽取服务（编排层，纯内存计算 + LLM 调用，无 DB 读）。"""

    COMPONENT_NAME = "file_summary"

    def __init__(self) -> None:
        self._config_manager = get_component_config_manager()
        self._llm_client = None  # 懒加载
        self._summarizer: Optional[FileSummarizer] = None  # 懒加载
        self._max_retries: int = int(
            self._config_manager.get_component_config(self.COMPONENT_NAME).get(
                "max_retries", 3
            )
        )

    # ========== 依赖懒加载 ==========

    def _get_llm_client(self):
        """懒加载 LLM 客户端（基于 components.json 的 file_summary 配置）。"""
        if self._llm_client is None:
            self._llm_client = (
                self._config_manager.get_llm_client_for_component(self.COMPONENT_NAME)
            )
            logger.info(
                f"FileSummaryService LLM 客户端已创建: "
                f"model={self._llm_client.model_name}"
            )
        return self._llm_client

    def _get_summarizer(self) -> FileSummarizer:
        """懒加载 FileSummarizer（注入 LLM 客户端与重试配置）。"""
        if self._summarizer is None:
            self._summarizer = FileSummarizer(
                llm_client=self._get_llm_client(),
                max_retries=self._max_retries,
            )
        return self._summarizer

    # ========== 主编排 ==========

    async def summarize_document(
        self,
        document_id: str,
        section_summaries_payload: List[Dict[str, Any]],
        document_title: str = "",
        language: str = "unknown",
        knowledge_base_id: Optional[str] = None,
        knowledge_base_name: Optional[str] = None,
    ) -> FileSummaryResult:
        """
        编排整文档的文件级摘要抽取。

        输入完全来自 SectionSummaryEndMessage 消息体（section_summaries_payload），
        不读数据库，消除「section_summary 写库异步 → file_summary 读库竞态」问题。

        流程：
        1. build_section_summaries_from_payload：从 payload 构造 SectionSummaryInput 列表
        2. FileSummarizer.summarize_document：调 LLM 汇总 + 解析 JSON 产出
        3. 包装成 FileSummaryResult 返回

        Args:
            document_id: 文档 ID
            section_summaries_payload: SectionSummaryEndMessage.section_summaries_payload，
                各项含 {section_id, summary_id, title, summary_text,
                       is_leaf, parent_section_id, chunk_count, language}
            document_title: 文档标题（可选，从消息体或文件名获取）
            language: 文档级语言（来自 SectionSummaryEndMessage，作为摘要语言检测回退）
            knowledge_base_id / knowledge_base_name: 知识库归属（透传到结果）

        Returns:
            FileSummaryResult（item 为 None 表示无 section 摘要可用或 LLM 失败）
        """
        # Step 1: 从 payload 构造上下文
        section_summaries = build_section_summaries_from_payload(
            section_summaries_payload
        )

        if not section_summaries:
            logger.warning(
                f"FileSummary: 消息 payload 无有效 section 摘要，返回空结果: "
                f"document_id={document_id}"
            )
            return FileSummaryResult(
                document_id=document_id,
                item=None,
                llm_model="",
                knowledge_base_id=knowledge_base_id,
                knowledge_base_name=knowledge_base_name,
            )

        # Step 2: 调 LLM 汇总
        summarizer = self._get_summarizer()
        item = await summarizer.summarize_document(
            section_summaries=section_summaries,
            document_id=document_id,
            document_title=document_title,
            knowledge_base_id=knowledge_base_id,
            knowledge_base_name=knowledge_base_name,
            language=language,
        )

        # Step 3: 包装结果
        llm_model = self._get_llm_client().model_name
        token_usage: Dict[str, int] = {"input": 0, "output": 0, "total": 0}

        if item is None:
            logger.warning(
                f"FileSummary: 文件摘要生成失败（LLM 全部重试失败）: "
                f"document_id={document_id}"
            )
        else:
            logger.info(
                f"FileSummary: 文档抽取完成 document_id={document_id}, "
                f"section_count={item.section_count}, "
                f"chunk_count={item.chunk_count}, "
                f"document_type={item.document_type}"
            )

        return FileSummaryResult(
            document_id=document_id,
            item=item,
            llm_model=llm_model,
            token_usage=token_usage,
            knowledge_base_id=knowledge_base_id,
            knowledge_base_name=knowledge_base_name,
        )
