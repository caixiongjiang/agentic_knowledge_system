#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Tag Repository
标签表的数据访问层
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from src.db.milvus.repositories.base_repository import BaseRepository
from src.db.milvus.models.kg.tag_schema import TagSchema
from src.db.milvus.milvus_base import BaseMilvusManager


class TagRepository(BaseRepository):
    """Tag表Repository
    
    提供标签表的专用查询方法
    """
    
    def __init__(self, manager: Optional[BaseMilvusManager] = None):
        """初始化
        
        Args:
            manager: Milvus连接管理器
        """
        schema = TagSchema()
        super().__init__(schema, manager)
    
    # ========== 专用查询方法 ==========
    
    def search_similar_tags(
        self,
        tag_vector: List[float],
        top_k: int = 10,
        user_id: Optional[str] = None,
        tag_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """搜索相似标签
        
        Args:
            tag_vector: 标签的向量表示
            top_k: 返回Top-K结果
            user_id: 限定用户ID
            tag_type: 限定标签类型（keyword/category/entity_type/topic）
            
        Returns:
            搜索结果列表
        """
        # 构建过滤表达式
        filter_parts = []
        if user_id:
            filter_parts.append(f"user_id == '{user_id}'")
        if tag_type:
            filter_parts.append(f"type == '{tag_type}'")
        
        filter_expr = " and ".join(filter_parts) if filter_parts else None
        
        # 执行搜索
        results = self.search(
            vectors=[tag_vector],
            vector_field="vector",
            top_k=top_k,
            filter_expr=filter_expr
        )
        
        return results[0] if results else []
    
    def get_tags_by_document(
        self,
        document_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """获取指定文档的所有标签
        
        Args:
            document_id: 文档ID
            limit: 返回数量限制
            
        Returns:
            标签列表
        """
        expr = f"document_id == '{document_id}'"
        return self.query(expr, limit=limit)
    
    def get_tags_by_type(
        self,
        tag_type: str,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """根据标签类型查询
        
        Args:
            tag_type: 标签类型（keyword/category/entity_type/topic）
            user_id: 限定用户ID（可选）
            limit: 返回数量限制
            
        Returns:
            标签列表
        """
        filter_parts = [f"type == '{tag_type}'"]
        if user_id:
            filter_parts.append(f"user_id == '{user_id}'")
        
        expr = " and ".join(filter_parts)
        return self.query(expr, limit=limit)
    
    def get_tags_by_role(
        self,
        role: str,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """根据角色查询标签
        
        Args:
            role: 角色（auto-extracted/user-defined/system）
            user_id: 限定用户ID（可选）
            limit: 返回数量限制
            
        Returns:
            标签列表
        """
        filter_parts = [f"role == '{role}'"]
        if user_id:
            filter_parts.append(f"user_id == '{user_id}'")
        
        expr = " and ".join(filter_parts)
        return self.query(expr, limit=limit)
    
    def get_tags_by_knowledge_type(
        self,
        knowledge_type: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """根据知识类型查询标签
        
        Args:
            knowledge_type: 知识类型
            limit: 返回数量限制
            
        Returns:
            标签列表
        """
        expr = f"knowledge_type == '{knowledge_type}'"
        return self.query(expr, limit=limit)
    
    def get_tags_by_knowledge_base(
        self,
        knowledge_base_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """获取指定知识库的所有标签
        
        Args:
            knowledge_base_id: 知识库ID
            limit: 返回数量限制
            
        Returns:
            标签列表
        """
        expr = f"knowledge_base_id == '{knowledge_base_id}'"
        return self.query(expr, limit=limit)
    
    def delete_by_document(self, document_id: str) -> None:
        """删除指定文档的所有标签
        
        Args:
            document_id: 文档ID
        """
        expr = f"document_id == '{document_id}'"
        self.delete(expr)
        self.logger.info(f"已删除文档 {document_id} 的所有标签")
