#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : database.py
@Author  : caixiongjiang
@Date    : 2026/01/21 10:00
@Function: 
    数据库依赖模块
    提供数据库连接的依赖注入功能
@Modify History:
    2026/02/18 - 实现 MySQL Session、StorageManager、KafkaProducer 依赖注入
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import AsyncGenerator, Generator
from sqlalchemy.orm import Session

from src.db.mysql.connection.factory import get_mysql_manager
from src.db.storage.manager import StorageManager
from src.db.kafka.connection.factory import get_kafka_manager
from src.db.kafka.producer import KafkaProducer
from src.db.redis.connection.factory import get_redis_manager
from src.states.state_manager import FileProgressManager


def get_db_session() -> Generator[Session, None, None]:
    """
    获取 MySQL 数据库会话（FastAPI 依赖注入）

    Yields:
        Session: SQLAlchemy 数据库会话
    """
    manager = get_mysql_manager()
    with manager.get_session() as session:
        yield session


async def get_storage_manager() -> AsyncGenerator[StorageManager, None]:
    """
    获取对象存储管理器（FastAPI 依赖注入）

    Yields:
        StorageManager: 对象存储管理器实例
    """
    async with StorageManager() as manager:
        yield manager


async def get_kafka_producer() -> AsyncGenerator[KafkaProducer, None]:
    """
    获取 Kafka Producer（FastAPI 依赖注入）

    Yields:
        KafkaProducer: Kafka 消息生产者封装
    """
    kafka_manager = get_kafka_manager()
    if not kafka_manager._is_connected:
        await kafka_manager.connect()
    raw_producer = await kafka_manager.get_producer()
    yield KafkaProducer(raw_producer)


async def get_file_progress_manager() -> AsyncGenerator[FileProgressManager, None]:
    """
    获取文件索引进度管理器（FastAPI 依赖注入）

    Yields:
        FileProgressManager: 基于 Redis 的进度管理器
    """
    redis_manager = await get_redis_manager()
    yield FileProgressManager(redis_manager)
