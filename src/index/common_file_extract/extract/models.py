#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : models.py
@Function:
    Section 摘要抽取阶段的内部数据结构（pydantic 版）。

    对应 splitter/models.py 的角色：定义 extract 层用到的
    内存聚合体与树节点，供 section_context / section_tree /
    section_summarizer 共享。

    - SectionWithChunks：单个 section 及其归属 chunk 的内存聚合体
      （来自 SplitEndMessage payload，不读数据库）
    - SectionNode：section 树节点，由 section_tree.build_section_tree
      从扁平 sections 构造得到；后序遍历用于叶子 LLM 摘要与父节点 rollup

    采用 pydantic v2 BaseModel（与 SectionSummaryItem / SplitConfig
    等周边模型一致），便于字段校验与序列化调试。SectionNode 存在
    parent / children 自引用，模块末尾通过 model_rebuild() 解析前向引用。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.types.models.section_summary_result import SectionSummaryItem
from src.utils.section_numbering import NumberingInfo


class SectionWithChunks(BaseModel):
    """单个 section 及其归属 chunk 的内存聚合体（来自消息 payload）。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    section_id: str
    title: str = ""
    level: int = 0
    page_index: Optional[int] = None
    # 该 section 下的 chunk payload 列表（顺序与 section.chunk_id_list 一致）
    chunks: List[Dict[str, Any]] = Field(default_factory=list)
    # split 阶段直属的 chunk_id_list（叶子摘要 & rollup 合并溯源用）
    chunk_id_list: List[str] = Field(default_factory=list)


class SectionNode(BaseModel):
    """
    Section 树节点。

    由 build_section_tree() 从扁平 sections 列表构造得到，
    编号解析出的 level 与父子关系挂在这里；后序遍历用于叶子 LLM 摘要
    与父节点 rollup。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    section: SectionWithChunks
    numbering: Optional[NumberingInfo] = None
    # 由编号推断得到的层级；无编号时回退 section.level（MinerU 提供）
    inferred_level: int = 1
    parent: Optional["SectionNode"] = None
    children: List["SectionNode"] = Field(default_factory=list)
    # 该节点摘要生成结果（叶子经 LLM、父节点经 rollup 后填入；失败/跳过为 None）
    summary_item: Optional[SectionSummaryItem] = None

    @property
    def section_id(self) -> str:
        return self.section.section_id

    @property
    def title(self) -> str:
        return self.section.title

    def is_structural_leaf(self) -> bool:
        """结构叶子：无子节点。"""
        return not self.children

    def has_own_chunks(self) -> bool:
        """是否有自身直属 chunk（不含后代）。"""
        return bool(self.section.chunk_id_list)

    def should_llm_summarize(self) -> bool:
        """是否需要走叶子 LLM 摘要：只要有自身直属 chunk 就走（含混合节点）。"""
        return self.has_own_chunks()

    def should_rollup(self) -> bool:
        """是否需要走父 rollup：只要有子节点就走。"""
        return bool(self.children)


# 解析 SectionNode 内 parent / children 的自引用前向引用
SectionNode.model_rebuild()


# ========== Atomic QA 抽取（v1.1 TextAnalyzer）==========


class QAChunk(BaseModel):
    """单个 chunk 的 QA 抽取输入项（来自 DB，纯内存结构）。"""

    chunk_id: str
    text: str = ""
    chunk_type: str = "text"


class QASection(BaseModel):
    """
    单个 section 的 QA 抽取输入聚合体（来自 DB 读数）。

    由 qa_context.build_qa_sections_from_db_data 构造：
    - section_id / title：来自 section_data（text 字段即 section 标题/正文）
    - chunks：来自 chunk_data.search_text，按 section_data.chunk_id_list 顺序
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    section_id: str
    title: str = ""
    chunks: List[QAChunk] = Field(default_factory=list)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)
