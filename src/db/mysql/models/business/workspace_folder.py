#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : workspace_folder.py
@Author  : caixiongjiang
@Date    : 2026/02/16
@Function: 
    WorkspaceFolder Schema 定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String, Integer, SmallInteger, Text, Index
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin


class WorkspaceFolder(BaseModel, KnowledgeMixin):
    """
    工作空间文件夹表
    
    独立管理文件夹的层级结构，支持：
    - 空文件夹的创建和保留
    - 文件夹重命名（仅改一条记录）
    - 文件夹移动（仅改 parent_folder_id）
    - 多知识库下的文件夹树
    - 每个 (user_id, knowledge_base_id) 下至多一个默认文件夹（应用层保证）
    
    通过 parent_folder_id 自关联实现文件夹嵌套。
    """
    __tablename__ = "workspace_folder"
    
    __table_args__ = (
        Index("idx_user_kb", "user_id", "knowledge_base_id"),
        Index("idx_user_parent", "user_id", "parent_folder_id"),
        Index("idx_user_kb_default", "user_id", "knowledge_base_id", "is_default"),
    )
    
    # 主键
    folder_id = Column(
        String(64),
        primary_key=True,
        comment="文件夹ID（UUID格式）"
    )
    
    # 归属信息
    user_id = Column(
        String(64),
        nullable=False,
        index=True,
        comment="所属用户ID"
    )
    
    # 文件夹信息
    folder_name = Column(
        String(255),
        nullable=False,
        comment="文件夹名称"
    )
    
    parent_folder_id = Column(
        String(64),
        nullable=True,
        comment="父文件夹ID（NULL 表示根目录）"
    )
    
    full_path = Column(
        String(1024),
        nullable=False,
        comment="完整路径（冗余缓存，如 /项目A/文档/设计稿/）"
    )
    
    depth = Column(
        Integer,
        default=0,
        nullable=False,
        comment="目录层级深度（根目录为0）"
    )
    
    sort_order = Column(
        Integer,
        default=0,
        nullable=False,
        comment="同级文件夹排序权重"
    )
    
    is_default = Column(
        SmallInteger,
        default=0,
        nullable=False,
        comment="是否为默认文件夹（0-否，1-是）。每个 (user_id, knowledge_base_id) 下至多一个"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="文件夹描述"
    )
    
    # BaseModel 和 KnowledgeMixin 字段会自动继承：
    # - knowledge_base_id, knowledge_base_name, parent_knowledge_base_id, parent_knowledge_base_name, knowledge_type
    # - status, creator, create_time, updater, update_time, deleted
