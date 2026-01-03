#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Chunk Repository
文本分块表的数据访问层
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from src.db.milvus.respositories.base_repository import BaseRepository
from src.db.milvus.models.base.chunk_schema import ChunkSchema, ChunkSchemaZh, ChunkSchemaEn
from src.db.milvus.milvus_base import BaseMilvusManager


class ChunkRepository(BaseRepository):
    """Chunk表Repository
    
    提供chunk表的专用查询方法
    """
    
    def __init__(self, manager: Optional[BaseMilvusManager] = None, language: str = "zh"):
        """初始化
        
        Args:
            manager: Milvus连接管理器
            language: 语言版本 ("zh"/"en")
        """
        if language == "zh":
            schema = ChunkSchemaZh()
        elif language == "en":
            schema = ChunkSchemaEn()
        else:
            schema = ChunkSchema()
        
        super().__init__(schema, manager)
    
    # ========== 专用查询方法 ==========
    
    def search_by_vector(
        self,
        query_vector: List[float],
        top_k: int = 10,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        knowledge_base_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """根据向量搜索相似分块
        
        Args:
            query_vector: 查询向量
            top_k: 返回Top-K结果
            user_id: 限定用户ID
            document_id: 限定文档ID
            knowledge_base_id: 限定知识库ID
            
        Returns:
            搜索结果列表
        """
        # 构建过滤表达式
        filter_parts = []
        if user_id:
            filter_parts.append(f"user_id == '{user_id}'")
        if document_id:
            filter_parts.append(f"document_id == '{document_id}'")
        if knowledge_base_id:
            filter_parts.append(f"knowledge_base_id == '{knowledge_base_id}'")
        
        filter_expr = " and ".join(filter_parts) if filter_parts else None
        
        # 执行搜索
        results = self.search(
            vectors=[query_vector],
            vector_field="vector",
            top_k=top_k,
            filter_expr=filter_expr
        )
        
        return results[0] if results else []
    
    def get_chunks_by_document(
        self,
        document_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """获取指定文档的所有分块
        
        Args:
            document_id: 文档ID
            limit: 返回数量限制
            
        Returns:
            分块列表
        """
        expr = f"document_id == '{document_id}'"
        return self.query(expr, limit=limit)
    
    def get_chunks_by_knowledge_base(
        self,
        knowledge_base_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """获取指定知识库的所有分块
        
        Args:
            knowledge_base_id: 知识库ID
            limit: 返回数量限制
            
        Returns:
            分块列表
        """
        expr = f"knowledge_base_id == '{knowledge_base_id}'"
        return self.query(expr, limit=limit)
    
    def delete_by_document(self, document_id: str) -> None:
        """删除指定文档的所有分块
        
        Args:
            document_id: 文档ID
        """
        expr = f"document_id == '{document_id}'"
        self.delete(expr)
        self.logger.info(f"已删除文档 {document_id} 的所有chunks")
