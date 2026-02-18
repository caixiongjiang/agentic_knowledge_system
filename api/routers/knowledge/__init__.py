#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/01/21 10:00
@Function: 
    Knowledge API 路由模块
    集成所有 Knowledge 相关的子路由：
      /api/knowledge/index  — 索引（上传、构建、进度）
      /api/knowledge/folder — 文件夹管理
@Modify History:
    2026/02/18 - 注册 index / folder 路由
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from fastapi import APIRouter

from api.routers.knowledge.index import router as index_router
from api.routers.knowledge.folder import router as folder_router

knowledge_router = APIRouter(prefix="/api/knowledge")
knowledge_router.include_router(index_router, prefix="/index")
knowledge_router.include_router(folder_router, prefix="/folder")

__all__ = ["knowledge_router"]
