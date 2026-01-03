#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
SPO Repository
SPO三元组表的数据访问层
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from src.db.milvus.respositories.base_repository import BaseRepository
from src.db.milvus.models.kg.spo_schema import (
    SPOSchema,
    SPOSchemaZh,
    SPOSchemaEn
)
from src.db.milvus.milvus_base import BaseMilvusManager


class SPORepository(BaseRepository):
    """SPO三元组表Repository
    
    提供SPO三元组表的专用查询方法
    
    注意：SPO表使用INT64自增主键，与其他表（VARCHAR主键）不同
    """
    
    def __init__(self, manager: Optional[BaseMilvusManager] = None, language: str = "zh"):
        """初始化
        
        Args:
            manager: Milvus连接管理器
            language: 语言版本 ("zh"/"en")
        """
        if language == "zh":
            schema = SPOSchemaZh()
        elif language == "en":
            schema = SPOSchemaEn()
        else:
            schema = SPOSchema()
        
        super().__init__(schema, manager)
    
    # ========== 专用查询方法 ==========
    
    def search_by_relation(
        self,
        relation_vector: List[float],
        top_k: int = 10,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        knowledge_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """根据关系向量搜索相似的三元组
        
        Args:
            relation_vector: 关系的向量表示
            top_k: 返回Top-K结果
            user_id: 限定用户ID
            document_id: 限定文档ID
            knowledge_type: 限定知识类型
            
        Returns:
            搜索结果列表
        """
        # 构建过滤表达式
        filter_parts = []
        if user_id:
            filter_parts.append(f"user_id == '{user_id}'")
        if document_id:
            filter_parts.append(f"document_id == '{document_id}'")
        if knowledge_type:
            filter_parts.append(f"knowledge_type == '{knowledge_type}'")
        
        filter_expr = " and ".join(filter_parts) if filter_parts else None
        
        # 执行搜索
        results = self.search(
            vectors=[relation_vector],
            vector_field="vector",
            top_k=top_k,
            filter_expr=filter_expr
        )
        
        return results[0] if results else []
    
    def get_triples_by_document(
        self,
        document_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """获取指定文档的所有三元组
        
        Args:
            document_id: 文档ID
            limit: 返回数量限制
            
        Returns:
            三元组列表
        """
        expr = f"document_id == '{document_id}'"
        return self.query(expr, limit=limit)
    
    def get_triples_by_tag(
        self,
        tag_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """根据标签查询三元组
        
        Args:
            tag_id: 标签ID
            limit: 返回数量限制
            
        Returns:
            三元组列表
        """
        expr = f"tag_id == '{tag_id}'"
        return self.query(expr, limit=limit)
    
    def get_triples_by_type(
        self,
        triple_type: str,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """根据三元组类型查询
        
        Args:
            triple_type: 三元组类型（如：entity-relation/event-relation/attribute）
            user_id: 限定用户ID（可选）
            limit: 返回数量限制
            
        Returns:
            三元组列表
        """
        filter_parts = [f"type == '{triple_type}'"]
        if user_id:
            filter_parts.append(f"user_id == '{user_id}'")
        
        expr = " and ".join(filter_parts)
        return self.query(expr, limit=limit)
    
    def get_triples_by_knowledge_base(
        self,
        knowledge_base_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """获取指定知识库的所有三元组
        
        Args:
            knowledge_base_id: 知识库ID
            limit: 返回数量限制
            
        Returns:
            三元组列表
        """
        expr = f"knowledge_base_id == '{knowledge_base_id}'"
        return self.query(expr, limit=limit)
    
    def delete_by_document(self, document_id: str) -> None:
        """删除指定文档的所有三元组
        
        Args:
            document_id: 文档ID
        """
        expr = f"document_id == '{document_id}'"
        self.delete(expr)
        self.logger.info(f"已删除文档 {document_id} 的所有SPO三元组")
    
    def delete_by_tag(self, tag_id: str) -> None:
        """删除指定标签关联的所有三元组
        
        Args:
            tag_id: 标签ID
        """
        expr = f"tag_id == '{tag_id}'"
        self.delete(expr)
        self.logger.info(f"已删除标签 {tag_id} 关联的所有SPO三元组")
