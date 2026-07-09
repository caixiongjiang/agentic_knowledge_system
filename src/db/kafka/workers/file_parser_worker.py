#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
FileParser Worker

监听: knowledge_base:index:start
功能: 调用 FileParserService 解析文件,提取结构化信息
输出: 
  - db_write.meta.start (MySQL 元数据写入)
  - db_write.mongo.start (MongoDB 文档数据写入)
  - knowledge_base.parse.end (解析完成消息)
"""

from typing import Optional, List, Dict, Any
from loguru import logger

from src.db.kafka.workers.base_worker import BaseWorker
from src.db.kafka.topics import KafkaTopics
from src.states.states import IndexStage
from src.types.messages.index import IndexStartMessage, ParseEndMessage
from src.types.messages.db_write import (
    MetaWriteMessage,
    MongoWriteMessage,
    MySQLTable,
    MongoCollection,
    WriteOperation,
)
from src.db.storage.manager import StorageManager
from src.service.knowledge.components.file_parser_service import FileParserService


class FileParserWorker(BaseWorker):
    """
    FileParser Worker
    
    职责:
    - 消费 Kafka 消息 (knowledge_base:index:start)
    - 调用 FileParserService 解析文件
    - 发送 MySQL 写入消息到 Kafka
    - 发送 MongoDB 写入消息到 Kafka
    - 发送解析完成消息到 Kafka
    
    架构说明:
    Worker 层 (本类):
      - 负责所有 Kafka 操作 (消费和生产)
      - 调用 Service 层处理业务逻辑
      - 不涉及具体业务逻辑
    
    Service 层 (FileParserService):
      - 负责文件解析业务逻辑
      - 不依赖 Kafka
      - 返回构建好的消息
    
    输入消息: IndexStartMessage
    输出消息: 
      - MySQL 写入消息 (db_write.meta.start)
      - MongoDB 写入消息 (db_write.mongo.start)
      - ParseEndMessage (knowledge_base.parse.end)
    
    配置要求:
    - 资源: 4 CPU, 16GB RAM, 1 GPU (如果使用 Mineru)
    - 扩容触发: Kafka lag > 50
    """
    
    def __init__(
        self,
        *args,
        storage_manager: Optional[StorageManager] = None,
        mysql_manager=None,
        **kwargs
    ):
        """
        初始化 FileParser Worker
        
        Args:
            storage_manager: 对象存储管理器（可选，如果不提供会自动创建）
            mysql_manager: MySQL 连接管理器（可选，延迟获取）
        """
        super().__init__(*args, **kwargs)
        self._storage_manager = storage_manager
        self._mysql_manager = mysql_manager
        self._parser_service = None  # 延迟创建
    
    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.INDEX_START

    def _get_failure_stage(self) -> str:
        return IndexStage.PARSE_END
    
    async def _get_parser_service(self) -> FileParserService:
        """
        获取 FileParserService 实例（懒加载）
        
        Returns:
            FileParserService 实例
        """
        if self._parser_service is None:
            # 如果没有提供 storage_manager，创建一个
            if self._storage_manager is None:
                self._storage_manager = StorageManager()
                await self._storage_manager.__aenter__()  # 手动进入上下文
            
            # 创建 FileParserService
            self._parser_service = FileParserService(
                storage_manager=self._storage_manager
            )
            logger.info("FileParserService 已创建")
        
        return self._parser_service
    
    async def process_message_impl(self, message: IndexStartMessage) -> bool:
        """
        处理索引开始消息，解析文件
        
        流程:
        1. 调用 FileParserService.parse_file()
        2. 获取返回值：(ParseResult, MySQL消息列表, MongoDB消息列表)
        3. 发送 MySQL 消息到 Kafka
        4. 发送 MongoDB 消息到 Kafka
        5. 发送解析完成消息到 Kafka
        
        Args:
            message: IndexStartMessage
            {
                "user_id": "user_123",
                "file_id": "file_456",
                "filename": "document.pdf",
                "storage_path": "bucket/path/to/file.pdf",
                "knowledge_base_id": "kb_001",
                "knowledge_base_name": "我的知识库",
                "session_id": "session_789",
                ...
            }
            
        Returns:
            bool: 是否处理成功
        """
        logger.info(
            f"开始解析文件: user_id={message.user_id}, "
            f"file_id={message.file_id}, filename={message.filename}"
        )
        
        try:
            # 1. 获取 FileParserService 实例
            parser_service = await self._get_parser_service()
            
            # 2. 调用 Service 解析文件
            logger.info("调用 FileParserService.parse_file()...")
            parse_result, mysql_messages, mongodb_messages, elements_payload = await parser_service.parse_file(
                user_id=message.user_id,
                file_id=message.file_id,
                filename=message.filename,
                storage_path=message.storage_path,
                knowledge_base_id=message.knowledge_base_id,
                knowledge_base_name=message.knowledge_base_name,
                document_id=message.document_id,
                session_id=getattr(message, 'session_id', None),
                parent_knowledge_base_id=getattr(message, 'parent_knowledge_base_id', None),
                parent_knowledge_base_name=getattr(message, 'parent_knowledge_base_name', None),
                knowledge_type=getattr(message, 'knowledge_type', None),
                creator=message.user_id,
                store_images=True  # 上传图片到 MinIO
            )
            
            # 检查解析是否成功
            if not parse_result.is_success():
                error_msg = f"文件解析失败: {parse_result.error_message}"
                logger.error(
                    f"文件解析失败: file_id={message.file_id}, "
                    f"error={parse_result.error_message}"
                )
                await self._fail_file_progress(
                    file_id=message.file_id,
                    stage=IndexStage.PARSE_END,
                    error_message=error_msg,
                )
                await self._update_mysql_file_status(
                    message.user_id, message.file_id, status=3, msg=error_msg,
                )
                return False
            
            logger.info(
                f"文件解析成功: file_id={message.file_id}, "
                f"mysql_messages={len(mysql_messages)}, "
                f"mongodb_messages={len(mongodb_messages)}, "
                f"elements_payload={len(elements_payload)}"
            )
            
            # 3. 发送 MySQL 写入消息到 Kafka
            if mysql_messages:
                await self._send_mysql_messages(message, mysql_messages)
            
            # 4. 发送 MongoDB 写入消息到 Kafka
            if mongodb_messages:
                await self._send_mongodb_messages(message, mongodb_messages)
            
            # 5. 发送解析完成消息（自包含 elements payload，供 split 阶段直接消费）
            await self._send_parse_end_message(message, parse_result, elements_payload)
            
            # 6. 更新 Redis 进度到 parse_end (40%)
            await self._update_file_progress(
                file_id=message.file_id,
                stage=IndexStage.PARSE_END,
                message=f"文件解析完成: {parse_result.total_pages} 页",
            )
            
            logger.info(f"文件解析处理完成: file_id={message.file_id}")
            return True
            
        except Exception as e:
            error_msg = f"文件解析失败: {e}"
            logger.error(
                f"文件解析失败: file_id={message.file_id}, error={e}",
                exc_info=True
            )
            await self._fail_file_progress(
                file_id=message.file_id,
                stage=IndexStage.PARSE_END,
                error_message=error_msg,
            )
            await self._update_mysql_file_status(
                message.user_id, message.file_id, status=3, msg=error_msg,
            )
            return False

    # ========== MySQL 状态回写 ==========

    def _get_mysql_manager(self):
        """获取 MySQL 连接管理器（懒加载）"""
        if self._mysql_manager is None:
            from src.db.mysql.connection.factory import MySQLManagerFactory
            self._mysql_manager = MySQLManagerFactory.get_manager()
        return self._mysql_manager

    async def _update_mysql_file_status(
        self, user_id: str, file_id: str, status: int, msg: str
    ) -> None:
        """回写 workspace_file_system.status（不阻塞主流程）"""
        try:
            from src.db.mysql.models.business.workspace_file_system import (
                WorkspaceFileSystem,
            )
            mysql_mgr = self._get_mysql_manager()
            with mysql_mgr.get_session() as session:
                session.query(WorkspaceFileSystem).filter(
                    WorkspaceFileSystem.user_id == user_id,
                    WorkspaceFileSystem.file_id == file_id,
                ).update(
                    {"status": status, "message": msg[:1024]},
                    synchronize_session="fetch",
                )
                session.commit()
        except Exception as e:
            logger.warning(
                f"回写 MySQL 文件状态失败（不阻塞）: file_id={file_id}, error={e}"
            )

    async def _send_mysql_messages(
        self,
        message: IndexStartMessage,
        records: List[Dict[str, Any]]
    ) -> None:
        """
        发送 MySQL 写入消息到 Kafka
        
        将原始 element dict 包装为 MetaWriteMessage 后发送。
        
        Args:
            message: 原始 IndexStartMessage（提供 user_id, file_id）
            records: MySQL 记录列表（来自 FileParserService）
        """
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 MySQL 消息")
            return
        
        logger.info(f"发送 {len(records)} 条 MySQL 消息到 Kafka")
        
        # P2 #7：先组装全部消息，再批量发送（aiokafka 合并为更少的 broker 请求）
        meta_msgs = [
            MetaWriteMessage(
                user_id=message.user_id,
                file_id=message.file_id,
                table_name=MySQLTable.ELEMENT_META_INFO,
                record_data=record,
                operation=WriteOperation.INSERT,
                record_id=record.get("element_id", message.file_id),
            )
            for record in records
        ]
        if meta_msgs:
            await self._producer.send_messages(
                topic=KafkaTopics.DB_WRITE_META,
                messages=meta_msgs
            )
        
        logger.debug(f"MySQL 消息发送完成: {len(records)} 条")
    
    async def _send_mongodb_messages(
        self,
        message: IndexStartMessage,
        documents: List[Dict[str, Any]]
    ) -> None:
        """
        发送 MongoDB 写入消息到 Kafka
        
        将原始 element dict 包装为 MongoWriteMessage 后发送。
        
        Args:
            message: 原始 IndexStartMessage（提供 user_id, file_id）
            documents: MongoDB 文档列表（来自 FileParserService）
        """
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 MongoDB 消息")
            return
        
        logger.info(f"发送 {len(documents)} 条 MongoDB 消息到 Kafka")
        
        # P2 #7：批量发送
        mongo_msgs = [
            MongoWriteMessage(
                user_id=message.user_id,
                file_id=message.file_id,
                collection_name=MongoCollection.ELEMENT_DATA,
                document_data=doc,
                operation=WriteOperation.INSERT,
                document_id=str(doc.get("_id", message.file_id)),
            )
            for doc in documents
        ]
        if mongo_msgs:
            await self._producer.send_messages(
                topic=KafkaTopics.DB_WRITE_MONGO,
                messages=mongo_msgs
            )
        
        logger.debug(f"MongoDB 消息发送完成: {len(documents)} 条")
    
    async def _send_parse_end_message(
        self,
        message: IndexStartMessage,
        parse_result,
        elements_payload: List[Dict[str, Any]]
    ) -> None:
        """
        发送解析完成消息（自包含 elements payload）
        
        Args:
            message: 原始消息
            parse_result: ParseResult 对象
            elements_payload: 全部 element 数据（供下游 TextSplitterWorker 直接消费，不读库）
        """
        if not self._producer:
            logger.warning("Producer 未配置，无法发送解析完成消息")
            return
        
        # 构建 ParseEndMessage
        # 处理 status：如果是枚举则取值，如果已经是字符串则直接使用
        status_value = parse_result.status.value if hasattr(parse_result.status, 'value') else str(parse_result.status)
        
        parse_end_msg = ParseEndMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            filename=parse_result.filename,
            status=status_value,
            total_pages=parse_result.total_pages,
            total_chars=parse_result.total_chars,
            parse_tool=parse_result.parse_tool,
            parse_quality=parse_result.parse_quality,
            document_language=parse_result.document_language,
            document_id=message.document_id,
            knowledge_base_id=getattr(parse_result, 'knowledge_base_id', None) or message.knowledge_base_id,
            knowledge_base_name=getattr(parse_result, 'knowledge_base_name', None) or message.knowledge_base_name,
            error_message=parse_result.error_message,
            # 自包含 element 数据：split 阶段从此字段构造 ParseResult，消除 parse→split 读库竞态
            elements=elements_payload,
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.PARSE_END,
            message=parse_end_msg
        )
        
        logger.debug(
            f"发送 ParseEndMessage: file_id={message.file_id}, "
            f"elements={len(elements_payload)}"
        )
    
    async def cleanup(self):
        """清理资源"""
        # 清理 StorageManager
        if self._storage_manager is not None:
            try:
                await self._storage_manager.close()
                logger.info("StorageManager 已关闭")
            except Exception as e:
                logger.error(f"关闭 StorageManager 失败: {e}")
        
        # 调用父类清理
        await super().cleanup()
