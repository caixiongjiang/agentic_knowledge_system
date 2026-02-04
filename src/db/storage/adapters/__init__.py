#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/2/4 15:00
@Function: 
    存储适配器模块
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.db.storage.adapters.minio_adapter import MinIOAdapter

__all__ = ["MinIOAdapter"]
