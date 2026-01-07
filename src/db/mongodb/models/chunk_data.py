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
    
    存储文档分块后的数据，包括：
    - 文本分块
    - 图片分块
    - 表格分块
    
    支持多语言翻译、增强处理、摘要和问答提取。
    """
    
    # ========== 基础字段 ==========
    message_id: Optional[int] = Field(
        None,
        description="消息ID：消息唯一标识符，来自global_id_generator"
    )
    
    chunk_type: Optional[str] = Field(
        None,
        alias="type",
        description="chunk类型：text=文本，image=图片，table=表格"
    )
    
    # ========== 文本内容 ==========
    text: Optional[str] = Field(
        None,
        description="chunk文本内容（如果为图片则为多模态理解内容）"
    )
    
    translation: List[Any] = Field(
        default_factory=list,
        description="chunk翻译内容列表（支持多语言）"
    )
    
    enhanced_text: Optional[str] = Field(
        None,
        description="chunk增强文本内容（清洗、重写后的版本）"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="chunk元数据（JSON格式，存储额外信息）"
    )
    
    # ========== 图片相关字段 ==========
    image_caption: Optional[str] = Field(
        None,
        description="chunk图片标题"
    )
    
    image_footnote: Optional[str] = Field(
        None,
        description="chunk图片脚注"
    )
    
    image_base64: Optional[str] = Field(
        None,
        description="chunk图片base64编码（用于存储小图片）"
    )
    
    # ========== 摘要字段 ==========
    summary_zh: Optional[str] = Field(
        None,
        description="chunk中文摘要"
    )
    
    summary_en: Optional[str] = Field(
        None,
        description="chunk英文摘要"
    )
    
    # ========== 问答对字段 ==========
    atomic_qa_zh: List[Any] = Field(
        default_factory=list,
        description="chunk中文问答对列表（原子级问答）"
    )
    
    atomic_qa_en: List[Any] = Field(
        default_factory=list,
        description="chunk英文问答对列表（原子级问答）"
    )
    
    # ========== Beanie 配置 ==========
    class Settings:
        name = "chunk_data"  # MongoDB 集合名称
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
            
            # type 字段索引（按类型筛选）
            IndexModel(
                [("type", ASCENDING)],
                name="idx_type"
            ),
        ]
    
    # ========== 自定义方法 ==========
    
    def has_image(self) -> bool:
        """检查是否包含图片"""
        return self.chunk_type == "image" or bool(self.image_base64)
    
    def has_text(self) -> bool:
        """检查是否包含文本"""
        return bool(self.text)
    
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
