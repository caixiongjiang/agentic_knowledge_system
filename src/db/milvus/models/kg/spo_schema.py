#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
SPO Schema - 三元组表
KG Layer: 知识图谱三元组（Subject-Predicate-Object）
"""

from typing import List, Dict, Any
from src.db.milvus.models.base_schema import (
    BaseSchema, FieldDefinition, FieldType,
    MetricType, IndexType
)


class SPOSchema(BaseSchema):
    """SPO三元组表结构
    
    用途：存储知识图谱的核心结构 - 三元组关系
    
    特点：
    - 表示主语-谓语-宾语的结构化知识
    - 向量化：支持基于关系的语义搜索
    - 可追溯：记录三元组的提取来源
    - 自增ID：使用Int64自增主键（与其他表不同）
    
    业务场景：
    - 知识图谱构建
    - 实体关系抽取
    - 图谱推理和查询
    - 关系型知识检索
    
    三元组示例：
    - (张三, 工作于, 阿里巴巴)
    - (Python, 是一种, 编程语言)
    - (北京, 位于, 中国)
    
    与其他表的区别：
    - 使用INT64自增ID，而不是VARCHAR ID
    - 包含tag_id字段（可能关联tag_store）
    """
    
    COLLECTION_NAME = "spo_store"
    DESCRIPTION = "SPO三元组表 - 存储知识图谱的主语-谓语-宾语结构"
    VECTOR_DIM = 1536
    ENABLE_DYNAMIC_FIELD = True
    
    index_type = "HNSW"
    metric_type = "COSINE"
    index_params = {"M": 8, "efConstruction": 128}
    
    def get_fields(self) -> List[FieldDefinition]:
        """定义字段列表
        
        注意：SPO表使用自增ID，这是唯一与其他表不同的地方
        """
        return [
            # ========== 主键（自增） ==========
            self.create_id_field(auto_id=True),  # INT64自增主键
            
            # ========== 向量字段 ==========
            self.create_vector_field(
                name="vector",
                dim=self.VECTOR_DIM,
                description="三元组关系的向量表示，用于关系语义搜索"
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
                description="三元组类型，如：entity-relation/event-relation/attribute"
            ),
            self.create_text_field(
                name="role",
                max_length=64,
                description="角色标识，如：extracted/inferred/manual"
            ),
            self.create_text_field(
                name="knowledge_type",
                max_length=255,
                description="知识类型，标识三元组的领域或分类"
            ),
            
            # ========== 文档和标签关联 ==========
            self.create_text_field(
                name="document_id",
                max_length=64,
                description="文档ID，标识三元组来源的原始文档"
            ),
            self.create_text_field(
                name="tag_id",
                max_length=64,
                description="标签ID，SPO表特有字段，可能关联tag_store表"
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


class SPOSchemaZh(SPOSchema):
    """中文SPO三元组表"""
    COLLECTION_NAME = "spo_store_zh"
    DESCRIPTION = "中文SPO三元组表 - 存储中文知识图谱关系"


class SPOSchemaEn(SPOSchema):
    """英文SPO三元组表"""
    COLLECTION_NAME = "spo_store_en"
    DESCRIPTION = "英文SPO三元组表 - 存储英文知识图谱关系"
