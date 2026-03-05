#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Enhanced Chunk Repository
增强分块表的数据访问层
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from src.db.milvus.repositories.base_repository import BaseRepository
from src.db.milvus.models.enhanced.enhanced_chunk_schema import EnhancedChunkSchema
from src.db.milvus import BaseMilvusManager


class EnhancedChunkRepository(BaseRepository):
    """Enhanced Chunk表Repository
    
    提供增强分块表的专用查询方法
    """
    
    def __init__(self, manager: Optional[BaseMilvusManager] = None):
        """初始化
        
        Args:
            manager: Milvus连接管理器
        """
        schema = EnhancedChunkSchema()
        super().__init__(schema, manager)
    
    # ========== 过滤表达式辅助 ==========

    @staticmethod
    def _build_filter(
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        knowledge_base_id: Optional[str] = None,
    ) -> Optional[str]:
        parts: List[str] = []
        if user_id:
            parts.append(f"user_id == '{user_id}'")
        if document_id:
            parts.append(f"document_id == '{document_id}'")
        if knowledge_base_id:
            parts.append(f"knowledge_base_id == '{knowledge_base_id}'")
        return " and ".join(parts) if parts else None
    
    # ========== 专用查询方法 ==========
    
    def search_by_vector(
        self,
        query_vector: List[float],
        top_k: int = 10,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        knowledge_base_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """根据稠密向量搜索相似的增强分块
        
        Args:
            query_vector: 查询向量
            top_k: 返回Top-K结果
            user_id: 限定用户ID
            document_id: 限定文档ID
            knowledge_base_id: 限定知识库ID
            
        Returns:
            搜索结果列表
        """
        filter_expr = self._build_filter(user_id, document_id, knowledge_base_id)
        results = self.search(
            vectors=[query_vector],
            vector_field="vector",
            top_k=top_k,
            filter_expr=filter_expr,
        )
        return results[0] if results else []

    def search_by_sparse_vector(
        self,
        query_sparse_vector: Dict[int, float],
        top_k: int = 10,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        knowledge_base_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """根据稀疏向量搜索增强分块（BM25 关键词检索）

        Args:
            query_sparse_vector: 查询稀疏向量 {dim_idx: weight}
            top_k: 返回 Top-K 结果
            user_id: 限定用户 ID
            document_id: 限定文档 ID
            knowledge_base_id: 限定知识库 ID

        Returns:
            搜索结果列表
        """
        filter_expr = self._build_filter(user_id, document_id, knowledge_base_id)
        results = self.search_sparse(
            sparse_vectors=[query_sparse_vector],
            sparse_field="sparse_vector",
            top_k=top_k,
            filter_expr=filter_expr,
        )
        return results[0] if results else []
    
