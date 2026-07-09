#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Summary Repository - 摘要表数据访问层

按 role 拆分为两个独立 Repository：
- FileSummaryRepository    → file_summary_store   (文档级摘要)
- SectionSummaryRepository → section_summary_store (章节级摘要)

两者字段与查询方法完全一致，仅绑定 Schema 不同。
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from src.db.milvus.repositories.base_repository import BaseRepository
from src.db.milvus.models.extract.summary_schema import (
    FileSummarySchema,
    SectionSummarySchema,
)
from src.db.milvus import BaseMilvusManager


class _BaseSummaryRepository(BaseRepository):
    """摘要 Repository 公共方法基类

    子类只需绑定对应 Schema，查询方法全部复用。
    """

    def __init__(
        self,
        schema: Any,
        manager: Optional[BaseMilvusManager] = None,
    ):
        super().__init__(schema, manager)

    def get_summaries_by_document(
        self,
        document_id: str,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """获取指定文档的所有摘要"""
        expr = f"document_id == '{document_id}'"
        return self.query(expr, limit=limit)

    def get_summaries_by_role(
        self,
        role: str,
        document_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """根据角色查询摘要"""
        filter_parts = [f"role == '{role}'"]
        if document_id:
            filter_parts.append(f"document_id == '{document_id}'")
        expr = " and ".join(filter_parts)
        return self.query(expr, limit=limit)

    def get_summaries_by_knowledge_base(
        self,
        knowledge_base_id: str,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """获取指定知识库的所有摘要"""
        expr = f"knowledge_base_id == '{knowledge_base_id}'"
        return self.query(expr, limit=limit)

    def delete_by_document(self, document_id: str) -> None:
        """删除指定文档的所有摘要"""
        expr = f"document_id == '{document_id}'"
        self.delete(expr)
        self.logger.info(f"已删除文档 {document_id} 的所有摘要")


class FileSummaryRepository(_BaseSummaryRepository):
    """文档级摘要 Repository → file_summary_store"""

    def __init__(self, manager: Optional[BaseMilvusManager] = None):
        super().__init__(FileSummarySchema(), manager)


class SectionSummaryRepository(_BaseSummaryRepository):
    """章节级摘要 Repository → section_summary_store"""

    def __init__(self, manager: Optional[BaseMilvusManager] = None):
        super().__init__(SectionSummarySchema(), manager)
