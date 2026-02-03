#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka Topic 定义和配置

定义系统中所有 Kafka Topics 及其配置。
"""

from typing import Dict, Any
from dataclasses import dataclass

from src.utils.config_manager import get_config_manager


@dataclass
class TopicConfig:
    """Topic 配置"""
    name: str
    num_partitions: int
    replication_factor: int
    retention_ms: int
    min_insync_replicas: int
    cleanup_policy: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "num_partitions": self.num_partitions,
            "replication_factor": self.replication_factor,
            "config": {
                "retention.ms": str(self.retention_ms),
                "min.insync.replicas": str(self.min_insync_replicas),
                "cleanup.policy": self.cleanup_policy,
            }
        }


class KafkaTopics:
    """
    Kafka Topics 管理类
    
    定义系统中所有 Topics 的名称和配置。
    命名规范：{业务模块}.{处理阶段}.{事件类型}
    注意：Kafka 不允许 Topic 名称中包含冒号，因此使用点号分隔
    """
    
    # ==================== 第一层：任务流转 Topics ====================
    
    # 前台阶段 Topics（用户等待，高优先级）
    INDEX_START = "knowledge_base.index.start"      # 索引构建开始（文件已在S3）
    PARSE_END = "knowledge_base.parse.end"          # 文件解析完成
    SPLIT_END = "knowledge_base.split.end"          # 文本分割完成（前台进度100%）
    
    # 后台串行阶段 Topics
    SUMMARY_END = "knowledge_base.summary.end"      # 文件摘要完成
    
    # 后台并行阶段 Topics
    GRAPH_END = "knowledge_base.graph.end"          # 知识图谱抽取完成
    IMAGE_END = "knowledge_base.image.end"          # 图片理解完成
    
    # ==================== 第二层：数据库写入 Topics ====================
    
    DB_WRITE_EMBEDDING = "db_write.embedding.start"  # 向量数据写入（原始文本）
    DB_WRITE_GRAPH = "db_write.graph.start"          # 图谱数据写入
    DB_WRITE_META = "db_write.meta.start"            # 元数据写入
    DB_WRITE_MONGO = "db_write.mongo.start"          # 文档数据写入
    
    # ==================== DLQ 和重试 Topics ====================
    
    @staticmethod
    def get_dlq_topic(topic: str) -> str:
        """获取死信队列 Topic 名称"""
        config = get_config_manager()
        dlq_suffix = config.get("kafka.retry.dlq_suffix", ".dlq")
        return f"{topic}{dlq_suffix}"
    
    @staticmethod
    def get_retry_topic(topic: str) -> str:
        """获取重试 Topic 名称"""
        config = get_config_manager()
        retry_suffix = config.get("kafka.retry.retry_suffix", ".retry")
        return f"{topic}{retry_suffix}"
    
    @classmethod
    def get_all_topics(cls) -> list[str]:
        """
        获取所有 Topic 名称列表
        
        Returns:
            所有业务 Topic 名称（不包括 DLQ 和重试 Topic）
        """
        return [
            # 第一层：任务流转
            cls.INDEX_START,
            cls.PARSE_END,
            cls.SPLIT_END,
            cls.SUMMARY_END,
            cls.GRAPH_END,
            cls.IMAGE_END,
            # 第二层：数据库写入
            cls.DB_WRITE_EMBEDDING,
            cls.DB_WRITE_GRAPH,
            cls.DB_WRITE_META,
            cls.DB_WRITE_MONGO,
        ]
    
    @classmethod
    def get_topic_configs(cls) -> Dict[str, TopicConfig]:
        """
        获取所有 Topic 的配置
        
        Returns:
            Topic 名称到配置的映射
        """
        config = get_config_manager()
        
        # 获取通用配置
        topics_config = config.get("kafka.topics", {})
        replication_factor = topics_config.get("replication_factor", 3)
        min_insync_replicas = topics_config.get("min_insync_replicas", 2)
        retention_ms = topics_config.get("retention_ms", 604800000)  # 7天
        cleanup_policy = topics_config.get("cleanup_policy", "delete")
        
        # 获取各 Topic 的分区数配置
        index_start_partitions = topics_config.get("index_start_partitions", 32)
        parse_end_partitions = topics_config.get("parse_end_partitions", 32)
        split_end_partitions = topics_config.get("split_end_partitions", 32)
        summary_end_partitions = topics_config.get("summary_end_partitions", 16)
        graph_end_partitions = topics_config.get("graph_end_partitions", 16)
        image_end_partitions = topics_config.get("image_end_partitions", 16)
        embedding_start_partitions = topics_config.get("embedding_start_partitions", 32)
        graph_start_partitions = topics_config.get("graph_start_partitions", 16)
        meta_start_partitions = topics_config.get("meta_start_partitions", 32)
        mongo_start_partitions = topics_config.get("mongo_start_partitions", 32)
        
        # 构建 Topic 配置字典
        topic_configs = {
            # 前台阶段 Topics
            cls.INDEX_START: TopicConfig(
                name=cls.INDEX_START,
                num_partitions=index_start_partitions,
                replication_factor=replication_factor,
                retention_ms=retention_ms,
                min_insync_replicas=min_insync_replicas,
                cleanup_policy=cleanup_policy,
            ),
            cls.PARSE_END: TopicConfig(
                name=cls.PARSE_END,
                num_partitions=parse_end_partitions,
                replication_factor=replication_factor,
                retention_ms=retention_ms,
                min_insync_replicas=min_insync_replicas,
                cleanup_policy=cleanup_policy,
            ),
            cls.SPLIT_END: TopicConfig(
                name=cls.SPLIT_END,
                num_partitions=split_end_partitions,
                replication_factor=replication_factor,
                retention_ms=retention_ms,
                min_insync_replicas=min_insync_replicas,
                cleanup_policy=cleanup_policy,
            ),
            # 后台阶段 Topics
            cls.SUMMARY_END: TopicConfig(
                name=cls.SUMMARY_END,
                num_partitions=summary_end_partitions,
                replication_factor=replication_factor,
                retention_ms=retention_ms,
                min_insync_replicas=min_insync_replicas,
                cleanup_policy=cleanup_policy,
            ),
            cls.GRAPH_END: TopicConfig(
                name=cls.GRAPH_END,
                num_partitions=graph_end_partitions,
                replication_factor=replication_factor,
                retention_ms=retention_ms,
                min_insync_replicas=min_insync_replicas,
                cleanup_policy=cleanup_policy,
            ),
            cls.IMAGE_END: TopicConfig(
                name=cls.IMAGE_END,
                num_partitions=image_end_partitions,
                replication_factor=replication_factor,
                retention_ms=retention_ms,
                min_insync_replicas=min_insync_replicas,
                cleanup_policy=cleanup_policy,
            ),
            # 数据库写入 Topics
            cls.DB_WRITE_EMBEDDING: TopicConfig(
                name=cls.DB_WRITE_EMBEDDING,
                num_partitions=embedding_start_partitions,
                replication_factor=replication_factor,
                retention_ms=retention_ms,
                min_insync_replicas=min_insync_replicas,
                cleanup_policy=cleanup_policy,
            ),
            cls.DB_WRITE_GRAPH: TopicConfig(
                name=cls.DB_WRITE_GRAPH,
                num_partitions=graph_start_partitions,
                replication_factor=replication_factor,
                retention_ms=retention_ms,
                min_insync_replicas=min_insync_replicas,
                cleanup_policy=cleanup_policy,
            ),
            cls.DB_WRITE_META: TopicConfig(
                name=cls.DB_WRITE_META,
                num_partitions=meta_start_partitions,
                replication_factor=replication_factor,
                retention_ms=retention_ms,
                min_insync_replicas=min_insync_replicas,
                cleanup_policy=cleanup_policy,
            ),
            cls.DB_WRITE_MONGO: TopicConfig(
                name=cls.DB_WRITE_MONGO,
                num_partitions=mongo_start_partitions,
                replication_factor=replication_factor,
                retention_ms=retention_ms,
                min_insync_replicas=min_insync_replicas,
                cleanup_policy=cleanup_policy,
            ),
        }
        
        return topic_configs
    
    @classmethod
    def get_topic_configs_dict(cls) -> Dict[str, Dict[str, Any]]:
        """
        获取所有 Topic 配置的字典格式（用于创建 Topics）
        
        Returns:
            Topic 名称到配置字典的映射
        """
        topic_configs = cls.get_topic_configs()
        return {
            name: config.to_dict()
            for name, config in topic_configs.items()
        }
