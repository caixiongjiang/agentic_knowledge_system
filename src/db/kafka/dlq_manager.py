#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka 死信队列（DLQ）管理模块

实现失败消息的死信队列管理：
- 死信队列消息存储
- 失败原因记录
- 支持重新回放到正常队列
- DLQ 监控和统计
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field

from src.db.kafka.topics import KafkaTopics
from src.db.kafka.types import EventID, TraceID
from src.types.messages.base import BaseMessage
from src.utils.config_manager import get_config_manager


class DLQRecord(BaseModel):
    """
    死信队列记录
    
    包含失败消息的完整信息，用于追溯和重新处理。
    """
    # 原始消息
    original_message: BaseMessage
    
    # 原始 Topic
    original_topic: str = Field(description="原始 Topic 名称")
    
    # 失败信息
    error: str = Field(description="失败原因")
    error_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="失败时间"
    )
    
    # 重试信息
    retry_count: int = Field(default=0, ge=0, description="已重试次数")
    
    # 追踪信息
    event_id: EventID = Field(description="事件ID")
    trace_id: TraceID = Field(description="追踪ID")
    
    # 额外信息
    stack_trace: Optional[str] = Field(default=None, description="堆栈信息")
    context: Dict = Field(default_factory=dict, description="额外上下文")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return self.model_dump(mode="json")
    
    @classmethod
    def from_dict(cls, data: dict) -> "DLQRecord":
        """从字典创建"""
        return cls.model_validate(data)


class DLQManager:
    """
    死信队列管理器
    
    功能：
    1. 接收并存储失败消息
    2. 记录详细的失败原因
    3. 支持重新回放到正常队列
    4. 提供 DLQ 统计和监控
    """
    
    def __init__(
        self,
        producer: object,  # KafkaProducer
        enable_dlq: Optional[bool] = None
    ):
        """
        初始化 DLQ 管理器
        
        Args:
            producer: Kafka Producer 实例
            enable_dlq: 是否启用 DLQ，默认从配置读取
        """
        self.config = get_config_manager()
        self.producer = producer
        
        # DLQ 配置
        self.enable_dlq = enable_dlq if enable_dlq is not None else self.config.get("kafka.retry.enable_dlq", True)
        
        # DLQ 统计
        self.stats = {
            "total_dlq_messages": 0,
            "dlq_by_topic": {},
            "dlq_by_error_type": {}
        }
        
        logger.info(f"DLQ管理器初始化完成 - 启用DLQ: {self.enable_dlq}")
    
    def _get_dlq_topic(self, original_topic: str) -> str:
        """
        获取 DLQ Topic 名称
        
        Args:
            original_topic: 原始 Topic 名称
            
        Returns:
            DLQ Topic 名称
        """
        return KafkaTopics.get_dlq_topic(original_topic)
    
    def _extract_error_type(self, error: str) -> str:
        """
        提取错误类型（用于统计）
        
        Args:
            error: 错误信息
            
        Returns:
            错误类型
        """
        # 简单提取：取第一行或前50个字符
        lines = error.split("\n")
        error_type = lines[0] if lines else error
        if len(error_type) > 50:
            error_type = error_type[:50] + "..."
        return error_type
    
    async def send_to_dlq(
        self,
        message: BaseMessage,
        original_topic: str,
        error: str,
        stack_trace: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> bool:
        """
        发送消息到 DLQ
        
        Args:
            message: 原始消息
            original_topic: 原始 Topic 名称
            error: 失败原因
            stack_trace: 堆栈信息（可选）
            context: 额外上下文（可选）
            
        Returns:
            是否成功发送
        """
        if not self.enable_dlq:
            logger.warning(f"DLQ 未启用，跳过发送 - event_id: {message.metadata.event_id}")
            return False
        
        try:
            # 创建 DLQ 记录
            dlq_record = DLQRecord(
                original_message=message,
                original_topic=original_topic,
                error=error,
                retry_count=message.metadata.retry_count,
                event_id=message.metadata.event_id,
                trace_id=message.metadata.trace_id,
                stack_trace=stack_trace,
                context=context or {}
            )
            
            # 获取 DLQ Topic
            dlq_topic = self._get_dlq_topic(original_topic)
            
            # 将 DLQ 记录序列化为消息
            # 注意：这里我们需要将 DLQRecord 转换为可以发送的格式
            dlq_message_dict = dlq_record.to_dict()
            
            # 发送到 DLQ Topic
            # 注意：Kafka headers 应该是 list of tuples，而不是 dict
            await self.producer.send_message(
                topic=dlq_topic,
                message=message,  # 发送原始消息
                headers=[
                    ("dlq_error", error.encode("utf-8")),
                    ("dlq_original_topic", original_topic.encode("utf-8")),
                    ("dlq_retry_count", str(dlq_record.retry_count).encode("utf-8"))
                ]
            )
            
            # 更新统计
            self.stats["total_dlq_messages"] += 1
            self.stats["dlq_by_topic"][original_topic] = self.stats["dlq_by_topic"].get(original_topic, 0) + 1
            
            error_type = self._extract_error_type(error)
            self.stats["dlq_by_error_type"][error_type] = self.stats["dlq_by_error_type"].get(error_type, 0) + 1
            
            logger.warning(
                f"消息已发送到DLQ - "
                f"event_id: {message.metadata.event_id}, "
                f"original_topic: {original_topic}, "
                f"dlq_topic: {dlq_topic}, "
                f"error: {error[:100]}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"发送到DLQ失败 - event_id: {message.metadata.event_id}: {e}", exc_info=True)
            return False
    
    async def replay_from_dlq(
        self,
        dlq_topic: str,
        target_topic: Optional[str] = None,
        max_messages: int = 100
    ) -> int:
        """
        从 DLQ 重新回放消息到正常队列
        
        Args:
            dlq_topic: DLQ Topic 名称
            target_topic: 目标 Topic（如果为 None，则回放到原始 Topic）
            max_messages: 最大回放消息数
            
        Returns:
            成功回放的消息数量
        """
        logger.warning(
            f"DLQ回放功能需要实现 Consumer 来读取 DLQ 消息。"
            f"这通常作为一个独立的管理工具实现。"
        )
        # TODO: 实现 DLQ 回放逻辑
        # 1. 创建临时 Consumer 订阅 DLQ Topic
        # 2. 读取消息
        # 3. 重置 retry_count
        # 4. 发送到目标 Topic
        return 0
    
    async def get_stats(self) -> dict:
        """
        获取 DLQ 统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "enable_dlq": self.enable_dlq,
            "total_dlq_messages": self.stats["total_dlq_messages"],
            "dlq_by_topic": dict(self.stats["dlq_by_topic"]),
            "dlq_by_error_type": dict(self.stats["dlq_by_error_type"]),
            "top_error_types": self._get_top_errors(5)
        }
    
    def _get_top_errors(self, top_n: int = 5) -> List[tuple]:
        """
        获取最常见的错误类型
        
        Args:
            top_n: 返回前 N 个
            
        Returns:
            (错误类型, 数量) 列表
        """
        sorted_errors = sorted(
            self.stats["dlq_by_error_type"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_errors[:top_n]
    
    async def clear_stats(self) -> None:
        """清空统计信息（测试用）"""
        self.stats = {
            "total_dlq_messages": 0,
            "dlq_by_topic": {},
            "dlq_by_error_type": {}
        }
        logger.warning("已清空DLQ统计信息")


# 全局 DLQ 管理器实例（单例）
_dlq_manager: Optional[DLQManager] = None


async def get_dlq_manager(
    producer: object,
    force_new: bool = False
) -> DLQManager:
    """
    获取全局 DLQ 管理器实例（单例）
    
    Args:
        producer: Kafka Producer 实例
        force_new: 是否强制创建新实例（测试用）
        
    Returns:
        DLQ 管理器实例
    """
    global _dlq_manager
    
    if _dlq_manager is None or force_new:
        _dlq_manager = DLQManager(producer=producer)
    
    return _dlq_manager


async def close_dlq_manager() -> None:
    """关闭全局 DLQ 管理器"""
    global _dlq_manager
    
    if _dlq_manager is not None:
        await _dlq_manager.clear_stats()
        _dlq_manager = None
        logger.info("DLQ管理器已关闭")
