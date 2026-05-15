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
      /api/knowledge/base   — 知识库管理
      /api/knowledge/index  — 索引（上传、构建、进度）
      /api/knowledge/folder — 文件夹管理（创建、查询、重命名、移动、删除文件夹）
      /api/knowledge/file   — 文件操作（移动、预览、软删除）
      /api/knowledge/trash  — 回收站（浏览、恢复、永久删除）
    
    删除流程：
      file:   DELETE /{file_id}, POST /batch-delete（软删除，移入回收站）
      folder: DELETE /{folder_id}（软删除文件夹，移入回收站）
      trash:  恢复 / 永久删除（仅 deleted=1 顶层条目，含级联清理索引数据）
@Modify History:
    2026/02/18 - 注册 index / folder 路由
    2026/02/19 - 注册 trash / knowledge_base 路由
    2026/03/16 - 注册 file 路由（文件移动、预览）
    2026/03/17 - 文件软删除从 folder 迁移到 file；移除 index 直接删除接口
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from fastapi import APIRouter

from api.routers.knowledge.knowledge_base import router as kb_router
from api.routers.knowledge.index import router as index_router
from api.routers.knowledge.folder import router as folder_router
from api.routers.knowledge.file import router as file_router
from api.routers.knowledge.trash import router as trash_router
from api.routers.knowledge.retrieve import router as retrieve_router

knowledge_router = APIRouter(prefix="/api/knowledge")
knowledge_router.include_router(kb_router, prefix="/base")
knowledge_router.include_router(index_router, prefix="/index")
knowledge_router.include_router(folder_router, prefix="/folder")
knowledge_router.include_router(file_router, prefix="/file")
knowledge_router.include_router(trash_router, prefix="/trash")
knowledge_router.include_router(retrieve_router)

__all__ = ["knowledge_router"]
