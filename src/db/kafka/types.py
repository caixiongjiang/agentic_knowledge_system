#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka 相关类型定义

定义 Kafka 消息的通用类型和枚举。
"""

from enum import Enum
from typing import NewType


# ==================== Message Key ====================

class MessageKey:
    """
    Kafka Message Key 生成器
    
    统一的 Key 格式：{user_id}:{file_id}
    保证同一文件的所有消息路由到同一分区，保证数据一致性。
    """
    
    @staticmethod
    def generate(user_id: str, file_id: str) -> str:
        """
        生成 Kafka Message Key
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
            
        Returns:
            统一格式的 Key：{user_id}:{file_id}
            
        Example:
            key = MessageKey.generate("user_123", "file_456")
            # 返回: "user_123:file_456"
        """
        return f"{user_id}:{file_id}"
    
    @staticmethod
    def parse(key: str) -> tuple[str, str]:
        """
        解析 Message Key
        
        Args:
            key: Message Key
            
        Returns:
            (user_id, file_id) 元组
            
        Raises:
            ValueError: 如果 Key 格式不正确
            
        Example:
            user_id, file_id = MessageKey.parse("user_123:file_456")
        """
        parts = key.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid message key format: {key}. Expected format: user_id:file_id")
        return parts[0], parts[1]


# ==================== Consumer Group ====================

class ConsumerGroup:
    """
    Consumer Group ID 定义
    
    分组策略：
    - Pipeline Worker: 每个 Worker 独立 Group，保证独立消费和扩缩容
    - DB Writer: 4 个 Writer 共享一个 Group（各自消费不同 Topic，互不干扰）
    """
    
    # Pipeline Worker Groups（各自独立）
    FILE_PARSER = "group-file-parser"
    TEXT_SPLITTER = "group-text-splitter"
    SECTION_SUMMARY = "group-section-summary"
    FILE_SUMMARY = "group-file-summary"
    KG_EXTRACTOR = "group-kg-extractor"
    TEXT_ANALYZER = "group-text-analyzer"
    
    # DB Writer Group（4 个 Writer 共享，各自消费不同 Topic）
    DB_WRITER = "group-db-writer"
    
    @staticmethod
    def with_prefix(group_name: str) -> str:
        """
        添加配置的 Group ID 前缀
        
        Args:
            group_name: Consumer Group 名称
            
        Returns:
            带前缀的 Group ID
        """
        from src.utils.config_manager import get_config_manager
        config = get_config_manager()
        prefix = config.get("kafka.consumer.group_id_prefix", "aks")
        return f"{prefix}-{group_name}"


# ==================== Message Status ====================

class MessageStatus(str, Enum):
    """消息处理状态"""
    PENDING = "pending"           # 待处理
    PROCESSING = "processing"     # 处理中
    SUCCESS = "success"           # 处理成功
    FAILED = "failed"             # 处理失败
    RETRY = "retry"               # 等待重试


# ==================== Processing Stage ====================

class ProcessingStage(str, Enum):
    """处理阶段枚举"""
    # 前台阶段
    INDEX_START = "index_start"
    PARSE_END = "parse_end"
    SPLIT_END = "split_end"

    # 后台串行1：section 摘要 → file 摘要
    SECTION_SUMMARY_END = "section_summary_end"
    FILE_SUMMARY_END = "file_summary_end"
    
    # 后台并行（file_summary.end 触发，与 KGExtractor 并行）
    GRAPH_END = "graph_end"
    ANALYZE_END = "analyze_end"


# ==================== Collection Type ====================

class CollectionType(str, Enum):
    """Milvus Collection 类型"""
    CHUNK = "chunk"               # 文本 Chunk 向量
    SUMMARY = "summary"           # 摘要向量
    ATOMIC_QA = "atomic_qa"       # Atomic QA 向量
    IMAGE = "image"               # 图片描述向量


# ==================== Language ====================

class Language(str, Enum):
    """语言类型"""
    CHINESE = "zh"
    ENGLISH = "en"
    MIXED = "mixed"
    UNKNOWN = "unknown"


# ==================== Type Aliases ====================

# 事件ID（用于幂等性检查）
EventID = NewType("EventID", str)

# 追踪ID（用于分布式追踪）
TraceID = NewType("TraceID", str)
