#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_atomic_qa.py
@Author  : agentic
@Date    : 2026/07/14
@Function:
    SectionAtomicQA Schema 定义

    存储 Section 与其原子问答（Atomic QA）之间的关联关系（v1.1 section 级抽取）。
    QA 正文（question/answer/source_chunk_ids/relevance）存储在 MongoDB
    section_data.atomic_qa 字段；QA 向量存储在 Milvus atomic_qa_store，
    通过 qa_id 关联。本表仅做关系/聚合/级联删除用，不存数组型字段。

    取代 v1.0 的 chunk_atomic_qa（chunk 级抽取遗留，已删除）。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String
from src.db.mysql.models.base_model import BaseModel, KnowledgeMixin


class SectionAtomicQA(BaseModel, KnowledgeMixin):
    """
    Section-AtomicQA 关联表

    存储每个 QA 与其所属 Section / Document 之间的关联关系。
    - 主键：qa_id（全局唯一，Milvus atomic_qa_store 主键 + MongoDB section_data.atomic_qa[].qa_id）
    - section_id：所属 section，便于按 section 批量查询/级联删除
    - document_id：所属文档，便于按文档批量查询/级联删除
    """
    __tablename__ = "section_atomic_qa"

    # 主键
    qa_id = Column(
        String(255),
        primary_key=True,
        index=True,
        comment="AtomicQA 唯一标识符（Milvus atomic_qa_store 主键，UUID 格式）"
    )

    # 所属 Section
    section_id = Column(
        String(255),
        index=True,
        nullable=False,
        comment="所属 Section ID（与 split / section_summary 阶段一致）"
    )

    # 所属文档
    document_id = Column(
        String(255),
        index=True,
        nullable=False,
        comment="所属 Document ID（document-{uuid}）"
    )

    # BaseModel 和 KnowledgeMixin 字段会自动继承：
    # - knowledge_base_id, knowledge_base_name, parent_knowledge_base_id, parent_knowledge_base_name, knowledge_type
    # - status, creator, create_time, updater, update_time, deleted
