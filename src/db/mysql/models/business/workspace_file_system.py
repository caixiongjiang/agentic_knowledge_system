#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : workspace_file_system.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    WorkspaceFileSystem Schema 定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String, Integer, BigInteger, Text
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin, AgentMixin

# TODO: 建立索引

class WorkspaceFileSystem(BaseModel, KnowledgeMixin, AgentMixin):
    """
    工作空间文件系统表
    
    存储用户工作空间中的文件信息，包括文件基本信息、Git信息、
    处理状态等，支持完整的调用链追溯。
    
    主键：(user_id, file_id) 联合主键
    """
    __tablename__ = "workspace_file_system"
    
    # 主键（联合主键）
    user_id = Column(
        String(64), 
        primary_key=True,
        comment="用户ID（主键之一）"
    )
    
    file_id = Column(
        String(255), 
        primary_key=True,
        nullable=False,
        comment="文件ID（主键之一，全局唯一UUID）"
    )
    
    # 文件基本信息
    file_name = Column(
        String(255), 
        nullable=False,
        comment="文件名"
    )
    
    folder_path = Column(
        String(500), 
        nullable=True,
        comment="文件夹路径"
    )
    
    folder_parent_path = Column(
        String(500), 
        nullable=True,
        comment="父文件夹路径"
    )
    
    file_size = Column(
        BigInteger, 
        nullable=True,
        comment="文件大小（字节）"
    )
    
    document_id = Column(
        String(255), 
        index=True, 
        nullable=True,
        comment="关联的Document ID"
    )
    
    # Git 相关
    git_path = Column(
        String(500), 
        nullable=True,
        comment="Git仓库中的物理路径"
    )
    
    git_commit_hash = Column(
        String(40), 
        nullable=True,
        comment="Git commit hash（40位十六进制）"
    )
    
    # 文件特征
    is_text_readable = Column(
        String(255), 
        nullable=True,
        comment="文本可读性标识：true, false, unknown"
    )
    
    mime_type = Column(
        String(255), 
        nullable=True,
        comment="文件MIME类型（如 text/plain, image/png）"
    )
    
    # 处理状态
    queue_position = Column(
        Integer, 
        nullable=True,
        comment="队列位置（用于排队处理）"
    )
    
    message = Column(
        String(1024), 
        nullable=True,
        comment="处理消息或错误信息"
    )
    
    is_duplication = Column(
        Integer, 
        nullable=True,
        comment="是否重复文件：0=否，1=是"
    )
    
    ext_attributes = Column(
        String(4096), 
        nullable=True,
        comment="扩展属性（JSON格式）"
    )
    
    description = Column(
        Text, 
        nullable=True,
        comment="文件描述"
    )
    
    # BaseModel、KnowledgeMixin 和 AgentMixin 字段会自动继承：
    # - role, knowledge_type, knowledge_id, parent_knowledge_id
    # - user_id, session_id, task_id, agent_id, agent_instance_id, etc.
    # - status, creator, create_time, updater, update_time, deleted
