#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : _filter_helper.py
@Author  : caixiongjiang
@Date    : 2026/04/17
@Function:
    为 Mongo 字面检索（ExactMatch / BooleanSearch）补齐 ``MetadataFilter`` 支持。

    背景:
        ``chunk_data`` 集合本身不存 knowledge_base_id / document_id，
        这些归属字段保存在 MySQL ``chunk_section_document`` 关系表里。
        因此 Mongo 侧无法直接通过 ``$match`` 完成元数据过滤，需要先去
        MySQL 解析出符合条件的 chunk_id 集合，再在 Mongo 查询里加 ``_id $in``。

@Modify History:
    2026/04/17 - 新增, 修复 ExactMatch / BooleanSearch 不应用 filters 的 bug
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from typing import List, Optional

from loguru import logger

from src.retrieve.types.query import MetadataFilter


_FILTER_FIELDS = (
    "knowledge_base_id",
    "document_id",
    "document_ids",
    "section_ids",
    "user_id",
)


def filter_has_chunk_scope(filters: Optional[MetadataFilter]) -> bool:
    """``filters`` 是否包含可用于裁剪 chunk_id 的字段"""
    if filters is None:
        return False
    return any(getattr(filters, f, None) for f in _FILTER_FIELDS)


def resolve_chunk_ids_from_filters(
    filters: Optional[MetadataFilter],
) -> Optional[List[str]]:
    """根据 ``MetadataFilter`` 在 MySQL 中解析出符合条件的 chunk_id 列表

    Returns:
        - ``None``: ``filters`` 为空或不含可裁剪字段，调用方应**不施加**任何 ID 限制
        - ``List[str]``: 命中的 chunk_id 列表（**可能为空** → 表示无任何 chunk 命中
          过滤条件，调用方应直接返回空结果，避免回退到全量查询）
    """
    if not filter_has_chunk_scope(filters):
        return None

    try:
        from sqlalchemy.orm import Session

        from src.db.mysql.connection.factory import get_mysql_manager
        from src.db.mysql.models.base.chunk_section_document import (
            ChunkSectionDocument,
        )
    except Exception as e:
        logger.warning(f"MySQL 模块加载失败，跳过 lexical filter 透传: {e}")
        return None

    try:
        manager = get_mysql_manager()
        with manager.get_session() as session:  # type: Session
            q = session.query(ChunkSectionDocument.chunk_id).filter(
                ChunkSectionDocument.deleted == 0,
            )
            if filters.knowledge_base_id:
                q = q.filter(
                    ChunkSectionDocument.knowledge_base_id == filters.knowledge_base_id,
                )
            if filters.document_id:
                q = q.filter(
                    ChunkSectionDocument.document_id == filters.document_id,
                )
            if filters.document_ids:
                q = q.filter(
                    ChunkSectionDocument.document_id.in_(list(filters.document_ids)),
                )
            if filters.section_ids:
                q = q.filter(
                    ChunkSectionDocument.section_id.in_(list(filters.section_ids)),
                )

            rows = q.all()
            chunk_ids = [r[0] for r in rows if r and r[0]]
            logger.debug(
                f"resolve_chunk_ids_from_filters: 解析出 {len(chunk_ids)} 个 chunk_id"
            )
            return chunk_ids
    except Exception as e:
        logger.warning(f"resolve_chunk_ids_from_filters 执行失败: {e}")
        return None
