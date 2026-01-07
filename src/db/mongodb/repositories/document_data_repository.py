#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : document_data_repository.py
@Author  : caixiongjiang
@Date    : 2026/1/7 16:47
@Function: 
    DocumentData Repository - Document数据访问层
    提供 DocumentData 的专用查询方法
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from datetime import datetime

from src.db.mongodb.repositories.base_repository import BaseRepository
from src.db.mongodb.models.document_data import DocumentData


class DocumentDataRepository(BaseRepository[DocumentData]):
    """
    DocumentData Repository
    
    提供 DocumentData 的专用查询方法，继承 BaseRepository 的通用 CRUD 操作。
    """
    
    def __init__(self):
        """初始化 DocumentDataRepository"""
        super().__init__(DocumentData)
    
    # ========== 专用查询方法 ==========
    
    async def get_by_message_id(
        self,
        message_id: int
    ) -> Optional[DocumentData]:
        """
        根据 message_id 查询文档
        
        Args:
            message_id: 消息ID
            
        Returns:
            DocumentData 或 None
        """
        results = await self.find(
            limit=1,
            message_id=message_id
        )
        return results[0] if results else None
    
    async def find_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> List[DocumentData]:
        """
        时间范围查询
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制数量
            
        Returns:
            DocumentData 列表
        """
        results = await DocumentData.find({
            "deleted": 0,
            "create_time": {
                "$gte": start_time,
                "$lte": end_time
            }
        }).limit(limit).to_list()
        
        return results
    
    async def search_by_summary(
        self,
        keyword: str,
        language: str = "zh",
        limit: int = 10
    ) -> List[DocumentData]:
        """
        在摘要中搜索关键词
        
        Args:
            keyword: 搜索关键词
            language: 语言（zh/en）
            limit: 限制数量
            
        Returns:
            DocumentData 列表
        """
        field = "summary_zh" if language == "zh" else "summary_en"
        
        results = await DocumentData.find({
            "deleted": 0,
            field: {"$regex": keyword, "$options": "i"}  # 不区分大小写
        }).limit(limit).to_list()
        
        return results
    
    async def get_by_ids(
        self,
        ids: List[str]
    ) -> List[DocumentData]:
        """
        根据ID列表批量查询
        
        Args:
            ids: ID列表
            
        Returns:
            DocumentData 列表
        """
        if not ids:
            return []
        
        results = await DocumentData.find({
            "_id": {"$in": ids},
            "deleted": 0
        }).to_list()
        
        return results


# ========== 全局实例 ==========
document_data_repository = DocumentDataRepository()
