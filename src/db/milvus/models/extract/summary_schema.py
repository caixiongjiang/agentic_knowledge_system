#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Summary Schema - 摘要表
Extract Layer: 多层次文本摘要

按 role 拆分为两个独立 Collection：
- FileSummarySchema    → file_summary_store      (文档级摘要)
- SectionSummarySchema → section_summary_store   (章节级摘要)
"""

from typing import List, Dict, Any
from src.db.milvus.models.base_schema import (
    BaseSchema, FieldDefinition, FieldType,
    MetricType, IndexType
)


class _BaseSummarySchema(BaseSchema):
    """摘要表共享字段定义

    两个子类（FileSummarySchema / SectionSummarySchema）字段完全一致，
    仅 COLLECTION_NAME 与 DESCRIPTION 不同；通过基类复用 get_fields /
    get_index_params，避免重复。
    """

    VECTOR_DIM = 1024
    ENABLE_DYNAMIC_FIELD = False

    index_type = "HNSW"
    metric_type = "COSINE"
    index_params = {"M": 8, "efConstruction": 128}

    def get_fields(self) -> List[FieldDefinition]:
        return [
            self.create_varchar_id_field(max_length=64),
            self.create_vector_field(
                name="vector",
                dim=self.VECTOR_DIM,
                description="摘要的向量表示，用于摘要级别的语义搜索"
            ),
            self.create_text_field(name="user_id", max_length=64,
                description="用户ID，标识数据所属用户"),
            self.create_text_field(name="knowledge_base_id", max_length=64,
                description="知识库ID，标识数据所属的知识库"),
            self.create_text_field(name="knowledge_base_name", max_length=255,
                description="知识库名称，便于查询和展示", nullable=True),
            self.create_text_field(name="parent_knowledge_base_id", max_length=64,
                description="父知识库ID，用于表示知识库之间的层次关系", nullable=True),
            self.create_text_field(name="parent_knowledge_base_name", max_length=255,
                description="父知识库名称，便于查询和展示", nullable=True),
            self.create_json_field(name="agent_ids",
                description="Agent追踪信息（JSON格式），包含message_id, session_id, task_id, agent_id等所有agent生命周期相关字段",
                nullable=True),
            self.create_text_field(name="type", max_length=32,
                description="摘要类型，如：extractive/abstractive/hybrid", nullable=True),
            self.create_text_field(name="role", max_length=64,
                description="角色标识：document_summary / section_summary", nullable=True),
            self.create_text_field(name="knowledge_type", max_length=255,
                description="知识类型，标识摘要的领域或分类", nullable=True),
            self.create_text_field(name="document_id", max_length=64,
                description="文档ID，标识摘要来源的原始文档"),
            self.create_text_field(name="label_id", max_length=64,
                description="标签ID，用于分类和过滤", nullable=True),
            self.create_int_field(name="timestamp",
                description="业务时间戳，记录业务发生时间", nullable=True),
            self.create_timestamp_field(name="create_time", nullable=True),
            self.create_timestamp_field(name="update_time", nullable=True),
        ]

    def get_index_params(self) -> Dict[str, Any]:
        return {
            "metric_type": self.metric_type,
            "index_type": self.index_type,
            "params": self.index_params
        }


class FileSummarySchema(_BaseSummarySchema):
    """文档级摘要表结构

    对应 Milvus Collection: file_summary_store
    存储文档级别的摘要（由 FileSummaryService 基于 section 摘要 rollup 生成）。
    """
    COLLECTION_NAME = "file_summary_store"
    DESCRIPTION = "文档级摘要表 - 存储文件/文档级别的文本摘要"


class SectionSummarySchema(_BaseSummarySchema):
    """章节级摘要表结构

    对应 Milvus Collection: section_summary_store
    存储章节级别的摘要（由 SectionSummaryWorker 对每个 section 生成，
    父 section 通过 rollup 聚合子 section 摘要）。
    """
    COLLECTION_NAME = "section_summary_store"
    DESCRIPTION = "章节级摘要表 - 存储章节级别的文本摘要"
