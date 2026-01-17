#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : element_data_repository.py
@Author  : caixiongjiang
@Date    : 2026/01/17
@Function: 
    ElementData Repository
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Dict, Any, Optional, Union
from bson import ObjectId
from beanie import PydanticObjectId
from src.db.mongodb.repositories.base_repository import BaseRepository
from src.db.mongodb.models.element_data import ElementData


class ElementDataRepository(BaseRepository[ElementData]):
    """ElementData Repository"""
    
    def __init__(self):
        """初始化 ElementDataRepository"""
        super().__init__(ElementData)
    
    # ========== 专用查询方法 ==========
    
    async def get_by_ids(
        self,
        element_ids: List[str]
    ) -> List[ElementData]:
        """
        批量获取元素内容（核心方法）
        
        Args:
            element_ids: 元素ID列表（来自 MySQL element_id）
        
        Returns:
            ElementData 列表
        
        Examples:
            >>> # 从 MySQL 获取 element_id
            >>> elements = element_meta_info_repo.get_by_page_index(session, 0)
            >>> element_ids = [e.element_id for e in elements]
            >>> 
            >>> # 批量获取内容
            >>> contents = await repo.get_by_ids(element_ids)
        """
        if not element_ids:
            return []
        
        # 注意：这里的 _id 是字符串类型（与 MySQL 的 element_id 一致）
        results = await ElementData.find({
            "_id": {"$in": element_ids},
            "deleted": 0
        }).to_list()
        
        self.logger.debug(f"批量获取 {len(results)} 个元素内容")
        return results
    
    async def get_by_element_type(
        self,
        element_type: str,
        limit: int = 100
    ) -> List[ElementData]:
        """
        根据类型查询
        
        Args:
            element_type: 元素类型（text, image, table, discarded）
            limit: 限制返回数量
        
        Returns:
            ElementData 列表
        """
        return await self.find(
            limit=limit,
            type=element_type,
            sort=[("create_time", -1)]
        )
    
    async def create_element(
        self,
        element_id: str,
        element_type: str,
        content: Dict[str, Any],
        creator: str = ""
    ) -> ElementData:
        """
        创建元素内容
        
        Args:
            element_id: 元素ID（与 MySQL element_id 一致）
            element_type: 元素类型
            content: 内容字典
            creator: 创建者
        
        Returns:
            创建的 ElementData 实例
        
        Examples:
            >>> element = await repo.create_element(
            ...     element_id="elem_001",
            ...     element_type="text",
            ...     content={"text": "some text"},
            ...     creator="user1"
            ... )
        """
        return await self.create(
            creator=creator,
            _id=element_id,  # 使用自定义 ID
            type=element_type,
            content=content
        )
    
    async def update_element_content(
        self,
        element_id: str,
        content: Dict[str, Any],
        updater: str = ""
    ) -> Optional[ElementData]:
        """
        更新元素内容
        
        Args:
            element_id: 元素ID
            content: 新的内容字典
            updater: 更新者
        
        Returns:
            更新后的 ElementData，失败返回 None
        """
        return await self.update(
            doc_id=element_id,
            updater=updater,
            content=content
        )
    
    async def bulk_create_elements(
        self,
        elements: List[Dict[str, Any]],
        creator: str = ""
    ) -> List[ElementData]:
        """
        批量创建元素内容
        
        Args:
            elements: 元素列表，每个元素包含 element_id, type, content
            creator: 创建者
        
        Returns:
            创建的 ElementData 列表
        
        Examples:
            >>> elements = [
            ...     {
            ...         "_id": "elem_001",
            ...         "type": "text",
            ...         "content": {"text": "..."}
            ...     },
            ...     {
            ...         "_id": "elem_002",
            ...         "type": "image",
            ...         "content": {"image_caption": [...]}
            ...     }
            ... ]
            >>> created = await repo.bulk_create_elements(elements, creator="user1")
        """
        return await self.create_batch(
            data_list=elements,
            creator=creator
        )
    
    async def bulk_upsert_elements(
        self,
        elements: List[Dict[str, Any]],
        creator: str = "",
        updater: str = ""
    ) -> int:
        """
        批量创建或更新元素内容
        
        Args:
            elements: 元素列表，每个元素包含 _id, type, content
            creator: 创建者
            updater: 更新者
        
        Returns:
            操作的记录数量
        
        Examples:
            >>> elements = [
            ...     {"_id": "elem_001", "type": "text", "content": {"text": "..."}},
            ...     {"_id": "elem_002", "type": "image", "content": {"image_caption": [...]}}
            ... ]
            >>> count = await repo.bulk_upsert_elements(elements, creator="user1")
        """
        return await self.upsert_batch_optimized(
            data_list=elements,
            id_field="_id",
            creator=creator,
            updater=updater
        )
    
    async def delete_elements_by_ids(
        self,
        element_ids: List[str],
        updater: str = ""
    ) -> int:
        """
        批量软删除元素内容
        
        Args:
            element_ids: 元素ID列表
            updater: 更新者
        
        Returns:
            删除的数量
        """
        return await self.bulk_delete_by_ids(
            ids=element_ids,
            updater=updater
        )
    
    async def count_by_type(
        self,
        element_type: str
    ) -> int:
        """
        统计指定类型的元素数量
        
        Args:
            element_type: 元素类型
        
        Returns:
            数量
        """
        return await self.count(type=element_type)


# ========== 全局实例 ==========
element_data_repository = ElementDataRepository()
