#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Summary Repository
摘要表的数据访问层
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from src.db.milvus.repositories.base_repository import BaseRepository
from src.db.milvus.models.extract.summary_schema import SummarySchema
from src.db.milvus import BaseMilvusManager


class SummaryRepository(BaseRepository):
    """Summary表Repository
    
    提供摘要表的专用查询方法
    """
    
    def __init__(self, manager: Optional[BaseMilvusManager] = None):
        """初始化
        
        Args:
            manager: Milvus连接管理器
        """
        schema = SummarySchema()
        super().__init__(schema, manager)
    
    # ========== 专用查询方法 ==========
    
    def search_by_vector(
        self,
        query_vector: List[float],
        top_k: int = 10,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        summary_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """根据向量搜索相似摘要
        
        Args:
            query_vector: 查询向量
            top_k: 返回Top-K结果
            user_id: 限定用户ID
            document_id: 限定文档ID
            summary_type: 限定摘要类型（extractive/abstractive/hybrid）
            
        Returns:
            搜索结果列表
        """
        # 构建过滤表达式
        filter_parts = []
        if user_id:
            filter_parts.append(f"user_id == '{user_id}'")
        if document_id:
            filter_parts.append(f"document_id == '{document_id}'")
        if summary_type:
            filter_parts.append(f"type == '{summary_type}'")
        
        filter_expr = " and ".join(filter_parts) if filter_parts else None
        
        # 执行搜索
        results = self.search(
            vectors=[query_vector],
            vector_field="vector",
            top_k=top_k,
            filter_expr=filter_expr
        )
        
        return results[0] if results else []
    
    def get_summaries_by_document(
        self,
        document_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """获取指定文档的所有摘要
        
        Args:
            document_id: 文档ID
            limit: 返回数量限制
            
        Returns:
            摘要列表
        """
        expr = f"document_id == '{document_id}'"
        return self.query(expr, limit=limit)
    
    def get_summaries_by_type(
        self,
        summary_type: str,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """根据摘要类型查询
        
        Args:
            summary_type: 摘要类型（extractive/abstractive/hybrid）
            user_id: 限定用户ID（可选）
            limit: 返回数量限制
            
        Returns:
            摘要列表
        """
        filter_parts = [f"type == '{summary_type}'"]
        if user_id:
            filter_parts.append(f"user_id == '{user_id}'")
        
        expr = " and ".join(filter_parts)
        return self.query(expr, limit=limit)
    
    def get_summaries_by_role(
        self,
        role: str,
        document_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """根据角色查询摘要
        
        Args:
            role: 角色（document_summary/section_summary/chunk_summary）
            document_id: 限定文档ID（可选）
            limit: 返回数量限制
            
        Returns:
            摘要列表
        """
        filter_parts = [f"role == '{role}'"]
        if document_id:
            filter_parts.append(f"document_id == '{document_id}'")
        
        expr = " and ".join(filter_parts)
        return self.query(expr, limit=limit)
    
    def get_summaries_by_knowledge_base(
        self,
        knowledge_base_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """获取指定知识库的所有摘要
        
        Args:
            knowledge_base_id: 知识库ID
            limit: 返回数量限制
            
        Returns:
            摘要列表
        """
        expr = f"knowledge_base_id == '{knowledge_base_id}'"
        return self.query(expr, limit=limit)
    
    def delete_by_document(self, document_id: str) -> None:
        """删除指定文档的所有摘要
        
        Args:
            document_id: 文档ID
        """
        expr = f"document_id == '{document_id}'"
        self.delete(expr)
        self.logger.info(f"已删除文档 {document_id} 的所有摘要")
