#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : tombstone.py
@Author  : caixiongjiang
@Date    : 2026/09/01
@Function:
    待清理文件的墓碑查询，供检索侧排除已删除内容
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import time
from typing import Dict, List, Optional, Tuple

from loguru import logger

from src.db.mysql.connection.factory import get_mysql_manager
from src.db.mysql.repositories.business.workspace_file_system_repo import (
    workspace_file_system_repo,
)
from src.retrieve.types.query import MetadataFilter

# 墓碑存活时间以秒计（清理 worker 跑完就物理删行），缓存只为压掉同一轮召回里的重复查询
_CACHE_TTL_SECONDS = 5.0

_cache: Dict[Tuple[str, Optional[str]], Tuple[float, List[str]]] = {}


def get_tombstoned_document_ids(
    user_id: str,
    knowledge_base_id: Optional[str] = None,
) -> List[str]:
    """获取已删除但尚未清理完的 document_id，用于在检索中排除

    删除是「同步写墓碑 + 异步清理」的：向量在 worker 跑完之前仍留在 Milvus 里，
    而且 Milvus 搜索走默认的 Bounded 一致性，即便已经删除并 flush，
    短窗口内依然可能召回。所以排除不能依赖清理速度，必须显式过滤。

    查询失败时返回空列表：此时排除失效，宁可短暂多召回，也不要让检索整体挂掉。

    Args:
        user_id: 用户ID
        knowledge_base_id: 可选，按知识库缩小范围

    Returns:
        document_id 列表，通常为空或个位数
    """
    if not user_id:
        return []

    key = (user_id, knowledge_base_id)
    now = time.monotonic()

    cached = _cache.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    try:
        manager = get_mysql_manager()
        with manager.get_session() as session:
            document_ids = workspace_file_system_repo.get_tombstoned_document_ids(
                session, user_id, knowledge_base_id
            )
    except Exception as e:
        logger.warning(f"查询待清理 document_id 失败，本轮不排除: {e}")
        return []

    _cache[key] = (now, document_ids)
    return document_ids


def invalidate(user_id: str) -> None:
    """删除受理后立刻失效缓存，避免刚删的文件在 TTL 内仍被召回"""
    for key in [k for k in _cache if k[0] == user_id]:
        _cache.pop(key, None)


def exclude_deleted(filters: MetadataFilter) -> MetadataFilter:
    """就地把该用户待清理的文件从检索范围里剔除

    所有构造 ``MetadataFilter`` 去做召回的地方都应该调一次，
    否则已删文件的向量在清理完成前仍会被召回到回答里。

    Returns:
        传入的 filters 本身，便于链式书写
    """
    excluded = get_tombstoned_document_ids(
        filters.user_id or "", filters.knowledge_base_id
    )
    if excluded:
        filters.exclude_document_ids = excluded
    return filters
