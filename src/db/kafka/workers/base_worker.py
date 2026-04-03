#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
基础 Worker 类

提供所有 Worker 的通用功能和基础设施支持。
"""

from abc import ABC
from typing import Optional, Type
from aiokafka import AIOKafkaConsumer
from loguru import logger

from src.db.kafka.consumer import BaseKafkaConsumer
from src.db.kafka.producer import KafkaProducer
from src.db.kafka.deduplication import DeduplicationManager
from src.db.kafka.retry_manager import RetryManager
from src.db.kafka.dlq_manager import DLQManager
from src.states.state_manager import FileProgressManager
from src.states.states import IndexStatus
from src.types.messages.base import BaseMessage


class BaseWorker(BaseKafkaConsumer, ABC):
    """
    基础 Worker 类
    
    在 BaseKafkaConsumer 的基础上增加:
    - 幂等性检查支持
    - 重试管理支持
    - DLQ 支持
    - Producer 支持(用于发送下游消息)
    - 进度管理支持(Redis 进度更新)
    - 统一的错误处理
    
    子类只需实现:
    - process_message_impl(): 具体的业务逻辑
    - get_original_topic(): 返回原始 Topic 名称(用于 DLQ)
    """
    
    def __init__(
        self,
        aiokafka_consumer: AIOKafkaConsumer,
        message_class: Type[BaseMessage],
        producer: Optional[KafkaProducer] = None,
        dedup_manager: Optional[DeduplicationManager] = None,
        retry_manager: Optional[RetryManager] = None,
        dlq_manager: Optional[DLQManager] = None,
        progress_manager: Optional[FileProgressManager] = None,
        batch_size: int = 1,
        commit_interval: int = 100,
        enable_idempotency: bool = True
    ):
        """
        初始化 Worker
        
        Args:
            aiokafka_consumer: aiokafka Consumer 实例
            message_class: 消息类型
            producer: Kafka Producer(用于发送下游消息)
            dedup_manager: 去重管理器
            retry_manager: 重试管理器
            dlq_manager: DLQ 管理器
            progress_manager: 文件索引进度管理器(Redis)
            batch_size: 批处理大小
            commit_interval: 提交间隔
            enable_idempotency: 是否启用幂等性检查
        """
        super().__init__(
            aiokafka_consumer=aiokafka_consumer,
            message_class=message_class,
            batch_size=batch_size,
            auto_commit=False,
            commit_interval=commit_interval
        )
        
        self._producer = producer
        self._dedup_manager = dedup_manager
        self._retry_manager = retry_manager
        self._dlq_manager = dlq_manager
        self._progress_manager = progress_manager
        self._enable_idempotency = enable_idempotency
        
        # 统计信息
        self._duplicate_count = 0
        self._retry_count = 0
        self._dlq_count = 0
    
    async def process_message(self, message: BaseMessage) -> bool:
        """
        处理消息(实现 BaseKafkaConsumer 的抽象方法)
        
        增加了幂等性检查、重试、DLQ 等功能。
        
        Args:
            message: 消息对象
            
        Returns:
            bool: 处理是否成功
        """
        # 1. 幂等性检查
        if self._enable_idempotency and self._dedup_manager:
            event_id = message.metadata.event_id
            if await self._dedup_manager.is_duplicate(event_id):
                self._duplicate_count += 1
                logger.debug(f"消息已处理过(幂等性),跳过: event_id={event_id}")
                return True  # 幂等性消息也视为成功
        
        # 2. 执行具体的业务逻辑
        try:
            success = await self.process_message_impl(message)
            
            if success:
                # 标记消息已处理(幂等性)
                if self._enable_idempotency and self._dedup_manager:
                    await self._dedup_manager.mark_processed(message.metadata.event_id)
                return True
            else:
                # 处理失败,进入重试流程
                await self._handle_failure(message, error="业务逻辑返回失败")
                return False
                
        except Exception as e:
            # 异常,进入重试流程
            logger.error(f"处理消息时发生异常: {e}", exc_info=True)
            await self._handle_failure(message, error=str(e))
            return False
    
    async def process_message_impl(self, message: BaseMessage) -> bool:
        """
        具体的业务逻辑实现(子类必须实现)
        
        Args:
            message: 消息对象
            
        Returns:
            bool: 处理是否成功
        """
        raise NotImplementedError("子类必须实现 process_message_impl 方法")
    
    def get_original_topic(self) -> str:
        """
        获取原始 Topic 名称(用于 DLQ 和重试)
        
        子类必须实现此方法,返回自己监听的 Topic 名称。
        
        Returns:
            str: Topic 名称
        """
        raise NotImplementedError("子类必须实现 get_original_topic 方法")
    
    def _get_failure_stage(self) -> str:
        """
        返回当前 Worker 失败时对应的进度阶段。

        子类应覆盖此方法返回具体的 IndexStage 值，
        供 _handle_failure 兜底写 Redis 失败态时使用。
        """
        return "unknown"

    async def _handle_failure(self, message: BaseMessage, error: str) -> None:
        """
        处理失败的消息
        
        Args:
            message: 失败的消息
            error: 错误信息
        """
        retried = False

        # 尝试重试
        if self._retry_manager:
            success = await self._retry_manager.schedule_retry(
                message=message,
                original_topic=self.get_original_topic(),
                error=error
            )
            
            if success:
                self._retry_count += 1
                retried = True
                logger.info(
                    f"消息已调度重试: event_id={message.metadata.event_id}, "
                    f"retry_count={message.metadata.retry_count}"
                )
            else:
                # 超过最大重试次数,发送到 DLQ
                if self._dlq_manager:
                    await self._dlq_manager.send_to_dlq(
                        message=message,
                        original_topic=self.get_original_topic(),
                        error=f"超过最大重试次数: {error}"
                    )
                    self._dlq_count += 1
                    logger.warning(
                        f"消息已发送到 DLQ: event_id={message.metadata.event_id}"
                    )
        else:
            # 没有配置重试管理器,直接发送到 DLQ
            if self._dlq_manager:
                await self._dlq_manager.send_to_dlq(
                    message=message,
                    original_topic=self.get_original_topic(),
                    error=error
                )
                self._dlq_count += 1

        # 兜底：若消息不会被重试，确保 Redis 进度标记为失败
        if not retried:
            file_id = getattr(message, "file_id", None)
            if file_id:
                await self._fail_file_progress(
                    file_id=file_id,
                    stage=self._get_failure_stage(),
                    error_message=error,
                )
    
    async def _update_file_progress(
        self,
        file_id: str,
        stage: str,
        message: Optional[str] = None,
    ) -> None:
        """
        更新文件索引进度到 Redis
        
        如果 progress_manager 未配置则静默跳过，不影响主流程。
        
        Args:
            file_id: 文件 ID
            stage: 当前完成阶段 (IndexStage 的值)
            message: 描述信息
        """
        if not self._progress_manager:
            return
        
        try:
            await self._progress_manager.update_progress(
                file_id=file_id,
                stage=stage,
                status=IndexStatus.PROCESSING,
                message=message,
            )
        except Exception as e:
            logger.warning(
                f"更新 Redis 进度失败（不阻塞主流程）: "
                f"file_id={file_id}, stage={stage}, error={e}"
            )
    
    async def _fail_file_progress(
        self,
        file_id: str,
        stage: str,
        error_message: str,
    ) -> None:
        """
        将文件索引进度标记为失败
        
        Args:
            file_id: 文件 ID
            stage: 失败所在阶段
            error_message: 错误信息
        """
        if not self._progress_manager:
            return
        
        try:
            await self._progress_manager.update_progress(
                file_id=file_id,
                stage=stage,
                status=IndexStatus.FAILED,
                message=error_message,
            )
        except Exception as e:
            logger.warning(
                f"更新 Redis 失败状态失败: "
                f"file_id={file_id}, stage={stage}, error={e}"
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
            "retry_count": self._retry_count,
            "dlq_count": self._dlq_count
        })
        return base_stats
