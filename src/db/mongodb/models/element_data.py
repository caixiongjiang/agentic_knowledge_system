#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : element_data.py
@Author  : caixiongjiang
@Date    : 2026/01/17
@Function: 
    ElementData Model - PDF 解析元素内容数据
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Dict, Any, Optional
from pydantic import Field
from pymongo import IndexModel, ASCENDING
from src.db.mongodb.models.base_model import BaseDocument

# TODO: 建立索引

class ElementData(BaseDocument):
    """
    ElementData - PDF 解析元素内容数据
    
    设计原则：
    - _id: 与 MySQL 的 element_id 一致
    - type: 外置类型字段，便于查询过滤
    - content: 存储具体内容，根据 type 不同而不同
    
    职责划分：
    - MySQL (element_meta_info): 存储关系、元数据、结构化字段
    - MongoDB (element_data): 存储纯粹的内容数据
    
    查询流程：
    1. 通过 MySQL 查询得到 element_id 列表
    2. 使用 element_id 到 MongoDB 批量获取内容
    """
    
    # 类型字段（外置）
    type: str = Field(
        ...,
        description="元素类型: text, image, table, discarded"
    )
    
    # 内容字段（根据类型不同，内容不同）
    content: Dict[str, Any] = Field(
        ...,
        description="元素具体内容"
    )
    
    # ========== Beanie 配置 ==========
    class Settings:
        name = "element_data"  # MongoDB 集合名称
        use_state_management = True  # 启用状态管理
        validate_on_save = True  # 保存时验证数据
        
        # 索引定义
        indexes = [
            # type 字段索引（按类型筛选）
            IndexModel(
                [("type", ASCENDING)],
                name="idx_type"
            ),
        ]
    
    class Config:
        """Pydantic 配置"""
        json_schema_extra = {
            "examples": [
                {
                    "_id": "elem_uuid_001",
                    "type": "text",
                    "content": {
                        "text": "Thick Film Surface Mount Chip Resistors..."
                    }
                },
                {
                    "_id": "elem_uuid_002",
                    "type": "image",
                    "content": {
                        "image_caption": ["图1: 示例图片"],
                        "image_footnote": ["注: 这是注释"]
                    }
                },
                {
                    "_id": "elem_uuid_003",
                    "type": "table",
                    "content": {
                        "table_caption": ["表1: 规格参数"],
                        "table_footnote": ["注: 参考标准"],
                        "table_body": "<table>...</table>"
                    }
                }
            ]
        }


# ===== 内容字段说明 =====
"""
根据 type 不同，content 包含的字段：

1. text 类型:
   - text: str - 文本内容

2. image 类型:
   - image_caption: List[str] - 图片标题列表
   - image_footnote: List[str] - 图片脚注列表

3. table 类型:
   - table_caption: List[str] - 表格标题列表
   - table_footnote: List[str] - 表格脚注列表
   - table_body: str - 表格内容（HTML格式）

4. discarded 类型:
   - text: str - 废弃的文本内容
"""
