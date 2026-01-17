#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_meta_info.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    ChunkMetaInfo Schema 定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String, Integer, JSON
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin

# TODO: 建立索引

class ChunkMetaInfo(BaseModel, KnowledgeMixin):
    """
    Chunk 元信息表
    
    存储 Chunk 在 Document 中的位置、类型、关联文件等信息。
    包含 Chunk 的页面位置、序号、图片文件信息等元数据。
    """
    __tablename__ = "chunk_meta_info"
    
    # 主键
    chunk_id = Column(
        String(255), 
        primary_key=True, 
        index=True,
        comment="Chunk唯一标识符（UUID格式）"
    )
    
    # Chunk 基础信息
    chunk_type = Column(
        String(50), 
        nullable=True,
        comment="Chunk类型：text=文本，image=图片，table=表格"
    )
    
    index = Column(
        Integer, 
        nullable=True,
        comment="Chunk在Document中的序号（从0开始）"
    )
    
    # 页面位置信息
    page_index = Column(
        Integer, 
        nullable=True,
        comment="所在页码（从0开始）"
    )
    
    page_position = Column(
        String(255), 
        nullable=True,
        comment="在页面中的位置（JSON格式：{x, y, width, height}）"
    )
    
    # 关联文件信息（如果 Chunk 对应图片）
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
    
    # 关联 Elements 信息（用于文件修改 pipeline）
    element_ids = Column(
        JSON,
        nullable=True,
        comment="关联的Element ID列表（JSON数组格式，用于追踪Chunk包含的元素）"
    )
    
    # BaseModel 和 KnowledgeMixin 字段会自动继承：
    # - knowledge_base_id, knowledge_base_name, parent_knowledge_base_id, parent_knowledge_base_name, knowledge_type
    # - status, creator, create_time, updater, update_time, deleted
