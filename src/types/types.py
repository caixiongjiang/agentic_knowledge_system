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

class KnowledgeBaseID(Enum):
    """知识库类型枚举"""
    COMMON_FILE = "1"  # 通用文件知识
    PCB_FILE = "2"  # pcb专业知识
    MEMORY = "3"  # 记忆知识
    TEXT2SQL = "4"  # 文本转SQL知识
    WORKSPACE = "5"  # Agent工作空间产物知识

class KnowledgeType(Enum):
    """知识类型枚举"""
    COMMON_FILE = "common_file"      # 通用文件知识类型
    PCB_FILE = "pcb_file"            # pcb专业知识类型
    MEMORY = "memory"                # 记忆知识类型
    TEXT2SQL = "text2sql"            # 文本转SQL知识类型
    WORKSPACE = "workspace"          # 工作空间产物知识类型






# 类型别名
KnowledgeBaseInstanceID = int  # 知识库实例ID
