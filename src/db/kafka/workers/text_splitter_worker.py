#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
TextSplitter Worker

监听: knowledge_base:parse:end
功能: 文本分割、语言检测、生成 Chunk (合并了 ChunkProcessor 的功能)
输出: knowledge_base:split:end, db_write:embedding:start, db_write:meta:start, db_write:mongo:start
"""

from typing import Optional, List, Dict, Any
from loguru import logger

from src.db.kafka.workers.base_worker import BaseWorker
from src.db.kafka.producer import KafkaProducer
from src.db.kafka.topics import KafkaTopics
from src.types.messages.index import ParseEndMessage, SplitEndMessage
from src.types.messages.db_write import EmbeddingWriteMessage, MetaWriteMessage, MongoWriteMessage


class TextSplitterWorker(BaseWorker):
    """
    TextSplitter Worker (包含 Chunk 处理)
    
    职责:
    - 从 MySQL 获取解析后的 PDF 结构化数据
    - 使用递归分割算法切分文本
    - 构建 Section-Chunk 层级关系
    - 检测每个 Chunk 的语言
    - 生成 Chunk ID 和元数据
    - 直接发送原始文本到向量化队列
    - 批量写入元数据和文档数据
    - 发送前台完成事件(进度100%)
    
    输入消息: ParseEndMessage
    输出消息: SplitEndMessage, EmbeddingWriteMessage, MetaWriteMessage, MongoWriteMessage
    
    配置要求:
    - 资源: 2 CPU, 4GB RAM
    - 扩容触发: Kafka lag > 200
    """
    
    def __init__(
        self,
        *args,
        text_splitter_service=None,  # 文本分割服务
        **kwargs
    ):
        """
        初始化 TextSplitter Worker
        
        Args:
            text_splitter_service: 文本分割服务实例（封装所有业务逻辑）
        """
        super().__init__(*args, **kwargs)
        self._splitter_service = text_splitter_service
    
    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.PARSE_END
    
    async def process_message_impl(self, message: ParseEndMessage) -> bool:
        """
        处理解析完成消息,分割文本
        
        Args:
            message: ParseEndMessage
            
        Returns:
            bool: 是否处理成功
        """
        logger.info(
            f"开始分割文本: user_id={message.user_id}, file_id={message.file_id}"
        )
        
        try:
            # TODO: 调用 TextSplitterService 处理业务逻辑
            # split_result = await self._splitter_service.split_and_process(
            #     file_id=message.file_id,
            #     text_content=message.text_content,
            #     user_id=message.user_id
            # )
            
            # 临时模拟数据（等待 Service 实现）
            processed_chunks = [
                {
                    "chunk_id": f"{message.file_id}_chunk_{i}",
                    "user_id": message.user_id,
                    "file_id": message.file_id,
                    "text": f"Chunk {i} content",
                    "language": "zh",
                    "position": i,
                    "metadata": {"char_count": 100, "word_count": 20}
                }
                for i in range(5)
            ]
            
            # 发送 EmbeddingWriteMessage
            await self._send_embedding_messages(message, processed_chunks)
            
            # 发送 MongoWriteMessage
            await self._send_mongo_messages(message, processed_chunks)
            
            # 发送 MetaWriteMessage
            await self._send_meta_message(message, processed_chunks)
            
            # 发送 SplitEndMessage (前台完成,进度100%)
            await self._send_split_end_message(message, processed_chunks)
            
            logger.info(
                f"文本分割完成: file_id={message.file_id}, "
                f"chunks={len(processed_chunks)}"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"文本分割失败: file_id={message.file_id}, error={e}",
                exc_info=True
            )
            return False
    
    async def _send_embedding_messages(
        self,
        message: ParseEndMessage,
        chunks: List[Dict]
    ) -> None:
        """
        发送向量化消息 (原始文本)
        
        Args:
            message: 原始消息
            chunks: Chunk 列表
        """
        if not self._producer:
            logger.warning("Producer 未配置,无法发送消息")
            return
        
        for chunk in chunks:
            emb_msg = EmbeddingWriteMessage(
                user_id=message.user_id,
                file_id=message.file_id,
                collection_type="chunk",
                data_items=[{
                    "id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "metadata": chunk["metadata"]
                }],
                source_stage="split",
                document_language=chunk["language"]
            )
            
            await self._producer.send_message(
                topic=KafkaTopics.DB_WRITE_EMBEDDING,
                message=emb_msg
            )
        
        logger.debug(f"发送 {len(chunks)} 条 EmbeddingWriteMessage")
    
    async def _send_mongo_messages(
        self,
        message: ParseEndMessage,
        chunks: List[Dict]
    ) -> None:
        """
        发送 MongoDB 写入消息
        
        Args:
            message: 原始消息
            chunks: Chunk 列表
        """
        if not self._producer:
            return
        
        mongo_msg = MongoWriteMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            document_data={
                "chunks": chunks
            },
            data_type="chunk_data",
            collection_name="chunk_data",
            operation="insert"
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.DB_WRITE_MONGO,
            message=mongo_msg
        )
        
        logger.debug(f"发送 MongoWriteMessage: {len(chunks)} chunks")
    
    async def _send_meta_message(
        self,
        message: ParseEndMessage,
        chunks: List[Dict]
    ) -> None:
        """
        发送元数据更新消息
        
        Args:
            message: 原始消息
            chunks: Chunk 列表
        """
        if not self._producer:
            return
        
        meta_msg = MetaWriteMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            file_metadata={},
            processing_metadata={
                "total_chunks": len(chunks),
                "total_chars": sum(len(c["text"]) for c in chunks)
            },
            update_fields=["processing_metadata"],
            operation="update",
            status="processing",
            progress=0.5
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.DB_WRITE_META,
            message=meta_msg
        )
        
        logger.debug("发送 MetaWriteMessage")
    
    async def _send_split_end_message(
        self,
        message: ParseEndMessage,
        chunks: List[Dict]
    ) -> None:
        """
        发送分割完成消息 (前台完成,进度100%)
        
        Args:
            message: 原始消息
            chunks: Chunk 列表
        """
        if not self._producer:
            return
        
        split_end_msg = SplitEndMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            chunks=[
                {"chunk_id": c["chunk_id"], "text": c["text"], "metadata": c["metadata"]}
                for c in chunks
            ],
            split_strategy="recursive",
            chunk_stats={
                "total_chunks": len(chunks),
                "avg_chunk_size": sum(len(c["text"]) for c in chunks) // len(chunks) if chunks else 0
            },
            document_language=chunks[0]["language"] if chunks else "zh",
            frontend_completed=True,
            short_summary="文档已成功分割为 {} 个文本块".format(len(chunks))
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.SPLIT_END,
            message=split_end_msg
        )
        
        logger.info(f"发送 SplitEndMessage (前台完成): file_id={message.file_id}")
