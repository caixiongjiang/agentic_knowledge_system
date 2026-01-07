#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_section_document.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    ChunkSectionDocument Schema 定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin

# TODO: 建立索引

class ChunkSectionDocument(BaseModel, KnowledgeMixin):
    """
    Chunk-Section-Document 三层关系表
    
    存储内容块（Chunk）、章节（Section）、文档（Document）之间的层级关系。
    用于追溯 Chunk 的来源和上下文。
    
    关系链：
    - Chunk -> Parent Chunk（可选，用于嵌套结构）
    - Chunk -> Section（所属章节）
    - Section -> Document（所属文档）
    """
    __tablename__ = "chunk_section_document"
    
    # 主键
    chunk_id = Column(
        String(255), 
        primary_key=True, 
        index=True,
        comment="Chunk唯一标识符（UUID格式）"
    )
    
    # 关系字段
    parent_chunk_id = Column(
        String(255), 
        nullable=True,
        comment="父Chunk ID（用于表示嵌套的Chunk层级关系）"
    )
    
    section_id = Column(
        String(255), 
        nullable=True,
        comment="所属Section的ID"
    )
    
    document_id = Column(
        String(255), 
        nullable=True,
        comment="所属Document的ID"
    )
    
    # BaseModel 和 KnowledgeMixin 字段会自动继承：
    # - knowledge_base_id, knowledge_base_name, parent_knowledge_base_id, parent_knowledge_base_name, knowledge_type
    # - status, creator, create_time, updater, update_time, deleted
