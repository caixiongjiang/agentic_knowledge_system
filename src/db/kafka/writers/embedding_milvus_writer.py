#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
EmbeddingMilvusWriter

监听: db_write:embedding:start
功能: 核心组件 - 统一处理 Embedding + Milvus 写入
    1. 接收原始文本 (不是向量)
    2. 批量调用 Embedding API
    3. 批量写入 Milvus
"""

from typing import List, Dict, Optional
from loguru import logger

from src.db.kafka.writers.base_writer import BaseWriter
from src.db.kafka.topics import KafkaTopics
from src.types.messages.db_write import EmbeddingWriteMessage


class EmbeddingMilvusWriter(BaseWriter):
    """
    EmbeddingMilvusWriter
    
    核心设计: 这是整个架构的关键组件
    - 消费 db_write:embedding:start Topic
    - 接收**原始文本** (不是向量,节省 Kafka 带宽)
    - 统一处理 Embedding + Milvus 写入
    - 批量优化: 批量 Embedding + 批量插入
    
    数据来源:
    - TextSplitter: 原始文本 chunk
    - ImageUnderstand: 图片描述
    - TextAnalyzer: summary/atomic_qa
    
    配置参数:
    - Batch Size: 100条
    - Flush Interval: 500ms
    - Embedding Batch Size: 64条/请求
    - Milvus Insert Batch Size: 100条/次
    
    职责:
    - 按 Collection 分组消息
    - 批量调用 Embedding API
    - 批量写入 Milvus
    - 异步处理,不阻塞前台
    
    配置要求:
    - 资源: 4 CPU, 8GB RAM
    - 扩容触发: Kafka lag > 500
    """
    
    def __init__(
        self,
        *args,
        embedding_client=None,  # Embedding 客户端
        milvus_repos=None,  # Milvus Repositories (按 Collection 分组)
        embedding_batch_size: int = 64,  # Embedding API 批处理大小
        **kwargs
    ):
        """
        初始化 EmbeddingMilvusWriter
        
        Args:
            embedding_client: Embedding 客户端实例
            milvus_repos: Milvus Repository 字典 (collection_type -> repo)
            embedding_batch_size: Embedding API 批处理大小
        """
        super().__init__(*args, **kwargs)
        self._embedding_client = embedding_client
        self._milvus_repos = milvus_repos or {}
        self._embedding_batch_size = embedding_batch_size
    
    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.DB_WRITE_EMBEDDING
    
    async def process_batch_impl(self, messages: List[EmbeddingWriteMessage]) -> List[bool]:
        """
        批量处理向量化和写入
        
        处理流程:
        1. 按 Collection 分组消息
        2. 提取所有文本
        3. 批量调用 Embedding API
        4. 批量写入 Milvus
        
        Args:
            messages: EmbeddingWriteMessage 列表
            
        Returns:
            List[bool]: 每条消息的处理结果
        """
        logger.info(f"开始批量向量化和写入: {len(messages)} 条消息")
        
        try:
            # 1. 按 Collection 分组
            grouped_messages = self._group_by_collection(messages)
            
            # 2. 为每个 Collection 批量处理
            results_map = {}  # message_id -> bool
            
            for collection_type, group_messages in grouped_messages.items():
                logger.debug(f"处理 Collection: {collection_type}, {len(group_messages)} 条消息")
                
                # 2.1 提取所有文本
                texts, message_mapping = self._extract_texts(group_messages)
                
                # 2.2 批量调用 Embedding API
                embeddings = await self._batch_embed(texts)
                
                # 2.3 构建 Milvus 插入数据
                insert_data = self._build_insert_data(
                    group_messages, embeddings, message_mapping
                )
                
                # 2.4 批量写入 Milvus
                success = await self._batch_insert_milvus(collection_type, insert_data)
                
                # 2.5 记录结果
                for msg in group_messages:
                    msg_id = msg.metadata.event_id
                    results_map[msg_id] = success
            
            # 3. 返回结果 (按原始顺序)
            results = [results_map.get(msg.metadata.event_id, False) for msg in messages]
            
            success_count = sum(results)
            logger.info(
                f"批量向量化完成: success={success_count}/{len(messages)}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"批量向量化失败: {e}", exc_info=True)
            return [False] * len(messages)
    
    def _group_by_collection(
        self,
        messages: List[EmbeddingWriteMessage]
    ) -> Dict[str, List[EmbeddingWriteMessage]]:
        """
        按 Collection 分组消息
        
        Args:
            messages: 消息列表
            
        Returns:
            dict: collection_type -> 消息列表
        """
        grouped = {}
        for msg in messages:
            collection_type = msg.collection_type
            if collection_type not in grouped:
                grouped[collection_type] = []
            grouped[collection_type].append(msg)
        
        return grouped
    
    def _extract_texts(
        self,
        messages: List[EmbeddingWriteMessage]
    ) -> tuple:
        """
        提取所有文本
        
        Args:
            messages: 消息列表
            
        Returns:
            tuple: (文本列表, 消息映射)
        """
        texts = []
        message_mapping = []  # (message_idx, data_item_idx)
        
        for msg_idx, msg in enumerate(messages):
            for item_idx, data_item in enumerate(msg.data_items):
                texts.append(data_item["text"])
                message_mapping.append((msg_idx, item_idx))
        
        return texts, message_mapping
    
    async def _batch_embed(self, texts: List[str]) -> List[List[float]]:
        """
        批量调用 Embedding API
        
        Args:
            texts: 文本列表
            
        Returns:
            List[List[float]]: 向量列表
        """
        # TODO: 实现批量 Embedding 调用
        # 将大批次拆分为小批次 (embedding_batch_size)
        # embeddings = []
        # for i in range(0, len(texts), self._embedding_batch_size):
        #     batch = texts[i:i+self._embedding_batch_size]
        #     batch_embeddings = await self._embedding_client.embed(batch)
        #     embeddings.extend(batch_embeddings)
        # return embeddings
        
        logger.debug(f"批量调用 Embedding API: {len(texts)} 文本")
        
        # 模拟 Embedding 结果
        return [[0.1] * 768 for _ in texts]
    
    def _build_insert_data(
        self,
        messages: List[EmbeddingWriteMessage],
        embeddings: List[List[float]],
        message_mapping: List[tuple]
    ) -> List[Dict]:
        """
        构建 Milvus 插入数据
        
        Args:
            messages: 消息列表
            embeddings: 向量列表
            message_mapping: 消息映射
            
        Returns:
            List[Dict]: 插入数据列表
        """
        insert_data = []
        
        for emb_idx, (msg_idx, item_idx) in enumerate(message_mapping):
            msg = messages[msg_idx]
            data_item = msg.data_items[item_idx]
            
            insert_record = {
                "id": data_item["id"],
                "user_id": msg.user_id,
                "file_id": msg.file_id,
                "vector": embeddings[emb_idx],
                "text": data_item["text"],
                "metadata": data_item.get("metadata", {})
            }
            
            insert_data.append(insert_record)
        
        return insert_data
    
    async def _batch_insert_milvus(
        self,
        collection_type: str,
        insert_data: List[Dict]
    ) -> bool:
        """
        批量写入 Milvus
        
        Args:
            collection_type: Collection 类型
            insert_data: 插入数据列表
            
        Returns:
            bool: 是否成功
        """
        # TODO: 实现批量写入 Milvus
        # repo = self._milvus_repos.get(collection_type)
        # if not repo:
        #     logger.error(f"未找到 Milvus Repository: {collection_type}")
        #     return False
        # 
        # return await repo.batch_insert(insert_data)
        
        logger.debug(
            f"批量写入 Milvus: collection={collection_type}, "
            f"count={len(insert_data)}"
        )
        
        # 模拟成功
        return True
