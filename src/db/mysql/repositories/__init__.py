#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    MySQL Repository 模块
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.db.mysql.repositories.base_repository import BaseRepository

__all__ = [
    "BaseRepository",
]
