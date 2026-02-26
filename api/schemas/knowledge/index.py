#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : index.py
@Author  : caixiongjiang
@Date    : 2026/01/21 10:00
@Function: 
    Knowledge 索引 API 模型
    定义索引相关的请求和响应模型：
    - 文件上传请求/响应
    - 索引构建请求/响应
    - 进度查询响应
@Modify History:
    2026/02/18 - 实现文件上传与索引构建的请求/响应模型
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


# ==================== 文件上传相关 ====================


class FileUploadResponse(BaseModel):
    """单个文件上传响应"""
    file_id: str = Field(..., description="文件唯一标识（格式: file-{uuid}）")
    document_id: str = Field(..., description="文档唯一标识（格式: document-{uuid}，基于file_sha256去重）")
    file_name: str = Field(..., description="原始文件名")
    session_id: str = Field(..., description="上传会话ID")
    file_size: int = Field(..., description="文件大小（字节）")
    mime_type: str = Field(..., description="文件 MIME 类型")
    file_sha256: str = Field(..., description="文件 SHA256 哈希值（十六进制）")


class BatchFileUploadResponse(BaseModel):
    """批量文件上传响应"""
    session_id: str = Field(..., description="上传会话ID")
    uploaded_files: List[FileUploadResponse] = Field(
        default_factory=list, description="上传成功的文件列表"
    )
    failed_files: List[Dict[str, str]] = Field(
        default_factory=list, description="上传失败的文件列表（{filename, error}）"
    )
    total: int = Field(..., description="总文件数")
    success_count: int = Field(..., description="成功数")
    fail_count: int = Field(..., description="失败数")


# ==================== 索引构建相关 ====================


class IndexBuildRequest(BaseModel):
    """索引构建请求"""
    file_ids: List[str] = Field(
        ..., min_length=1, description="要索引的文件ID列表"
    )
    knowledge_base_id: str = Field(..., description="目标知识库ID")
    parse_options: Dict[str, Any] = Field(
        default_factory=dict, description="解析选项"
    )


class IndexBuildFileResult(BaseModel):
    """单个文件索引构建结果"""
    file_id: str = Field(..., description="文件ID")
    file_name: str = Field(..., description="文件名")
    status: str = Field(..., description="状态: submitted / failed")
    message: str = Field(default="", description="附加信息")


class IndexBuildResponse(BaseModel):
    """索引构建响应"""
    knowledge_base_id: str = Field(..., description="知识库ID")
    results: List[IndexBuildFileResult] = Field(
        default_factory=list, description="各文件索引构建结果"
    )
    submitted_count: int = Field(default=0, description="已提交数")
    failed_count: int = Field(default=0, description="失败数")


# ==================== 进度查询相关 ====================


class FileProgressResponse(BaseModel):
    """文件索引进度查询响应"""
    file_id: str = Field(..., description="文件ID")
    file_name: str = Field(..., description="文件名")
    progress: float = Field(
        default=0.0, ge=0.0, le=1.0, description="进度（0.0~1.0）"
    )
    status: str = Field(
        default="pending",
        description="状态: pending / processing / success / failed"
    )
    stage: Optional[str] = Field(default=None, description="当前处理阶段")
    message: Optional[str] = Field(default=None, description="状态描述")


class BatchProgressResponse(BaseModel):
    """批量文件进度查询响应"""
    files: List[FileProgressResponse] = Field(
        default_factory=list, description="各文件进度列表"
    )
    total: int = Field(default=0, description="总文件数")
    completed_count: int = Field(default=0, description="已完成数")
    processing_count: int = Field(default=0, description="处理中数")
    failed_count: int = Field(default=0, description="失败数")
