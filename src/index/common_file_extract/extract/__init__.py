#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Section 摘要抽取模块

提供 Section 摘要抽取的核心功能（对应 splitter 模块的角色）：
- 上下文构造（payload → SectionWithChunks + combined_text）
- 树构建与遍历（编号推层级、后序遍历、后代 chunk 收集）
- LLM 抽取封装（叶子摘要 + 父 rollup，含重试/降级）

由 SectionSummaryService（service 层）编排调用，本模块不碰 Kafka / DB /
业务编排。
"""

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

__all__ = [
    "SectionWithChunks",
    "SectionNode",
    "build_sections_from_payload",
    "build_section_combined_text",
    "build_section_tree",
    "post_order",
    "collect_descendant_chunk_ids",
    "SectionSummarizer",
]
