#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka 消息模型

提供所有 Kafka 消息的类型定义和序列化/反序列化支持。
"""

from src.types.messages.base import BaseMessage, MessageMetadata
from src.types.messages.index import (
    IndexStartMessage,
    ParseEndMessage,
    SplitEndMessage,
)
from src.types.messages.extract import (
    SummaryEndMessage,
    GraphEndMessage,
    ImageEndMessage,
)
from src.types.messages.db_write import (
    EmbeddingWriteMessage,
    GraphWriteMessage,
    MetaWriteMessage,
    MongoWriteMessage,
)

__all__ = [
    # 基础模型
    "BaseMessage",
    "MessageMetadata",
    # 索引相关消息
    "IndexStartMessage",
    "ParseEndMessage",
    "SplitEndMessage",
    # 提取相关消息
    "SummaryEndMessage",
    "GraphEndMessage",
    "ImageEndMessage",
    # 数据库写入消息
    "EmbeddingWriteMessage",
    "GraphWriteMessage",
    "MetaWriteMessage",
    "MongoWriteMessage",
]
