#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_document.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    SectionDocument Schema 定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin

# TODO: 建立索引

class SectionDocument(BaseModel, KnowledgeMixin):
    """
    Section-Document 两层关系表
    
    存储章节（Section）与文档（Document）之间的关系。
    用于追溯 Section 所属的文档。
    
    关系链：
    - Section -> Parent Section（可选，用于嵌套章节结构）
    - Section -> Document（所属文档）
    """
    __tablename__ = "section_document"
    
    # 主键
    section_id = Column(
        String(255), 
        primary_key=True, 
        index=True,
        comment="Section唯一标识符（UUID格式）"
    )
    
    # 关系字段
    parent_section_id = Column(
        String(255), 
        nullable=True,
        comment="父Section ID（用于表示嵌套的章节层级关系）"
    )
    
    document_id = Column(
        String(255), 
        nullable=True,
        comment="所属Document的ID"
    )
    
    # BaseModel 和 KnowledgeMixin 字段会自动继承：
    # - role, knowledge_type, knowledge_id, parent_knowledge_id
    # - status, creator, create_time, updater, update_time, deleted
