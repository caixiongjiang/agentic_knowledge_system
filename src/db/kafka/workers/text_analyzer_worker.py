#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
TextAnalyzer Worker（v1.1 section 级 atomic_qa 抽取）

监听: knowledge_base.file_summary.end（file_summary 完成后触发，与 KGExtractor 并行）
功能: section 级抽取 atomic_qa（带 [Cn] 占位符 → chunk_id 溯源），超长 section 自动分批
输入: SummaryEndMessage（file_summary 从消息体取；section/chunk 读 DB）
输出:
  - db_write.embedding.start  (Milvus atomic_qa_store，向量化源=question，标量含 section_id)
  - db_write.mongo.start      (MongoDB section_data.atomic_qa，按 section_id 局部 $set)
  - db_write.meta.start       (MySQL section_atomic_qa 关联表)
  - knowledge_base.analyze.end (供 status manager 标记后台 ANALYZE_END 完成)

设计要点：
- 后台阶段，对前台进度完全无感知：不调用 _update_file_progress()，
  并覆盖 _fail_file_progress() 为空实现，避免 BaseWorker 兜底把 Redis
  status 写成 failed 污染用户可见状态（失败隔离）。
- 组件开关：config/components.json 中 text_analyzer.enabled=false 时
  空跑（消费但跳过），避免 Kafka lag 堆积。
- DB + Message 混合取数：section/chunk 读 DB（链路末端已稳定落盘），
  file_summary 读消息体（file_summary 刚发出，落库进度不保证先于本 Worker）。
- Worker 层只做编排：Kafka 消息构造/分发；业务逻辑全部在 TextAnalyzerService 中。
"""

from typing import Optional, List, Dict, Any

from loguru import logger

from src.db.kafka.workers.base_worker import BaseWorker
from src.db.kafka.topics import KafkaTopics
from src.states.states import IndexStage
from src.types.messages.extract import AnalyzeEndMessage, SummaryEndMessage
from src.types.messages.db_write import (
    EmbeddingWriteMessage,
    MetaWriteMessage,
    MongoWriteMessage,
    MilvusCollection,
    MongoCollection,
    MySQLTable,
    WriteOperation,
)
from src.service.knowledge.components.text_analyzer_service import (
    TextAnalyzerService,
)
from src.types.models.text_analyzer_result import TextAnalyzerResult
from src.utils.component_config_manager import get_component_config_manager


class TextAnalyzerWorker(BaseWorker):
    """
    TextAnalyzer Worker

    职责:
    - 消费 Kafka 消息 (knowledge_base.file_summary.end)
    - 校验组件开关 (text_analyzer.enabled)
    - 调用 TextAnalyzerService 抽取 section 级 atomic_qa
    - 将结果分发到 db_write.embedding / db_write.mongo / db_write.meta
    - 发送 AnalyzeEndMessage (knowledge_base.analyze.end)

    输入消息: SummaryEndMessage
    输出消息:
      - EmbeddingWriteMessage (db_write.embedding.start) → atomic_qa_store
      - MongoWriteMessage (db_write.mongo.start) → section_data.atomic_qa
      - MetaWriteMessage (db_write.meta.start) → section_atomic_qa
      - AnalyzeEndMessage (knowledge_base.analyze.end)

    配置要求:
    - 资源: 4 CPU, 8GB RAM（LLM 调用为主，IO 次之）
    - 扩容触发: Kafka lag > 50
    """

    COMPONENT_NAME = "text_analyzer"

    def __init__(
        self,
        *args,
        text_analyzer_service: Optional[TextAnalyzerService] = None,
        **kwargs,
    ):
        """
        Args:
            text_analyzer_service: TextAnalyzerService 实例（可选，懒加载）
        """
        super().__init__(*args, **kwargs)
        self._analyzer_service = text_analyzer_service
        self._config_manager = get_component_config_manager()

    # ========== 抽象方法实现 ==========

    def get_original_topic(self) -> str:
        return KafkaTopics.FILE_SUMMARY_END

    def _get_failure_stage(self) -> str:
        # 后台阶段，仅用于日志标识；_fail_file_progress 已覆盖为空实现
        return IndexStage.ANALYZE_END

    # ========== 失败隔离：后台阶段不污染前台进度 ==========

    async def _fail_file_progress(
        self, file_id: str, stage: str, error_message: str
    ) -> None:
        """覆盖基类行为：后台阶段失败不写 Redis 进度，仅记录日志。"""
        logger.warning(
            f"TextAnalyzer 后台阶段失败（不污染前台进度）: "
            f"file_id={file_id}, stage={stage}, error={error_message}"
        )

    # ========== 懒加载依赖 ==========

    def _get_analyzer_service(self) -> TextAnalyzerService:
        if self._analyzer_service is None:
            self._analyzer_service = TextAnalyzerService()
            logger.info("TextAnalyzerService 已创建")
        return self._analyzer_service

    # ========== 主流程 ==========

    async def process_message_impl(self, message: SummaryEndMessage) -> bool:
        """
        处理 file_summary 完成消息，抽取 section 级 atomic_qa 并分发下游。

        Args:
            message: SummaryEndMessage

        Returns:
            bool: 是否处理成功
        """
        logger.info(
            f"开始文本分析（atomic_qa 抽取）: user_id={message.user_id}, "
            f"file_id={message.file_id}, document_id={message.document_id}"
        )

        # 1. 组件开关守卫：禁用时空跑
        if not self._config_manager.is_component_enabled(self.COMPONENT_NAME):
            logger.info(
                f"TextAnalyzer 组件已禁用，跳过处理: file_id={message.file_id}"
            )
            return True

        # 2. 校验溯源字段
        document_id = message.document_id
        if not document_id:
            logger.error(
                f"TextAnalyzer: SummaryEndMessage 缺少 document_id，跳过: "
                f"file_id={message.file_id}"
            )
            return True

        try:
            service = self._get_analyzer_service()

            # 3. 调用 Service 抽取（DB + Message 混合取数）
            result: TextAnalyzerResult = await service.analyze_document(
                document_id=document_id,
                file_summary=message.file_summary,
                language=message.language,
                knowledge_base_id=message.knowledge_base_id,
                knowledge_base_name=message.knowledge_base_name,
            )

            # 4. 分发到 db_write.*
            if result.is_success():
                await self._send_embedding_messages(message, result)
                await self._send_mongodb_messages(message, result)
                await self._send_mysql_messages(message, result)
            else:
                logger.warning(
                    f"TextAnalyzer: 文档无 QA 产出（可能无 chunk 文本或 LLM 全失败），"
                    f"仅发送 analyze.end: file_id={message.file_id}, "
                    f"document_id={document_id}"
                )

            # 5. 发送 AnalyzeEndMessage（供 status manager 标记后台完成）
            await self._send_analyze_end_message(message, result)

            logger.info(
                f"文本分析处理完成: file_id={message.file_id}, "
                f"document_id={document_id}, qa={result.total_qa}, "
                f"sections={result.section_count}, "
                f"llm_calls={result.llm_call_count}"
            )
            return True

        except Exception as e:
            logger.error(
                f"文本分析失败: file_id={message.file_id}, error={e}",
                exc_info=True,
            )
            return False

    # ========== 下游消息发送 ==========

    async def _send_mysql_messages(
        self,
        message: SummaryEndMessage,
        result: TextAnalyzerResult,
    ) -> None:
        """发送 MySQL section_atomic_qa 关联表写入消息。"""
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 MySQL 消息")
            return

        mysql_data = result.get_mysql_data()
        records = mysql_data.get("section_atomic_qa", [])
        if not records:
            return

        meta_msgs: List[MetaWriteMessage] = []
        for record in records:
            qa_id = record.get("qa_id") or ""
            meta_msgs.append(MetaWriteMessage(
                user_id=message.user_id,
                file_id=message.file_id,
                table_name=MySQLTable.SECTION_ATOMIC_QA,
                record_data=record,
                operation=WriteOperation.UPSERT,
                record_id=qa_id,
            ))

        if meta_msgs:
            await self._producer.send_messages(
                topic=KafkaTopics.DB_WRITE_META,
                messages=meta_msgs,
            )
        logger.debug(
            f"TextAnalyzer MySQL 消息发送完成: {len(meta_msgs)} 条 (section_atomic_qa)"
        )

    async def _send_mongodb_messages(
        self,
        message: SummaryEndMessage,
        result: TextAnalyzerResult,
    ) -> None:
        """发送 MongoDB section_data.atomic_qa 局部更新消息（按 section 聚合）。"""
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 MongoDB 消息")
            return

        mongo_data = result.get_mongodb_data()
        documents = mongo_data.get("section_data", [])
        if not documents:
            return

        mongo_msgs: List[MongoWriteMessage] = []
        for doc in documents:
            section_id = doc.get("_id", "")
            mongo_msgs.append(MongoWriteMessage(
                user_id=message.user_id,
                file_id=message.file_id,
                collection_name=MongoCollection.SECTION_DATA,
                document_data=doc,
                operation=WriteOperation.UPSERT,
                document_id=str(section_id),
            ))

        if mongo_msgs:
            await self._producer.send_messages(
                topic=KafkaTopics.DB_WRITE_MONGO,
                messages=mongo_msgs,
            )
        logger.debug(
            f"TextAnalyzer MongoDB 消息发送完成: {len(mongo_msgs)} 条 "
            f"(section_data.atomic_qa)"
        )

    async def _send_embedding_messages(
        self,
        message: SummaryEndMessage,
        result: TextAnalyzerResult,
    ) -> None:
        """发送 Milvus atomic_qa_store 向量化消息（向量化源=question）。"""
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 Embedding 消息")
            return

        items = result.get_embedding_messages()
        if not items:
            return

        emb_msg = EmbeddingWriteMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            collection_type=MilvusCollection.ATOMIC_QA,
            items=items,
            source_stage="analyze_end",
            document_id=message.document_id or "",
            knowledge_base_id=message.knowledge_base_id,
            knowledge_base_name=message.knowledge_base_name,
            language=message.language,
        )

        await self._producer.send_message(
            topic=KafkaTopics.DB_WRITE_EMBEDDING,
            message=emb_msg,
        )
        logger.debug(
            f"TextAnalyzer Embedding 消息发送完成: {len(items)} 条 (atomic_qa_store)"
        )

    async def _send_analyze_end_message(
        self,
        message: SummaryEndMessage,
        result: TextAnalyzerResult,
    ) -> None:
        """发送 AnalyzeEndMessage（轻量，决策 a），供 status manager 标记后台完成。"""
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 AnalyzeEndMessage")
            return

        stats = result.get_analyze_end_stats()
        analyze_end_msg = AnalyzeEndMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            document_id=message.document_id,
            knowledge_base_id=message.knowledge_base_id,
            knowledge_base_name=message.knowledge_base_name,
            total_sections=stats["total_sections"],
            total_qa=stats["total_qa"],
            llm_call_count=stats["llm_call_count"],
            llm_model=result.llm_model,
            token_usage=result.token_usage,
        )

        await self._producer.send_message(
            topic=KafkaTopics.ANALYZE_END,
            message=analyze_end_msg,
        )
        logger.info(
            f"发送 AnalyzeEndMessage: file_id={message.file_id}, "
            f"total_qa={stats['total_qa']}, "
            f"llm_calls={stats['llm_call_count']}"
        )
