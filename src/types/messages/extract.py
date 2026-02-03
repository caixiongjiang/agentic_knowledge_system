#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
提取相关消息模型

定义后台提取流程的各阶段消息：
- SummaryEndMessage: 文件摘要完成
- GraphEndMessage: 知识图谱抽取完成
- ImageEndMessage: 图片理解完成
"""

from typing import Dict, List, Optional, Any
from pydantic import Field

from src.types.messages.base import BaseMessage


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


class ImageEndMessage(BaseMessage):
    """
    图片理解完成消息
    
    对文档中的图片进行理解和描述。
    发送到: knowledge_base.image.end
    消费者: EmbeddingMilvusWriter（数据库写入图片描述向量）
    """
    
    # 图片理解结果
    image_understandings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="图片理解结果列表"
    )
    
    # 处理的图片数量
    total_images: int = Field(
        default=0,
        ge=0,
        description="处理的图片总数"
    )
    
    # 成功处理的图片数量
    successful_images: int = Field(
        default=0,
        ge=0,
        description="成功处理的图片数量"
    )
    
    # 使用的视觉模型
    vision_model: str = Field(
        ...,
        description="使用的视觉模型"
    )
    
    # Token 使用统计
    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token 使用统计"
    )
    
    # 图片类型分布
    image_type_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="图片类型分布（chart, diagram, photo 等）"
    )
    
    # 平均理解质量（0-1）
    average_quality: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="平均理解质量评分"
    )
