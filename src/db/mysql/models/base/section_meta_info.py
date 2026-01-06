#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_meta_info.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    SectionMetaInfo Schema 定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String, Integer
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin

# TODO: 建立索引

class SectionMetaInfo(BaseModel, KnowledgeMixin):
    """
    Section 元信息表
    
    存储 Section 在 Document 中的位置、类型等信息。
    包含 Section 的序号、层级、页面范围等元数据。
    """
    __tablename__ = "section_meta_info"
    
    # 主键
    section_id = Column(
        String(255), 
        primary_key=True, 
        index=True,
        comment="Section唯一标识符（UUID格式）"
    )
    
    # Section 基础信息
    section_type = Column(
        String(50), 
        nullable=True,
        comment="Section类型：chapter=章节，heading=标题"
    )
    
    index = Column(
        Integer, 
        nullable=True,
        comment="Section在Document中的序号（从0开始）"
    )
    
    level = Column(
        Integer, 
        nullable=True,
        comment="Section的层级深度（1=一级标题，2=二级标题）"
    )
    
    # 页面范围信息
    start_page_index = Column(
        Integer, 
        nullable=True,
        comment="起始页码（从0开始）"
    )
    
    end_page_index = Column(
        Integer, 
        nullable=True,
        comment="结束页码（从0开始）"
    )
    
    # Section 标题
    title = Column(
        String(1024), 
        nullable=True,
        comment="Section标题"
    )
    
    # BaseModel 和 KnowledgeMixin 字段会自动继承：
    # - role, knowledge_type, knowledge_id, parent_knowledge_id
    # - status, creator, create_time, updater, update_time, deleted
