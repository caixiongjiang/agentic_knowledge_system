#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
TextSplitter Worker

监听: knowledge_base.parse.end
功能: 从数据库加载 ParseResult，执行文本切分，生成 Chunk 并分发到下游
输出:
  - db_write.embedding.start (向量化写入)
  - db_write.meta.start (MySQL 元数据写入)
  - db_write.mongo.start (MongoDB 文档数据写入)
  - knowledge_base.split.end (前台完成通知)
"""

from typing import Optional, List, Dict, Any
from loguru import logger

from src.db.kafka.workers.base_worker import BaseWorker
from src.db.kafka.topics import KafkaTopics
from src.states.states import IndexStage
from src.types.messages.index import ParseEndMessage, SplitEndMessage
from src.types.messages.db_write import (
    EmbeddingWriteMessage,
    MetaWriteMessage,
    MongoWriteMessage,
    MySQLTable,
    MongoCollection,
    MilvusCollection,
    WriteOperation,
)
from src.service.knowledge.components.text_splitter_service import TextSplitterService
from src.types.models.split_result import SplitResult


class TextSplitterWorker(BaseWorker):
    """
    TextSplitter Worker
    
    职责:
    - 消费 Kafka 消息 (knowledge_base.parse.end)
    - 从 MySQL/MongoDB 加载 ParseResult
    - 调用 TextSplitterService 执行文本切分
    - 发送 MySQL 写入消息到 Kafka (section/chunk 元信息)
    - 发送 MongoDB 写入消息到 Kafka (section/chunk 内容数据)
    - 发送 Embedding 写入消息到 Kafka (文本向量化)
    - 发送 SplitEndMessage (前台完成通知，进度100%)
    
    架构说明:
    Worker 层 (本类):
      - 负责所有 Kafka 操作 (消费和生产)
      - 管理 MySQL 会话生命周期
      - 调用 Service 层处理业务逻辑
      - 不涉及具体的切分算法
    
    Service 层 (TextSplitterService):
      - 负责文本切分业务逻辑
      - 从数据库加载 ParseResult
      - 执行文本/表格/图片切分
      - 返回 SplitResult
    
    输入消息: ParseEndMessage
    输出消息:
      - MySQL 写入消息 (db_write.meta.start)
      - MongoDB 写入消息 (db_write.mongo.start)
      - EmbeddingWriteMessage (db_write.embedding.start)
      - SplitEndMessage (knowledge_base.split.end)
    
    配置要求:
    - 资源: 2 CPU, 4GB RAM
    - 扩容触发: Kafka lag > 200
    """
    
    def __init__(
        self,
        *args,
        text_splitter_service: Optional[TextSplitterService] = None,
        mysql_manager=None,
        **kwargs
    ):
        """
        初始化 TextSplitter Worker
        
        Args:
            text_splitter_service: 文本切分服务实例（可选，延迟创建）
            mysql_manager: MySQL 连接管理器（可选，延迟获取）
        """
        super().__init__(*args, **kwargs)
        self._splitter_service = text_splitter_service
        self._mysql_manager = mysql_manager
    
    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.PARSE_END

    def _get_failure_stage(self) -> str:
        return IndexStage.SPLIT_END
    
    def _get_splitter_service(self) -> TextSplitterService:
        """
        获取 TextSplitterService 实例（懒加载）
        
        Returns:
            TextSplitterService 实例
        """
        if self._splitter_service is None:
            self._splitter_service = TextSplitterService()
            logger.info("TextSplitterService 已创建")
        return self._splitter_service
    
    def _get_mysql_manager(self):
        """
        获取 MySQL 连接管理器（懒加载）
        
        Returns:
            BaseMySQLManager 实例
        """
        if self._mysql_manager is None:
            from src.db.mysql.connection.factory import MySQLManagerFactory
            self._mysql_manager = MySQLManagerFactory.get_manager()
            logger.info("MySQL 连接管理器已获取")
        return self._mysql_manager
    
    async def process_message_impl(self, message: ParseEndMessage) -> bool:
        """
        处理解析完成消息，执行文本切分
        
        流程:
        1. 校验消息状态（跳过解析失败的文件）
        2. 获取 MySQL 会话
        3. 调用 TextSplitterService.load_parse_result_from_db() 加载 ParseResult
        4. 调用 TextSplitterService.split_document() 执行切分
        5. 使用 SplitResult 的转换方法生成各类数据
        6. 分发到 4 个下游 Kafka Topic
        
        Args:
            message: ParseEndMessage
            
        Returns:
            bool: 是否处理成功
        """
        logger.info(
            f"开始文本切分: user_id={message.user_id}, "
            f"file_id={message.file_id}, filename={message.filename}"
        )
        
        # 1. 校验解析状态
        if message.status == "failed":
            error_msg = f"上游解析失败: {message.error_message}"
            logger.warning(
                f"跳过解析失败的文件: file_id={message.file_id}, "
                f"error={message.error_message}"
            )
            await self._fail_file_progress(
                file_id=message.file_id,
                stage=IndexStage.PARSE_END,
                error_message=error_msg,
            )
            await self._update_mysql_file_status(
                message.user_id, message.file_id, status=3, msg=error_msg,
            )
            return True
        
        try:
            # 2. 获取 Service 和 MySQL 会话
            splitter_service = self._get_splitter_service()
            mysql_manager = self._get_mysql_manager()
            
            # 3. 从数据库加载 ParseResult
            with mysql_manager.get_session() as session:
                parse_result = await splitter_service.load_parse_result_from_db(
                    user_id=message.user_id,
                    file_id=message.file_id,
                    document_id=message.document_id,
                    mysql_session=session,
                    knowledge_base_id=message.knowledge_base_id
                )
            
            if not parse_result.is_success():
                error_msg = f"ParseResult 加载失败: {parse_result.error_message}"
                logger.error(
                    f"ParseResult 加载失败: file_id={message.file_id}, "
                    f"error={parse_result.error_message}"
                )
                await self._fail_file_progress(
                    file_id=message.file_id,
                    stage=IndexStage.SPLIT_END,
                    error_message=error_msg,
                )
                await self._update_mysql_file_status(
                    message.user_id, message.file_id, status=3, msg=error_msg,
                )
                return False
            
            if not parse_result.elements:
                error_msg = "ParseResult 无元素，无法切分"
                logger.warning(f"ParseResult 无元素: file_id={message.file_id}")
                await self._fail_file_progress(
                    file_id=message.file_id,
                    stage=IndexStage.SPLIT_END,
                    error_message=error_msg,
                )
                await self._update_mysql_file_status(
                    message.user_id, message.file_id, status=3, msg=error_msg,
                )
                return False
            
            # 补充知识库信息（从消息透传到 ParseResult）
            if message.knowledge_base_name and not parse_result.knowledge_base_name:
                parse_result.knowledge_base_name = message.knowledge_base_name
            
            # 4. 执行文本切分
            document_id = message.document_id
            split_result = await splitter_service.split_document(
                parse_result=parse_result,
                document_id=document_id
            )
            
            if not split_result.is_success():
                error_msg = f"文本切分失败: {split_result.error_message}"
                logger.error(
                    f"文本切分失败: file_id={message.file_id}, "
                    f"error={split_result.error_message}"
                )
                await self._fail_file_progress(
                    file_id=message.file_id,
                    stage=IndexStage.SPLIT_END,
                    error_message=error_msg,
                )
                await self._update_mysql_file_status(
                    message.user_id, message.file_id, status=3, msg=error_msg,
                )
                return False
            
            logger.info(
                f"文本切分完成: file_id={message.file_id}, "
                f"sections={split_result.total_sections}, "
                f"chunks={split_result.total_chunks}, "
                f"text={len(split_result.text_chunks)}, "
                f"image={len(split_result.image_chunks)}, "
                f"table={len(split_result.table_chunks)}"
            )
            
            # 5. 分发到下游 Kafka Topic（暂时禁用，后续阶段尚未启用）
            # 5a. 发送 MySQL 写入消息
            mysql_data = split_result.get_mysql_data(document_id=document_id)
            await self._send_mysql_messages(message, mysql_data)
            
            # 5b. 发送 MongoDB 写入消息
            mongodb_data = split_result.get_mongodb_data()
            await self._send_mongodb_messages(message, mongodb_data)
            
            # 5c. 发送 Chunk Embedding 写入消息
            embedding_items = split_result.get_embedding_messages()
            if embedding_items:
                await self._send_embedding_messages(message, embedding_items, split_result)
            
            # 5d. 发送 Section Embedding 写入消息
            section_embedding_items = split_result.get_section_embedding_messages()
            if section_embedding_items:
                await self._send_section_embedding_messages(
                    message, section_embedding_items, split_result
                )
            
            # 5e. 发送 Enhanced Chunk Embedding 写入消息
            enhanced_items = split_result.get_enhanced_chunk_embedding_messages()
            if enhanced_items:
                await self._send_enhanced_chunk_embedding_messages(
                    message, enhanced_items, split_result
                )
            
            # # 5f. 发送 SplitEndMessage (前台完成通知)
            # await self._send_split_end_message(message, split_result)
            # logger.info(
            #     f"下游消息分发已禁用 (暂时跳过): file_id={message.file_id}, "
            #     f"chunks={split_result.total_chunks}"
            # )
            
            # 6. 更新 Redis 进度到 split_end (100%)
            success_msg = (
                f"文本切分完成: {split_result.total_chunks} 个文本块, "
                f"{split_result.total_sections} 个章节"
            )
            await self._update_file_progress(
                file_id=message.file_id,
                stage=IndexStage.SPLIT_END,
                message=success_msg,
            )

            # 7. 回写 MySQL status=2（前台阶段全部完成）
            await self._update_mysql_file_status(
                message.user_id, message.file_id, status=2, msg=success_msg,
            )
            
            logger.info(f"文本切分处理完成: file_id={message.file_id}")
            return True
            
        except Exception as e:
            error_msg = f"文本切分失败: {e}"
            logger.error(
                f"文本切分失败: file_id={message.file_id}, error={e}",
                exc_info=True
            )
            await self._fail_file_progress(
                file_id=message.file_id,
                stage=IndexStage.SPLIT_END,
                error_message=error_msg,
            )
            await self._update_mysql_file_status(
                message.user_id, message.file_id, status=3, msg=error_msg,
            )
            return False
    
    # ========== MySQL 状态回写 ==========

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

    # ========== 下游消息发送方法 ==========
    
    # MySQL 表名字符串 → MySQLTable 枚举的映射
    _MYSQL_TABLE_MAP: Dict[str, MySQLTable] = {
        "section_document": MySQLTable.SECTION_DOCUMENT,
        "section_meta_info": MySQLTable.SECTION_META_INFO,
        "chunk_section_document": MySQLTable.CHUNK_SECTION_DOCUMENT,
        "chunk_meta_info": MySQLTable.CHUNK_META_INFO,
    }

    async def _send_mysql_messages(
        self,
        message: ParseEndMessage,
        mysql_data: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """
        发送 MySQL 写入消息到 Kafka

        将 SplitResult 的 4 个表数据分别发送:
        - section_document (Section-Document 关系)
        - section_meta_info (Section 元信息)
        - chunk_section_document (Chunk-Section-Document 关系)
        - chunk_meta_info (Chunk 元信息)

        Args:
            message: 原始 ParseEndMessage
            mysql_data: SplitResult.get_mysql_data() 的返回值
        """
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 MySQL 消息")
            return

        # P2 #7：跨表汇总后一次性批量发送（同一 Topic）
        meta_msgs: List[MetaWriteMessage] = []

        for table_name_str, records in mysql_data.items():
            if not records:
                continue

            table_enum = self._MYSQL_TABLE_MAP.get(table_name_str)
            if not table_enum:
                logger.error(f"未知的 MySQL 表名: {table_name_str}")
                continue

            for record in records:
                record_id = (
                    record.get("chunk_id")
                    or record.get("section_id")
                    or message.file_id
                )

                meta_msgs.append(MetaWriteMessage(
                    user_id=message.user_id,
                    file_id=message.file_id,
                    table_name=table_enum,
                    record_data=record,
                    operation=WriteOperation.INSERT,
                    record_id=record_id,
                ))

        if meta_msgs:
            await self._producer.send_messages(
                topic=KafkaTopics.DB_WRITE_META,
                messages=meta_msgs
            )

        logger.debug(f"MySQL 消息发送完成: {len(meta_msgs)} 条 (4 个表)")
    
    # MongoDB Collection 名称字符串 → MongoCollection 枚举的映射
    _MONGO_COLLECTION_MAP: Dict[str, MongoCollection] = {
        "section_data": MongoCollection.SECTION_DATA,
        "chunk_data": MongoCollection.CHUNK_DATA,
    }

    async def _send_mongodb_messages(
        self,
        message: ParseEndMessage,
        mongodb_data: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """
        发送 MongoDB 写入消息到 Kafka

        将 SplitResult 的 2 个集合数据分别发送:
        - section_data (Section 内容)
        - chunk_data (Chunk 内容)

        Args:
            message: 原始 ParseEndMessage
            mongodb_data: SplitResult.get_mongodb_data() 的返回值
        """
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 MongoDB 消息")
            return

        # P2 #7：跨集合汇总后一次性批量发送（同一 Topic）
        mongo_msgs: List[MongoWriteMessage] = []

        for collection_name_str, documents in mongodb_data.items():
            if not documents:
                continue

            collection_enum = self._MONGO_COLLECTION_MAP.get(collection_name_str)
            if not collection_enum:
                logger.error(f"未知的 MongoDB Collection: {collection_name_str}")
                continue

            for doc in documents:
                document_id = doc.get("_id", message.file_id)

                mongo_msgs.append(MongoWriteMessage(
                    user_id=message.user_id,
                    file_id=message.file_id,
                    collection_name=collection_enum,
                    document_data=doc,
                    operation=WriteOperation.UPSERT,
                    document_id=str(document_id),
                ))

        if mongo_msgs:
            await self._producer.send_messages(
                topic=KafkaTopics.DB_WRITE_MONGO,
                messages=mongo_msgs
            )

        logger.debug(f"MongoDB 消息发送完成: {len(mongo_msgs)} 条 (2 个集合)")
    
    async def _send_embedding_messages(
        self,
        message: ParseEndMessage,
        embedding_items: List[Dict[str, Any]],
        split_result: SplitResult
    ) -> None:
        """
        发送向量化写入消息到 Kafka
        
        将所有需要向量化的 Chunk（text/table/code_block）批量发送。
        
        Args:
            message: 原始 ParseEndMessage
            embedding_items: SplitResult.get_embedding_messages() 的返回值
            split_result: 切分结果（用于获取语言信息）
        """
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 Embedding 消息")
            return
        
        emb_msg = EmbeddingWriteMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            collection_type=MilvusCollection.CHUNK,
            items=embedding_items,
            source_stage="split",
            document_id=message.document_id,
            knowledge_base_id=message.knowledge_base_id,
            knowledge_base_name=message.knowledge_base_name,
            language=split_result.document_language,
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.DB_WRITE_EMBEDDING,
            message=emb_msg
        )
        
        logger.debug(f"Embedding 消息发送完成: {len(embedding_items)} 个 Chunk")
    
    async def _send_section_embedding_messages(
        self,
        message: ParseEndMessage,
        section_items: List[Dict[str, Any]],
        split_result: SplitResult
    ) -> None:
        """
        发送 Section 向量化写入消息到 Kafka
        
        将所有 Section 标题文本发送到 section_store 进行向量化。
        
        Args:
            message: 原始 ParseEndMessage
            section_items: SplitResult.get_section_embedding_messages() 的返回值
            split_result: 切分结果（用于获取语言信息）
        """
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 Section Embedding 消息")
            return
        
        emb_msg = EmbeddingWriteMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            collection_type=MilvusCollection.SECTION,
            items=section_items,
            source_stage="split",
            document_id=message.document_id,
            knowledge_base_id=message.knowledge_base_id,
            knowledge_base_name=message.knowledge_base_name,
            language=split_result.document_language,
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.DB_WRITE_EMBEDDING,
            message=emb_msg
        )
        
        logger.debug(f"Section Embedding 消息发送完成: {len(section_items)} 个 Section")
    
    async def _send_enhanced_chunk_embedding_messages(
        self,
        message: ParseEndMessage,
        enhanced_items: List[Dict[str, Any]],
        split_result: SplitResult
    ) -> None:
        """
        发送 Enhanced Chunk 向量化写入消息到 Kafka
        
        将含有 enhanced_vector_text（Section标题+Chunk文本）的 Chunk 发送到
        enhanced_chunk_store 进行向量化。
        
        Args:
            message: 原始 ParseEndMessage
            enhanced_items: SplitResult.get_enhanced_chunk_embedding_messages() 的返回值
            split_result: 切分结果（用于获取语言信息）
        """
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 Enhanced Chunk Embedding 消息")
            return
        
        emb_msg = EmbeddingWriteMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            collection_type=MilvusCollection.ENHANCED_CHUNK,
            items=enhanced_items,
            source_stage="split",
            document_id=message.document_id,
            knowledge_base_id=message.knowledge_base_id,
            knowledge_base_name=message.knowledge_base_name,
            language=split_result.document_language,
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.DB_WRITE_EMBEDDING,
            message=emb_msg
        )
        
        logger.debug(
            f"Enhanced Chunk Embedding 消息发送完成: {len(enhanced_items)} 个 Chunk"
        )
    
    async def _send_split_end_message(
        self,
        message: ParseEndMessage,
        split_result: SplitResult
    ) -> None:
        """
        发送切分完成消息（前台进度 100%）
        
        Args:
            message: 原始 ParseEndMessage
            split_result: 切分结果
        """
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 SplitEndMessage")
            return
        
        # 构建 chunks 摘要数据（供下游使用）
        chunks_summary = [
            {
                "chunk_id": chunk.chunk_id,
                "chunk_type": chunk.chunk_type,
                "text": chunk.get_text_content() or "",
                "page_index": chunk.page_index,
                "language": chunk.language,
            }
            for chunk in split_result.chunks
        ]
        
        split_end_msg = SplitEndMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            chunks=chunks_summary,
            split_strategy=split_result.split_method,
            chunk_stats={
                "total_chunks": split_result.total_chunks,
                "total_sections": split_result.total_sections,
                "text_chunks": len(split_result.text_chunks),
                "image_chunks": len(split_result.image_chunks),
                "table_chunks": len(split_result.table_chunks),
                "code_chunks": len(split_result.code_chunks),
                "avg_chunk_size": (
                    split_result.total_chars // split_result.total_chunks
                    if split_result.total_chunks > 0 else 0
                ),
            },
            total_length=split_result.total_chars,
            language=split_result.document_language,
            frontend_complete=True,
            brief_summary=(
                f"文档已切分为 {split_result.total_chunks} 个文本块，"
                f"包含 {split_result.total_sections} 个章节"
            )
        )
        
        await self._producer.send_message(
            topic=KafkaTopics.SPLIT_END,
            message=split_end_msg
        )
        
        logger.info(
            f"发送 SplitEndMessage (前台完成): file_id={message.file_id}, "
            f"chunks={split_result.total_chunks}"
        )
