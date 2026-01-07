#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_data_repository.py
@Author  : caixiongjiang
@Date    : 2026/1/7 16:46
@Function: 
    ChunkData Repository - Chunk数据访问层
    提供 ChunkData 的专用查询方法
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional, Union
from datetime import datetime
from bson import ObjectId
from beanie import PydanticObjectId

from src.db.mongodb.repositories.base_repository import BaseRepository
from src.db.mongodb.models.chunk_data import ChunkData


class ChunkDataRepository(BaseRepository[ChunkData]):
    """
    ChunkData Repository
    
    提供 ChunkData 的专用查询方法，继承 BaseRepository 的通用 CRUD 操作。
    """
    
    def __init__(self):
        """初始化 ChunkDataRepository"""
        super().__init__(ChunkData)
    
    # ========== 专用查询方法 ==========
    
    async def get_by_message_id(
        self,
        message_id: int
    ) -> List[ChunkData]:
        """
        根据 message_id 查询所有 chunk
        
        Args:
            message_id: 消息ID
            
        Returns:
            ChunkData 列表
        """
        return await self.find(
            limit=1000,
            message_id=message_id,
            sort=[("create_time", 1)]
        )
    
    async def find_by_type(
        self,
        chunk_type: str,
        limit: int = 100
    ) -> List[ChunkData]:
        """
        根据类型查询 chunk
        
        Args:
            chunk_type: chunk类型（text/image/table）
            limit: 限制数量
            
        Returns:
            ChunkData 列表
        """
        # 注意：chunk_type 字段在数据库中的实际名称是 "type"（因为设置了 alias）
        return await self.find(
            limit=limit,
            type=chunk_type,  # 使用数据库中的字段名 "type"
            sort=[("create_time", -1)]
        )
    
    async def find_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> List[ChunkData]:
        """
        时间范围查询
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制数量
            
        Returns:
            ChunkData 列表
        """
        results = await ChunkData.find({
            "deleted": 0,
            "create_time": {
                "$gte": start_time,
                "$lte": end_time
            }
        }).limit(limit).to_list()
        
        return results
    
    async def search_by_text(
        self,
        keyword: str,
        limit: int = 10
    ) -> List[ChunkData]:
        """
        文本模糊搜索
        
        Args:
            keyword: 搜索关键词
            limit: 限制数量
            
        Returns:
            ChunkData 列表
        """
        results = await ChunkData.find({
            "deleted": 0,
            "text": {"$regex": keyword, "$options": "i"}  # 不区分大小写
        }).limit(limit).to_list()
        
        return results
    
    async def get_by_ids(
        self,
        ids: List[Union[str, ObjectId, PydanticObjectId]]
    ) -> List[ChunkData]:
        """
        根据ID列表批量查询
        
        Args:
            ids: ID列表（字符串、ObjectId 或 PydanticObjectId）
            
        Returns:
            ChunkData 列表
        """
        if not ids:
            return []
        
        # 类型转换：确保所有ID都是ObjectId类型
        object_ids = []
        for id_val in ids:
            if isinstance(id_val, str):
                try:
                    object_ids.append(PydanticObjectId(id_val))
                except Exception:
                    continue
            elif isinstance(id_val, (ObjectId, PydanticObjectId)):
                object_ids.append(id_val)
        
        if not object_ids:
            return []
        
        results = await ChunkData.find({
            "_id": {"$in": object_ids},
            "deleted": 0
        }).to_list()
        
        return results
    
    async def count_by_type(
        self,
        chunk_type: str
    ) -> int:
        """
        统计指定类型的 chunk 数量
        
        Args:
            chunk_type: chunk类型
            
        Returns:
            数量
        """
        # 注意：chunk_type 字段在数据库中的实际名称是 "type"（因为设置了 alias）
        return await self.count(type=chunk_type)


# ========== 全局实例 ==========
chunk_data_repository = ChunkDataRepository()
