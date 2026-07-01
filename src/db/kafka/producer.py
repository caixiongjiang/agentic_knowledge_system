#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka Producer 封装

提供统一的消息发送接口，自动处理序列化、Key 生成等。
"""

import asyncio
from typing import Optional, List
from aiokafka import AIOKafkaProducer
from aiokafka.structs import RecordMetadata
from loguru import logger

from src.types.messages.base import BaseMessage


class KafkaProducer:
    """
    Kafka Producer 封装类
    
    功能：
    - 自动序列化消息（BaseMessage -> JSON bytes）
    - 自动生成 Message Key（{user_id}:{file_id}）
    - 支持单条和批量发送
    - 提供简洁的 API
    - 错误处理和日志记录
    
    使用示例：
        from src.db.kafka import get_kafka_manager, KafkaTopics
        from src.db.kafka.producer import KafkaProducer
        from src.types.messages import IndexStartMessage
        
        # 获取 Manager 并连接
        manager = get_kafka_manager()
        await manager.connect()
        
        # 创建 Producer 封装
        producer = KafkaProducer(await manager.get_producer())
        
        # 发送消息
        message = IndexStartMessage(
            user_id="user_123",
            file_id="file_456",
            s3_path="s3://bucket/user_123/file_456.pdf",
            filename="document.pdf",
            file_size=1024000,
            mime_type="application/pdf",
            file_extension=".pdf"
        )
        
        await producer.send_message(
            topic=KafkaTopics.INDEX_START,
            message=message
        )
    """
    
    def __init__(self, aiokafka_producer: AIOKafkaProducer):
        """
        初始化 Producer 封装
        
        Args:
            aiokafka_producer: aiokafka 的 Producer 实例
        """
        self._producer = aiokafka_producer
    
    async def send_message(
        self,
        topic: str,
        message: BaseMessage,
        key: Optional[str] = None,
        partition: Optional[int] = None,
        headers: Optional[List[tuple[str, bytes]]] = None
    ) -> RecordMetadata:
        """
        发送单条消息
        
        Args:
            topic: Topic 名称
            message: 消息对象（BaseMessage 子类）
            key: 消息 Key（默认自动从 message 生成）
            partition: 指定分区（默认根据 key 哈希分配）
            headers: 消息头（可选）
            
        Returns:
            RecordMetadata: 发送结果元数据（topic, partition, offset）
            
        Raises:
            ValueError: 如果消息类型不正确
            RuntimeError: 如果发送失败
        """
        if not isinstance(message, BaseMessage):
            raise ValueError(f"message 必须是 BaseMessage 的子类，实际类型: {type(message)}")
        
        try:
            # 自动生成 Key（如果未指定）
            if key is None:
                key = message.get_message_key()
            
            # 序列化消息
            value = message.to_bytes()
            key_bytes = key.encode("utf-8")
            
            # 发送消息（send 返回 Future，需要 await 两次）
            future = await self._producer.send(
                topic=topic,
                value=value,
                key=key_bytes,
                partition=partition,
                headers=headers
            )
            
            # 等待消息实际发送完成
            metadata = await future
            
            logger.debug(
                f"消息已发送: topic={topic}, partition={metadata.partition}, "
                f"offset={metadata.offset}, key={key}"
            )
            
            return metadata
            
        except Exception as e:
            logger.error(f"发送消息失败: topic={topic}, key={key}, error={e}")
            raise RuntimeError(f"发送消息失败: {e}") from e
    
    async def send_messages(
        self,
        topic: str,
        messages: List[BaseMessage],
        partition: Optional[int] = None
    ) -> List[RecordMetadata]:
        """
        批量发送消息
        
        Args:
            topic: Topic 名称
            messages: 消息列表
            partition: 指定分区（默认根据 key 哈希分配）
            
        Returns:
            发送结果元数据列表
            
        Raises:
            ValueError: 如果消息列表为空或类型不正确
            RuntimeError: 如果发送失败
        
        说明（P2 #7）：
            先把全部消息入队到 aiokafka（拿到每条的 Future），再用 asyncio.gather
            统一等待 ack。aiokafka 内部会按 linger_ms / batch_size 把同分区消息
            合并成更少的 broker 请求，吞吐显著优于「逐条 send 再逐条 await」。
        """
        if not messages:
            raise ValueError("消息列表不能为空")
        
        if not all(isinstance(msg, BaseMessage) for msg in messages):
            raise ValueError("所有消息必须是 BaseMessage 的子类")
        
        try:
            # 1. 全部入队，收集 Future（send 仅入队，不等待 ack）
            futures = []
            for message in messages:
                key = message.get_message_key()
                value = message.to_bytes()
                future = await self._producer.send(
                    topic=topic,
                    value=value,
                    key=key.encode("utf-8"),
                    partition=partition
                )
                futures.append(future)
            
            # 2. 并发等待全部 ack
            results = await asyncio.gather(*futures)
            
            logger.info(f"批量发送完成: topic={topic}, count={len(messages)}")
            return results
            
        except Exception as e:
            logger.error(f"批量发送失败: topic={topic}, count={len(messages)}, error={e}")
            raise RuntimeError(f"批量发送失败: {e}") from e
    
    async def flush(self) -> None:
        """
        刷新所有待发送的消息
        
        确保所有消息都已发送到 Kafka Broker。
        """
        try:
            await self._producer.flush()
            logger.debug("Producer 已刷新所有待发送消息")
        except Exception as e:
            logger.error(f"刷新 Producer 失败: {e}")
            raise RuntimeError(f"刷新 Producer 失败: {e}") from e
    
    async def send_and_flush(
        self,
        topic: str,
        message: BaseMessage,
        key: Optional[str] = None,
        partition: Optional[int] = None
    ) -> RecordMetadata:
        """
        发送消息并立即刷新
        
        适用于需要确保消息立即发送的场景（如关键业务消息）。
        
        Args:
            topic: Topic 名称
            message: 消息对象
            key: 消息 Key（默认自动生成）
            partition: 指定分区
            
        Returns:
            RecordMetadata: 发送结果元数据
        """
        metadata = await self.send_message(
            topic=topic,
            message=message,
            key=key,
            partition=partition
        )
        await self.flush()
        return metadata
    
    def get_raw_producer(self) -> AIOKafkaProducer:
        """
        获取底层的 aiokafka Producer 实例
        
        用于需要直接使用 aiokafka API 的场景。
        
        Returns:
            AIOKafkaProducer 实例
        """
        return self._producer
