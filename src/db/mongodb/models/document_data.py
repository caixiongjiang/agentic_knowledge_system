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
    
    # ========== 主键字段 ==========
    id: str = Field(
        ...,
        alias="_id",
        description="文档唯一标识（格式：document_<uuid>）"
    )
    
    # ========== 基础字段 ==========
    message_id: Optional[int] = Field(
        None,
        description="消息ID：消息唯一标识符，来自global_id_generator"
    )
    
    # ========== 摘要字段（结构化子文档）==========
    # 由 FileSummaryService 通过 UPSERT $set 写入，与 section_data.summary 风格对齐。
    # 结构：{summary_id, text, keywords, topics, document_type,
    #        section_count, chunk_count, language}
    summary: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "文件级摘要子文档（由 FileSummaryService 通过 UPSERT $set 写入）。"
            "结构：{summary_id, text, keywords, topics, document_type, "
            "section_count, chunk_count, language}。"
        )
    )
    
    # ========== 元数据 ==========
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="文档的元数据（JSON格式，存储额外信息）"
    )
    
    # ========== Pydantic 配置 ==========
    class Config:
        """Pydantic 配置"""
        populate_by_name = True  # 允许使用字段名和别名
    
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
    
    def get_summary_text(self) -> Optional[str]:
        """获取摘要文本（从结构化 summary 子文档提取 text 字段）。"""
        if self.summary and isinstance(self.summary, dict):
            return self.summary.get("text")
        return None
    
    def has_summary(self) -> bool:
        """检查是否有摘要"""
        return bool(self.get_summary_text())
