#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : types.py
@Author  : caixiongjiang
@Date    : 2025/12/30 15:09
@Function: 
    函数功能名称
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from enum import Enum

class KnowledgeType(Enum):
    """知识类型枚举"""
    COMMON_FILE = "common_file"      # 通用文件知识类型
    PCB_FILE = "pcb_file"            # pcb专业知识类型
    MEMORY = "memory"                # 记忆知识类型
    TEXT2SQL = "text2sql"            # 文本转SQL知识类型
    WORKSPACE = "workspace"          # 工作空间产物知识类型






# 类型别名
KnowledgeBaseID = int  # 知识库实例ID
KnowledgeBaseName = str  # 知识库实例名称