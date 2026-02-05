#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2025/12/30 15:12
@Function: 
    类型定义模块，导出所有消息类型和数据模型
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

# 注意：为避免循环导入，这里不直接导入
# 使用时请直接从子模块导入，例如：
# from src.types.messages.base import BaseMessage
# from src.types.models.parse_result import ParseResult

__all__ = [
    # 基础消息类型
    "BaseMessage",
    "MessageMetadata",
    
    # 索引相关消息
    "IndexStartMessage",
    "ParseEndMessage",
    "SplitEndMessage",
    
    # 数据模型
    "ParseResult",
    "ParseStatus",
    "ImageInfo",
    "TableInfo",
]
