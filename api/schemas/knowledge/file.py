#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : file.py
@Author  : caixiongjiang
@Date    : 2026/03/16
@Function: 
    文件操作 API 模型
    包含文件移动、文件预览、文件删除等操作的请求和响应模型
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from pydantic import BaseModel, Field


# ==================== 文件移动 ====================


class FileMoveRequest(BaseModel):
    """文件移动请求"""
    target_folder_id: Optional[str] = Field(
        default=None, description="目标文件夹ID（None 表示移到根目录）"
    )


class FileMoveResponse(BaseModel):
    """文件移动响应"""
    file_id: str = Field(..., description="文件ID")
    file_name: str = Field(..., description="文件名")
    folder_id: Optional[str] = Field(default=None, description="移动后的文件夹ID")
    knowledge_base_id: str = Field(default="", description="所属知识库ID")


# ==================== 批量文件移动 ====================


class BatchFileMoveRequest(BaseModel):
    """批量文件移动请求"""
    file_ids: list[str] = Field(
        ..., min_length=1, max_length=100, description="文件ID列表（1-100个）"
    )
    target_folder_id: Optional[str] = Field(
        default=None, description="目标文件夹ID（None 表示移到根目录）"
    )


class SkippedFileDetail(BaseModel):
    """被跳过的文件详情"""
    file_id: str = Field(..., description="文件ID")
    reason: str = Field(..., description="跳过原因")


class BatchFileMoveResponse(BaseModel):
    """批量文件移动响应"""
    moved_count: int = Field(default=0, description="成功移动的文件数量")
    total_requested: int = Field(default=0, description="请求移动的文件数量")
    skipped_files: List[SkippedFileDetail] = Field(
        default_factory=list, description="被跳过的文件列表（含原因）"
    )


# ==================== 文件预览 ====================


class FilePreviewResponse(BaseModel):
    """文件预览响应"""
    file_id: str = Field(..., description="文件ID")
    file_name: str = Field(..., description="文件名")
    mime_type: Optional[str] = Field(default=None, description="MIME 类型")
    file_size: Optional[int] = Field(default=None, description="文件大小（字节）")
    preview_url: str = Field(..., description="预览URL（MinIO 预签名URL）")
    expires_in: int = Field(..., description="URL 过期时间（秒）")


# ==================== Chunk 图片预览 ====================


class ChunkImagePreviewResponse(BaseModel):
    """图片 chunk 预览响应"""
    chunk_id: str = Field(..., description="Chunk ID")
    preview_url: str = Field(..., description="图片预览URL（MinIO 预签名URL）")
    expires_in: int = Field(..., description="URL 过期时间（秒）")
    file_name: Optional[str] = Field(default=None, description="关联文件名")


# ==================== Chunk 定位信息 ====================


class ElementPosition(BaseModel):
    """元素位置信息"""
    element_id: str = Field(..., description="元素 ID")
    element_type: str = Field(..., description="元素类型：text, image, table")
    page_index: Optional[int] = Field(
        default=None,
        description=(
            "元素所在页码（从 0 开始）。文本 chunk 可能跨页，前端需按此逐元素"
            "渲染高亮框，避免用 chunk 级 page_index 错位。"
        ),
    )
    page_position: Optional[List[float]] = Field(
        default=None,
        description=(
            "MinerU 页面边界框 [x0, y0, x1, y1]：左上角与右下角，"
            "坐标空间见 ChunkPositionResponse.coord_space"
        ),
    )


class ChunkPositionResponse(BaseModel):
    """Chunk 定位响应"""
    chunk_id: str = Field(..., description="Chunk ID")
    chunk_type: Optional[str] = Field(default=None, description="Chunk 类型")
    page_index: Optional[int] = Field(default=None, description="页码（从 0 开始）")
    coord_space: str = Field(
        default="mineru-normalized-1000",
        description="page_position 使用的坐标空间标识",
    )
    coord_range: int = Field(
        default=1000,
        description="归一化坐标轴最大值（MinerU bbox 映射到 0~coord_range）",
    )
    elements: List[ElementPosition] = Field(
        default_factory=list,
        description="关联元素的位置信息列表",
    )


# ==================== 文件删除（软删除） ====================


class FileDeleteResponse(BaseModel):
    """单个文件软删除响应"""
    file_id: str = Field(..., description="文件ID")
    success: bool = Field(..., description="是否成功")


class BatchFileDeleteRequest(BaseModel):
    """批量文件软删除请求"""
    file_ids: List[str] = Field(
        ..., min_length=1, max_length=100, description="文件ID列表（1-100个）"
    )


class BatchFileDeleteResponse(BaseModel):
    """批量文件软删除响应"""
    deleted_count: int = Field(default=0, description="成功删除的文件数量")
    total_requested: int = Field(default=0, description="请求删除的文件数量")
