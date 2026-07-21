#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
FileSummary Worker

监听: knowledge_base.section_summary.end
功能: 基于 section 摘要汇总生成文件级别摘要，为后续 QA / KG 抽取提供全局上下文
输出:
  - db_write.meta.start     (MySQL document_summary 关联表)
  - db_write.mongo.start    (MongoDB document_data.summary 结构化子文档)
  - db_write.embedding.start (Milvus file_summary_store, role=document_summary)
  - knowledge_base.file_summary.end (触发下游 KGExtractor / TextAnalyzer)

设计要点：
- 后台阶段，对前台进度完全无感知：不调用 _update_file_progress()，
  并覆盖 _fail_file_progress() 为空实现，避免 BaseWorker 兜底把 Redis
  status 写成 failed 污染用户可见状态（失败隔离）。
- 组件开关：config/components.json 中 file_summary.enabled=false 时
  空跑（消费但跳过），避免 Kafka lag 堆积。
- **不读数据库**：section 摘要正文输入完全来自 SectionSummaryEndMessage
  的 section_summaries_payload 字段（自包含），避免 section_summary
  写库异步导致的竞态。
- Worker 层只做编排：Kafka 消息构造/分发；业务逻辑全部在 FileSummaryService 中。

下游接通状态：
- TextAnalyzerWorker 已落地（v1.1 section 级 atomic_qa 抽取），本 Worker 正常发送
  SummaryEndMessage 到 knowledge_base.file_summary.end。下游 TextAnalyzerWorker
  消费该消息并输出 db_write.embedding / db_write.mongo / db_write.meta +
  knowledge_base.analyze.end。
- KGExtractorWorker 仍为 mock 实现，消费同一消息产出模拟图谱数据；如需暂避其
  产出，启动时不加 kg_extractor 即可（start_all_workers.py 按 --workers 启停）。
- 启停：start_all_workers.py 默认不启动 text_analyzer / kg_extractor，
  需在启动命令加 --workers ...,text_analyzer[,kg_extractor] 即可接通。
"""

from typing import Optional, List, Dict, Any
from loguru import logger

from src.db.kafka.workers.base_worker import BaseWorker
from src.db.kafka.topics import KafkaTopics
from src.states.states import IndexStage
from src.types.messages.extract import (
    SectionSummaryEndMessage,
    SummaryEndMessage,
)
from src.types.messages.db_write import (
    EmbeddingWriteMessage,
    MetaWriteMessage,
    MongoWriteMessage,
    MySQLTable,
    MongoCollection,
    MilvusCollection,
    WriteOperation,
)
from src.service.knowledge.components.file_summary_service import (
    FileSummaryService,
)
from src.types.models.file_summary_result import FileSummaryResult
from src.utils.component_config_manager import get_component_config_manager


class FileSummaryWorker(BaseWorker):
    """
    FileSummary Worker

    职责:
    - 消费 Kafka 消息 (knowledge_base.section_summary.end)
    - 校验组件开关 (file_summary.enabled)
    - 从 SectionSummaryEndMessage 的 section_summaries_payload 字段读取
      section 摘要正文（不读库）
    - 调用 FileSummaryService 生成文件级摘要
    - 将结果分发到 db_write.meta / db_write.mongo / db_write.embedding
    - 发送 SummaryEndMessage (触发下游 KGExtractor / TextAnalyzer)

    输入消息: SectionSummaryEndMessage
    输出消息:
      - MetaWriteMessage (db_write.meta.start) → document_summary 表
      - MongoWriteMessage (db_write.mongo.start) → document_data.summary
      - EmbeddingWriteMessage (db_write.embedding.start) → file_summary_store
      - SummaryEndMessage (knowledge_base.file_summary.end)

    配置要求:
    - 资源: 4 CPU, 8GB RAM（LLM 调用为主，IO 次之）
    - 扩容触发: Kafka lag > 50
    """

    COMPONENT_NAME = "file_summary"

    def __init__(
        self,
        *args,
        file_summary_service: Optional[FileSummaryService] = None,
        **kwargs,
    ):
        """
        初始化 FileSummary Worker

        Args:
            file_summary_service: FileSummaryService 实例（可选，懒加载）
        """
        super().__init__(*args, **kwargs)
        self._summary_service = file_summary_service
        self._config_manager = get_component_config_manager()

    # ========== 抽象方法实现 ==========

    def get_original_topic(self) -> str:
        return KafkaTopics.SECTION_SUMMARY_END

    def _get_failure_stage(self) -> str:
        # 后台阶段，仅用于日志标识；_fail_file_progress 已覆盖为空实现
        return IndexStage.FILE_SUMMARY_END

    # ========== 失败隔离：后台阶段不污染前台进度 ==========

    async def _fail_file_progress(
        self, file_id: str, stage: str, error_message: str
    ) -> None:
        """覆盖基类行为：后台阶段失败不写 Redis 进度，仅记录日志。"""
        logger.warning(
            f"FileSummary 后台阶段失败（不污染前台进度）: "
            f"file_id={file_id}, stage={stage}, error={error_message}"
        )

    # ========== 懒加载依赖 ==========

    def _get_summary_service(self) -> FileSummaryService:
        if self._summary_service is None:
            self._summary_service = FileSummaryService()
            logger.info("FileSummaryService 已创建")
        return self._summary_service

    # ========== 主流程 ==========

    async def process_message_impl(self, message: SectionSummaryEndMessage) -> bool:
        """
        处理 section 摘要完成消息，生成文件级摘要并分发下游。

        Args:
            message: SectionSummaryEndMessage

        Returns:
            bool: 是否处理成功
        """
        logger.info(
            f"开始文件摘要抽取: user_id={message.user_id}, "
            f"file_id={message.file_id}, document_id={message.document_id}, "
            f"sections={message.total_sections}"
        )

        # 1. 组件开关守卫：禁用时空跑（消费但不落库，避免 lag 堆积）
        if not self._config_manager.is_component_enabled(self.COMPONENT_NAME):
            logger.info(
                f"FileSummary 组件已禁用，跳过处理: file_id={message.file_id}"
            )
            return True

        # 2. 校验溯源字段
        document_id = message.document_id
        if not document_id:
            logger.error(
                f"FileSummary: SectionSummaryEndMessage 缺少 document_id，跳过: "
                f"file_id={message.file_id}"
            )
            return True

        try:
            summary_service = self._get_summary_service()

            # 3. 调用 Service 生成文件级摘要
            #    输入完全来自 SectionSummaryEndMessage 的 section_summaries_payload，
            #    不读数据库——避免 section_summary 写库异步导致的竞态。
            result: FileSummaryResult = await summary_service.summarize_document(
                document_id=document_id,
                section_summaries_payload=message.section_summaries_payload,
                document_title=message.document_title,
                language=message.language,
                knowledge_base_id=message.knowledge_base_id,
                knowledge_base_name=message.knowledge_base_name,
            )

            if not result.is_success():
                logger.warning(
                    f"FileSummary: 文档无文件摘要产出（可能无 section 摘要或 LLM 失败）: "
                    f"file_id={message.file_id}, document_id={document_id}"
                )
                # 无摘要产出仍需通知下游：TextAnalyzer 没有 file_summary 锚点也能跑
                # （QA 抽取以 section 正文为主，file_summary 仅作主题约束）。
                await self._send_summary_end_message(message, result)
                return True

            # 4. 分发到 db_write.*
            await self._send_mysql_messages(message, result)
            await self._send_mongodb_messages(message, result)
            await self._send_embedding_messages(message, result)

            # 5. 发送 SummaryEndMessage（触发下游 KGExtractor / TextAnalyzer）
            await self._send_summary_end_message(message, result)

            logger.info(
                f"文件摘要处理完成: file_id={message.file_id}, "
                f"document_id={document_id}, "
                f"document_type={result.item.document_type if result.item else None}"
            )
            return True

        except Exception as e:
            logger.error(
                f"文件摘要处理失败: file_id={message.file_id}, error={e}",
                exc_info=True,
            )
            return False

    # ========== 下游消息发送 ==========

    async def _send_mysql_messages(
        self,
        message: SectionSummaryEndMessage,
        result: FileSummaryResult,
    ) -> None:
        """发送 MySQL document_summary 表写入消息。"""
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 MySQL 消息")
            return

        mysql_data = result.get_mysql_data()
        records = mysql_data.get("document_summary", [])
        if not records:
            return

        meta_msgs: List[MetaWriteMessage] = []
        for record in records:
            record_id = record.get("document_id") or message.file_id
            meta_msgs.append(MetaWriteMessage(
                user_id=message.user_id,
                file_id=message.file_id,
                table_name=MySQLTable.DOCUMENT_SUMMARY,
                record_data=record,
                operation=WriteOperation.UPSERT,
                record_id=record_id,
            ))

        if meta_msgs:
            await self._producer.send_messages(
                topic=KafkaTopics.DB_WRITE_META,
                messages=meta_msgs,
            )
        logger.debug(
            f"FileSummary MySQL 消息发送完成: {len(meta_msgs)} 条 (document_summary)"
        )

    async def _send_mongodb_messages(
        self,
        message: SectionSummaryEndMessage,
        result: FileSummaryResult,
    ) -> None:
        """发送 MongoDB document_data.summary 局部更新消息。"""
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 MongoDB 消息")
            return

        mongo_data = result.get_mongodb_data()
        documents = mongo_data.get("document_data", [])
        if not documents:
            return

        mongo_msgs: List[MongoWriteMessage] = []
        for doc in documents:
            document_id = doc.get("_id", message.document_id or message.file_id)
            mongo_msgs.append(MongoWriteMessage(
                user_id=message.user_id,
                file_id=message.file_id,
                collection_name=MongoCollection.DOCUMENT_DATA,
                document_data=doc,
                operation=WriteOperation.UPSERT,
                document_id=str(document_id),
            ))

        if mongo_msgs:
            await self._producer.send_messages(
                topic=KafkaTopics.DB_WRITE_MONGO,
                messages=mongo_msgs,
            )
        logger.debug(
            f"FileSummary MongoDB 消息发送完成: {len(mongo_msgs)} 条 (document_data.summary)"
        )

    async def _send_embedding_messages(
        self,
        message: SectionSummaryEndMessage,
        result: FileSummaryResult,
    ) -> None:
        """发送 Milvus file_summary_store 向量化消息（role=document_summary）。"""
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 Embedding 消息")
            return

        items = result.get_embedding_messages()
        if not items:
            return

        emb_msg = EmbeddingWriteMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            collection_type=MilvusCollection.FILE_SUMMARY,
            items=items,
            source_stage="file_summary",
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
            f"FileSummary Embedding 消息发送完成: {len(items)} 条 (file_summary_store)"
        )

    async def _send_summary_end_message(
        self,
        message: SectionSummaryEndMessage,
        result: FileSummaryResult,
    ) -> None:
        """发送 SummaryEndMessage，触发下游 KGExtractor / TextAnalyzer。"""
        if not self._producer:
            logger.warning("Producer 未配置，无法发送 SummaryEndMessage")
            return

        item = result.item
        summary_end_msg = SummaryEndMessage(
            user_id=message.user_id,
            file_id=message.file_id,
            file_summary=item.summary_text if item else "",
            keywords=item.keywords if item else [],
            topics=item.topics if item else [],
            summary_quality=1.0,  # 默认值（本次不产出 quality）
            llm_model=result.llm_model,
            token_usage=result.token_usage,
            document_type=item.document_type if item else None,
            difficulty_level=None,  # 默认值（本次不产出 difficulty）
            # 溯源字段透传，供下游 TextAnalyzer 读 DB + 写库带知识库归属
            document_id=message.document_id,
            knowledge_base_id=message.knowledge_base_id,
            knowledge_base_name=message.knowledge_base_name,
            language=message.language,
        )

        await self._producer.send_message(
            topic=KafkaTopics.FILE_SUMMARY_END,
            message=summary_end_msg,
        )
        logger.info(
            f"发送 SummaryEndMessage: file_id={message.file_id}, "
            f"success={result.is_success()}"
        )
