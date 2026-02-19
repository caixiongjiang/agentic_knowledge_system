#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : trash.py
@Author  : caixiongjiang
@Date    : 2026/02/19
@Function: 
    回收站 API 模型
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TrashItemType(str, Enum):
    """回收站条目类型"""
    FOLDER = "folder"
    FILE = "file"


class TrashItem(BaseModel):
    """回收站条目（文件夹或文件）"""
    item_type: TrashItemType = Field(..., description="条目类型: folder / file")
    item_id: str = Field(..., description="条目ID（folder_id 或 file_id）")
    item_name: str = Field(..., description="名称")
    full_path: Optional[str] = Field(default=None, description="完整路径（仅文件夹）")
    folder_id: Optional[str] = Field(default=None, description="所属文件夹ID（仅文件）")
    file_size: Optional[int] = Field(default=None, description="文件大小（仅文件）")
    mime_type: Optional[str] = Field(default=None, description="MIME 类型（仅文件）")
    knowledge_base_id: str = Field(default="", description="所属知识库ID")
    deleted_at: Optional[str] = Field(default=None, description="删除时间")


class TrashListResponse(BaseModel):
    """回收站列表响应"""
    items: List[TrashItem] = Field(default_factory=list, description="回收站条目")
    total: int = Field(default=0, description="总数")


class TrashRestoreResponse(BaseModel):
    """恢复响应"""
    item_type: TrashItemType = Field(..., description="恢复的条目类型")
    item_id: str = Field(..., description="恢复的条目ID")
    restored_folder_count: int = Field(default=0, description="恢复的文件夹数量")
    restored_file_count: int = Field(default=0, description="恢复的文件数量")


class TrashFolderChildItem(BaseModel):
    """回收站内文件夹的子文件夹信息"""
    folder_id: str = Field(..., description="文件夹ID")
    folder_name: str = Field(..., description="文件夹名称")
    full_path: str = Field(..., description="完整路径")
    parent_folder_id: Optional[str] = Field(default=None, description="父文件夹ID")
    depth: int = Field(default=0, description="层级深度")
    knowledge_base_id: str = Field(default="", description="所属知识库ID")


class TrashFolderFileItem(BaseModel):
    """回收站内文件夹的子文件信息"""
    file_id: str = Field(..., description="文件ID")
    file_name: str = Field(..., description="文件名")
    folder_id: Optional[str] = Field(default=None, description="所属文件夹ID")
    file_size: Optional[int] = Field(default=None, description="文件大小（字节）")
    mime_type: Optional[str] = Field(default=None, description="MIME 类型")
    knowledge_base_id: str = Field(default="", description="所属知识库ID")


class TrashFolderChildrenResponse(BaseModel):
    """回收站内文件夹的子文件夹列表响应"""
    folder_id: str = Field(..., description="被浏览的文件夹ID")
    children: List[TrashFolderChildItem] = Field(
        default_factory=list, description="直接子文件夹列表"
    )
    total: int = Field(default=0, description="总数")


class TrashFolderFilesResponse(BaseModel):
    """回收站内文件夹的子文件列表响应"""
    folder_id: str = Field(..., description="被浏览的文件夹ID")
    files: List[TrashFolderFileItem] = Field(
        default_factory=list, description="直接子文件列表"
    )
    total: int = Field(default=0, description="总数")


class TrashEmptyResponse(BaseModel):
    """清空回收站响应"""
    deleted_folder_count: int = Field(default=0, description="永久删除的文件夹数量")
    deleted_file_count: int = Field(default=0, description="永久删除的文件数量")
