#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Summary Schema - 摘要表
Extract Layer: 多层次文本摘要
"""

from typing import List, Dict, Any
from src.db.milvus.models.base_schema import (
    BaseSchema, FieldDefinition, FieldType,
    MetricType, IndexType
)

# TODO：建立标量索引

class SummarySchema(BaseSchema):
    """摘要表结构
    
    用途：存储不同粒度和层次的文本摘要
    
    特点：
    - 多层次：支持文档、章节、段落等不同粒度的摘要
    - 向量化：摘要的语义向量，支持摘要级别的检索
    - 可追溯：记录摘要来源和生成方法
    
    业务场景：
    - 文档快速浏览
    - 层次化知识导航
    - 摘要式RAG检索
    - 长文本压缩和理解
    
    摘要类型：
    - 抽取式（extractive）：从原文抽取关键句子
    - 生成式（abstractive）：AI生成的概括性文本
    """
    
    COLLECTION_NAME = "summary_store"
    DESCRIPTION = "摘要表 - 存储多层次文本摘要"
    VECTOR_DIM = 1536
    ENABLE_DYNAMIC_FIELD = True
    
    index_type = "HNSW"
    metric_type = "COSINE"
    index_params = {"M": 8, "efConstruction": 128}
    
    def get_fields(self) -> List[FieldDefinition]:
        """定义字段列表
        
        继承标准字段结构，保持系统一致性
        """
        return [
            # ========== 主键 ==========
            self.create_varchar_id_field(max_length=64),
            
            # ========== 向量字段 ==========
            self.create_vector_field(
                name="vector",
                dim=self.VECTOR_DIM,
                description="摘要的向量表示，用于摘要级别的语义搜索"
            ),
            
            # ========== 用户信息 ==========
            self.create_text_field(
                name="user_id",
                max_length=64,
                description="用户ID，标识数据所属用户"
            ),
            
            # ========== 知识库信息 ==========
            self.create_text_field(
                name="knowledge_base_id",
                max_length=64,
                description="知识库ID，标识数据所属的知识库"
            ),
            self.create_text_field(
                name="knowledge_base_name",
                max_length=255,
                description="知识库名称，便于查询和展示"
            ),
            self.create_text_field(
                name="parent_knowledge_base_id",
                max_length=64,
                description="父知识库ID，用于表示知识库之间的层次关系"
            ),
            self.create_text_field(
                name="parent_knowledge_base_name",
                max_length=255,
                description="父知识库名称，便于查询和展示"
            ),
            
            # ========== Agent追踪信息（JSON） ==========
            self.create_json_field(
                name="agent_ids",
                description="Agent追踪信息（JSON格式），包含message_id, session_id, task_id, agent_id等所有agent生命周期相关字段"
            ),
            
            # ========== 类型和分类 ==========
            self.create_text_field(
                name="type",
                max_length=32,
                description="摘要类型，如：extractive/abstractive/hybrid"
            ),
            self.create_text_field(
                name="role",
                max_length=64,
                description="角色标识，如：document_summary/section_summary/chunk_summary"
            ),
            self.create_text_field(
                name="knowledge_type",
                max_length=255,
                description="知识类型，标识摘要的领域或分类"
            ),
            
            # ========== 文档和标签关联 ==========
            self.create_text_field(
                name="document_id",
                max_length=64,
                description="文档ID，标识摘要来源的原始文档"
            ),
            self.create_text_field(
                name="label_id",
                max_length=64,
                description="标签ID，用于分类和过滤"
            ),
            
            # ========== 时间戳 ==========
            self.create_int_field(
                name="timestamp",
                description="业务时间戳，记录业务发生时间"
            ),
            self.create_timestamp_field(name="create_time"),
            self.create_timestamp_field(name="update_time"),
        ]
    
    def get_index_params(self) -> Dict[str, Any]:
        """索引参数配置"""
        return {
            "metric_type": self.metric_type,
            "index_type": self.index_type,
            "params": self.index_params
        }
