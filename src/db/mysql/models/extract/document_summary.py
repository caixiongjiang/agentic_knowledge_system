#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : document_summary.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    DocumentSummary Schema 定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin

# TODO: 建立索引

class DocumentSummary(BaseModel, KnowledgeMixin):
    """
    Document-Summary 关联表
    
    存储 Document 与其摘要（Summary）之间的关联关系。
    Summary 数据存储在 Milvus 向量数据库中，通过 summary_id 关联。
    """
    __tablename__ = "document_summary"
    
    # 主键
    document_id = Column(
        String(255), 
        primary_key=True, 
        index=True,
        comment="Document唯一标识符（UUID格式）"
    )
    
    # 关联字段
    summary_id = Column(
        String(255), 
        index=True,
        nullable=False,
        comment="关联的Summary ID（在Milvus中的ID）"
    )
    
    # BaseModel 和 KnowledgeMixin 字段会自动继承：
    # - role, knowledge_type, knowledge_id, parent_knowledge_id
    # - status, creator, create_time, updater, update_time, deleted
