#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
ImageUnderstand Worker

监听: knowledge_base:summary:end
功能: 多模态图片理解,生成图片描述文本
输出: knowledge_base:image:end, db_write:embedding:start
"""

from typing import Optional, List, Dict
from loguru import logger

from src.db.kafka.workers.base_worker import BaseWorker
from src.db.kafka.producer import KafkaProducer
from src.db.kafka.topics import KafkaTopics
from src.types.messages.extract import SummaryEndMessage, ImageEndMessage
from src.types.messages.db_write import EmbeddingWriteMessage, MilvusCollection


class ImageUnderstandWorker(BaseWorker):
    """
    ImageUnderstand Worker
    
    职责:
    - 监听 summary:end 事件
    - 从 S3 加载图片 Chunk
    - 调用 VLM (Vision Language Model) 理解图片
    - 生成图片描述文本
    - 发送原始文本到向量化队列
    - 为 TextAnalyzer 提供完整的 Chunk 信息
    
    输入消息: SummaryEndMessage
    输出消息: ImageEndMessage, EmbeddingWriteMessage
    
    配置要求:
    - 资源: 4 CPU, 8GB RAM, 1 GPU
    - 扩容触发: Kafka lag > 50
    """
    
    def __init__(
        self,
        *args,
        image_understand_service=None,  # 图片理解服务
        **kwargs
    ):
        """
        初始化 ImageUnderstand Worker
        
        Args:
            image_understand_service: 图片理解服务实例（封装所有业务逻辑）
        """
        super().__init__(*args, **kwargs)
        self._image_service = image_understand_service
    
    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.SUMMARY_END
    
    async def process_message_impl(self, message: SummaryEndMessage) -> bool:
        """
        处理摘要完成消息,理解图片
        
        Args:
            message: SummaryEndMessage
            
        Returns:
            bool: 是否处理成功
        """
        logger.info(
            f"开始图片理解: user_id={message.user_id}, file_id={message.file_id}"
        )
        
        try:
            # TODO: 调用 ImageUnderstandService 处理业务逻辑
            # image_result = await self._image_service.understand_images(
            #     file_id=message.file_id,
            #     file_summary=message.file_summary,
            #     user_id=message.user_id
            # )
            
            # 临时模拟数据（等待 Service 实现）
            understanding_results = [
                {
                    "chunk_id": f"{message.file_id}_img_{i}",
                    "description": f"图片描述: 这是一张示例图片 {i}",
                    "image_type": "diagram",
                    "quality": 0.88
                }
                for i in range(2)
            ]
            
            # 如果没有图片，直接发送空结果
            if not understanding_results:
                await self._send_image_end_message(message, [])
                return True
            
            # 发送 EmbeddingWriteMessage
            await self._send_embedding_messages(message, understanding_results)
            
            # 发送 ImageEndMessage
            await self._send_image_end_message(message, understanding_results)
            
            logger.info(
                f"图片理解完成: file_id={message.file_id}, "
                f"images={len(understanding_results)}"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"图片理解失败: file_id={message.file_id}, error={e}",
                exc_info=True
            )
            return False
    
    async def _send_embedding_messages(
        self,
        message: SummaryEndMessage,
        understanding_results: List[Dict]
    ) -> None:
        """
        发送向量化消息 (图片描述文本)
        
        Args:
            message: 原始消息
            understanding_results: 理解结果列表
        """
        if not self._producer:
            logger.warning("Producer 未配置,无法发送消息")
            return
        
        for result in understanding_results:
            emb_msg = EmbeddingWriteMessage(
                user_id=message.user_id,
                file_id=message.file_id,
                collection_type=MilvusCollection.CHUNK,
                items=[{
                    "id": result["chunk_id"],
                    "text": result["description"],
                    "metadata": {
                        "type": "image",
                        "image_type": result["image_type"]
                    }
                }],
                source_stage="image_understand",
                language=message.document_type or "zh"
            )
            
            await self._producer.send_message(
                topic=KafkaTopics.DB_WRITE_EMBEDDING,
                message=emb_msg
            )
        
        logger.debug(f"发送 {len(understanding_results)} 条图片描述 EmbeddingWriteMessage")
    
    async def _send_image_end_message(
        self,
        message: SummaryEndMessage,
        understanding_results: List[Dict]
    ) -> None:
        """
        发送图片理解完成消息
        
        Args:
            message: 原始消息
            understanding_results: 理解结果列表
        """
        if not self._producer:
            logger.warning("Producer 未配置,无法发送消息")
            return
        
        image_end_msg = ImageEndMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            image_understanding_results=understanding_results,
            processed_image_count=len(understanding_results),
            vision_model="gpt-4-vision",
            tokens_used={"input": 1000, "output": 300},
            image_types={"diagram": len(understanding_results)},
            avg_understanding_quality=sum(r["quality"] for r in understanding_results) / len(understanding_results) if understanding_results else 0.0
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.IMAGE_END,
            message=image_end_msg
        )
        
        logger.debug(f"发送 ImageEndMessage: file_id={message.file_id}")
