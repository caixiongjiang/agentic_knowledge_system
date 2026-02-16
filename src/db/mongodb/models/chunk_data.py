#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_data.py
@Author  : caixiongjiang
@Date    : 2026/1/7 16:44
@Function: 
    ChunkData Schema - Chunk数据表
    存储各种类型的chunk数据，包括文本、图片等
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional, List, Dict, Any
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING

from src.db.mongodb.models.base_model import BaseDocument


class ChunkData(BaseDocument):
    """
    Chunk数据表
    
    存储文档分块后的核心内容数据：
    - chunk_type: chunk类型
    - text: chunk文本内容
    - translation: 翻译列表
    - summary: 摘要
    - atomic_qa: 原子问答对
    """
    
    # ========== 主键字段 ==========
    id: str = Field(
        ...,
        alias="_id",
        description="chunk唯一标识（格式：chunk_<uuid>）"
    )
    
    # ========== 核心字段 ==========
    chunk_type: Optional[str] = Field(
        None,
        alias="type",
        description="chunk类型：text=文本，image=图片，table=表格，code_block=代码块"
    )
    
    text: Optional[str] = Field(
        None,
        description="chunk文本内容"
    )
    
    translation: List[Any] = Field(
        default_factory=list,
        description="chunk翻译内容列表（支持多语言）"
    )
    
    summary: Optional[str] = Field(
        None,
        description="chunk摘要"
    )
    
    atomic_qa: List[Any] = Field(
        default_factory=list,
        description="chunk原子问答对列表"
    )
    
    # ========== Pydantic 配置 ==========
    class Config:
        """Pydantic 配置"""
        populate_by_name = True  # 允许使用字段名和别名
    
    # ========== Beanie 配置 ==========
    class Settings:
        name = "chunk_data"  # MongoDB 集合名称
        use_state_management = True  # 启用状态管理
        validate_on_save = True  # 保存时验证数据
        
        # 索引定义
        indexes = [
            # 软删除 + 创建时间复合索引（常用查询）
            IndexModel(
                [("deleted", ASCENDING), ("create_time", DESCENDING)],
                name="idx_deleted_create_time"
            ),
            
            # type 字段索引（按类型筛选）
            IndexModel(
                [("type", ASCENDING)],
                name="idx_type"
            ),
        ]
    
    # ========== 自定义方法 ==========
    
    def has_text(self) -> bool:
        """检查是否包含文本"""
        return bool(self.text)
    
    def has_summary(self) -> bool:
        """检查是否有摘要"""
        return bool(self.summary)
