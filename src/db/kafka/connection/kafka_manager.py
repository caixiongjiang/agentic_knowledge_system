#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka 连接管理器实现

基于 aiokafka 的异步 Kafka 连接管理。
"""

from typing import Dict, Any, Optional
from loguru import logger
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError

from src.db.kafka.connection.base import BaseKafkaManager
from src.utils.env_manager import get_env_manager


class KafkaManager(BaseKafkaManager):
    """
    Kafka 连接管理器
    
    功能：
    - 管理 Producer 和 Consumer 连接
    - 支持 SASL/SSL 认证
    - 自动创建 Topics
    - 连接池管理
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Kafka 连接管理器
        
        Args:
            config: Kafka 配置字典，包含：
                - bootstrap_servers: Kafka 集群地址列表
                - security_protocol: 安全协议
                - sasl_mechanism: SASL 机制
                - producer: Producer 配置
                - consumer: Consumer 配置
        """
        super().__init__(config)
        
        # 获取环境变量管理器
        self.env_manager = get_env_manager()
        
        # 获取 bootstrap_servers
        self.bootstrap_servers = config.get("bootstrap_servers", ["localhost:9092"])
        
        # 安全配置
        self.security_protocol = config.get("security_protocol", "PLAINTEXT")
        self.sasl_mechanism = config.get("sasl_mechanism", "PLAIN")
        
        # 从环境变量获取认证信息
        kafka_auth = self.env_manager.get_kafka_auth()
        self.sasl_username = kafka_auth.get("sasl_username")
        self.sasl_password = kafka_auth.get("sasl_password")
        
        # SSL 配置
        self.ssl_cafile = kafka_auth.get("ssl_cafile")
        self.ssl_certfile = kafka_auth.get("ssl_certfile")
        self.ssl_keyfile = kafka_auth.get("ssl_keyfile")
        self.ssl_password = kafka_auth.get("ssl_password")
        
        # Producer 和 Consumer 配置
        self.producer_config = config.get("producer", {})
        self.consumer_config = config.get("consumer", {})
        
        # Admin Client（用于创建 Topics）
        self._admin_client: Optional[AIOKafkaAdminClient] = None
        
        logger.info(f"初始化 KafkaManager，连接到: {self.bootstrap_servers}")
    
    def _build_connection_config(self) -> Dict[str, Any]:
        """
        构建通用连接配置
        
        Returns:
            包含认证和 SSL 配置的字典
        """
        config = {
            "bootstrap_servers": self.bootstrap_servers,
            "security_protocol": self.security_protocol,
        }
        
        # SASL 认证配置
        if self.security_protocol in ("SASL_PLAINTEXT", "SASL_SSL"):
            if self.sasl_username and self.sasl_password:
                config["sasl_mechanism"] = self.sasl_mechanism
                config["sasl_plain_username"] = self.sasl_username
                config["sasl_plain_password"] = self.sasl_password
            else:
                logger.warning("SASL 认证启用但未提供用户名或密码")
        
        # SSL 配置
        if self.security_protocol in ("SSL", "SASL_SSL"):
            if self.ssl_cafile:
                config["ssl_cafile"] = self.ssl_cafile
            if self.ssl_certfile:
                config["ssl_certfile"] = self.ssl_certfile
            if self.ssl_keyfile:
                config["ssl_keyfile"] = self.ssl_keyfile
            if self.ssl_password:
                config["ssl_password"] = self.ssl_password
        
        return config
    
    async def connect(self) -> None:
        """
        建立 Kafka 连接
        
        创建 Producer 和 Admin Client 实例。
        """
        if self._is_connected:
            logger.warning("Kafka 已连接，跳过重复连接")
            return
        
        try:
            # 构建基础连接配置
            connection_config = self._build_connection_config()
            
            # 创建 Producer
            # 注意：aiokafka 的参数名称和默认行为与 kafka-python 略有不同
            # acks: 0, 1, 或 'all' (-1)
            acks_value = self.producer_config.get("acks", "all")
            if acks_value == "all":
                acks_value = -1  # aiokafka 使用 -1 表示 all
            
            producer_config = {
                **connection_config,
                "acks": acks_value,
                # aiokafka 没有 retries 参数，它会自动重试
                # "retries": self.producer_config.get("retries", 3),  # 不支持
                "max_batch_size": self.producer_config.get("batch_size", 65536),  # 注意参数名
                "linger_ms": self.producer_config.get("linger_ms", 5),
                "compression_type": self.producer_config.get("compression_type", "lz4"),
                "request_timeout_ms": self.producer_config.get("request_timeout_ms", 30000),
                "max_request_size": self.producer_config.get("max_request_size", 1048576),
            }
            
            self._producer = AIOKafkaProducer(**producer_config)
            await self._producer.start()
            logger.info("Kafka Producer 已连接")
            
            # 创建 Admin Client（用于创建 Topics）
            self._admin_client = AIOKafkaAdminClient(**connection_config)
            await self._admin_client.start()
            logger.info("Kafka Admin Client 已连接")
            
            self._is_connected = True
            logger.success("Kafka 连接成功")
            
        except Exception as e:
            logger.error(f"Kafka 连接失败: {e}")
            await self.disconnect()
            raise
    
    async def disconnect(self) -> None:
        """
        断开 Kafka 连接
        
        清理所有连接资源。
        """
        if not self._is_connected:
            return
        
        try:
            # 关闭所有 Consumers
            for consumer_id, consumer in self._consumers.items():
                try:
                    await consumer.stop()
                    logger.info(f"Consumer {consumer_id} 已关闭")
                except Exception as e:
                    logger.error(f"关闭 Consumer {consumer_id} 失败: {e}")
            self._consumers.clear()
            
            # 关闭 Producer
            if self._producer:
                await self._producer.stop()
                self._producer = None
                logger.info("Kafka Producer 已关闭")
            
            # 关闭 Admin Client
            if self._admin_client:
                await self._admin_client.close()
                self._admin_client = None
                logger.info("Kafka Admin Client 已关闭")
            
            self._is_connected = False
            logger.success("Kafka 连接已断开")
            
        except Exception as e:
            logger.error(f"断开 Kafka 连接时出错: {e}")
            raise
    
    async def get_producer(self) -> AIOKafkaProducer:
        """
        获取 Kafka Producer 实例
        
        Returns:
            AIOKafkaProducer: 已连接的 Producer 实例
            
        Raises:
            RuntimeError: 如果连接未建立
        """
        if not self._is_connected or not self._producer:
            raise RuntimeError("Kafka 未连接，请先调用 connect()")
        
        return self._producer
    
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
        if not self._is_connected:
            raise RuntimeError("Kafka 未连接，请先调用 connect()")
        
        # 生成唯一的 Consumer ID
        consumer_id = f"{group_id}:{','.join(topics)}"
        
        # 如果已存在相同的 Consumer，直接返回
        if consumer_id in self._consumers:
            logger.info(f"复用现有 Consumer: {consumer_id}")
            return self._consumers[consumer_id]
        
        try:
            # 构建 Consumer 配置
            connection_config = self._build_connection_config()
            consumer_config = {
                **connection_config,
                "group_id": group_id,
                "enable_auto_commit": self.consumer_config.get("enable_auto_commit", False),
                "auto_commit_interval_ms": self.consumer_config.get("auto_commit_interval_ms", 5000),
                "auto_offset_reset": self.consumer_config.get("auto_offset_reset", "earliest"),
                "max_poll_records": self.consumer_config.get("max_poll_records", 500),
                "fetch_min_bytes": self.consumer_config.get("fetch_min_bytes", 1),
                "fetch_max_wait_ms": self.consumer_config.get("fetch_max_wait_ms", 500),
                "request_timeout_ms": self.consumer_config.get("request_timeout_ms", 60000),
                "retry_backoff_ms": self.consumer_config.get("retry_backoff_ms", 500),
                "session_timeout_ms": self.consumer_config.get("session_timeout_ms", 30000),
                "heartbeat_interval_ms": self.consumer_config.get("heartbeat_interval_ms", 3000),
                "max_poll_interval_ms": self.consumer_config.get("max_poll_interval_ms", 300000),
                **kwargs,  # 允许覆盖配置
            }
            
            # 创建 Consumer
            consumer = AIOKafkaConsumer(*topics, **consumer_config)
            await consumer.start()
            
            # 缓存 Consumer
            self._consumers[consumer_id] = consumer
            
            logger.info(f"Consumer 已创建: {consumer_id}")
            return consumer
            
        except Exception as e:
            logger.error(f"创建 Consumer 失败: {e}")
            raise
    
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
                        "config": {
                            "retention.ms": "604800000",
                            "cleanup.policy": "delete"
                        }
                    }
                }
        """
        if not self._is_connected or not self._admin_client:
            raise RuntimeError("Kafka 未连接，请先调用 connect()")
        
        try:
            # 构建 NewTopic 对象列表
            new_topics = []
            for topic_name, config in topic_configs.items():
                new_topic = NewTopic(
                    name=topic_name,
                    num_partitions=config.get("num_partitions", 1),
                    replication_factor=config.get("replication_factor", 1),
                    topic_configs=config.get("config", {})
                )
                new_topics.append(new_topic)
            
            # 创建 Topics
            await self._admin_client.create_topics(new_topics, validate_only=False)
            logger.success(f"成功创建 {len(new_topics)} 个 Topics")
            
        except TopicAlreadyExistsError:
            logger.warning("部分 Topic 已存在，跳过创建")
        except Exception as e:
            logger.error(f"创建 Topics 失败: {e}")
            raise
    
    async def list_topics(self) -> list[str]:
        """
        列出所有 Topics
        
        Returns:
            Topic 名称列表
        """
        if not self._is_connected or not self._admin_client:
            raise RuntimeError("Kafka 未连接，请先调用 connect()")
        
        try:
            metadata = await self._admin_client.list_topics()
            return list(metadata)
        except Exception as e:
            logger.error(f"列出 Topics 失败: {e}")
            raise
