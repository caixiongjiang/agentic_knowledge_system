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
    
    # ========== 专用查询方法 ==========
    
    def search_by_vector(
        self,
        query_vector: List[float],
        top_k: int = 10,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """根据向量搜索相似的增强分块
        
        Args:
            query_vector: 查询向量
            top_k: 返回Top-K结果
            user_id: 限定用户ID
            document_id: 限定文档ID
            
        Returns:
            搜索结果列表
        """
        # 构建过滤表达式
        filter_parts = []
        if user_id:
            filter_parts.append(f"user_id == '{user_id}'")
        if document_id:
            filter_parts.append(f"document_id == '{document_id}'")
        
        filter_expr = " and ".join(filter_parts) if filter_parts else None
        
        # 执行搜索
        results = self.search(
            vectors=[query_vector],
            vector_field="vector",
            top_k=top_k,
            filter_expr=filter_expr
        )
        
        return results[0] if results else []
    
