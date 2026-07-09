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
    
    存储文档的章节核心内容数据：
    - text: section文本内容（标题）
    - translation: 翻译列表
    """
    
    # ========== 主键字段 ==========
    id: str = Field(
        ...,
        alias="_id",
        description="章节唯一标识（格式：section_<uuid>）"
    )
    
    # ========== 核心字段 ==========
    text: Optional[str] = Field(
        None,
        description="section文本内容（标题）"
    )
    
    translation: List[Any] = Field(
        default_factory=list,
        description="section翻译内容列表（支持多语言）"
    )

    # ========== 结构层级 ==========
    parent_section_id: Optional[str] = Field(
        None,
        description=(
            "直接父 section ID（顶级 section 为 None）。"
            "由 SectionSummaryService 从标题编号推断得到，前端骨架接口据此拼树。"
        )
    )

    is_leaf: Optional[bool] = Field(
        None,
        description=(
            "是否叶子 section。True=挂有 chunk 的叶子 section；"
            "False=父 section（rollup 摘要）。None 表示尚未由 section_summary 更新。"
        )
    )

    chunk_id_list: List[str] = Field(
        default_factory=list,
        description=(
            "该 section 及其所有后代叶子的 chunk_id 列表（去重、保序）。"
            "用于「Milvus 命中 summary → 拿到 chunk_id 列表下钻」检索路径。"
        )
    )

    # ========== 摘要 ==========
    summary: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "section 摘要子文档（由 SectionSummaryService 通过 UPSERT $set 写入）。"
            "结构：{summary_id, text, chunk_count, language}。"
        )
    )
    
    # ========== Pydantic 配置 ==========
    class Config:
        """Pydantic 配置"""
        populate_by_name = True  # 允许使用字段名和别名
    
    # ========== Beanie 配置 ==========
    class Settings:
        name = "section_data"  # MongoDB 集合名称
        use_state_management = True  # 启用状态管理
        validate_on_save = True  # 保存时验证数据
        
        # 索引定义
        indexes = [
            # 软删除 + 创建时间复合索引（常用查询）
            IndexModel(
                [("deleted", ASCENDING), ("create_time", DESCENDING)],
                name="idx_deleted_create_time"
            ),
            # Milvus summary_id → section_data 反查（检索命中后拿 section 上下文）
            IndexModel(
                [("summary.summary_id", ASCENDING)],
                name="idx_summary_id"
            ),
            # 按 parent_section_id 拼树（前端骨架接口 / agent 下钻）
            IndexModel(
                [("parent_section_id", ASCENDING)],
                name="idx_parent_section_id"
            ),
        ]
    
    # ========== 自定义方法 ==========
    
    def has_text(self) -> bool:
        """检查是否包含文本"""
        return bool(self.text)
