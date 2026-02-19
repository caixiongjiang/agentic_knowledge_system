#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : knowledge_base.py
@Author  : caixiongjiang
@Date    : 2026/02/19
@Function: 
    知识库管理 API 模型
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional

from pydantic import BaseModel, Field


# ==================== 通用信息 ====================


class KnowledgeBaseInfo(BaseModel):
    """知识库信息"""
    knowledge_base_id: str = Field(..., description="知识库ID")
    knowledge_base_name: str = Field(..., description="知识库名称")
    parent_knowledge_base_id: Optional[str] = Field(
        default=None, description="父知识库ID"
    )
    knowledge_type: str = Field(default="common_file", description="知识库类型")
    description: Optional[str] = Field(default=None, description="知识库描述")


# ==================== 创建 ====================


class KnowledgeBaseCreateRequest(BaseModel):
    """创建知识库请求"""
    knowledge_base_name: str = Field(
        ..., min_length=1, max_length=255, description="知识库名称"
    )
    parent_knowledge_base_id: Optional[str] = Field(
        default=None, description="父知识库ID（不传则为顶级知识库）"
    )
    knowledge_type: str = Field(
        default="common_file", description="知识库类型"
    )
    description: Optional[str] = Field(default=None, description="知识库描述")


# ==================== 查询 ====================


class KnowledgeBaseListResponse(BaseModel):
    """知识库列表响应"""
    knowledge_bases: List[KnowledgeBaseInfo] = Field(
        default_factory=list, description="知识库列表"
    )
    total: int = Field(default=0, description="总数")


# ==================== 更新 ====================


class KnowledgeBaseUpdateRequest(BaseModel):
    """更新知识库请求"""
    knowledge_base_name: Optional[str] = Field(
        default=None, min_length=1, max_length=255, description="新名称"
    )
    description: Optional[str] = Field(default=None, description="新描述")


# ==================== 删除 ====================


class KnowledgeBaseDeleteResponse(BaseModel):
    """删除知识库响应"""
    knowledge_base_id: str = Field(..., description="被删除的知识库ID")
    deleted_folder_count: int = Field(
        default=0, description="同时清理的空文件夹数量"
    )
