#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/09/04
@Function: 
    User 类 Schema 定义
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.db.mysql.models.user.user_profile import UserProfile

__all__ = [
    "UserProfile",
]
