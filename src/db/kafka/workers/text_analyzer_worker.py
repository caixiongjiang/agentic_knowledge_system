#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
TextAnalyzer Worker

监听: knowledge_base:image:end
功能: 生成 chunk 级别的 summary 和 atomic_qa
输出: db_write:embedding:start
"""

from typing import Optional, List, Dict
from loguru import logger

from src.db.kafka.workers.base_worker import BaseWorker
from src.db.kafka.producer import KafkaProducer
from src.db.kafka.topics import KafkaTopics
from src.types.messages.extract import ImageEndMessage
from src.types.messages.db_write import EmbeddingWriteMessage, MilvusCollection


class TextAnalyzerWorker(BaseWorker):
    """
    TextAnalyzer Worker
    
    职责:
    - 监听 image:end 事件(依赖图片理解结果,因为图片是 chunk 的一部分)
    - 加载文本 chunk 和图片描述
    - 调用 LLM 生成 chunk 级别的 summary 和 atomic_qa
    - 发送原始文本到向量化队列
    
    输入消息: ImageEndMessage
    输出消息: EmbeddingWriteMessage
    
    配置要求:
    - 资源: 4 CPU, 8GB RAM
    - 扩容触发: Kafka lag > 50
    """
    
    def __init__(
        self,
        *args,
        text_analyzer_service=None,  # 文本分析服务
        **kwargs
    ):
        """
        初始化 TextAnalyzer Worker
        
        Args:
            text_analyzer_service: 文本分析服务实例（封装所有业务逻辑）
        """
        super().__init__(*args, **kwargs)
        self._analyzer_service = text_analyzer_service
    
    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.IMAGE_END
    
    async def process_message_impl(self, message: ImageEndMessage) -> bool:
        """
        处理图片理解完成消息,分析文本
        
        Args:
            message: ImageEndMessage
            
        Returns:
            bool: 是否处理成功
        """
        logger.info(
            f"开始文本分析: user_id={message.user_id}, file_id={message.file_id}"
        )
        
        try:
            # TODO: 调用 TextAnalyzerService 处理业务逻辑
            # analysis_result = await self._analyzer_service.analyze_text(
            #     file_id=message.file_id,
            #     image_understanding_results=message.image_understanding_results,
            #     user_id=message.user_id
            # )
            
            # 临时模拟数据（等待 Service 实现）
            analysis_results = [
                {
                    "chunk_id": f"{message.file_id}_chunk_{i}",
                    "summary": f"Chunk 摘要: Chunk {i} 的内容摘要",
                    "atomic_qa": [
                        {"question": f"Q{i}-1", "answer": f"A{i}-1"},
                        {"question": f"Q{i}-2", "answer": f"A{i}-2"}
                    ]
                }
                for i in range(3)
            ]
            
            # 发送 EmbeddingWriteMessage
            await self._send_embedding_messages(message, analysis_results)
            
            logger.info(
                f"文本分析完成: file_id={message.file_id}, "
                f"analyzed_chunks={len(analysis_results)}"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"文本分析失败: file_id={message.file_id}, error={e}",
                exc_info=True
            )
            return False
    
    async def _send_embedding_messages(
        self,
        message: ImageEndMessage,
        analysis_results: List[Dict]
    ) -> None:
        """
        发送向量化消息 (summary 和 atomic_qa 文本)
        
        Args:
            message: 原始消息
            analysis_results: 分析结果列表
        """
        if not self._producer:
            logger.warning("Producer 未配置,无法发送消息")
            return
        
        for result in analysis_results:
            # 发送 summary
            summary_msg = EmbeddingWriteMessage(
                user_id=message.user_id,
                file_id=message.file_id,
                collection_type=MilvusCollection.SUMMARY,
                items=[{
                    "id": f"{result['chunk_id']}_summary",
                    "text": result["summary"],
                    "metadata": {"chunk_id": result["chunk_id"]}
                }],
                source_stage="text_analyzer",
                language="zh"
            )
            
            await self._producer.send_message(
                topic=KafkaTopics.DB_WRITE_EMBEDDING,
                message=summary_msg
            )
            
            # 发送 atomic_qa
            for qa in result["atomic_qa"]:
                qa_text = f"Q: {qa['question']}\nA: {qa['answer']}"
                qa_msg = EmbeddingWriteMessage(
                    user_id=message.user_id,
                    file_id=message.file_id,
                    collection_type=MilvusCollection.ATOMIC_QA,
                    items=[{
                        "id": f"{result['chunk_id']}_qa_{qa['question'][:20]}",
                        "text": qa_text,
                        "metadata": {
                            "chunk_id": result["chunk_id"],
                            "question": qa["question"],
                            "answer": qa["answer"]
                        }
                    }],
                    source_stage="text_analyzer",
                    language="zh"
                )
                
                await self._producer.send_message(
                    topic=KafkaTopics.DB_WRITE_EMBEDDING,
                    message=qa_msg
                )
        
        logger.debug(f"发送 summary 和 atomic_qa EmbeddingWriteMessage: {len(analysis_results)} chunks")
