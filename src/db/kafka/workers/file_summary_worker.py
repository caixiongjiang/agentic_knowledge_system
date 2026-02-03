#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
FileSummary Worker

监听: knowledge_base:split:end
功能: 生成文件级别摘要,为后续 KG 抽取和图片理解提供上下文
输出: knowledge_base:summary:end
"""

from typing import Optional, List, Dict
from loguru import logger

from src.db.kafka.workers.base_worker import BaseWorker
from src.db.kafka.producer import KafkaProducer
from src.db.kafka.topics import KafkaTopics
from src.types.messages.index import SplitEndMessage
from src.types.messages.extract import SummaryEndMessage


class FileSummaryWorker(BaseWorker):
    """
    FileSummary Worker
    
    职责:
    - 监听 split:end 事件
    - 加载所有文本 Chunk
    - 调用 LLM 生成文件级别摘要
    - 提取关键词和主题标签
    - 评估摘要质量
    - 发送摘要完成事件
    
    输入消息: SplitEndMessage
    输出消息: SummaryEndMessage
    
    配置要求:
    - 资源: 4 CPU, 8GB RAM
    - 扩容触发: Kafka lag > 50
    """
    
    def __init__(
        self,
        *args,
        file_summary_service=None,  # 文件摘要服务
        **kwargs
    ):
        """
        初始化 FileSummary Worker
        
        Args:
            file_summary_service: 文件摘要服务实例（封装所有业务逻辑）
        """
        super().__init__(*args, **kwargs)
        self._summary_service = file_summary_service
    
    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.SPLIT_END
    
    async def process_message_impl(self, message: SplitEndMessage) -> bool:
        """
        处理分割完成消息,生成文件摘要
        
        Args:
            message: SplitEndMessage
            
        Returns:
            bool: 是否处理成功
        """
        logger.info(
            f"开始生成文件摘要: user_id={message.user_id}, file_id={message.file_id}"
        )
        
        try:
            # TODO: 调用 FileSummaryService 处理业务逻辑
            # summary_result = await self._summary_service.generate_summary(
            #     file_id=message.file_id,
            #     chunks=message.chunks,
            #     user_id=message.user_id
            # )
            
            # 临时模拟数据（等待 Service 实现）
            summary_result = {
                "summary": "这是文件的摘要内容",
                "keywords": ["关键词1", "关键词2", "关键词3"],
                "topics": ["主题1", "主题2"],
                "quality": 0.92,
                "llm_model": "gpt-4",
                "tokens_used": {"input": 1000, "output": 200},
                "document_type": "technical",
                "difficulty_level": "medium"
            }
            
            # 发送 SummaryEndMessage
            await self._send_summary_end_message(message, summary_result)
            
            logger.info(
                f"文件摘要生成完成: file_id={message.file_id}, "
                f"quality={summary_result['quality']}"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"文件摘要生成失败: file_id={message.file_id}, error={e}",
                exc_info=True
            )
            return False
    
    async def _send_summary_end_message(
        self,
        message: SplitEndMessage,
        summary_result: Dict
    ) -> None:
        """
        发送摘要完成消息
        
        Args:
            message: 原始消息
            summary_result: 摘要结果
            keywords: 关键词列表
            topics: 主题列表
            quality_score: 质量分数
        """
        if not self._producer:
            logger.warning("Producer 未配置,无法发送消息")
            return
        
        summary_end_msg = SummaryEndMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            file_summary=summary_result.get("summary", ""),
            keywords=summary_result.get("keywords", []),
            topics=summary_result.get("topics", []),
            summary_quality=summary_result.get("quality", 0.9),
            llm_model=summary_result.get("llm_model", "gpt-4"),
            tokens_used=summary_result.get("tokens_used", {}),
            document_type=summary_result.get("document_type", "technical"),
            difficulty_level=summary_result.get("difficulty_level", "medium")
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.SUMMARY_END,
            message=summary_end_msg
        )
        
        logger.debug(f"发送 SummaryEndMessage: file_id={message.file_id}")
