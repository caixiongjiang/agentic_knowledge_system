#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka 连接管理模块

提供 Kafka 连接的创建、管理和销毁功能。
"""

from src.db.kafka.connection.factory import get_kafka_manager
from src.db.kafka.connection.base import BaseKafkaManager

__all__ = [
    "get_kafka_manager",
    "BaseKafkaManager",
]
