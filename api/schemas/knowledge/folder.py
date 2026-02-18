#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : folder.py
@Author  : caixiongjiang
@Date    : 2026/02/18
@Function: 
    文件夹管理 API 模型
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional
from pydantic import BaseModel, Field


class FolderCreateRequest(BaseModel):
    """创建文件夹请求"""
    folder_name: str = Field(
        ..., min_length=1, max_length=255, description="文件夹名称"
    )
    knowledge_base_id: str = Field(..., description="所属知识库ID")
    knowledge_base_name: str = Field(default="", description="所属知识库名称")
    parent_folder_id: Optional[str] = Field(
        default=None, description="父文件夹ID（不传则在根目录创建）"
    )
    description: Optional[str] = Field(default=None, description="文件夹描述")


class FolderCreateResponse(BaseModel):
    """创建文件夹响应"""
    folder_id: str = Field(..., description="文件夹ID（UUID）")
    folder_name: str = Field(..., description="文件夹名称")
    full_path: str = Field(..., description="完整路径")
    parent_folder_id: Optional[str] = Field(
        default=None, description="父文件夹ID"
    )
    depth: int = Field(..., description="目录层级深度")
    knowledge_base_id: str = Field(..., description="所属知识库ID")
