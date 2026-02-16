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
    3. file_summary     - 文件摘要 (knowledge_base.split.end → knowledge_base.summary.end)
    4. kg_extractor     - 知识图谱抽取 (knowledge_base.summary.end → knowledge_base.graph.end)
    5. image_understand - 图片理解 (knowledge_base.summary.end → knowledge_base.image.end)
    6. text_analyzer    - 文本分析 (knowledge_base.image.end → 完成)
    
    Writer 列表（第二层：数据库写入）:
    7. embedding_milvus_writer - 向量写入 (db_write.embedding.start → Milvus)
    8. neo4j_writer     - 图谱写入 (db_write.graph.start → Neo4j)
    9. mysql_writer     - 元数据写入 (db_write.meta.start → MySQL)
    10. mongo_writer    - 文档写入 (db_write.mongo.start → MongoDB)
    
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
from src.types.messages.extract import SummaryEndMessage, GraphEndMessage, ImageEndMessage
from src.types.messages.db_write import EmbeddingWriteMessage, GraphWriteMessage, MetaWriteMessage, MongoWriteMessage


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
    "file_summary": WorkerConfig(
        name="file_summary",
        class_name="FileSummaryWorker",
        module_path="src.db.kafka.workers.file_summary_worker",
        input_topic=KafkaTopics.SPLIT_END,
        output_topics=[KafkaTopics.SUMMARY_END],
        message_class=SplitEndMessage,
        group_id=ConsumerGroup.FILE_SUMMARY,
        description="文件摘要 Worker (生成文件级摘要)"
    ),
    "kg_extractor": WorkerConfig(
        name="kg_extractor",
        class_name="KGExtractorWorker",
        module_path="src.db.kafka.workers.kg_extractor_worker",
        input_topic=KafkaTopics.SUMMARY_END,
        output_topics=[KafkaTopics.GRAPH_END, KafkaTopics.DB_WRITE_GRAPH],
        message_class=SummaryEndMessage,
        group_id=ConsumerGroup.KG_EXTRACTOR,
        description="知识图谱抽取 Worker (抽取实体关系、事件)"
    ),
    "image_understand": WorkerConfig(
        name="image_understand",
        class_name="ImageUnderstandWorker",
        module_path="src.db.kafka.workers.image_understand_worker",
        input_topic=KafkaTopics.SUMMARY_END,
        output_topics=[KafkaTopics.IMAGE_END, KafkaTopics.DB_WRITE_EMBEDDING],
        message_class=SummaryEndMessage,
        group_id=ConsumerGroup.IMAGE_UNDERSTAND,
        description="图片理解 Worker (VLM 生成图片描述)"
    ),
    "text_analyzer": WorkerConfig(
        name="text_analyzer",
        class_name="TextAnalyzerWorker",
        module_path="src.db.kafka.workers.text_analyzer_worker",
        input_topic=KafkaTopics.IMAGE_END,
        output_topics=[KafkaTopics.DB_WRITE_EMBEDDING],
        message_class=ImageEndMessage,
        group_id=ConsumerGroup.TEXT_ANALYZER,
        description="文本分析 Worker (生成 summary 和 atomic_qa)"
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
        self.workers: Dict[str, object] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        
    async def initialize(self):
        """初始化 Kafka 连接"""
        logger.info("=" * 80)
        logger.info("🚀 正在初始化 Kafka 连接...")
        logger.info("=" * 80)
        
        # 获取 Kafka Manager 并连接
        self.kafka_manager = get_kafka_manager()
        await self.kafka_manager.connect()
        logger.success("✓ Kafka 连接成功")
        
        # 创建 Producer
        aiokafka_producer = await self.kafka_manager.get_producer()
        self.producer = KafkaProducer(aiokafka_producer)
        logger.success("✓ Kafka Producer 创建成功")
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
            worker = worker_class(
                aiokafka_consumer=aiokafka_consumer,
                message_class=config.message_class,
                producer=self.producer
            )
            
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
        """清理所有资源"""
        logger.info("=" * 80)
        logger.info("正在清理资源...")
        logger.info("=" * 80)
        
        # 取消所有任务
        for name, task in self.tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.info(f"✓ Worker 任务已取消: {name}")
        
        # 清理所有 Workers
        for name, worker in self.workers.items():
            try:
                await worker.cleanup()
                logger.success(f"✓ Worker 资源已清理: {name}")
            except Exception as e:
                logger.warning(f"⚠ Worker 清理失败 ({name}): {e}")
        
        # 关闭 Kafka 连接
        if self.kafka_manager:
            try:
                await self.kafka_manager.disconnect()
                logger.success("✓ Kafka 连接已关闭")
            except Exception as e:
                logger.warning(f"⚠ Kafka 关闭失败: {e}")
        
        logger.info("=" * 80)
        logger.info("所有 Workers 已停止")
        logger.info("=" * 80)


# ==================== 辅助函数 ====================

def print_worker_list():
    """打印所有可用的 Workers"""
    print("\n" + "=" * 80)
    print("可用的 Workers:")
    print("=" * 80)
    
    # 第一层：Pipeline Workers（每个独立 Group）
    print("\n【第一层：Pipeline Workers】（每个 Worker 独立 Group）")
    for name in ["file_parser", "text_splitter", "file_summary", "kg_extractor", "image_understand", "text_analyzer"]:
        if name in WORKER_CONFIGS:
            config = WORKER_CONFIGS[name]
            print(f"    {name:25} - {config.description}  [{config.group_id}]")
    
    # 第二层：DB Writers（共享 Group）
    print(f"\n【第二层：DB Writers】（共享 {ConsumerGroup.DB_WRITER}）")
    for name in ["embedding_milvus_writer", "neo4j_writer", "mysql_writer", "mongo_writer"]:
        if name in WORKER_CONFIGS:
            config = WORKER_CONFIGS[name]
            print(f"    {name:25} - {config.description}")
    
    print("\n" + "=" * 80)
    print("用法:")
    print("  启动所有 Workers:        uv run python scripts/start_all_workers.py")
    print("  启动所有 Pipeline Workers: uv run python scripts/start_all_workers.py --workers file_parser,text_splitter,file_summary,kg_extractor,image_understand,text_analyzer")
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
