#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : document_data.py
@Author  : caixiongjiang
@Date    : 2026/1/7 16:44
@Function: 
    DocumentData Schema - 文档数据表
    存储文档级别的数据和元信息
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional, Dict, Any
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING

from src.db.mongodb.models.base_model import BaseDocument


class DocumentData(BaseDocument):
    """
    Document数据表
    
    存储文档级别的数据，包括文档摘要和元信息。
    """
    
    # ========== 基础字段 ==========
    message_id: Optional[int] = Field(
        None,
        description="消息ID：消息唯一标识符，来自global_id_generator"
    )
    
    # ========== 摘要字段 ==========
    summary_zh: Optional[str] = Field(
        None,
        description="文档的中文摘要"
    )
    
    summary_en: Optional[str] = Field(
        None,
        description="文档的英文摘要"
    )
    
    # ========== 元数据 ==========
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="文档的元数据（JSON格式，存储额外信息）"
    )
    
    # ========== Beanie 配置 ==========
    class Settings:
        name = "document_data"  # MongoDB 集合名称
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
    
    async def get_summary(self, language: str = "zh") -> Optional[str]:
        """
        获取指定语言的摘要
        
        Args:
            language: 语言代码，'zh' 或 'en'
            
        Returns:
            摘要文本，如果不存在则返回 None
        """
        if language == "zh":
            return self.summary_zh
        elif language == "en":
            return self.summary_en
        return None
    
    def has_summary(self) -> bool:
        """检查是否有摘要（任一语言）"""
        return bool(self.summary_zh or self.summary_en)
