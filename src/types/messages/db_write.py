#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
数据库写入消息模型

定义数据库写入相关消息：
- EmbeddingWriteMessage: 向量写入（Milvus）
- GraphWriteMessage: 图谱写入（Neo4j）
- MetaWriteMessage: 元数据写入（MySQL）
- MongoWriteMessage: 文档写入（MongoDB）

路由策略：
- 每种消息类型携带目标表/Collection 路由字段
- Writer 根据路由字段将消息分发到具体的 Repository
"""

from enum import StrEnum
from typing import Dict, List, Optional, Any
from pydantic import Field

from src.types.messages.base import BaseMessage


# ==================== 路由枚举定义 ====================


class MySQLTable(StrEnum):
    """MySQL 目标表枚举

    Base 层（基础表）：
    - chunk_meta_info: Chunk 元数据
    - section_meta_info: Section 元数据
    - element_meta_info: Element 元数据
    - chunk_section_document: Chunk-Section-Document 关联表
    - section_document: Section-Document 关联表

    Business 层（业务表）：
    - workspace_file_system: 工作空间文件系统（含文档元数据）
    - workspace_folder: 工作空间文件夹

    Extract 层（提取类表）：
    - chunk_summary: Chunk 摘要
    - chunk_atomic_qa: Chunk 原子QA
    - document_summary: Document 摘要
    """
    CHUNK_META_INFO = "chunk_meta_info"
    SECTION_META_INFO = "section_meta_info"
    ELEMENT_META_INFO = "element_meta_info"
    CHUNK_SECTION_DOCUMENT = "chunk_section_document"
    SECTION_DOCUMENT = "section_document"
    WORKSPACE_FILE_SYSTEM = "workspace_file_system"
    WORKSPACE_FOLDER = "workspace_folder"
    CHUNK_SUMMARY = "chunk_summary"
    CHUNK_ATOMIC_QA = "chunk_atomic_qa"
    DOCUMENT_SUMMARY = "document_summary"


class MongoCollection(StrEnum):
    """MongoDB 目标 Collection 枚举

    - chunk_data: Chunk 完整数据
    - section_data: Section 完整数据
    - document_data: Document 完整数据
    - element_data: Element 完整数据
    """
    CHUNK_DATA = "chunk_data"
    SECTION_DATA = "section_data"
    DOCUMENT_DATA = "document_data"
    ELEMENT_DATA = "element_data"


class MilvusCollection(StrEnum):
    """Milvus 目标 Collection 枚举

    Base 层：
    - chunk: Chunk 向量
    - section: Section 向量

    Enhanced 层：
    - enhanced_chunk: 增强 Chunk 向量

    Extract 层：
    - summary: 摘要向量
    - atomic_qa: 原子QA 向量

    KG 层：
    - spo: SPO 三元组向量
    - tag: 标签向量
    """
    CHUNK = "chunk"
    SECTION = "section"
    ENHANCED_CHUNK = "enhanced_chunk"
    SUMMARY = "summary"
    ATOMIC_QA = "atomic_qa"
    SPO = "spo"
    TAG = "tag"


class WriteOperation(StrEnum):
    """写入操作类型枚举"""
    INSERT = "insert"
    UPDATE = "update"
    UPSERT = "upsert"
    REPLACE = "replace"


# ==================== 消息模型定义 ====================


class EmbeddingWriteMessage(BaseMessage):
    """
    向量写入消息

    写入文本向量到 Milvus。
    发送到: db_write.embedding.start
    消费者: EmbeddingMilvusWriter

    路由字段: collection_type → MilvusCollection 枚举值
    """

    collection_type: MilvusCollection = Field(
        ...,
        description="目标 Milvus Collection 类型"
    )

    items: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="待向量化的数据项列表"
    )

    batch_size: int = Field(
        default=100,
        gt=0,
        description="向量写入批处理大小"
    )

    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="写入优先级"
    )

    source_stage: str = Field(
        ...,
        description="数据来源阶段（split_end, summary_end, analyze_end, image_end）"
    )

    knowledge_base_id: Optional[str] = Field(
        default=None,
        description="知识库ID"
    )

    knowledge_base_name: Optional[str] = Field(
        default=None,
        description="知识库名称"
    )

    need_embedding: bool = Field(
        default=True,
        description="是否需要调用 Embedding API"
    )

    embedding_model: Optional[str] = Field(
        default=None,
        description="使用的 Embedding 模型"
    )

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

    路由逻辑: 按实体类型（entity_type）分组批量写入
    """

    entities: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="待写入的实体列表"
    )

    relations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="待写入的关系列表"
    )

    batch_size: int = Field(
        default=500,
        gt=0,
        description="图谱写入批处理大小"
    )

    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="写入优先级"
    )

    graph_version: Optional[str] = Field(
        default=None,
        description="图谱版本号"
    )

    need_inference: bool = Field(
        default=False,
        description="是否需要图谱推理"
    )

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

    路由字段: table_name → MySQLTable 枚举值
    """

    table_name: MySQLTable = Field(
        ...,
        description="目标 MySQL 表名"
    )

    record_data: Dict[str, Any] = Field(
        ...,
        description="待写入的记录数据（字段名 → 值）"
    )

    operation: WriteOperation = Field(
        default=WriteOperation.UPSERT,
        description="操作类型"
    )

    record_id: Optional[str] = Field(
        default=None,
        description="记录主键 ID（update/upsert 时必填）"
    )

    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="写入优先级"
    )

    updater: str = Field(
        default="system",
        description="更新者标识"
    )


class MongoWriteMessage(BaseMessage):
    """
    文档写入消息

    写入完整文档数据到 MongoDB。
    发送到: db_write.mongo.start
    消费者: MongoWriter

    路由字段: collection_name → MongoCollection 枚举值
    """

    collection_name: MongoCollection = Field(
        ...,
        description="目标 MongoDB Collection 名称"
    )

    document_data: Dict[str, Any] = Field(
        ...,
        description="完整的文档数据"
    )

    operation: WriteOperation = Field(
        default=WriteOperation.UPSERT,
        description="操作类型"
    )

    document_id: Optional[str] = Field(
        default=None,
        description="文档 ID（update/upsert 时使用）"
    )

    batch_size: int = Field(
        default=100,
        gt=0,
        description="文档写入批处理大小"
    )

    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="写入优先级"
    )

    compress: bool = Field(
        default=False,
        description="是否压缩存储大文档"
    )

    ttl_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="数据过期时间（秒，None 表示不过期）"
    )

    updater: str = Field(
        default="system",
        description="更新者标识"
    )
