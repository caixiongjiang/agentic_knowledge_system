#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_data_repository.py
@Author  : caixiongjiang
@Date    : 2026/1/7 16:46
@Function: 
    SectionData Repository - Section数据访问层
    提供 SectionData 的专用查询方法
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from datetime import datetime

from src.db.mongodb.repositories.base_repository import BaseRepository
from src.db.mongodb.models.section_data import SectionData


class SectionDataRepository(BaseRepository[SectionData]):
    """
    SectionData Repository
    
    提供 SectionData 的专用查询方法，继承 BaseRepository 的通用 CRUD 操作。
    """
    
    def __init__(self):
        """初始化 SectionDataRepository"""
        super().__init__(SectionData)
    
    # ========== 专用查询方法 ==========
    
    async def get_by_message_id(
        self,
        message_id: int
    ) -> List[SectionData]:
        """
        根据 message_id 查询所有 section
        
        Args:
            message_id: 消息ID
            
        Returns:
            SectionData 列表
        """
        return await self.find(
            limit=1000,
            message_id=message_id,
            sort=[("create_time", 1)]
        )
    
    async def find_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> List[SectionData]:
        """
        时间范围查询
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制数量
            
        Returns:
            SectionData 列表
        """
        results = await SectionData.find({
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
    ) -> List[SectionData]:
        """
        文本模糊搜索
        
        Args:
            keyword: 搜索关键词
            limit: 限制数量
            
        Returns:
            SectionData 列表
        """
        results = await SectionData.find({
            "deleted": 0,
            "text": {"$regex": keyword, "$options": "i"}  # 不区分大小写
        }).limit(limit).to_list()
        
        return results
    
    async def get_by_ids(
        self,
        ids: List[str]
    ) -> List[SectionData]:
        """
        根据ID列表批量查询
        
        Args:
            ids: ID列表
            
        Returns:
            SectionData 列表
        """
        if not ids:
            return []
        
        results = await SectionData.find({
            "_id": {"$in": ids},
            "deleted": 0
        }).to_list()
        
        return results


# ========== 全局实例 ==========
section_data_repository = SectionDataRepository()
