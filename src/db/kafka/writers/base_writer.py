#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
基础 Writer 类

提供所有 Writer 的通用功能和批量写入基础设施。
"""

from abc import ABC
from typing import List, Optional, Type
from aiokafka import AIOKafkaConsumer
from loguru import logger

from src.db.kafka.consumer import BatchKafkaConsumer
from src.db.kafka.producer import KafkaProducer
from src.db.kafka.deduplication import DeduplicationManager
from src.db.kafka.retry_manager import RetryManager
from src.db.kafka.dlq_manager import DLQManager
from src.types.messages.base import BaseMessage


class BaseWriter(BatchKafkaConsumer, ABC):
    """
    基础 Writer 类
    
    在 BatchKafkaConsumer 的基础上增加:
    - 幂等性检查支持
    - 批量去重
    - 重试管理
    - DLQ 支持
    - 统一的错误处理
    - 批量写入统计
    
    子类只需实现:
    - process_batch_impl(): 具体的批量写入逻辑
    - get_original_topic(): 返回原始 Topic 名称
    """
    
    def __init__(
        self,
        aiokafka_consumer: AIOKafkaConsumer,
        message_class: Type[BaseMessage],
        producer: Optional[KafkaProducer] = None,
        dedup_manager: Optional[DeduplicationManager] = None,
        retry_manager: Optional[RetryManager] = None,
        dlq_manager: Optional[DLQManager] = None,
        batch_size: int = 100,
        flush_interval_ms: int = 500,
        enable_idempotency: bool = True
    ):
        """
        初始化 Writer
        
        Args:
            aiokafka_consumer: aiokafka Consumer 实例
            message_class: 消息类型
            producer: Kafka Producer 实例
            dedup_manager: 去重管理器
            retry_manager: 重试管理器
            dlq_manager: DLQ 管理器
            batch_size: 批处理大小
            flush_interval_ms: 刷新间隔 (毫秒)
            enable_idempotency: 是否启用幂等性检查
        """
        super().__init__(
            aiokafka_consumer=aiokafka_consumer,
            message_class=message_class,
            batch_size=batch_size,
            fetch_timeout_ms=flush_interval_ms
        )
        self._producer = producer
        self._dedup_manager = dedup_manager
        self._retry_manager = retry_manager
        self._dlq_manager = dlq_manager
        self._enable_idempotency = enable_idempotency
        
        # 统计信息
        self._duplicate_count = 0
        self._total_written = 0
        self._batch_count = 0
    
    async def process_batch(self, messages: List[BaseMessage]) -> List[bool]:
        """
        处理批量消息 (实现 BatchKafkaConsumer 的抽象方法)
        
        增加了批量幂等性检查、批量写入、重试、DLQ 等功能。
        
        Args:
            messages: 消息列表
            
        Returns:
            List[bool]: 每条消息的处理结果
        """
        if not messages:
            return []
        
        logger.debug(f"开始处理批量消息: {len(messages)} 条")
        
        # 1. 批量幂等性检查
        unique_messages = []
        results_map = {}  # event_id -> bool
        
        if self._enable_idempotency and self._dedup_manager:
            for msg in messages:
                event_id = msg.metadata.event_id
                if await self._dedup_manager.is_duplicate(event_id):
                    self._duplicate_count += 1
                    results_map[event_id] = True  # 幂等性消息视为成功
                    logger.debug(f"消息已处理过(幂等性): event_id={event_id}")
                else:
                    unique_messages.append(msg)
        else:
            unique_messages = messages
        
        if not unique_messages:
            # 所有消息都是重复的
            return [True] * len(messages)
        
        # 2. 执行批量写入
        try:
            success_flags = await self.process_batch_impl(unique_messages)
            
            # 3. 标记成功处理的消息 (幂等性)
            if self._enable_idempotency and self._dedup_manager:
                for i, msg in enumerate(unique_messages):
                    if success_flags[i]:
                        await self._dedup_manager.mark_processed(msg.metadata.event_id)
                        results_map[msg.metadata.event_id] = True
                    else:
                        results_map[msg.metadata.event_id] = False
            else:
                for i, msg in enumerate(unique_messages):
                    results_map[msg.metadata.event_id] = success_flags[i]
            
            # 4. 处理失败的消息
            for i, msg in enumerate(unique_messages):
                if not success_flags[i]:
                    await self._handle_failure(msg, error="批量写入失败")
            
            # 5. 统计
            success_count = sum(success_flags)
            self._total_written += success_count
            self._batch_count += 1
            
            logger.info(
                f"批量写入完成: success={success_count}/{len(unique_messages)}, "
                f"batch_count={self._batch_count}, total_written={self._total_written}"
            )
            
        except Exception as e:
            logger.error(f"批量写入时发生异常: {e}", exc_info=True)
            
            # 所有消息都失败
            for msg in unique_messages:
                results_map[msg.metadata.event_id] = False
                await self._handle_failure(msg, error=str(e))
        
        # 6. 返回结果 (按原始顺序)
        return [results_map.get(msg.metadata.event_id, False) for msg in messages]
    
    async def process_batch_impl(self, messages: List[BaseMessage]) -> List[bool]:
        """
        具体的批量写入逻辑实现 (子类必须实现)
        
        Args:
            messages: 去重后的消息列表
            
        Returns:
            List[bool]: 每条消息的处理结果
        """
        raise NotImplementedError("子类必须实现 process_batch_impl 方法")
    
    def get_original_topic(self) -> str:
        """
        获取原始 Topic 名称 (用于 DLQ 和重试)
        
        子类必须实现此方法,返回自己监听的 Topic 名称。
        
        Returns:
            str: Topic 名称
        """
        raise NotImplementedError("子类必须实现 get_original_topic 方法")
    
    async def _handle_failure(self, message: BaseMessage, error: str) -> None:
        """
        处理失败的消息
        
        Args:
            message: 失败的消息
            error: 错误信息
        """
        # 尝试重试
        if self._retry_manager:
            success = await self._retry_manager.schedule_retry(
                message=message,
                original_topic=self.get_original_topic(),
                error=error
            )
            
            if not success:
                # 超过最大重试次数,发送到 DLQ
                if self._dlq_manager:
                    await self._dlq_manager.send_to_dlq(
                        message=message,
                        original_topic=self.get_original_topic(),
                        error=f"超过最大重试次数: {error}"
                    )
        else:
            # 没有配置重试管理器,直接发送到 DLQ
            if self._dlq_manager:
                await self._dlq_manager.send_to_dlq(
                    message=message,
                    original_topic=self.get_original_topic(),
                    error=error
                )
    
    def get_stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            dict: 统计信息字典
        """
        base_stats = super().get_stats()
        base_stats.update({
            "duplicate_count": self._duplicate_count,
            "total_written": self._total_written,
            "batch_count": self._batch_count,
            "avg_batch_size": self._total_written / self._batch_count if self._batch_count > 0 else 0
        })
        return base_stats
