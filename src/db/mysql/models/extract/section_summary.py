#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_summary.py
@Author  : agentic
@Date    : 2026/07/02
@Function:
    SectionSummary Schema 定义

    存储 Section 与其摘要（Summary）之间的关联关系。
    摘要正文存储在 MongoDB section_data.summary 字段；
    摘要向量存储在 Milvus summary collection（role=section_summary），
    通过 summary_id 关联。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin


class SectionSummary(BaseModel, KnowledgeMixin):
    """
    Section-Summary 关联表

    存储每个 Section 与其摘要之间的关联关系。
    - 主键：section_id（与 split 阶段一致，全局唯一）
    - summary_id：Milvus summary collection 主键 + MongoDB section_data.summary.summary_id
    - document_id：所属文档，便于按文档批量删除/查询
    """
    __tablename__ = "section_summary"

    # 主键
    section_id = Column(
        String(255),
        primary_key=True,
        index=True,
        comment="Section 唯一标识符（与 split 阶段一致，UUID 格式）"
    )

    # 所属文档
    document_id = Column(
        String(255),
        index=True,
        nullable=False,
        comment="所属 Document ID（document-{uuid}）"
    )

    # 关联字段
    summary_id = Column(
        String(255),
        index=True,
        nullable=False,
        comment="关联的 Summary ID（Milvus summary collection 主键）"
    )

    # BaseModel 和 KnowledgeMixin 字段会自动继承：
    # - knowledge_base_id, knowledge_base_name, parent_knowledge_base_id, parent_knowledge_base_name, knowledge_type
    # - status, creator, create_time, updater, update_time, deleted
