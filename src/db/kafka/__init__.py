#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka 消息队列基础设施

提供：
- Kafka 连接管理
- Producer/Consumer 封装
- Topic 配置管理
- 消息类型定义
- 幂等性保证
- 重试机制
- 死信队列管理
- Worker 组件 (业务处理)
- Writer 组件 (数据库批量写入)
"""

from src.db.kafka.connection.factory import get_kafka_manager
from src.db.kafka.topics import KafkaTopics
from src.db.kafka.types import MessageKey, ConsumerGroup
from src.db.kafka.producer import KafkaProducer
from src.db.kafka.consumer import BaseKafkaConsumer, BatchKafkaConsumer
from src.db.kafka.deduplication import (
    DeduplicationManager,
    get_deduplication_manager,
    close_deduplication_manager,
    close_redis_manager
)
from src.db.kafka.retry_manager import (
    RetryManager,
    RetryStrategy,
    get_retry_manager,
    close_retry_manager
)
from src.db.kafka.dlq_manager import (
    DLQManager,
    DLQRecord,
    get_dlq_manager,
    close_dlq_manager
)

# Phase 4: Worker 组件
from src.db.kafka.workers import (
    BaseWorker,
    FileParserWorker,
    TextSplitterWorker,
    FileSummaryWorker,
    KGExtractorWorker,
    ImageUnderstandWorker,
    TextAnalyzerWorker,
)

# Phase 4: Writer 组件
from src.db.kafka.writers import (
    BaseWriter,
    EmbeddingMilvusWriter,
    Neo4jWriter,
    MySQLWriter,
    MongoWriter,
)

__all__ = [
    # 连接管理
    "get_kafka_manager",
    # Topic 管理
    "KafkaTopics",
    # 类型定义
    "MessageKey",
    "ConsumerGroup",
    # Producer/Consumer
    "KafkaProducer",
    "BaseKafkaConsumer",
    "BatchKafkaConsumer",
    # 幂等性保证
    "DeduplicationManager",
    "get_deduplication_manager",
    "close_deduplication_manager",
    "close_redis_manager",
    # 重试管理
    "RetryManager",
    "RetryStrategy",
    "get_retry_manager",
    "close_retry_manager",
    # DLQ 管理
    "DLQManager",
    "DLQRecord",
    "get_dlq_manager",
    "close_dlq_manager",
    # Phase 4: Worker 组件
    "BaseWorker",
    "FileParserWorker",
    "TextSplitterWorker",
    "FileSummaryWorker",
    "KGExtractorWorker",
    "ImageUnderstandWorker",
    "TextAnalyzerWorker",
    # Phase 4: Writer 组件
    "BaseWriter",
    "EmbeddingMilvusWriter",
    "Neo4jWriter",
    "MySQLWriter",
    "MongoWriter",
]
