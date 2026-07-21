#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : start_all_workers.py
@Author  : caixiongjiang
@Date    : 2026/02/05
@Function: 
    统一启动所有 Kafka Workers
    
    功能:
    - 支持启动所有 Workers 或指定的 Workers
    - 并发管理多个 Worker 实例
    - 统一的日志和错误处理
    - 优雅的关闭机制
    
    用法:
        # 启动所有 Workers
        uv run python scripts/start_all_workers.py
        
        # 启动指定的 Workers（用逗号分隔）
        uv run python scripts/start_all_workers.py --workers file_parser,text_splitter
        
        # 查看可用的 Workers
        uv run python scripts/start_all_workers.py --list
    
    Worker 列表（第一层：任务流转）:
    1. file_parser      - 文件解析 (knowledge_base.index.start → knowledge_base.parse.end)
    2. text_splitter    - 文本分割 (knowledge_base.parse.end → knowledge_base.split.end)
    3. section_summary  - Section 摘要 (knowledge_base.split.end → knowledge_base.section_summary.end)
    4. file_summary     - 文件摘要 (knowledge_base.section_summary.end → knowledge_base.file_summary.end)
    5. kg_extractor     - 知识图谱抽取 (knowledge_base.file_summary.end → knowledge_base.graph.end)  [mock]
    6. text_analyzer    - 文本分析 / Atomic QA (knowledge_base.file_summary.end → analyze.end + db_write.*)  [v1.1]

    Writer 列表（第二层：数据库写入）:
    7. embedding_milvus_writer - 向量写入 (db_write.embedding.start → Milvus)
    8. neo4j_writer     - 图谱写入 (db_write.graph.start → Neo4j)
    9. mysql_writer     - 元数据写入 (db_write.meta.start → MySQL)
    10. mongo_writer    - 文档写入 (db_write.mongo.start → MongoDB)

    注: image_understand 已从后台 pipeline 移除，图片理解改为 agent 需要时临时调用
        （见 src/service/chat/image_chunk_reader_service.py）。
    
    前置条件:
    - Kafka: 192.168.201.14:9092
    - MinIO: 192.168.201.14:9000 (file_parser 需要)
    - MinerU: http://192.168.201.14:18000 (file_parser 需要)
    - LLM API: 配置在 config/config.toml (summary, kg, image, analyzer 需要)
        
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
from dataclasses import dataclass

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.kafka import get_kafka_manager
from src.db.kafka.producer import KafkaProducer
from src.db.kafka.topics import KafkaTopics
from src.db.kafka.types import ConsumerGroup
from src.types.messages.index import IndexStartMessage, ParseEndMessage, SplitEndMessage
from src.types.messages.extract import (
    SummaryEndMessage,
    GraphEndMessage,
    SectionSummaryEndMessage,
)
from src.types.messages.db_write import (
    EmbeddingWriteMessage, GraphWriteMessage, MetaWriteMessage, MongoWriteMessage,
    MongoCollection, MySQLTable, MilvusCollection,
)
from src.utils.config_manager import get_config


# Writer 名称 → (batch_size 配置路径, flush_interval_ms 配置路径, 代码默认值)
# 配置来源统一为 config.toml [kafka.batch]，components.json 中的同名字段仅作历史保留、不再生效
_WRITER_BATCH_CONFIG_PATHS: Dict[str, tuple] = {
    "mysql_writer": (
        "kafka.batch.mysql_batch_size",
        "kafka.batch.mysql_flush_interval_ms",
        200,
        1000,
    ),
    "mongo_writer": (
        "kafka.batch.mongo_batch_size",
        "kafka.batch.mongo_flush_interval_ms",
        100,
        500,
    ),
    "neo4j_writer": (
        "kafka.batch.neo4j_batch_size",
        "kafka.batch.neo4j_flush_interval_ms",
        500,
        2000,
    ),
    "embedding_milvus_writer": (
        "kafka.batch.embedding_batch_size",
        "kafka.batch.embedding_flush_interval_ms",
        100,
        500,
    ),
}


def _resolve_writer_batch_kwargs(worker_name: str) -> Dict[str, int]:
    """从 config.toml [kafka.batch] 解析 Writer 的 batch_size / flush_interval_ms。

    缺失时回退到代码默认值（与 _WRITER_BATCH_CONFIG_PATHS 中的兜底一致），
    保证「文档说一套、代码跑一套」不再发生。
    """
    entry = _WRITER_BATCH_CONFIG_PATHS.get(worker_name)
    if entry is None:
        return {}
    bs_path, fi_path, default_bs, default_fi = entry
    return {
        "batch_size": int(get_config(bs_path, default_bs)),
        "flush_interval_ms": int(get_config(fi_path, default_fi)),
    }


@dataclass
class WorkerConfig:
    """Worker 配置"""
    name: str
    class_name: str
    module_path: str
    input_topic: str
    output_topics: List[str]
    message_class: type
    group_id: str
    description: str


# ==================== Worker 配置定义 ====================

WORKER_CONFIGS: Dict[str, WorkerConfig] = {
    # ==================== 第一层：Pipeline Workers ====================
    # 每个 Worker 独立 Group，保证独立消费和扩缩容
    
    "file_parser": WorkerConfig(
        name="file_parser",
        class_name="FileParserWorker",
        module_path="src.db.kafka.workers.file_parser_worker",
        input_topic=KafkaTopics.INDEX_START,
        output_topics=[KafkaTopics.PARSE_END, KafkaTopics.DB_WRITE_META, KafkaTopics.DB_WRITE_MONGO],
        message_class=IndexStartMessage,
        group_id=ConsumerGroup.FILE_PARSER,
        description="文件解析 Worker (解析 PDF/Word/Excel/PPT 等)"
    ),
    "text_splitter": WorkerConfig(
        name="text_splitter",
        class_name="TextSplitterWorker",
        module_path="src.db.kafka.workers.text_splitter_worker",
        input_topic=KafkaTopics.PARSE_END,
        output_topics=[KafkaTopics.SPLIT_END, KafkaTopics.DB_WRITE_EMBEDDING, KafkaTopics.DB_WRITE_MONGO],
        message_class=ParseEndMessage,
        group_id=ConsumerGroup.TEXT_SPLITTER,
        description="文本分割 Worker (递归分割、语言检测、生成 Chunk)"
    ),
    "section_summary": WorkerConfig(
        name="section_summary",
        class_name="SectionSummaryWorker",
        module_path="src.db.kafka.workers.section_summary_worker",
        input_topic=KafkaTopics.SPLIT_END,
        output_topics=[
            KafkaTopics.SECTION_SUMMARY_END,
            KafkaTopics.DB_WRITE_META,
            KafkaTopics.DB_WRITE_MONGO,
            KafkaTopics.DB_WRITE_EMBEDDING,
        ],
        message_class=SplitEndMessage,
        group_id=ConsumerGroup.SECTION_SUMMARY,
        description="Section 摘要 Worker (基于 section 下 chunk 生成 section 级摘要)"
    ),
    "file_summary": WorkerConfig(
        name="file_summary",
        class_name="FileSummaryWorker",
        module_path="src.db.kafka.workers.file_summary_worker",
        input_topic=KafkaTopics.SECTION_SUMMARY_END,
        output_topics=[KafkaTopics.FILE_SUMMARY_END, KafkaTopics.DB_WRITE_META, KafkaTopics.DB_WRITE_MONGO, KafkaTopics.DB_WRITE_EMBEDDING],
        message_class=SectionSummaryEndMessage,
        group_id=ConsumerGroup.FILE_SUMMARY,
        description="文件摘要 Worker (基于 section 摘要汇总生成 file 级摘要 + keywords/topics/document_type)"
    ),
    # ⚠️ KGExtractor 尚为 mock 实现，默认启动不包含（见 --workers 参数）。
    # TextAnalyzer v1.1 已落地，默认不启动（后台并行阶段），在 --workers 列表加入即可接通。
    "kg_extractor": WorkerConfig(
        name="kg_extractor",
        class_name="KGExtractorWorker",
        module_path="src.db.kafka.workers.kg_extractor_worker",
        input_topic=KafkaTopics.FILE_SUMMARY_END,
        output_topics=[KafkaTopics.GRAPH_END, KafkaTopics.DB_WRITE_GRAPH],
        message_class=SummaryEndMessage,
        group_id=ConsumerGroup.KG_EXTRACTOR,
        description="[mock] 知识图谱抽取 Worker (抽取实体关系、事件)"
    ),
    "text_analyzer": WorkerConfig(
        name="text_analyzer",
        class_name="TextAnalyzerWorker",
        module_path="src.db.kafka.workers.text_analyzer_worker",
        input_topic=KafkaTopics.FILE_SUMMARY_END,
        output_topics=[
            KafkaTopics.DB_WRITE_EMBEDDING,
            KafkaTopics.DB_WRITE_MONGO,
            KafkaTopics.DB_WRITE_META,
            KafkaTopics.ANALYZE_END,
        ],
        message_class=SummaryEndMessage,
        group_id=ConsumerGroup.TEXT_ANALYZER,
        description="文本分析 Worker (v1.1 section 级 atomic_qa 抽取，与 KGExtractor 并行消费 file_summary.end)"
    ),
    
    # ==================== 第二层：DB Writers ====================
    # 4 个 Writer 共享 DB_WRITER Group（各自消费不同 Topic，互不干扰）
    
    "embedding_milvus_writer": WorkerConfig(
        name="embedding_milvus_writer",
        class_name="EmbeddingMilvusWriter",
        module_path="src.db.kafka.writers.embedding_milvus_writer",
        input_topic=KafkaTopics.DB_WRITE_EMBEDDING,
        output_topics=[],
        message_class=EmbeddingWriteMessage,
        group_id=ConsumerGroup.DB_WRITER,
        description="向量写入 Writer (批量 Embedding + 批量写入 Milvus)"
    ),
    "neo4j_writer": WorkerConfig(
        name="neo4j_writer",
        class_name="Neo4jWriter",
        module_path="src.db.kafka.writers.neo4j_writer",
        input_topic=KafkaTopics.DB_WRITE_GRAPH,
        output_topics=[],
        message_class=GraphWriteMessage,
        group_id=ConsumerGroup.DB_WRITER,
        description="图谱写入 Writer (批量写入 Neo4j)"
    ),
    "mysql_writer": WorkerConfig(
        name="mysql_writer",
        class_name="MySQLWriter",
        module_path="src.db.kafka.writers.mysql_writer",
        input_topic=KafkaTopics.DB_WRITE_META,
        output_topics=[],
        message_class=MetaWriteMessage,
        group_id=ConsumerGroup.DB_WRITER,
        description="元数据写入 Writer (批量写入 MySQL)"
    ),
    "mongo_writer": WorkerConfig(
        name="mongo_writer",
        class_name="MongoWriter",
        module_path="src.db.kafka.writers.mongo_writer",
        input_topic=KafkaTopics.DB_WRITE_MONGO,
        output_topics=[],
        message_class=MongoWriteMessage,
        group_id=ConsumerGroup.DB_WRITER,
        description="文档写入 Writer (批量写入 MongoDB)"
    ),
}


# ==================== Worker 启动器 ====================

class WorkerManager:
    """Worker 管理器"""
    
    def __init__(self):
        self.kafka_manager = None
        self.producer = None
        self.mysql_manager = None
        self.mongo_manager = None
        self.milvus_manager = None
        self.redis_manager = None
        self.progress_manager = None
        self._embedding_client = None
        self._sparse_embedding_client = None
        self.workers: Dict[str, object] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        
    async def initialize(self):
        """初始化所有基础设施连接（Kafka + MySQL + MongoDB + Milvus）"""
        logger.info("=" * 80)
        logger.info("正在初始化基础设施连接...")
        logger.info("=" * 80)
        
        # 1. Kafka
        self.kafka_manager = get_kafka_manager()
        await self.kafka_manager.connect()
        aiokafka_producer = await self.kafka_manager.get_producer()
        self.producer = KafkaProducer(aiokafka_producer)
        logger.success("Kafka 连接成功（Producer 已创建）")
        
        # 2. MySQL
        from src.db.mysql.connection.factory import get_mysql_manager
        self.mysql_manager = get_mysql_manager()
        self.mysql_manager.init_db()
        logger.success("MySQL 连接成功（自动建表）")
        
        # 3. MongoDB + Beanie ODM
        from src.db.mongodb.mongodb_manager import get_mongodb_manager
        self.mongo_manager = await get_mongodb_manager()
        logger.success("MongoDB 连接成功（Beanie ODM 已初始化）")
        
        # 4. Redis + FileProgressManager
        from src.db.redis.connection.factory import get_redis_manager
        from src.states.state_manager import FileProgressManager
        self.redis_manager = await get_redis_manager()
        self.progress_manager = FileProgressManager(self.redis_manager)
        logger.success("Redis 连接成功（FileProgressManager 已创建）")
        
        # 5. Milvus
        import os
        os.environ.setdefault("MILVUS_AUTO_CREATE_COLLECTION", "true")
        from src.db.milvus import get_milvus_manager
        self.milvus_manager = get_milvus_manager()
        logger.success("Milvus 连接成功")
        
        logger.info("=" * 80 + "\n")
    
    async def start_worker(self, worker_name: str) -> bool:
        """
        启动指定的 Worker
        
        Args:
            worker_name: Worker 名称
            
        Returns:
            是否启动成功
        """
        if worker_name not in WORKER_CONFIGS:
            logger.error(f"❌ 未知的 Worker: {worker_name}")
            return False
        
        config = WORKER_CONFIGS[worker_name]
        
        try:
            logger.info(f"正在启动 Worker: {config.name}")
            logger.info(f"  描述: {config.description}")
            logger.info(f"  输入: {config.input_topic}")
            logger.info(f"  输出: {', '.join(config.output_topics)}")
            
            # 动态导入 Worker 类
            module = __import__(config.module_path, fromlist=[config.class_name])
            worker_class = getattr(module, config.class_name)
            
            # 创建 Consumer
            aiokafka_consumer = await self.kafka_manager.get_consumer(
                group_id=config.group_id,
                topics=[config.input_topic]
            )
            
            # 创建 Worker 实例
            worker_kwargs: Dict[str, object] = {
                "aiokafka_consumer": aiokafka_consumer,
                "message_class": config.message_class,
                "producer": self.producer,
            }
            # Pipeline Worker 注入进度管理器，DB Writer 不需要
            if self.progress_manager and config.group_id != ConsumerGroup.DB_WRITER:
                worker_kwargs["progress_manager"] = self.progress_manager

            # DB Writer 注入批处理参数（来自 config.toml [kafka.batch]）
            if config.group_id == ConsumerGroup.DB_WRITER:
                worker_kwargs.update(_resolve_writer_batch_kwargs(worker_name))
                logger.info(
                    f"  批处理参数: batch_size={worker_kwargs.get('batch_size')}, "
                    f"flush_interval_ms={worker_kwargs.get('flush_interval_ms')}"
                )

            worker = worker_class(**worker_kwargs)
            
            # Writer 类型需要注册 Repository 和客户端
            self._register_writer_repositories(worker_name, worker)
            if worker_name == "embedding_milvus_writer":
                if self._embedding_client:
                    await self._embedding_client.__aenter__()
                    logger.info("稠密向量 Embedding 异步连接池已创建")
                if self._sparse_embedding_client:
                    await self._sparse_embedding_client.__aenter__()
                    logger.info("稀疏向量 Embedding (BGE-M3) 异步连接池已创建")
            
            self.workers[worker_name] = worker
            
            # 启动 Worker（异步任务）
            task = asyncio.create_task(
                worker.start(),
                name=f"worker_{worker_name}"
            )
            self.tasks[worker_name] = task
            
            logger.success(f"✓ Worker 启动成功: {config.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Worker 启动失败: {config.name}")
            logger.exception(f"错误详情: {e}")
            return False
    
    def _register_writer_repositories(self, worker_name: str, worker: object) -> None:
        """
        为 Writer 注册对应的 Repository 实例
        
        数据库连接已在 initialize() 中统一建立，这里只注册路由映射。
        
        Args:
            worker_name: Worker 名称
            worker: Worker 实例
        """
        if worker_name == "mongo_writer":
            from src.db.mongodb.repositories import (
                element_data_repository,
                chunk_data_repository,
                section_data_repository,
                document_data_repository,
            )
            worker.register_repositories({
                MongoCollection.ELEMENT_DATA: element_data_repository,
                MongoCollection.CHUNK_DATA: chunk_data_repository,
                MongoCollection.SECTION_DATA: section_data_repository,
                MongoCollection.DOCUMENT_DATA: document_data_repository,
            })
        elif worker_name == "mysql_writer":
            from src.db.mysql.repositories.base import (
                element_meta_info_repo,
                chunk_meta_info_repo,
                section_meta_info_repo,
                chunk_section_document_repo,
                section_document_repo,
            )
            from src.db.mysql.repositories.extract import section_summary_repo, document_summary_repo, section_atomic_qa_repo
            worker._session_factory = self.mysql_manager.SessionLocal
            worker.register_repositories({
                MySQLTable.ELEMENT_META_INFO: element_meta_info_repo,
                MySQLTable.CHUNK_META_INFO: chunk_meta_info_repo,
                MySQLTable.SECTION_META_INFO: section_meta_info_repo,
                MySQLTable.CHUNK_SECTION_DOCUMENT: chunk_section_document_repo,
                MySQLTable.SECTION_DOCUMENT: section_document_repo,
                MySQLTable.SECTION_SUMMARY: section_summary_repo,
                MySQLTable.DOCUMENT_SUMMARY: document_summary_repo,
                MySQLTable.SECTION_ATOMIC_QA: section_atomic_qa_repo,
            })
        elif worker_name == "embedding_milvus_writer":
            from src.client.embedding import create_embedding_client, create_sparse_embedding_client
            from src.db.milvus.repositories import (
                ChunkRepository,
                SectionRepository,
                EnhancedChunkRepository,
                FileSummaryRepository,
                SectionSummaryRepository,
                AtomicQARepository,
                SPORepository,
                TagRepository,
            )
            self._embedding_client = create_embedding_client()
            self._sparse_embedding_client = create_sparse_embedding_client()
            worker._embedding_client = self._embedding_client
            worker._sparse_embedding_client = self._sparse_embedding_client
            milvus_repo_map = {
                MilvusCollection.CHUNK: ChunkRepository,
                MilvusCollection.SECTION: SectionRepository,
                MilvusCollection.ENHANCED_CHUNK: EnhancedChunkRepository,
                MilvusCollection.FILE_SUMMARY: FileSummaryRepository,
                MilvusCollection.SECTION_SUMMARY: SectionSummaryRepository,
                MilvusCollection.ATOMIC_QA: AtomicQARepository,
                MilvusCollection.SPO: SPORepository,
                MilvusCollection.TAG: TagRepository,
            }
            for collection_type, repo_class in milvus_repo_map.items():
                try:
                    worker.register_repository(collection_type, repo_class())
                except RuntimeError:
                    logger.warning(
                        f"跳过 Milvus Collection {collection_type}: 集合不存在，"
                        f"后续写入该 Collection 的消息将失败"
                    )
    
    async def start_workers(self, worker_names: List[str]):
        """
        启动多个 Workers
        
        Args:
            worker_names: Worker 名称列表
        """
        logger.info("=" * 80)
        logger.info(f"📋 准备启动 {len(worker_names)} 个 Workers")
        logger.info("=" * 80)
        
        for name in worker_names:
            await self.start_worker(name)
            await asyncio.sleep(0.5)  # 间隔启动，避免资源竞争
        
        logger.info("=" * 80)
        logger.success(f"🎉 所有 Workers 已启动 ({len(self.workers)}/{len(worker_names)})")
        logger.info("=" * 80)
        logger.info("提示:")
        logger.info("  - 按 Ctrl+C 停止所有 Workers")
        logger.info("  - Workers 会持续运行直到手动停止")
        logger.info("=" * 80 + "\n")
    
    async def wait_all(self):
        """等待所有 Worker 任务完成"""
        if not self.tasks:
            return
        
        try:
            # 等待所有任务完成（或被中断）
            await asyncio.gather(*self.tasks.values())
        except asyncio.CancelledError:
            logger.warning("⚠️  收到停止信号，正在关闭所有 Workers...")
    
    async def cleanup(self):
        """清理所有资源（Workers + 数据库连接）"""
        logger.info("=" * 80)
        logger.info("正在清理资源...")
        logger.info("=" * 80)
        
        # 1. 取消所有 Worker 任务
        for name, task in self.tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.info(f"Worker 任务已取消: {name}")
        
        # 2. 清理所有 Workers 内部资源
        for name, worker in self.workers.items():
            try:
                await worker.cleanup()
                logger.info(f"Worker 资源已清理: {name}")
            except Exception as e:
                logger.warning(f"Worker 清理失败 ({name}): {e}")
        
        # 3. 关闭基础设施连接
        if self.kafka_manager:
            try:
                await self.kafka_manager.disconnect()
                logger.info("Kafka 连接已关闭")
            except Exception as e:
                logger.warning(f"Kafka 关闭失败: {e}")
        
        if self.mysql_manager:
            try:
                self.mysql_manager.close()
                logger.info("MySQL 连接已关闭")
            except Exception as e:
                logger.warning(f"MySQL 关闭失败: {e}")
        
        if self.mongo_manager:
            try:
                await self.mongo_manager.disconnect()
                logger.info("MongoDB 连接已关闭")
            except Exception as e:
                logger.warning(f"MongoDB 关闭失败: {e}")
        
        if self.redis_manager:
            try:
                await self.redis_manager.disconnect()
                logger.info("Redis 连接已关闭")
            except Exception as e:
                logger.warning(f"Redis 关闭失败: {e}")
        
        if self._embedding_client:
            try:
                await self._embedding_client.__aexit__(None, None, None)
                logger.info("稠密向量 Embedding 连接池已关闭")
            except Exception as e:
                logger.warning(f"稠密向量 Embedding 关闭失败: {e}")
        
        if self._sparse_embedding_client:
            try:
                await self._sparse_embedding_client.__aexit__(None, None, None)
                logger.info("稀疏向量 Embedding (BGE-M3) 连接池已关闭")
            except Exception as e:
                logger.warning(f"稀疏向量 Embedding 关闭失败: {e}")
        
        if self.milvus_manager:
            try:
                self.milvus_manager.disconnect()
                logger.info("Milvus 连接已关闭")
            except Exception as e:
                logger.warning(f"Milvus 关闭失败: {e}")
        
        logger.info("=" * 80)
        logger.info("所有资源已释放")
        logger.info("=" * 80)


# ==================== 辅助函数 ====================

def print_worker_list():
    """打印所有可用的 Workers"""
    print("\n" + "=" * 80)
    print("可用的 Workers:")
    print("=" * 80)
    
    # 第一层：Pipeline Workers（每个独立 Group）
    print("\n【第一层：Pipeline Workers】（每个 Worker 独立 Group）")
    # 默认已实现：file_parser / text_splitter / section_summary / file_summary
    for name in ["file_parser", "text_splitter", "section_summary", "file_summary"]:
        if name in WORKER_CONFIGS:
            config = WORKER_CONFIGS[name]
            print(f"    {name:25} - {config.description}  [{config.group_id}]")
    # 后台并行阶段：text_analyzer (v1.1 已落地) / kg_extractor (mock)，默认不启动
    for name in ["text_analyzer", "kg_extractor"]:
        if name in WORKER_CONFIGS:
            config = WORKER_CONFIGS[name]
            print(f"    {name:25} - {config.description}  [{config.group_id}]  [默认不启动]")
    
    # 第二层：DB Writers（共享 Group）
    print(f"\n【第二层：DB Writers】（共享 {ConsumerGroup.DB_WRITER}）")
    for name in ["embedding_milvus_writer", "neo4j_writer", "mysql_writer", "mongo_writer"]:
        if name in WORKER_CONFIGS:
            config = WORKER_CONFIGS[name]
            print(f"    {name:25} - {config.description}")
    
    print("\n" + "=" * 80)
    print("用法:")
    print("  启动所有 Workers:        uv run python scripts/start_all_workers.py")
    print("  启动所有 Pipeline Workers: uv run python scripts/start_all_workers.py --workers file_parser,text_splitter,section_summary,file_summary")
    print("  (后台并行: text_analyzer v1.1 已落地 / kg_extractor mock，在 --workers 列表追加即可接通)")
    print("  启动所有 DB Writers:     uv run python scripts/start_all_workers.py --workers embedding_milvus_writer,neo4j_writer,mysql_writer,mongo_writer")
    print("  启动指定 Workers:        uv run python scripts/start_all_workers.py --workers file_parser,text_splitter")
    print("  查看可用 Workers:        uv run python scripts/start_all_workers.py --list")
    print("=" * 80 + "\n")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="统一启动所有 Kafka Workers",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--workers",
        type=str,
        help="指定要启动的 Workers（用逗号分隔），例如: file_parser,text_splitter"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用的 Workers"
    )
    
    return parser.parse_args()


# ==================== 主函数 ====================

async def main():
    """主函数"""
    args = parse_arguments()
    
    # 如果只是列出 Workers
    if args.list:
        print_worker_list()
        return
    
    # 确定要启动的 Workers
    if args.workers:
        worker_names = [name.strip() for name in args.workers.split(",")]
        # 验证 Worker 名称
        invalid_names = [name for name in worker_names if name not in WORKER_CONFIGS]
        if invalid_names:
            logger.error(f"❌ 无效的 Worker 名称: {', '.join(invalid_names)}")
            print_worker_list()
            return
    else:
        # 默认启动所有 Workers
        worker_names = list(WORKER_CONFIGS.keys())
    
    # 打印启动信息
    logger.info("=" * 80)
    logger.info("🚀 Kafka Workers 统一启动程序")
    logger.info("=" * 80)
    logger.info(f"准备启动 {len(worker_names)} 个 Workers:")
    for name in worker_names:
        config = WORKER_CONFIGS[name]
        logger.info(f"  - {name:20} ({config.description})")
    logger.info("=" * 80 + "\n")
    
    manager = WorkerManager()
    
    try:
        # 初始化
        await manager.initialize()
        
        # 启动 Workers
        await manager.start_workers(worker_names)
        
        # 等待所有 Workers（直到 Ctrl+C）
        await manager.wait_all()
        
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 80)
        logger.warning("⚠️  收到停止信号 (Ctrl+C)，正在关闭所有 Workers...")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ 程序运行失败: {e}")
        logger.error("=" * 80)
        logger.exception("详细错误信息:")
        
    finally:
        await manager.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        sys.exit(1)
