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

    # section 摘要列表（仅统计字段，不含正文）
    section_summaries: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="各 section 摘要统计：{section_id, summary_id, chunk_count, summary_length}"
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
    发送到: knowledge_base.summary.end
    消费者: 
    - TextAnalyzer（后台串行）
    - EmbeddingMilvusWriter（数据库写入摘要向量）
    - MySQLWriter（更新文件元数据）
    """
    
    # 文件级摘要
    file_summary: str = Field(
        ...,
        min_length=1,
        description="文件级摘要"
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

