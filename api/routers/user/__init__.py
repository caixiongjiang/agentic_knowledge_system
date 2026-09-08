#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/09/04
@Function: 
    User API 路由模块
    包含端点：
      /api/user/profile - 个人资料管理
      /api/user/avatar  - 头像上传/删除/展示
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from fastapi import APIRouter
from api.routers.user.profile import router as profile_router

user_router = APIRouter(prefix="/api/user")
user_router.include_router(profile_router)

__all__ = ["user_router"]
