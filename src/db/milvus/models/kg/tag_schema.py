#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Tag Schema - 标签表
KG Layer: 实体和文档的标签/分类系统
"""

from typing import List, Dict, Any
from src.db.milvus.models.base_schema import (
    BaseSchema, FieldDefinition, FieldType,
    MetricType, IndexType
)


class TagSchema(BaseSchema):
    """标签表结构
    
    用途：存储各种标签、分类和元数据标注
    
    特点：
    - 多用途：支持实体标签、文档标签、关键词等
    - 向量化：标签的语义向量，支持标签相似度搜索
    - 层次化：支持标签的层次关系
    
    业务场景：
    - 文档分类和标注
    - 实体类型标注
    - 关键词提取
    - 分类检索和过滤
    - 标签推荐系统
    
    标签类型示例：
    - 文档标签：技术文档、产品介绍、用户手册
    - 实体标签：人名、地名、组织名
    - 关键词：Python、机器学习、数据库
    - 分类标签：编程、科学、历史
    """
    
    COLLECTION_NAME = "tag_store"
    DESCRIPTION = "标签表 - 存储实体和文档的标签分类系统"
    VECTOR_DIM = 1536
    ENABLE_DYNAMIC_FIELD = True
    
    index_type = "HNSW"
    metric_type = "COSINE"
    index_params = {"M": 8, "efConstruction": 128}
    
    def get_fields(self) -> List[FieldDefinition]:
        """定义字段列表"""
        return [
            # ========== 主键 ==========
            self.create_varchar_id_field(max_length=64),
            
            # ========== 向量字段 ==========
            self.create_vector_field(
                name="vector",
                dim=self.VECTOR_DIM,
                description="标签的向量表示，用于标签语义搜索和相似标签推荐"
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
                description="标签类型，如：keyword/category/entity_type/topic"
            ),
            self.create_text_field(
                name="role",
                max_length=64,
                description="角色标识，如：auto-extracted/user-defined/system"
            ),
            self.create_text_field(
                name="knowledge_type",
                max_length=255,
                description="知识类型，标识标签的领域或分类"
            ),
            
            # ========== 文档和标签关联 ==========
            self.create_text_field(
                name="document_id",
                max_length=64,
                description="文档ID，标识标签关联的文档"
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


class TagSchemaZh(TagSchema):
    """中文标签表"""
    COLLECTION_NAME = "tag_store_zh"
    DESCRIPTION = "中文标签表 - 存储中文标签和分类"


class TagSchemaEn(TagSchema):
    """英文标签表"""
    COLLECTION_NAME = "tag_store_en"
    DESCRIPTION = "英文标签表 - 存储英文标签和分类"
