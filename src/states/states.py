#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : states.py
@Author  : caixiongjiang
@Date    : 2025/12/30 15:13
@Function: 
    知识处理 Pipeline 状态数据模型定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ProcessStage(str, Enum):
    """处理阶段枚举"""
    EXTRACT = "extract"      # 提取阶段
    PARSER = "parser"        # 解析阶段
    SPLITTER = "splitter"    # 分割阶段
    UPDATE = "update"        # 更新阶段
    COMPLETED = "completed"  # 完成


class ProcessStatus(str, Enum):
    """处理状态枚举"""
    PENDING = "pending"        # 等待处理
    PROCESSING = "processing"  # 处理中
    SUCCESS = "success"        # 成功
    FAILED = "failed"          # 失败
    SKIPPED = "skipped"        # 跳过


class ExtractResult(BaseModel):
    """提取阶段结果"""
    status: ProcessStatus = Field(..., description="提取状态")
    file_bytes: Optional[bytes] = Field(None, description="文件字节内容（可选存储）")
    file_hash: Optional[str] = Field(None, description="文件哈希值")
    extract_time: float = Field(0.0, description="提取耗时（秒）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="提取阶段元数据")
    error_message: Optional[str] = Field(None, description="错误信息")

    class Config:
        # 不序列化 file_bytes 到 JSON（太大）
        json_encoders = {
            bytes: lambda v: f"<bytes: {len(v)} bytes>" if v else None
        }


class PageInfo(BaseModel):
    """页面信息"""
    page_idx: int
    page_size: Dict[str, int]
    page_info: List[Dict[str, Any]]


class ParserResult(BaseModel):
    """解析阶段结果"""
    status: ProcessStatus = Field(..., description="解析状态")
    pages: int = Field(0, description="页面数量")
    content: str = Field("", description="Markdown 内容")
    struct_content: Optional[Dict[str, Any]] = Field(None, description="结构化内容")
    images_info: Optional[List[Dict[str, Any]]] = Field(None, description="图片信息")
    tables_info: Optional[List[Dict[str, Any]]] = Field(None, description="表格信息")
    parse_time: float = Field(0.0, description="解析耗时（秒）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="解析阶段元数据")
    error_message: Optional[str] = Field(None, description="错误信息")


class ChunkInfo(BaseModel):
    """分块信息"""
    chunk_id: str = Field(..., description="分块唯一ID")
    chunk_index: int = Field(..., description="分块索引")
    content: str = Field(..., description="分块内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="分块元数据")
    token_count: Optional[int] = Field(None, description="Token 数量")


class SplitterResult(BaseModel):
    """分割阶段结果"""
    status: ProcessStatus = Field(..., description="分割状态")
    chunks: List[ChunkInfo] = Field(default_factory=list, description="分块列表")
    chunk_count: int = Field(0, description="分块数量")
    split_method: str = Field("", description="分割方法")
    split_time: float = Field(0.0, description="分割耗时（秒）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="分割阶段元数据")
    error_message: Optional[str] = Field(None, description="错误信息")


class UpdateResult(BaseModel):
    """更新阶段结果（入库）"""
    status: ProcessStatus = Field(..., description="更新状态")
    updated_ids: List[str] = Field(default_factory=list, description="更新的文档ID列表")
    success_count: int = Field(0, description="成功数量")
    failed_count: int = Field(0, description="失败数量")
    update_time: float = Field(0.0, description="更新耗时（秒）")
    db_collection: Optional[str] = Field(None, description="数据库集合名称")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="更新阶段元数据")
    error_message: Optional[str] = Field(None, description="错误信息")


class DocumentState(BaseModel):
    """文档处理的全局状态
    
    这个类记录了整个文档处理 Pipeline 的状态和各阶段的结果
    """
    # ============ 基础信息 ============
    doc_id: str = Field(..., description="文档唯一ID")
    file_name: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    file_type: str = Field(..., description="文件类型，如 pdf, docx, md")
    file_size: int = Field(..., description="文件大小（字节）")
    
    # ============ 处理状态 ============
    current_stage: ProcessStage = Field(
        default=ProcessStage.EXTRACT, 
        description="当前处理阶段"
    )
    overall_status: ProcessStatus = Field(
        default=ProcessStatus.PENDING, 
        description="总体处理状态"
    )
    
    # ============ 时间戳 ============
    created_at: datetime = Field(
        default_factory=datetime.now, 
        description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, 
        description="更新时间"
    )
    started_at: Optional[datetime] = Field(
        None, 
        description="开始处理时间"
    )
    completed_at: Optional[datetime] = Field(
        None, 
        description="完成时间"
    )
    
    # ============ 各阶段结果 ============
    extract_result: Optional[ExtractResult] = Field(
        None, 
        description="提取阶段结果"
    )
    parser_result: Optional[ParserResult] = Field(
        None, 
        description="解析阶段结果"
    )
    splitter_result: Optional[SplitterResult] = Field(
        None, 
        description="分割阶段结果"
    )
    update_result: Optional[UpdateResult] = Field(
        None, 
        description="更新阶段结果"
    )
    
    # ============ 全局元数据 ============
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="全局元数据"
    )
    tags: List[str] = Field(
        default_factory=list, 
        description="标签列表"
    )
    
    # ============ 错误追踪 ============
    error_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="错误历史记录"
    )
    retry_count: int = Field(
        default=0, 
        description="重试次数"
    )
    max_retries: int = Field(
        default=3, 
        description="最大重试次数"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    def add_error(self, stage: ProcessStage, error_message: str) -> None:
        """添加错误记录"""
        self.error_history.append({
            "stage": stage.value,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat(),
            "retry_count": self.retry_count
        })
    
    def is_completed(self) -> bool:
        """判断是否完成所有处理"""
        return (
            self.current_stage == ProcessStage.COMPLETED and 
            self.overall_status == ProcessStatus.SUCCESS
        )
    
    def is_failed(self) -> bool:
        """判断是否处理失败"""
        return self.overall_status == ProcessStatus.FAILED
    
    def can_retry(self) -> bool:
        """判断是否可以重试"""
        return (
            self.is_failed() and 
            self.retry_count < self.max_retries
        )
    
    def get_processing_duration(self) -> Optional[float]:
        """获取处理总耗时（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return None
    
    def get_stage_result(self, stage: ProcessStage) -> Optional[Any]:
        """根据阶段获取对应的结果"""
        stage_mapping = {
            ProcessStage.EXTRACT: self.extract_result,
            ProcessStage.PARSER: self.parser_result,
            ProcessStage.SPLITTER: self.splitter_result,
            ProcessStage.UPDATE: self.update_result,
        }
        return stage_mapping.get(stage)
    
    def to_summary(self) -> Dict[str, Any]:
        """生成状态摘要"""
        return {
            "doc_id": self.doc_id,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "current_stage": self.current_stage.value,
            "overall_status": self.overall_status.value,
            "processing_duration": self.get_processing_duration(),
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class BatchProcessState(BaseModel):
    """批量处理状态
    
    用于追踪多个文档的批量处理状态
    """
    batch_id: str = Field(..., description="批次ID")
    batch_name: Optional[str] = Field(None, description="批次名称")
    doc_states: List[DocumentState] = Field(
        default_factory=list, 
        description="文档状态列表"
    )
    total_count: int = Field(0, description="总文档数")
    success_count: int = Field(0, description="成功数")
    failed_count: int = Field(0, description="失败数")
    processing_count: int = Field(0, description="处理中数")
    pending_count: int = Field(0, description="待处理数")
    
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="更新时间"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    def update_counts(self) -> None:
        """更新统计数量"""
        self.total_count = len(self.doc_states)
        self.success_count = sum(
            1 for doc in self.doc_states 
            if doc.overall_status == ProcessStatus.SUCCESS
        )
        self.failed_count = sum(
            1 for doc in self.doc_states 
            if doc.overall_status == ProcessStatus.FAILED
        )
        self.processing_count = sum(
            1 for doc in self.doc_states 
            if doc.overall_status == ProcessStatus.PROCESSING
        )
        self.pending_count = sum(
            1 for doc in self.doc_states 
            if doc.overall_status == ProcessStatus.PENDING
        )
        self.updated_at = datetime.now()
    
    def get_progress(self) -> float:
        """获取处理进度（0-100）"""
        if self.total_count == 0:
            return 0.0
        completed = self.success_count + self.failed_count
        return (completed / self.total_count) * 100
