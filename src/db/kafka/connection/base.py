#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka 连接管理器基类

定义 Kafka 连接管理器的抽象接口。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer


class BaseKafkaManager(ABC):
    """
    Kafka 连接管理器基类
    
    职责：
    - 管理 Kafka 连接生命周期
    - 提供 Producer 和 Consumer 实例
    - 处理连接配置和认证
    - 管理连接池和资源清理
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Kafka 连接管理器
        
        Args:
            config: Kafka 配置字典
        """
        self.config = config
        self._producer: Optional[AIOKafkaProducer] = None
        self._consumers: Dict[str, AIOKafkaConsumer] = {}
        self._is_connected = False
    
    @abstractmethod
    async def connect(self) -> None:
        """
        建立 Kafka 连接
        
        创建必要的连接实例并验证连接有效性。
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        断开 Kafka 连接
        
        清理所有连接资源，包括 Producer 和 Consumer。
        """
        pass
    
    @abstractmethod
    async def get_producer(self) -> AIOKafkaProducer:
        """
        获取 Kafka Producer 实例
        
        Returns:
            AIOKafkaProducer: 已连接的 Producer 实例
            
        Raises:
            RuntimeError: 如果连接未建立
        """
        pass
    
    @abstractmethod
    async def get_consumer(
        self,
        topics: list[str],
        group_id: str,
        **kwargs
    ) -> AIOKafkaConsumer:
        """
        获取 Kafka Consumer 实例
        
        Args:
            topics: 要订阅的 Topic 列表
            group_id: Consumer Group ID
            **kwargs: 额外的 Consumer 配置参数
            
        Returns:
            AIOKafkaConsumer: 已连接的 Consumer 实例
            
        Raises:
            RuntimeError: 如果连接未建立
        """
        pass
    
    @abstractmethod
    async def create_topics(
        self,
        topic_configs: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        创建 Kafka Topics
        
        Args:
            topic_configs: Topic 配置字典
                格式: {
                    "topic_name": {
                        "num_partitions": 32,
                        "replication_factor": 3,
                        "config": {...}
                    }
                }
        """
        pass
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._is_connected
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()
