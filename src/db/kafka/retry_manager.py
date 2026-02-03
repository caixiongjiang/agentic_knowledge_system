#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka 消息重试管理模块

实现失败消息的自动重试机制：
- 指数退避重试策略
- 最大重试次数限制
- 重试 Topic 管理
- 延迟重试队列
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from loguru import logger

from src.db.kafka.topics import KafkaTopics
from src.db.kafka.types import EventID
from src.types.messages.base import BaseMessage
from src.utils.config_manager import get_config_manager


class RetryStrategy:
    """
    重试策略
    
    支持多种重试延迟策略：
    - 固定延迟
    - 指数退避
    - 自定义延迟列表
    """
    
    @staticmethod
    def fixed(delay_seconds: float) -> List[float]:
        """
        固定延迟策略
        
        Args:
            delay_seconds: 延迟秒数
            
        Returns:
            延迟列表
        """
        return [delay_seconds] * 10  # 假设最多 10 次重试
    
    @staticmethod
    def exponential(base_delay: float, max_retries: int, max_delay: float = 300.0) -> List[float]:
        """
        指数退避策略
        
        延迟计算：delay = min(base_delay * (2 ^ retry_count), max_delay)
        
        Args:
            base_delay: 基础延迟（秒）
            max_retries: 最大重试次数
            max_delay: 最大延迟上限（秒）
            
        Returns:
            延迟列表
        """
        delays = []
        for i in range(max_retries):
            delay = min(base_delay * (2 ** i), max_delay)
            delays.append(delay)
        return delays
    
    @staticmethod
    def linear(base_delay: float, max_retries: int, increment: float = 1.0) -> List[float]:
        """
        线性递增策略
        
        延迟计算：delay = base_delay + (retry_count * increment)
        
        Args:
            base_delay: 基础延迟（秒）
            max_retries: 最大重试次数
            increment: 每次增加的延迟（秒）
            
        Returns:
            延迟列表
        """
        delays = []
        for i in range(max_retries):
            delay = base_delay + (i * increment)
            delays.append(delay)
        return delays
    
    @staticmethod
    def from_list(delays: List[float]) -> List[float]:
        """
        自定义延迟列表
        
        Args:
            delays: 延迟列表（秒）
            
        Returns:
            延迟列表
        """
        return delays


class RetryMessage:
    """
    重试消息封装
    
    包含原始消息、重试次数、下次重试时间等信息。
    """
    
    def __init__(
        self,
        original_message: BaseMessage,
        error: str,
        next_retry_time: datetime,
        retry_count: int = 0
    ):
        """
        初始化重试消息
        
        Args:
            original_message: 原始消息
            error: 失败原因
            next_retry_time: 下次重试时间
            retry_count: 当前重试次数
        """
        self.original_message = original_message
        self.error = error
        self.next_retry_time = next_retry_time
        self.retry_count = retry_count
        self.event_id = original_message.metadata.event_id
    
    def __lt__(self, other: "RetryMessage") -> bool:
        """比较函数，用于优先队列排序"""
        return self.next_retry_time < other.next_retry_time


class RetryManager:
    """
    消息重试管理器
    
    功能：
    1. 管理失败消息的重试
    2. 支持多种重试策略
    3. 自动发送到重试 Topic
    4. 超过最大重试次数后发送到 DLQ
    """
    
    def __init__(
        self,
        producer: object,  # KafkaProducer
        dlq_manager: Optional[object] = None,  # DLQManager
        max_retries: Optional[int] = None,
        retry_delays: Optional[List[float]] = None
    ):
        """
        初始化重试管理器
        
        Args:
            producer: Kafka Producer 实例
            dlq_manager: DLQ 管理器实例
            max_retries: 最大重试次数，默认从配置读取
            retry_delays: 重试延迟列表（秒），默认从配置读取
        """
        self.config = get_config_manager()
        self.producer = producer
        self.dlq_manager = dlq_manager
        
        # 重试配置
        self.max_retries = max_retries or self.config.get("kafka.retry.max_retries", 3)
        self.retry_delays = retry_delays or self.config.get("kafka.retry.retry_delays", [1, 5, 30])
        
        # 确保延迟列表长度足够
        if len(self.retry_delays) < self.max_retries:
            # 用最后一个延迟填充
            last_delay = self.retry_delays[-1] if self.retry_delays else 30
            self.retry_delays.extend([last_delay] * (self.max_retries - len(self.retry_delays)))
        
        # 重试队列（优先队列，按时间排序）
        self.retry_queue: List[RetryMessage] = []
        self.queue_lock = asyncio.Lock()
        
        # 是否运行中
        self.is_running = False
        self._retry_task: Optional[asyncio.Task] = None
        
        logger.info(
            f"重试管理器初始化完成 - "
            f"最大重试次数: {self.max_retries}, "
            f"重试延迟: {self.retry_delays}"
        )
    
    def _get_retry_topic(self, original_topic: str) -> str:
        """
        获取重试 Topic 名称
        
        Args:
            original_topic: 原始 Topic 名称
            
        Returns:
            重试 Topic 名称
        """
        return KafkaTopics.get_retry_topic(original_topic)
    
    def _calculate_next_retry_time(self, retry_count: int) -> datetime:
        """
        计算下次重试时间
        
        Args:
            retry_count: 当前重试次数（从 0 开始）
            
        Returns:
            下次重试时间
        """
        if retry_count >= len(self.retry_delays):
            delay = self.retry_delays[-1]
        else:
            delay = self.retry_delays[retry_count]
        
        next_time = datetime.now(timezone.utc) + timedelta(seconds=delay)
        return next_time
    
    async def schedule_retry(
        self,
        message: BaseMessage,
        original_topic: str,
        error: str
    ) -> bool:
        """
        调度消息重试
        
        Args:
            message: 原始消息
            original_topic: 原始 Topic 名称
            error: 失败原因
            
        Returns:
            是否成功调度（False 表示已达最大重试次数）
        """
        current_retry = message.metadata.retry_count
        
        # 检查是否超过最大重试次数
        if current_retry >= self.max_retries:
            logger.warning(
                f"消息已达最大重试次数 {self.max_retries}，"
                f"发送到DLQ - event_id: {message.metadata.event_id}"
            )
            
            # 发送到 DLQ
            if self.dlq_manager is not None:
                await self.dlq_manager.send_to_dlq(
                    message=message,
                    original_topic=original_topic,
                    error=f"超过最大重试次数 {self.max_retries}. 最后错误: {error}"
                )
            
            return False
        
        # 增加重试计数
        message.increment_retry()
        
        # 计算下次重试时间
        next_retry_time = self._calculate_next_retry_time(current_retry)
        
        # 创建重试消息
        retry_msg = RetryMessage(
            original_message=message,
            error=error,
            next_retry_time=next_retry_time,
            retry_count=current_retry + 1
        )
        
        # 添加到重试队列
        async with self.queue_lock:
            self.retry_queue.append(retry_msg)
            # 按时间排序（最早的在前面）
            self.retry_queue.sort()
        
        logger.info(
            f"消息已调度重试 - "
            f"event_id: {message.metadata.event_id}, "
            f"重试次数: {current_retry + 1}/{self.max_retries}, "
            f"下次重试时间: {next_retry_time.isoformat()}"
        )
        
        return True
    
    async def _process_retry_queue(self) -> None:
        """
        处理重试队列（后台任务）
        
        定期检查队列，将到期的消息发送到重试 Topic。
        """
        logger.info("重试队列处理任务已启动")
        
        while self.is_running:
            try:
                now = datetime.now(timezone.utc)
                messages_to_retry: List[RetryMessage] = []
                
                # 获取到期的消息
                async with self.queue_lock:
                    while self.retry_queue and self.retry_queue[0].next_retry_time <= now:
                        messages_to_retry.append(self.retry_queue.pop(0))
                
                # 发送到重试 Topic
                for retry_msg in messages_to_retry:
                    try:
                        # 从消息中获取原始 topic（如果有的话）
                        original_topic = retry_msg.original_message.metadata.context.get("original_topic", "unknown")
                        retry_topic = self._get_retry_topic(original_topic)
                        
                        # 发送消息
                        await self.producer.send_message(
                            topic=retry_topic,
                            message=retry_msg.original_message
                        )
                        
                        logger.info(
                            f"消息已发送到重试Topic - "
                            f"event_id: {retry_msg.event_id}, "
                            f"重试次数: {retry_msg.retry_count}, "
                            f"topic: {retry_topic}"
                        )
                    except Exception as e:
                        logger.error(
                            f"发送重试消息失败 - "
                            f"event_id: {retry_msg.event_id}: {e}"
                        )
                        # 重新加入队列
                        async with self.queue_lock:
                            self.retry_queue.append(retry_msg)
                            self.retry_queue.sort()
                
                # 短暂休眠
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"重试队列处理出错: {e}", exc_info=True)
                await asyncio.sleep(5)
        
        logger.info("重试队列处理任务已停止")
    
    async def start(self) -> None:
        """启动重试管理器"""
        if self.is_running:
            logger.warning("重试管理器已在运行")
            return
        
        self.is_running = True
        self._retry_task = asyncio.create_task(self._process_retry_queue())
        logger.info("重试管理器已启动")
    
    async def stop(self) -> None:
        """停止重试管理器"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self._retry_task is not None:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
            self._retry_task = None
        
        logger.info("重试管理器已停止")
    
    async def get_stats(self) -> dict:
        """
        获取重试统计信息
        
        Returns:
            统计信息字典
        """
        async with self.queue_lock:
            queue_size = len(self.retry_queue)
            
            if queue_size > 0:
                next_retry = self.retry_queue[0].next_retry_time
                pending_retries = {}
                for msg in self.retry_queue:
                    count = pending_retries.get(msg.retry_count, 0)
                    pending_retries[msg.retry_count] = count + 1
            else:
                next_retry = None
                pending_retries = {}
        
        return {
            "is_running": self.is_running,
            "max_retries": self.max_retries,
            "retry_delays": self.retry_delays,
            "queue_size": queue_size,
            "next_retry_time": next_retry.isoformat() if next_retry else None,
            "pending_retries_by_count": pending_retries
        }
    
    async def clear_queue(self) -> int:
        """
        清空重试队列（测试用）
        
        Returns:
            清空的消息数量
        """
        async with self.queue_lock:
            count = len(self.retry_queue)
            self.retry_queue.clear()
        
        logger.warning(f"已清空重试队列，共 {count} 条消息")
        return count


# 全局重试管理器实例（单例）
_retry_manager: Optional[RetryManager] = None


async def get_retry_manager(
    producer: object,
    dlq_manager: Optional[object] = None,
    force_new: bool = False
) -> RetryManager:
    """
    获取全局重试管理器实例（单例）
    
    Args:
        producer: Kafka Producer 实例
        dlq_manager: DLQ 管理器实例
        force_new: 是否强制创建新实例（测试用）
        
    Returns:
        重试管理器实例
    """
    global _retry_manager
    
    if _retry_manager is None or force_new:
        _retry_manager = RetryManager(
            producer=producer,
            dlq_manager=dlq_manager
        )
    
    return _retry_manager


async def close_retry_manager() -> None:
    """关闭全局重试管理器"""
    global _retry_manager
    
    if _retry_manager is not None:
        await _retry_manager.stop()
        _retry_manager = None
        logger.info("重试管理器已关闭")
