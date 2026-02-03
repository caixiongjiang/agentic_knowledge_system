#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
FileParser Worker

监听: knowledge_base:index:start
功能: 调用 Mineru 解析 PDF 文件,提取结构化信息和图片
输出: knowledge_base:parse:end, db_write:meta:start
"""

from typing import Optional
from loguru import logger

from src.db.kafka.workers.base_worker import BaseWorker
from src.db.kafka.producer import KafkaProducer
from src.db.kafka.topics import KafkaTopics
from src.types.messages.index import IndexStartMessage, ParseEndMessage
from src.types.messages.db_write import MetaWriteMessage


class FileParserWorker(BaseWorker):
    """
    FileParser Worker
    
    职责:
    - 从 S3 下载 PDF 文件
    - 调用 Mineru API 进行 PDF 解析
    - 分页并发处理提高效率
    - 提取 PDF 结构化信息和图片
    - 存储 PDF 结构化信息到 MySQL
    - 上传图片到 S3
    - 发送解析完成事件
    
    输入消息: IndexStartMessage
    输出消息: ParseEndMessage, MetaWriteMessage
    
    配置要求:
    - 资源: 4 CPU, 16GB RAM, 1 GPU
    - 扩容触发: Kafka lag > 50
    """
    
    def __init__(
        self,
        *args,
        file_parser_service=None,  # 文件解析服务
        **kwargs
    ):
        """
        初始化 FileParser Worker
        
        Args:
            file_parser_service: 文件解析服务实例（封装所有业务逻辑）
        """
        super().__init__(*args, **kwargs)
        self._parser_service = file_parser_service
    
    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.INDEX_START
    
    async def process_message_impl(self, message: IndexStartMessage) -> bool:
        """
        处理索引开始消息,解析文件
        
        Args:
            message: IndexStartMessage
            
        Returns:
            bool: 是否处理成功
        """
        logger.info(
            f"开始解析文件: user_id={message.user_id}, "
            f"file_id={message.file_id}, filename={message.filename}"
        )
        
        try:
            # TODO: 调用 FileParserService 处理业务逻辑
            # parse_result = await self._parser_service.parse_file(
            #     file_id=message.file_id,
            #     s3_path=message.s3_path,
            #     filename=message.filename,
            #     user_id=message.user_id
            # )
            
            # 临时模拟数据（等待 Service 实现）
            parse_result = {
                "text_content": "解析后的文本内容",
                "document_metadata": {
                    "author": "Author Name",
                    "creation_date": "2024-01-01",
                    "title": message.filename
                },
                "parse_tool": "mineru",
                "parse_quality": 0.95,
                "images": [],
                "tables": [],
                "document_language": "zh",
                "total_pages": 10
            }
            
            # 发送 ParseEndMessage
            await self._send_parse_end_message(message, parse_result)
            
            # 发送 MetaWriteMessage
            await self._send_meta_write_message(message, parse_result)
            
            logger.info(f"文件解析完成: file_id={message.file_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"文件解析失败: file_id={message.file_id}, error={e}", exc_info=True)
            return False
    
    async def _send_parse_end_message(
        self,
        message: IndexStartMessage,
        parse_result: dict
    ) -> None:
        """
        发送解析完成消息
        
        Args:
            message: 原始消息
            parse_result: 解析结果
            image_paths: 图片路径列表
        """
        if not self._producer:
            logger.warning("Producer 未配置,无法发送消息")
            return
        
        parse_end_msg = ParseEndMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            text_content=parse_result.get("text_content", ""),
            document_metadata=parse_result.get("document_metadata", {}),
            parse_tool=parse_result.get("parse_tool", "mineru"),
            parse_quality=parse_result.get("parse_quality", 0.9),
            images=parse_result.get("images", []),
            tables=parse_result.get("tables", []),
            document_language=parse_result.get("document_language", "zh")
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.PARSE_END,
            message=parse_end_msg
        )
        
        logger.debug(f"发送 ParseEndMessage: file_id={message.file_id}")
    
    async def _send_meta_write_message(
        self,
        message: IndexStartMessage,
        parse_result: dict
    ) -> None:
        """
        发送元数据写入消息
        
        Args:
            message: 原始消息
            parse_result: 解析结果
        """
        if not self._producer:
            logger.warning("Producer 未配置,无法发送消息")
            return
        
        meta_write_msg = MetaWriteMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            file_metadata={
                "filename": message.filename,
                "file_size": message.file_size,
                "mime_type": message.mime_type,
                "s3_path": message.s3_path
            },
            processing_metadata={
                "total_pages": parse_result.get("total_pages", 0),
                "parse_quality": parse_result.get("parse_quality", 0.9),
                "images_count": len(parse_result.get("images", [])),
                "tables_count": len(parse_result.get("tables", []))
            },
            update_fields=["file_metadata", "processing_metadata"],
            operation="upsert"
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.DB_WRITE_META,
            message=meta_write_msg
        )
        
        logger.debug(f"发送 MetaWriteMessage: file_id={message.file_id}")
