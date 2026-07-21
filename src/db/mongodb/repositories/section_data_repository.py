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

from typing import Any, Dict, List, Optional
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

    async def get_atomic_qa_by_qa_ids(
        self,
        qa_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        检索侧下钻：按 qa_id 列表反查所属 section_data.atomic_qa 条目。

        遵循「Milvus 返回 id → Mongo 取数」原则：
        Milvus atomic_qa_store 命中后拿到 qa_id/section_id，
        本方法按 qa_id 在 section_data.atomic_qa[] 中定位，取出
        question/answer/source_chunk_ids 供 QAItem 填充。

        Args:
            qa_ids: qa_id 列表

        Returns:
            {qa_id: atomic_qa_dict} 映射（dict 含 question/answer/source_chunk_ids/qa_type/relevance）
        """
        if not qa_ids:
            return {}
        # 利用 idx_atomic_qa_qa_id 索引
        results = await SectionData.find({
            "deleted": 0,
            "atomic_qa.qa_id": {"$in": qa_ids},
        }).to_list()

        qa_map: Dict[str, Dict[str, Any]] = {}
        for sec in results:
            section_id = sec.id
            for qa in (sec.atomic_qa or []):
                qid = qa.get("qa_id")
                if qid and qid in qa_ids:
                    # 注入 section_id，供检索侧下钻回填 QAItem.metadata
                    entry = dict(qa)
                    entry["section_id"] = section_id
                    qa_map[qid] = entry
        return qa_map


# ========== 全局实例 ==========
section_data_repository = SectionDataRepository()
