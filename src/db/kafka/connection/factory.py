#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka 连接工厂

提供全局单例的 Kafka 连接管理器。
"""

from typing import Optional
from loguru import logger

from src.db.kafka.connection.kafka_manager import KafkaManager
from src.utils.config_manager import get_config_manager


# 全局 Kafka Manager 实例
_kafka_manager: Optional[KafkaManager] = None


def get_kafka_manager(force_new: bool = False) -> KafkaManager:
    """
    获取全局 Kafka Manager 实例（单例模式）
    
    Args:
        force_new: 是否强制创建新实例（用于测试或重新连接）
        
    Returns:
        KafkaManager: Kafka 连接管理器实例
        
    Example:
        # 获取 Manager
        kafka_manager = get_kafka_manager()
        
        # 建立连接
        await kafka_manager.connect()
        
        # 获取 Producer
        producer = await kafka_manager.get_producer()
        
        # 发送消息
        await producer.send("my_topic", value=b"message")
        
        # 断开连接
        await kafka_manager.disconnect()
    """
    global _kafka_manager
    
    if force_new or _kafka_manager is None:
        # 从配置文件加载 Kafka 配置（使用统一的配置管理器）
        config_manager = get_config_manager()
        kafka_config = config_manager.get_kafka_config()
        
        if not kafka_config:
            raise ValueError("Kafka 配置未找到，请检查 config.toml")
        
        logger.info("创建新的 KafkaManager 实例")
        _kafka_manager = KafkaManager(kafka_config)
    
    return _kafka_manager


async def close_kafka_manager() -> None:
    """
    关闭全局 Kafka Manager 实例
    
    在应用关闭时调用，确保资源正确释放。
    """
    global _kafka_manager
    
    if _kafka_manager is not None:
        try:
            await _kafka_manager.disconnect()
            logger.info("KafkaManager 已关闭")
        except Exception as e:
            logger.error(f"关闭 KafkaManager 失败: {e}")
        finally:
            _kafka_manager = None


def reset_kafka_manager() -> None:
    """
    重置全局 Kafka Manager 实例
    
    主要用于测试环境。
    """
    global _kafka_manager
    _kafka_manager = None
    logger.info("KafkaManager 已重置")
