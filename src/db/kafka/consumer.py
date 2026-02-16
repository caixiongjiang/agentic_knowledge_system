#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka Consumer 封装

提供统一的消息消费接口，自动处理反序列化、offset 管理等。
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Type, Optional, Dict, Any, List
from aiokafka import AIOKafkaConsumer
from aiokafka.structs import ConsumerRecord
from loguru import logger

from src.types.messages.base import BaseMessage


class BaseKafkaConsumer(ABC):
    """
    Kafka Consumer 抽象基类
    
    提供通用的消费逻辑框架，子类只需实现 process_message 方法。
    
    功能：
    - 自动反序列化消息（JSON bytes -> BaseMessage）
    - 手动提交 offset 管理
    - 错误处理和重试
    - 批量消费支持
    - 优雅关闭
    
    使用示例：
        from src.db.kafka.consumer import BaseKafkaConsumer
        from src.types.messages import IndexStartMessage
        
        class FileParserConsumer(BaseKafkaConsumer):
            async def process_message(self, message: IndexStartMessage) -> bool:
                # 实现具体的处理逻辑
                logger.info(f"处理文件: {message.file_id}")
                # ... 解析文件 ...
                return True  # 返回 True 表示处理成功
        
        # 创建并运行
        consumer = FileParserConsumer(
            aiokafka_consumer=await manager.get_consumer("my_group", "my_topic"),
            message_class=IndexStartMessage
        )
        
        await consumer.start()
    """
    
    def __init__(
        self,
        aiokafka_consumer: AIOKafkaConsumer,
        message_class: Type[BaseMessage],
        batch_size: int = 1,
        auto_commit: bool = False,
        commit_interval: int = 100
    ):
        """
        初始化 Consumer 封装
        
        Args:
            aiokafka_consumer: aiokafka 的 Consumer 实例
            message_class: 消息类型（BaseMessage 的子类）
            batch_size: 批处理大小（每次拉取的消息数量）
            auto_commit: 是否自动提交 offset（默认手动提交）
            commit_interval: 提交间隔（处理多少条消息后提交一次）
        """
        self._consumer = aiokafka_consumer
        self._message_class = message_class
        self._batch_size = batch_size
        self._auto_commit = auto_commit
        self._commit_interval = commit_interval
        
        self._running = False
        self._processed_count = 0
        self._failed_count = 0
    
    @abstractmethod
    async def process_message(self, message: BaseMessage) -> bool:
        """
        处理单条消息（子类必须实现）
        
        Args:
            message: 反序列化后的消息对象
            
        Returns:
            bool: True 表示处理成功，False 表示处理失败
            
        注意：
        - 如果返回 False，消息会被记录但不会阻塞后续消息处理
        - 如果抛出异常，消息会被记录并根据配置决定是否重试
        """
        pass
    
    async def start(self) -> None:
        """
        启动消费者
        
        开始消费消息并处理。这是一个阻塞方法，会持续运行直到调用 stop()。
        """
        self._running = True
        logger.info(f"Consumer 已启动: {self._consumer.subscription()}")
        
        try:
            while self._running:
                # 批量拉取消息
                records = await self._fetch_batch()
                
                if not records:
                    # 没有消息时短暂休眠
                    await asyncio.sleep(0.1)
                    continue
                
                # 处理消息批次
                await self._process_batch(records)
                
        except asyncio.CancelledError:
            logger.info("Consumer 收到取消信号")
        except Exception as e:
            logger.error(f"Consumer 运行异常: {e}")
            raise
        finally:
            await self._cleanup()
    
    async def stop(self) -> None:
        """
        停止消费者
        
        优雅地停止消费循环。
        """
        logger.info("正在停止 Consumer...")
        self._running = False
    
    async def _fetch_batch(self) -> List[ConsumerRecord]:
        """
        拉取一批消息
        
        Returns:
            ConsumerRecord 列表
        """
        try:
            # getmany() 返回 {TopicPartition: [ConsumerRecord]} 字典
            data = await self._consumer.getmany(
                timeout_ms=1000,
                max_records=self._batch_size
            )
            
            # 展平为单一列表
            records = []
            for partition_records in data.values():
                records.extend(partition_records)
            
            return records
            
        except Exception as e:
            logger.error(f"拉取消息失败: {e}")
            return []
    
    async def _process_batch(self, records: List[ConsumerRecord]) -> None:
        """
        处理一批消息
        
        Args:
            records: ConsumerRecord 列表
        """
        for record in records:
            try:
                # 反序列化消息
                message = self._deserialize_message(record)
                
                # 处理消息
                success = await self.process_message(message)
                
                if success:
                    self._processed_count += 1
                    logger.debug(
                        f"消息处理成功: topic={record.topic}, "
                        f"partition={record.partition}, offset={record.offset}"
                    )
                else:
                    self._failed_count += 1
                    logger.warning(
                        f"消息处理失败: topic={record.topic}, "
                        f"partition={record.partition}, offset={record.offset}"
                    )
                
                # 手动提交 offset（如果不是自动提交）
                if not self._auto_commit and self._processed_count % self._commit_interval == 0:
                    await self._commit_offset()
                
            except Exception as e:
                self._failed_count += 1
                logger.error(
                    f"处理消息时发生异常: topic={record.topic}, "
                    f"partition={record.partition}, offset={record.offset}, error={e}"
                )
                # 继续处理下一条消息（可根据需求调整）
        
        # 批次处理完成后提交 offset
        if not self._auto_commit:
            await self._commit_offset()
    
    def _deserialize_message(self, record: ConsumerRecord) -> BaseMessage:
        """
        反序列化消息
        
        Args:
            record: Kafka 消息记录
            
        Returns:
            反序列化后的消息对象
            
        Raises:
            ValueError: 如果反序列化失败
        """
        try:
            message = self._message_class.from_bytes(record.value)
            return message
        except Exception as e:
            logger.error(f"反序列化消息失败: {e}, value={record.value[:100]}")
            raise ValueError(f"反序列化消息失败: {e}") from e
    
    async def _commit_offset(self) -> None:
        """提交 offset"""
        try:
            await self._consumer.commit()
            logger.debug(f"Offset 已提交，已处理: {self._processed_count} 条消息")
        except Exception as e:
            logger.error(f"提交 offset 失败: {e}")
    
    async def _cleanup(self) -> None:
        """内部清理资源（由 start() 的 finally 调用）"""
        await self.cleanup()
    
    async def cleanup(self) -> None:
        """
        清理资源
        
        子类可以覆盖此方法来清理自己的资源，但必须调用 super().cleanup()。
        """
        try:
            # 最后一次提交 offset
            if not self._auto_commit:
                await self._commit_offset()
            
            logger.info(
                f"Consumer 已停止，统计: 成功={self._processed_count}, "
                f"失败={self._failed_count}"
            )
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
    
    def get_raw_consumer(self) -> AIOKafkaConsumer:
        """
        获取底层的 aiokafka Consumer 实例
        
        Returns:
            AIOKafkaConsumer 实例
        """
        return self._consumer
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取消费统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "processed_count": self._processed_count,
            "failed_count": self._failed_count,
            "success_rate": (
                self._processed_count / (self._processed_count + self._failed_count)
                if (self._processed_count + self._failed_count) > 0
                else 0.0
            ),
            "running": self._running
        }


class BatchKafkaConsumer(BaseKafkaConsumer):
    """
    批量处理的 Kafka Consumer
    
    与 BaseKafkaConsumer 不同，这个类支持批量处理消息。
    子类需要实现 process_batch 方法而不是 process_message。
    
    使用示例：
        class BatchEmbeddingWriter(BatchKafkaConsumer):
            async def process_batch(self, messages: List[EmbeddingWriteMessage]) -> List[bool]:
                # 批量处理消息
                embeddings = await generate_embeddings([m.text for m in messages])
                await milvus.insert(embeddings)
                return [True] * len(messages)  # 返回每条消息的处理结果
    """
    
    async def process_message(self, message: BaseMessage) -> bool:
        """
        单条消息处理（由框架调用）
        
        不需要子类实现，由 process_batch 统一处理。
        """
        raise NotImplementedError("BatchKafkaConsumer 使用 process_batch 而不是 process_message")
    
    @abstractmethod
    async def process_batch(self, messages: List[BaseMessage]) -> List[bool]:
        """
        批量处理消息（子类必须实现）
        
        Args:
            messages: 消息列表
            
        Returns:
            处理结果列表（每条消息对应一个 bool 值）
        """
        pass
    
    async def _process_batch(self, records: List[ConsumerRecord]) -> None:
        """
        处理一批消息（覆盖父类方法）
        
        Args:
            records: ConsumerRecord 列表
        """
        if not records:
            return
        
        try:
            # 反序列化所有消息
            messages = []
            for record in records:
                try:
                    message = self._deserialize_message(record)
                    messages.append(message)
                except Exception as e:
                    logger.error(f"反序列化消息失败，跳过: {e}")
                    self._failed_count += 1
            
            if not messages:
                return
            
            # 批量处理
            results = await self.process_batch(messages)
            
            # 统计结果
            for success in results:
                if success:
                    self._processed_count += 1
                else:
                    self._failed_count += 1
            
            logger.info(
                f"批量处理完成: total={len(records)}, "
                f"success={sum(results)}, failed={len(results) - sum(results)}"
            )
            
            # 提交 offset
            if not self._auto_commit:
                await self._commit_offset()
                
        except Exception as e:
            logger.error(f"批量处理失败: {e}")
            self._failed_count += len(records)
