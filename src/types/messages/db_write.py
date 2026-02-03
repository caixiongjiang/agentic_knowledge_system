#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
数据库写入消息模型

定义数据库写入相关消息：
- EmbeddingWriteMessage: 向量写入（Milvus）
- GraphWriteMessage: 图谱写入（Neo4j）
- MetaWriteMessage: 元数据写入（MySQL）
- MongoWriteMessage: 文档写入（MongoDB）
"""

from typing import Dict, List, Optional, Any
from pydantic import Field

from src.types.messages.base import BaseMessage


class EmbeddingWriteMessage(BaseMessage):
    """
    向量写入消息
    
    写入文本向量到 Milvus。
    发送到: db_write.embedding.start
    消费者: EmbeddingMilvusWriter
    """
    
    # Collection 类型
    collection_type: str = Field(
        ...,
        description="Collection 类型（chunk, summary, atomic_qa, image）"
    )
    
    # 待向量化的数据
    items: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="待向量化的数据项列表"
    )
    
    # 批处理配置
    batch_size: int = Field(
        default=100,
        gt=0,
        description="向量写入批处理大小"
    )
    
    # 优先级（1-5，5 最高）
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="写入优先级"
    )
    
    # 来源阶段（split_end, summary_end, analyze_end, image_end）
    source_stage: str = Field(
        ...,
        description="数据来源阶段"
    )
    
    # 是否需要生成 Embedding
    need_embedding: bool = Field(
        default=True,
        description="是否需要调用 Embedding API"
    )
    
    # 使用的 Embedding 模型
    embedding_model: Optional[str] = Field(
        default=None,
        description="使用的 Embedding 模型"
    )
    
    # 文档语言
    language: str = Field(
        default="unknown",
        description="文档语言"
    )


class GraphWriteMessage(BaseMessage):
    """
    图谱写入消息
    
    写入知识图谱到 Neo4j。
    发送到: db_write.graph.start
    消费者: Neo4jWriter
    """
    
    # 实体列表
    entities: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="待写入的实体列表"
    )
    
    # 关系列表
    relations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="待写入的关系列表"
    )
    
    # 批处理配置
    batch_size: int = Field(
        default=500,
        gt=0,
        description="图谱写入批处理大小"
    )
    
    # 优先级
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="写入优先级"
    )
    
    # 图谱版本（用于回滚）
    graph_version: Optional[str] = Field(
        default=None,
        description="图谱版本号"
    )
    
    # 是否需要推理
    need_inference: bool = Field(
        default=False,
        description="是否需要图谱推理"
    )
    
    # 实体去重策略
    entity_dedup_strategy: str = Field(
        default="by_name_and_type",
        description="实体去重策略"
    )


class MetaWriteMessage(BaseMessage):
    """
    元数据写入消息
    
    写入文件和处理元数据到 MySQL。
    发送到: db_write.meta.start
    消费者: MySQLWriter
    """
    
    # 文件元数据
    file_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="文件元数据"
    )
    
    # 处理元数据
    processing_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="处理元数据（处理时间、token 使用等）"
    )
    
    # 更新的字段
    update_fields: List[str] = Field(
        default_factory=list,
        description="需要更新的字段列表"
    )
    
    # 操作类型
    operation: str = Field(
        default="upsert",
        description="操作类型（insert, update, upsert）"
    )
    
    # 优先级
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="写入优先级"
    )
    
    # 状态
    status: str = Field(
        default="processing",
        description="文件处理状态"
    )
    
    # 进度百分比（0-100）
    progress_percentage: int = Field(
        default=0,
        ge=0,
        le=100,
        description="处理进度百分比"
    )
    
    # 错误信息（如果有）
    error_message: Optional[str] = Field(
        default=None,
        description="错误信息"
    )


class MongoWriteMessage(BaseMessage):
    """
    文档写入消息
    
    写入完整文档数据到 MongoDB。
    发送到: db_write.mongo.start
    消费者: MongoWriter
    """
    
    # 文档数据
    document_data: Dict[str, Any] = Field(
        ...,
        description="完整的文档数据"
    )
    
    # 数据类型
    data_type: str = Field(
        ...,
        description="数据类型（parsed_document, chunks, summary, etc.）"
    )
    
    # Collection 名称
    collection_name: Optional[str] = Field(
        default=None,
        description="指定的 Collection 名称（默认根据 data_type 决定）"
    )
    
    # 操作类型
    operation: str = Field(
        default="upsert",
        description="操作类型（insert, update, upsert, replace）"
    )
    
    # 批处理配置
    batch_size: int = Field(
        default=100,
        gt=0,
        description="文档写入批处理大小"
    )
    
    # 优先级
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="写入优先级"
    )
    
    # 是否压缩存储
    compress: bool = Field(
        default=False,
        description="是否压缩存储大文档"
    )
    
    # TTL（Time To Live，秒）
    ttl_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="数据过期时间（秒，None 表示不过期）"
    )
    
    # 索引字段
    index_fields: List[str] = Field(
        default_factory=list,
        description="需要建立索引的字段"
    )
