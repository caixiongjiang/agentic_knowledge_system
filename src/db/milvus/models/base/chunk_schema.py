#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Chunk Schema - 文本分块表
Base Layer: 原始文档分块存储
"""

from typing import List, Dict, Any
from src.db.milvus.models.base_schema import (
    BaseSchema, FieldDefinition, FieldType,
    MetricType, IndexType
)


class ChunkSchema(BaseSchema):
    """文本分块表结构
    
    用途：存储文档经过分块处理后的文本片段，是知识库的基础数据层
    
    特点：
    - 包含向量表示，支持语义搜索
    - 记录完整的上下文信息（会话、任务、Agent等）
    - 支持分层存储（中文/英文分表）
    
    业务场景：
    - RAG检索的基础数据源
    - 记忆系统的原始存储
    - 多Agent协作的知识共享
    """
    
    COLLECTION_NAME = "chunk_store"
    DESCRIPTION = "文本分块表 - 存储原始文档分块及其向量表示"
    VECTOR_DIM = 1536  # 根据实际embedding模型调整
    ENABLE_DYNAMIC_FIELD = True
    
    # 索引类型配置
    index_type = "HNSW"
    metric_type = "COSINE"
    index_params = {"M": 8, "efConstruction": 128}
    
    def get_fields(self) -> List[FieldDefinition]:
        """定义字段列表
        
        字段分类：
        1. 主键和标识：id
        2. 向量：vector
        3. 用户信息：user_id
        4. 知识库信息：knowledge_base_id, knowledge_base_name
        5. Agent追踪：agent_ids (JSON，包含所有agent相关信息)
        6. 分类标记：type, role, knowledge_type
        7. 文档关联：document_id, label_id
        8. 知识关系：knowledge_id, parent_knowledge_id
        9. 时间戳：timestamp, create_time, update_time
        
        agent_ids JSON字段说明：
        {
            "message_id": int,           # 消息ID
            "session_id": int,           # 会话ID
            "task_id": int,              # 任务ID
            "agent_id": str,             # Agent ID
            "agent_instance_id": int,    # Agent实例ID
            "component_id": str,         # 组件ID
            "parent_agent_instance_id": int,  # 父Agent实例ID
            "event_id": str,             # 事件ID
            "await_command_uuid": str,   # 等待命令UUID
            "caller_id": str,            # 调用者ID
            "caller_instance_id": int,   # 调用者实例ID
            "caller_type": str,          # 调用者类型
            "callee_id": str,            # 被调用者ID
            "callee_instance_id": int,   # 被调用者实例ID
            "callee_type": str,          # 被调用者类型
            "call_batch_id": int         # 调用批次ID
        }
        """
        return [
            # ========== 主键 ==========
            self.create_varchar_id_field(max_length=64),
            
            # ========== 向量字段 ==========
            self.create_vector_field(
                name="vector",
                dim=self.VECTOR_DIM,
                description="文本块的向量表示，用于语义相似度搜索"
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
                description="Chunk类型，如：text/code/table等"
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
        """索引参数配置
        
        使用HNSW索引，平衡查询性能和索引构建速度
        """
        return {
            "metric_type": self.metric_type,
            "index_type": self.index_type,
            "params": self.index_params
        }


class ChunkSchemaZh(ChunkSchema):
    """中文文本分块表"""
    COLLECTION_NAME = "chunk_store_zh"
    DESCRIPTION = "中文文本分块表 - 存储中文文档分块"


class ChunkSchemaEn(ChunkSchema):
    """英文文本分块表"""
    COLLECTION_NAME = "chunk_store_en"
    DESCRIPTION = "英文文本分块表 - 存储英文文档分块"
