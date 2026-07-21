#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
提取相关消息模型

定义后台提取流程的各阶段消息：
- SectionSummaryEndMessage: Section 摘要完成
- SummaryEndMessage: 文件摘要完成
- GraphEndMessage: 知识图谱抽取完成

注: ImageEndMessage 已移除；图片理解不再作为后台 pipeline 一环，
    改为 agent 需要时临时调用（见 src/service/chat/image_chunk_reader_service.py）。
"""

from typing import Dict, List, Optional, Any
from pydantic import Field

from src.types.messages.base import BaseMessage


class SectionSummaryEndMessage(BaseMessage):
    """
    Section 摘要完成消息

    文档内所有 section 的摘要生成完成。
    发送到: knowledge_base.section_summary.end
    消费者:
    - FileSummaryWorker（基于 section 摘要 rollup 生成 file_summary）
    - EmbeddingMilvusWriter（section 摘要向量写入 Milvus summary collection）

    设计说明：
    - 仅携带轻量统计，不携带全部摘要文本（避免大消息）；
      下游若需正文，按 document_id 从 MySQL section_summary / MongoDB section_data 读取。
    - 后台阶段消息，不影响前台进度。
    """

    # 所属文档 ID
    document_id: str = Field(
        ...,
        description="所属文档 ID（document-{uuid}）"
    )

    # section 摘要列表（仅统计字段，不含正文；供状态管理器/日志使用）
    section_summaries: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="各 section 摘要统计：{section_id, summary_id, chunk_count, summary_length}"
    )

    # section 摘要完整 payload（含正文，供 FileSummaryWorker 自包含消费，不读库）
    # 每项含：{section_id, summary_id, title, summary_text,
    #         is_leaf, parent_section_id, chunk_count, language}
    section_summaries_payload: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "各 section 摘要完整数据（含 summary_text 正文），供 FileSummaryWorker "
            "自包含消费，消除 section_summary 写库异步竞态。"
            "与 section_summaries（仅统计）并存：后者给状态管理器/日志，"
            "前者给下游 FileSummary。"
        )
    )

    # 文档标题（供 FileSummary 的 LLM prompt 使用，从 SplitEndMessage 透传）
    document_title: str = Field(
        default="",
        description="文档标题（供 FileSummary 的 LLM prompt 使用）"
    )

    # 文档语言（供 FileSummary 的语言检测回退）
    language: str = Field(
        default="unknown",
        description="文档语言（供 FileSummary 的语言检测回退）"
    )

    # 知识库归属（透传给 FileSummary）
    knowledge_base_id: Optional[str] = Field(
        default=None,
        description="知识库 ID"
    )
    knowledge_base_name: Optional[str] = Field(
        default=None,
        description="知识库名称"
    )

    # section 总数
    total_sections: int = Field(
        default=0,
        ge=0,
        description="文档 section 总数"
    )

    # 成功生成摘要的 section 数
    successful_sections: int = Field(
        default=0,
        ge=0,
        description="成功生成摘要的 section 数"
    )

    # 使用的 LLM 模型
    llm_model: str = Field(
        ...,
        description="使用的 LLM 模型"
    )

    # Token 使用统计
    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token 使用统计（input, output, total）"
    )


class SummaryEndMessage(BaseMessage):
    """
    文件摘要完成消息
    
    文件级摘要生成完成。
    发送到: knowledge_base.file_summary.end
    消费者: 
    - TextAnalyzer（后台并行，section 级 atomic_qa 抽取）
    - KGExtractor（后台并行，知识图谱抽取）
    - EmbeddingMilvusWriter（数据库写入摘要向量）
    - MySQLWriter（更新文件元数据）

    溯源字段（document_id / knowledge_base_id / knowledge_base_name / language）
    由 FileSummaryWorker 从 SectionSummaryEndMessage 透传，供下游 TextAnalyzer
    「按 document_id 读 DB 取 section/chunk」、以及写库时带上知识库归属。
    """

    # 所属文档 ID（供 TextAnalyzer 读 DB 取 section/chunk）
    document_id: Optional[str] = Field(
        default=None,
        description="所属文档 ID（document-{uuid}），供下游 TextAnalyzer 读 DB"
    )

    # 知识库归属（透传给下游写库）
    knowledge_base_id: Optional[str] = Field(
        default=None,
        description="知识库 ID"
    )
    knowledge_base_name: Optional[str] = Field(
        default=None,
        description="知识库名称"
    )

    # 文档语言（供 TextAnalyzer prompt 语言适配）
    language: str = Field(
        default="unknown",
        description="文档语言（供 TextAnalyzer prompt 语言适配）"
    )

    # 文件级摘要
    file_summary: str = Field(
        ...,
        min_length=1,
        description="文件级摘要（全局主题锚点，TextAnalyzer 从消息体直取，不读库）"
    )
    
    # 关键词
    keywords: List[str] = Field(
        default_factory=list,
        description="提取的关键词"
    )
    
    # 主题标签
    topics: List[str] = Field(
        default_factory=list,
        description="识别的主题标签"
    )
    
    # 摘要质量评分（0-1）
    summary_quality: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="摘要质量评分"
    )
    
    # 使用的 LLM 模型
    llm_model: str = Field(
        ...,
        description="使用的 LLM 模型"
    )
    
    # Token 使用统计
    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token 使用统计（input, output, total）"
    )
    
    # 文档类型分类
    document_type: Optional[str] = Field(
        default=None,
        description="文档类型分类（如 research_paper, blog, tutorial）"
    )
    
    # 文档难度等级（0-5）
    difficulty_level: Optional[int] = Field(
        default=None,
        ge=0,
        le=5,
        description="文档难度等级"
    )


class GraphEndMessage(BaseMessage):
    """
    知识图谱抽取完成消息
    
    从文档中抽取的知识图谱（实体和关系）。
    发送到: knowledge_base.graph.end
    消费者: Neo4jWriter（数据库写入）
    """
    
    # 抽取的实体
    entities: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="抽取的实体列表"
    )
    
    # 抽取的关系
    relations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="抽取的关系列表"
    )
    
    # 图谱统计信息
    graph_stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="图谱统计信息（实体数、关系数等）"
    )
    
    # 抽取质量评分（0-1）
    extraction_quality: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="抽取质量评分"
    )
    
    # 使用的 LLM 模型
    llm_model: str = Field(
        ...,
        description="使用的 LLM 模型"
    )
    
    # Token 使用统计
    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token 使用统计"
    )
    
    # 抽取策略
    extraction_strategy: str = Field(
        default="default",
        description="使用的抽取策略"
    )
    
    # 实体类型分布
    entity_type_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="实体类型分布统计"
    )
    
    # 关系类型分布
    relation_type_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="关系类型分布统计"
    )


class AnalyzeEndMessage(BaseMessage):
    """
    文本分析（atomic_qa 抽取）完成消息

    TextAnalyzer 完成一个文档所有 section 的 atomic_qa 抽取后发送。
    发送到: knowledge_base.analyze.end
    消费者: status manager（标记后台 ANALYZE_END 阶段完成）

    设计说明（决策 a：轻量）：
    - 仅携带统计与溯源字段，不携带 QA 正文（正文已通过 db_write.mongo /
      db_write.meta / db_write.embedding 分发落库，下游按 document_id 读库即可）。
    - 后台阶段消息，不影响前台进度（stage_to_progress 对 analyze_end 返回 1.0）。
    """

    # 所属文档 ID
    document_id: Optional[str] = Field(
        default=None,
        description="所属文档 ID（document-{uuid}）"
    )

    # 知识库归属（透传，供状态管理器/日志）
    knowledge_base_id: Optional[str] = Field(
        default=None,
        description="知识库 ID"
    )
    knowledge_base_name: Optional[str] = Field(
        default=None,
        description="知识库名称"
    )

    # 统计：参与抽取的 section 数
    total_sections: int = Field(
        default=0,
        ge=0,
        description="参与 atomic_qa 抽取的 section 数"
    )

    # 统计：产出 QA 总数
    total_qa: int = Field(
        default=0,
        ge=0,
        description="本文档抽取的 atomic_qa 总数"
    )

    # 统计：实际发起的 LLM 调用次数（含分批）
    llm_call_count: int = Field(
        default=0,
        ge=0,
        description="实际发起的 LLM 调用次数（section 数 × 批次，含分批）"
    )

    # 使用的 LLM 模型
    llm_model: str = Field(
        default="",
        description="使用的 LLM 模型"
    )

    # Token 使用统计
    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token 使用统计（input, output, total）"
    )

