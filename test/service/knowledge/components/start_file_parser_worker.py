#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : start_file_parser_worker.py
@Author  : caixiongjiang
@Date    : 2026/02/05
@Function: 
    启动 FileParser Worker
    
    功能:
    - 监听 Kafka Topic: knowledge_base.index.start
    - 调用 FileParserService 解析文件
    - 发送结果到下游 Topics:
      - db_write.meta.start (MySQL 数据)
      - db_write.mongo.start (MongoDB 数据)
      - knowledge_base.parse.end (解析完成)
    
    用法:
        uv run python scripts/start_file_parser_worker.py
        
    前置条件:
    - Kafka: 192.168.201.14:9092
    - MinIO: 192.168.201.14:9000
    - MinerU: http://192.168.201.14:18000
        
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import asyncio
from pathlib import Path
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.kafka.workers.file_parser_worker import FileParserWorker
from src.db.kafka.producer import KafkaProducer
from src.db.kafka import get_kafka_manager
from src.db.kafka.topics import KafkaTopics
from src.types.messages.index import IndexStartMessage


async def main():
    """启动 FileParser Worker"""
    logger.info("=" * 80)
    logger.info("🚀 FileParser Worker 启动程序")
    logger.info("=" * 80)
    logger.info("监听 Topic: knowledge_base.index.start")
    logger.info("输出 Topics:")
    logger.info("  - db_write.meta.start (MySQL 元数据)")
    logger.info("  - db_write.mongo.start (MongoDB 内容)")
    logger.info("  - knowledge_base.parse.end (解析完成)")
    logger.info("=" * 80)
    
    kafka_manager = None
    producer = None
    consumer = None
    worker = None
    
    try:
        # 1. 获取 Kafka Manager 并连接
        logger.info("正在连接 Kafka...")
        kafka_manager = get_kafka_manager()
        await kafka_manager.connect()
        logger.success("✓ Kafka 连接成功")
        
        # 2. 创建 Producer 封装
        logger.info("正在创建 Kafka Producer...")
        aiokafka_producer = await kafka_manager.get_producer()
        producer = KafkaProducer(aiokafka_producer)
        logger.success("✓ Kafka Producer 创建成功")
        
        # 3. 创建 Consumer
        logger.info("正在创建 Kafka Consumer...")
        aiokafka_consumer = await kafka_manager.get_consumer(
            group_id="file_parser_worker_group",
            topics=[KafkaTopics.INDEX_START]
        )
        logger.success("✓ Kafka Consumer 创建成功")
        
        # 4. 创建 Worker（注入 Consumer 和 Producer）
        logger.info("正在创建 FileParser Worker...")
        worker = FileParserWorker(
            aiokafka_consumer=aiokafka_consumer,
            message_class=IndexStartMessage,
            producer=producer
        )
        logger.success("✓ FileParser Worker 创建成功")
        
        # 5. 启动 Worker（开始监听消息）
        logger.info("=" * 80)
        logger.success("🎉 Worker 已启动，开始监听消息...")
        logger.info("=" * 80)
        logger.info("提示:")
        logger.info("  - 按 Ctrl+C 停止 Worker")
        logger.info("  - Worker 会持续运行直到手动停止")
        logger.info("=" * 80 + "\n")
        
        await worker.start()
        
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 80)
        logger.warning("⚠️  收到停止信号 (Ctrl+C)，正在关闭 Worker...")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ Worker 运行失败: {e}")
        logger.error("=" * 80)
        logger.exception("详细错误信息:")
        
    finally:
        # 6. 清理资源
        logger.info("正在清理资源...")
        
        if worker:
            try:
                await worker.cleanup()
                logger.success("✓ Worker 资源已清理")
            except Exception as e:
                logger.warning(f"⚠ Worker 清理失败: {e}")
        
        if kafka_manager:
            try:
                await kafka_manager.disconnect()
                logger.success("✓ Kafka 连接已关闭")
            except Exception as e:
                logger.warning(f"⚠ Kafka 关闭失败: {e}")
        
        logger.info("=" * 80)
        logger.info("Worker 已停止")
        logger.info("=" * 80)


if __name__ == "__main__":
    # 运行主函数
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # 已在 main() 中处理，这里不需要额外处理
        pass
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        sys.exit(1)
