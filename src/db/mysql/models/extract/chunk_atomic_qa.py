#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_atomic_qa.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    ChunkAtomicQA Schema 定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin

# TODO: 建立索引

class ChunkAtomicQA(BaseModel, KnowledgeMixin):
    """
    Chunk-AtomicQA 关联表
    
    存储 Chunk 与其原子问答（Atomic QA）之间的关联关系。
    AtomicQA 数据存储在 Milvus 向量数据库中，通过 atomic_qa_id 关联。
    """
    __tablename__ = "chunk_atomic_qa"
    
    # 主键
    chunk_id = Column(
        String(255), 
        primary_key=True, 
        index=True,
        comment="Chunk唯一标识符（UUID格式）"
    )
    
    # 关联字段
    atomic_qa_id = Column(
        String(255), 
        index=True,
        nullable=False,
        comment="关联的AtomicQA ID（在Milvus中的ID）"
    )
    
    # BaseModel 和 KnowledgeMixin 字段会自动继承：
    # - knowledge_base_id, knowledge_base_name, parent_knowledge_base_id, parent_knowledge_base_name, knowledge_type
    # - status, creator, create_time, updater, update_time, deleted
