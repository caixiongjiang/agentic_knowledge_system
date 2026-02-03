#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka Writers 模块

提供各类数据库批量写入 Writer 组件,基于 BatchKafkaConsumer 实现。
"""

from src.db.kafka.writers.base_writer import BaseWriter
from src.db.kafka.writers.embedding_milvus_writer import EmbeddingMilvusWriter
from src.db.kafka.writers.neo4j_writer import Neo4jWriter
from src.db.kafka.writers.mysql_writer import MySQLWriter
from src.db.kafka.writers.mongo_writer import MongoWriter

__all__ = [
    "BaseWriter",
    "EmbeddingMilvusWriter",
    "Neo4jWriter",
    "MySQLWriter",
    "MongoWriter",
]
