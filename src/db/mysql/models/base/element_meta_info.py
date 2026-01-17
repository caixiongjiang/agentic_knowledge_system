#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : element_meta_info.py
@Author  : caixiongjiang
@Date    : 2026/01/16
@Function: 
    ElementMetaInfo Schema 定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String, Integer
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin

# TODO: 建立索引

class ElementMetaInfo(BaseModel, KnowledgeMixin):
    """
    Element 元信息表（PDF解析元素元信息表，热数据）
    
    存储 PDF 解析后的元素信息，包括文本、图片、表格等元素的位置和属性。
    每个元素对应一个页面上的解析单元，包含空间位置、类型、图片存储等信息。
    """
    __tablename__ = "element_meta_info"
    
    # 主键
    element_id = Column(
        String(255), 
        primary_key=True,
        comment="全局唯一ID (UUID格式)"
    )
    
    # 基础信息
    page_index = Column(
        Integer, 
        nullable=True,
        comment="页码（从0开始）"
    )
    
    element_type = Column(
        String(32), 
        nullable=False,
        comment="元素类型：text=文本, image=图片, table=表格, discarded=丢弃"
    )
    
    # 空间位置信息
    page_position = Column(
        String(255), 
        nullable=True,
        comment="在页面中的位置（JSON格式：{x, y, width, height}）"
    )
    
    # 辅助元数据
    level = Column(
        Integer, 
        nullable=True,
        comment="元素层级深度（1=一级，2=二级，仅text类型有效）"
    )
    
    # MinIO 存储相关（仅图片类型使用）
    bucket_name = Column(
        String(255), 
        nullable=True,
        comment="对象存储桶名称（如 MinIO bucket）"
    )
    
    image_file_path = Column(
        String(1024), 
        nullable=True,
        comment="图片文件路径"
    )
    
    image_file_name = Column(
        String(255), 
        nullable=True,
        comment="图片文件名"
    )
    
    image_file_type = Column(
        String(50), 
        nullable=True,
        comment="图片文件类型：png, jpg, svg等"
    )
    
    image_file_format = Column(
        String(255), 
        nullable=True,
        comment="图片格式详细信息"
    )
    
    image_file_suffix = Column(
        String(20), 
        nullable=True,
        comment="图片文件后缀名（含.）"
    )
    
    # BaseModel 和 KnowledgeMixin 字段会自动继承：
    # - knowledge_base_id, knowledge_base_name, parent_knowledge_base_id, parent_knowledge_base_name, knowledge_type
    # - status, creator, create_time, updater, update_time, deleted
    
    # 注意：SQL 中的 created_at/updated_at 对应 BaseModel 中的 create_time/update_time
