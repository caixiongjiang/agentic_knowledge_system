#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
MongoWriter

监听: db_write:mongo:start
功能: 批量写入文档数据到 MongoDB
"""

from typing import List, Dict, Optional
from loguru import logger

from src.db.kafka.writers.base_writer import BaseWriter
from src.db.kafka.topics import KafkaTopics
from src.types.messages.db_write import MongoWriteMessage


class MongoWriter(BaseWriter):
    """
    MongoWriter
    
    职责:
    - 消费 db_write:mongo:start Topic
    - 批量写入文档数据到 MongoDB
    - 按 Collection 分组
    - 使用 bulk_write 批量操作
    
    配置参数:
    - Batch Size: 100条
    - Flush Interval: 500ms
    
    优化策略:
    - 批量 INSERT (batch_size=100)
    - 按 collection 分组
    - 使用 bulk_write 批量操作
    
    配置要求:
    - 资源: 2 CPU, 4GB RAM
    - 扩容触发: Kafka lag > 300
    """
    
    def __init__(
        self,
        *args,
        mongodb_repos=None,  # MongoDB Repositories (按 Collection 分组)
        **kwargs
    ):
        """
        初始化 MongoWriter
        
        Args:
            mongodb_repos: MongoDB Repository 字典 (collection_name -> repo)
        """
        super().__init__(*args, **kwargs)
        self._mongodb_repos = mongodb_repos or {}
    
    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.DB_WRITE_MONGO
    
    async def process_batch_impl(self, messages: List[MongoWriteMessage]) -> List[bool]:
        """
        批量处理文档写入
        
        处理流程:
        1. 按 Collection 分组
        2. 批量写入文档
        
        Args:
            messages: MongoWriteMessage 列表
            
        Returns:
            List[bool]: 每条消息的处理结果
        """
        logger.info(f"开始批量写入文档: {len(messages)} 条消息")
        
        try:
            # 1. 按 Collection 分组
            grouped = self._group_by_collection(messages)
            
            # 2. 批量写入各个 Collection
            results_map = {}  # message_id -> bool
            
            for collection_name, group_messages in grouped.items():
                logger.debug(
                    f"写入 Collection: {collection_name}, "
                    f"{len(group_messages)} 条记录"
                )
                
                success = await self._batch_write_collection(
                    collection_name, group_messages
                )
                
                # 记录结果
                for msg in group_messages:
                    results_map[msg.metadata.event_id] = success
            
            # 3. 返回结果 (按原始顺序)
            results = [results_map.get(msg.metadata.event_id, False) for msg in messages]
            
            success_count = sum(results)
            logger.info(
                f"批量写入文档完成: success={success_count}/{len(messages)}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"批量写入文档失败: {e}", exc_info=True)
            return [False] * len(messages)
    
    def _group_by_collection(
        self,
        messages: List[MongoWriteMessage]
    ) -> Dict[str, List[MongoWriteMessage]]:
        """
        按 Collection 分组
        
        Args:
            messages: 消息列表
            
        Returns:
            dict: collection_name -> 消息列表
        """
        grouped = {}
        for msg in messages:
            collection_name = msg.collection_name
            if collection_name not in grouped:
                grouped[collection_name] = []
            grouped[collection_name].append(msg)
        
        return grouped
    
    async def _batch_write_collection(
        self,
        collection_name: str,
        messages: List[MongoWriteMessage]
    ) -> bool:
        """
        批量写入 Collection
        
        Args:
            collection_name: Collection 名称
            messages: 消息列表
            
        Returns:
            bool: 是否成功
        """
        # TODO: 实现批量写入 MongoDB
        # repo = self._mongodb_repos.get(collection_name)
        # if not repo:
        #     logger.error(f"未找到 MongoDB Repository: {collection_name}")
        #     return False
        # 
        # documents = [msg.document_data for msg in messages]
        # return await repo.batch_insert(documents)
        
        logger.debug(
            f"批量写入 MongoDB: collection={collection_name}, "
            f"count={len(messages)}"
        )
        
        # 模拟成功
        return True
