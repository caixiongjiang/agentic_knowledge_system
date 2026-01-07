#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : document_meta_info.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    DocumentMetaInfo Schema 定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String, Integer, LargeBinary
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin

# TODO: 建立索引

class DocumentMetaInfo(BaseModel, KnowledgeMixin):
    """
    Document 元信息表
    
    存储文档的文件信息、存储位置等元数据。
    包含文件路径、文件类型、SHA256 哈希值等信息。
    """
    __tablename__ = "document_meta_info"
    
    # 主键
    document_id = Column(
        String(255), 
        primary_key=True, 
        index=True,
        comment="Document唯一标识符（UUID格式）"
    )
    
    # 存储信息
    storage_id = Column(
        Integer, 
        default=-1,
        nullable=False,
        comment="存储系统ID：-1=本地存储，其他值对应具体存储系统"
    )
    
    bucket_name = Column(
        String(255), 
        nullable=True,
        comment="对象存储桶名称"
    )
    
    # 文件信息
    file_path = Column(
        String(1024), 
        nullable=True,
        comment="文件路径（相对路径或完整路径）"
    )
    
    file_name = Column(
        String(255), 
        nullable=True,
        comment="文件名（不含路径）"
    )
    
    file_type = Column(
        String(50), 
        nullable=True,
        comment="文件类型：pdf, docx, txt等"
    )
    
    file_format = Column(
        String(255), 
        nullable=True,
        comment="文件格式详细信息"
    )
    
    file_suffix = Column(
        String(50), 
        nullable=True,
        comment="文件后缀名（含.）"
    )
    
    file_sha256 = Column(
        LargeBinary(32), 
        nullable=True,
        comment="文件SHA256哈希值（32字节二进制）"
    )
    
    original_filename = Column(
        String(255), 
        nullable=True,
        comment="用户上传时的原始文件名"
    )
    
    # BaseModel 和 KnowledgeMixin 字段会自动继承：
    # - knowledge_base_id, knowledge_base_name, parent_knowledge_base_id, parent_knowledge_base_name, knowledge_type
    # - status, creator, create_time, updater, update_time, deleted
