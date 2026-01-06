#!/usr:bin/env python
# -*- coding: UTF-8 -*-
"""
Section Schema - 章节表
Base Layer: 文档章节结构存储
"""

from typing import List, Dict, Any
from src.db.milvus.models.base_schema import (
    BaseSchema, FieldDefinition, FieldType,
    MetricType, IndexType
)

# TODO：建立标量索引

class SectionSchema(BaseSchema):
    """章节表结构
    
    用途：存储文档的章节层次结构和章节级别的向量表示
    
    特点：
    - 记录章节的层次关系（父子关系）
    - 包含章节向量，支持章节级别的语义搜索
    - 与chunk表配合，提供文档的结构化视图
    
    业务场景：
    - 结构化文档解析（如技术文档、论文）
    - 章节级别的检索和导航
    - 多粒度的知识定位
    """
    
    COLLECTION_NAME = "section_store"
    DESCRIPTION = "章节表 - 存储文档章节结构和向量表示"
    VECTOR_DIM = 1536
    ENABLE_DYNAMIC_FIELD = True
    
    index_type = "HNSW"
    metric_type = "COSINE"
    index_params = {"M": 8, "efConstruction": 128}
    
    def get_fields(self) -> List[FieldDefinition]:
        """定义字段列表
        
        字段继承chunk_store的结构，保持一致性
        """
        return [
            # ========== 主键 ==========
            self.create_varchar_id_field(max_length=64),
            
            # ========== 向量字段 ==========
            self.create_vector_field(
                name="vector",
                dim=self.VECTOR_DIM,
                description="章节的向量表示，用于章节级别的语义搜索"
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
                description="Section类型，如：chapter/section/subsection"
            ),
            self.create_text_field(
                name="role",
                max_length=64,
                description="角色标识，章节在文档中的角色"
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
                description="文档ID，标识section所属的原始文档"
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
