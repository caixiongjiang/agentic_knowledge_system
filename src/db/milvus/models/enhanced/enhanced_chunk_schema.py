#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Enhanced Chunk Schema - 增强分块表
Enhanced Layer: 包含向量的增强文本块
"""

from typing import List, Dict, Any
from src.db.milvus.models.base_schema import (
    BaseSchema, FieldDefinition, FieldType,
    MetricType, IndexType
)


class EnhancedChunkSchema(BaseSchema):
    """增强分块表结构
    
    用途：存储经过增强处理的文本分块，提供更高质量的向量表示
    
    特点：
    - 在chunk_store基础上提供增强的向量表示
    - 可能包含清洗、重写或优化后的文本
    - 支持更精准的语义搜索
    
    业务场景：
    - 高质量的RAG检索
    - 重写或清洗后的文本存储
    - 增强的语义理解
    """
    
    COLLECTION_NAME = "enhanced_chunk_store"
    DESCRIPTION = "增强分块表 - 存储增强处理后的文本块"
    VECTOR_DIM = 1536
    ENABLE_DYNAMIC_FIELD = True
    
    index_type = "HNSW"
    metric_type = "COSINE"
    index_params = {"M": 8, "efConstruction": 128}
    
    def get_fields(self) -> List[FieldDefinition]:
        """定义字段列表
        
        字段结构与chunk_store完全一致，通过动态字段支持扩展
        """
        return [
            # ========== 主键 ==========
            self.create_varchar_id_field(max_length=64),
            
            # ========== 向量字段 ==========
            self.create_vector_field(
                name="vector",
                dim=self.VECTOR_DIM,
                description="增强文本块的向量表示，可能使用不同的embedding策略"
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
                description="增强Chunk类型，如：enhanced_text/rewritten/cleaned"
            ),
            self.create_text_field(
                name="role",
                max_length=64,
                description="角色标识，如：user/assistant/system"
            ),
            self.create_text_field(
                name="knowledge_type",
                max_length=255,
                description="知识类型，标识知识的分类或领域"
            ),
            
            # ========== 文档和标签关联 ==========
            self.create_text_field(
                name="document_id",
                max_length=64,
                description="文档ID，标识chunk来源的原始文档"
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


class EnhancedChunkSchemaZh(EnhancedChunkSchema):
    """中文增强分块表"""
    COLLECTION_NAME = "enhanced_chunk_store_zh"
    DESCRIPTION = "中文增强分块表 - 存储中文增强文本"


class EnhancedChunkSchemaEn(EnhancedChunkSchema):
    """英文增强分块表"""
    COLLECTION_NAME = "enhanced_chunk_store_en"
    DESCRIPTION = "英文增强分块表 - 存储英文增强文本"
