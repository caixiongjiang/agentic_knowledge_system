#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : knowledge_base.py
@Author  : caixiongjiang
@Date    : 2026/02/19
@Function: 
    KnowledgeBase Schema 定义
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String, Text, Index
from src.db.mysql.models.base_model import BaseModel


class KnowledgeBase(BaseModel):
    """
    知识库表

    管理用户的知识库，每个知识库下可以包含多个文件夹和文件。
    支持层级结构（通过 parent_knowledge_base_id 自关联）。

    删除规则：
    - 只有知识库下（含回收站中）不存在任何文件时才允许删除
    - 空文件夹不影响删除
    - 删除为物理删除，不进回收站
    """
    __tablename__ = "knowledge_base"

    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_user_parent", "user_id", "parent_knowledge_base_id"),
    )

    knowledge_base_id = Column(
        String(64),
        primary_key=True,
        comment="知识库ID（UUID格式）",
    )

    user_id = Column(
        String(64),
        nullable=False,
        comment="所属用户ID",
    )

    knowledge_base_name = Column(
        String(255),
        nullable=False,
        comment="知识库名称",
    )

    parent_knowledge_base_id = Column(
        String(64),
        nullable=True,
        comment="父知识库ID（NULL 表示顶级知识库）",
    )

    knowledge_type = Column(
        String(255),
        default="common_file",
        nullable=False,
        comment="知识库类型：common_file=普通文件",
    )

    description = Column(
        Text,
        nullable=True,
        comment="知识库描述",
    )

    # BaseModel 字段会自动继承：
    # - status, creator, create_time, updater, update_time, deleted
