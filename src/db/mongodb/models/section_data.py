#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_data.py
@Author  : caixiongjiang
@Date    : 2026/1/7 16:44
@Function: 
    SectionData Schema - 章节数据表
    存储文档的章节数据
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional, List, Dict, Any
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING

from src.db.mongodb.models.base_model import BaseDocument


class SectionData(BaseDocument):
    """
    Section数据表
    
    存储文档的章节数据，用于组织文档的层级结构。
    """
    
    # ========== 基础字段 ==========
    message_id: Optional[int] = Field(
        None,
        description="消息ID：消息唯一标识符，来自global_id_generator"
    )
    
    # ========== 文本内容 ==========
    text: Optional[str] = Field(
        None,
        description="section文本内容"
    )
    
    translation: List[Any] = Field(
        default_factory=list,
        description="section翻译内容列表（支持多语言）"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="section元数据（JSON格式，存储额外信息）"
    )
    
    # ========== Beanie 配置 ==========
    class Settings:
        name = "section_data"  # MongoDB 集合名称
        use_state_management = True  # 启用状态管理
        validate_on_save = True  # 保存时验证数据
        
        # 索引定义
        indexes = [
            # message_id 索引（用于关联查询）
            IndexModel(
                [("message_id", ASCENDING)],
                name="idx_message_id"
            ),
            
            # 软删除 + 创建时间复合索引（常用查询）
            IndexModel(
                [("deleted", ASCENDING), ("create_time", DESCENDING)],
                name="idx_deleted_create_time"
            ),
        ]
    
    # ========== 自定义方法 ==========
    
    def has_text(self) -> bool:
        """检查是否包含文本"""
        return bool(self.text)
    
    def has_translation(self) -> bool:
        """检查是否有翻译内容"""
        return bool(self.translation)
