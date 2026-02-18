#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : states.py
@Author  : caixiongjiang
@Date    : 2025/12/30 15:13
@Function: 
    文件索引进度状态模型，对齐 Kafka 事件驱动架构
@Modify History:
    2026/02/18 - 重写：删除旧模型，新建 IndexStage / IndexStatus / FileIndexProgress
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class IndexStage(str, Enum):
    """
    索引处理阶段枚举

    对齐 src/db/kafka/types.py 的 ProcessingStage，
    代表文件索引流程中的各个事件节点。
    """
    INDEX_START = "index_start"
    PARSE_END = "parse_end"
    SPLIT_END = "split_end"
    SUMMARY_END = "summary_end"
    GRAPH_END = "graph_end"
    IMAGE_END = "image_end"
    ANALYZE_END = "analyze_end"


class IndexStatus(str, Enum):
    """索引处理状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


# 前台阶段到进度百分比的映射（设计文档定义的权重）
STAGE_PROGRESS_MAP: Dict[str, float] = {
    IndexStage.INDEX_START: 0.10,
    IndexStage.PARSE_END: 0.40,
    IndexStage.SPLIT_END: 1.00,
}


def stage_to_progress(stage: str) -> float:
    """
    根据阶段名称返回对应的进度值

    后台阶段（summary_end / graph_end / image_end / analyze_end）不影响前台进度，
    一律返回 1.0（前台已完成）。

    Args:
        stage: 阶段名称

    Returns:
        进度值 0.0~1.0
    """
    return STAGE_PROGRESS_MAP.get(stage, 1.0)


class FileIndexProgress(BaseModel):
    """
    单文件索引进度模型

    存储在 Redis Hash 中，每个字段对应一个 Hash field。
    """
    file_id: str = Field(..., description="文件ID")
    user_id: str = Field(..., description="用户ID")
    file_name: str = Field(..., description="文件名")
    progress: float = Field(
        default=0.0, ge=0.0, le=1.0, description="进度 0.0~1.0"
    )
    status: IndexStatus = Field(
        default=IndexStatus.PENDING, description="处理状态"
    )
    stage: Optional[str] = Field(
        default=None, description="当前处理阶段"
    )
    message: Optional[str] = Field(
        default=None, description="状态描述"
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="最后更新时间 (ISO 8601)",
    )

    def to_redis_dict(self) -> Dict[str, str]:
        """序列化为 Redis Hash 可存储的 str->str 字典"""
        return {
            "file_id": self.file_id,
            "user_id": self.user_id,
            "file_name": self.file_name,
            "progress": str(self.progress),
            "status": self.status.value,
            "stage": self.stage or "",
            "message": self.message or "",
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_redis_dict(cls, data: Dict[str, str]) -> "FileIndexProgress":
        """从 Redis Hash 字典反序列化"""
        return cls(
            file_id=data["file_id"],
            user_id=data["user_id"],
            file_name=data["file_name"],
            progress=float(data.get("progress", "0.0")),
            status=IndexStatus(data.get("status", "pending")),
            stage=data.get("stage") or None,
            message=data.get("message") or None,
            updated_at=data.get("updated_at", ""),
        )
