#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka 消息基础模型

提供所有 Kafka 消息的基类和通用字段。
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel, Field, field_validator

from src.db.kafka.types import EventID, TraceID


T = TypeVar("T", bound="BaseMessage")


class MessageMetadata(BaseModel):
    """
    消息元数据
    
    所有消息都包含的通用元数据字段。
    """
    # 事件ID（用于幂等性检查，确保消息不被重复处理）
    event_id: EventID = Field(
        default_factory=lambda: EventID(str(uuid.uuid4())),
        description="事件唯一标识符，用于幂等性检查"
    )
    
    # 追踪ID（用于分布式追踪，跟踪整个处理流程）
    trace_id: TraceID = Field(
        default_factory=lambda: TraceID(str(uuid.uuid4())),
        description="追踪ID，用于分布式追踪"
    )
    
    # 时间戳（消息创建时间）
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="消息创建时间（UTC）"
    )
    
    # 重试次数
    retry_count: int = Field(
        default=0,
        ge=0,
        description="消息重试次数"
    )
    
    # 来源（哪个组件产生的消息）
    source: Optional[str] = Field(
        default=None,
        description="消息来源组件"
    )
    
    # 额外的上下文信息
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="额外的上下文信息"
    )
    
    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> datetime:
        """解析时间戳，支持字符串和 datetime 对象"""
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BaseMessage(BaseModel):
    """
    Kafka 消息基类
    
    所有 Kafka 消息都应该继承此类。提供：
    - 自动序列化/反序列化（JSON）
    - 消息元数据管理
    - 类型安全的字段定义
    """
    
    # 用户ID
    user_id: str = Field(
        ...,
        min_length=1,
        description="用户ID"
    )
    
    # 文件ID
    file_id: str = Field(
        ...,
        min_length=1,
        description="文件ID"
    )
    
    # 消息元数据
    metadata: MessageMetadata = Field(
        default_factory=MessageMetadata,
        description="消息元数据"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            消息的字典表示
        """
        return self.model_dump(mode="json")
    
    def to_json(self) -> str:
        """
        序列化为 JSON 字符串
        
        Returns:
            JSON 字符串
        """
        return self.model_dump_json()
    
    def to_bytes(self) -> bytes:
        """
        序列化为字节流（用于 Kafka 发送）
        
        Returns:
            UTF-8 编码的 JSON 字节流
        """
        return self.to_json().encode("utf-8")
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """
        从字典反序列化
        
        Args:
            data: 消息字典
            
        Returns:
            消息对象
        """
        return cls.model_validate(data)
    
    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        """
        从 JSON 字符串反序列化
        
        Args:
            json_str: JSON 字符串
            
        Returns:
            消息对象
        """
        return cls.model_validate_json(json_str)
    
    @classmethod
    def from_bytes(cls: Type[T], data: bytes) -> T:
        """
        从字节流反序列化（用于 Kafka 接收）
        
        Args:
            data: UTF-8 编码的 JSON 字节流
            
        Returns:
            消息对象
        """
        return cls.from_json(data.decode("utf-8"))
    
    def get_message_key(self) -> str:
        """
        获取消息的 Kafka Key
        
        格式：{user_id}:{file_id}
        保证同一文件的所有消息路由到同一分区。
        
        Returns:
            Kafka Message Key
        """
        from src.db.kafka.types import MessageKey
        return MessageKey.generate(self.user_id, self.file_id)
    
    def increment_retry(self) -> None:
        """增加重试计数"""
        self.metadata.retry_count += 1
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
