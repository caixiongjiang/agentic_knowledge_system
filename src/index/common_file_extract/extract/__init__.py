#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Section / File 摘要抽取模块

提供两阶段摘要抽取的核心功能（对应 splitter 模块的角色）：
- Section 摘要（section_summary）：每个 section 一份摘要 + 父节点 rollup
- File 摘要（file_summary）：基于 section 摘要汇总生成文件级摘要

由 Service 层（SectionSummaryService / FileSummaryService）编排调用，
本模块不碰 Kafka / DB / 业务编排。
"""

# ========== Section 摘要 ==========
from src.index.common_file_extract.extract.models import SectionNode, SectionWithChunks
from src.index.common_file_extract.extract.section_context import (
    build_section_combined_text,
    build_sections_from_payload,
)
from src.index.common_file_extract.extract.section_summarizer import SectionSummarizer
from src.index.common_file_extract.extract.section_tree import (
    build_section_tree,
    collect_descendant_chunk_ids,
    post_order,
)

# ========== File 摘要 ==========
from src.index.common_file_extract.extract.file_summary_context import (
    SectionSummaryInput,
    aggregate_chunk_count,
    build_section_summaries_from_payload,
)
from src.index.common_file_extract.extract.file_summary_summarizer import FileSummarizer

# ========== Atomic QA 抽取（v1.1 TextAnalyzer） ==========
from src.index.common_file_extract.extract.models import QAChunk, QASection
from src.index.common_file_extract.extract.qa_context import (
    build_qa_batch_text,
    build_qa_sections_from_db_data,
    split_into_batches,
)
from src.index.common_file_extract.extract.qa_summarizer import QASummarizer

__all__ = [
    # Section 摘要
    "SectionWithChunks",
    "SectionNode",
    "build_sections_from_payload",
    "build_section_combined_text",
    "build_section_tree",
    "post_order",
    "collect_descendant_chunk_ids",
    "SectionSummarizer",
    # File 摘要
    "SectionSummaryInput",
    "build_section_summaries_from_payload",
    "aggregate_chunk_count",
    "FileSummarizer",
    # Atomic QA
    "QAChunk",
    "QASection",
    "build_qa_sections_from_db_data",
    "build_qa_batch_text",
    "split_into_batches",
    "QASummarizer",
]
