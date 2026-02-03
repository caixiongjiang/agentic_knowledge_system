#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka Producer/Consumer 测试

测试 Phase 2 的 Producer 和 Consumer 封装功能。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from datetime import datetime, timezone
from loguru import logger

from src.db.kafka import get_kafka_manager, KafkaTopics, KafkaProducer, BaseKafkaConsumer
from src.types.messages import IndexStartMessage, ParseEndMessage


# ==================== 测试 Consumer 实现 ====================

class TestFileParserConsumer(BaseKafkaConsumer):
    """
    测试用的 FileParser Consumer
    
    模拟文件解析器，接收 IndexStartMessage，处理后发送 ParseEndMessage。
    """
    
    def __init__(self, aiokafka_consumer, producer: KafkaProducer):
        super().__init__(
            aiokafka_consumer=aiokafka_consumer,
            message_class=IndexStartMessage,
            batch_size=10,
            commit_interval=5
        )
        self.producer = producer
    
    async def process_message(self, message: IndexStartMessage) -> bool:
        """
        处理 IndexStartMessage
        
        模拟文件解析流程：
        1. 接收索引开始消息
        2. "解析"文件（这里只是模拟）
        3. 发送解析完成消息
        """
        try:
            logger.info(f"开始处理文件: user_id={message.user_id}, file_id={message.file_id}")
            logger.info(f"  文件名: {message.filename}")
            logger.info(f"  S3路径: {message.s3_path}")
            logger.info(f"  文件大小: {message.file_size} bytes")
            
            # 模拟文件解析（实际应该调用解析器）
            await asyncio.sleep(0.1)
            
            # 构造解析完成消息
            parse_end_message = ParseEndMessage(
                user_id=message.user_id,
                file_id=message.file_id,
                text_content=f"这是从 {message.filename} 解析出的文本内容...",
                document_metadata={
                    "filename": message.filename,
                    "file_size": message.file_size,
                    "mime_type": message.mime_type,
                    "parsed_at": datetime.now(timezone.utc).isoformat()
                },
                parser_name="test_parser",
                parse_quality=0.95,
                has_images=False,
                language="zh"
            )
            
            # 发送解析完成消息
            await self.producer.send_message(
                topic=KafkaTopics.PARSE_END,
                message=parse_end_message
            )
            
            logger.success(f"✅ 文件处理完成: {message.file_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 文件处理失败: {message.file_id}, error={e}")
            return False


# ==================== 测试用例 ====================

async def test_producer():
    """
    测试 1: Producer 发送消息
    """
    logger.info("=" * 60)
    logger.info("测试 1: Producer 发送消息")
    logger.info("=" * 60)
    
    kafka_manager = get_kafka_manager()
    
    try:
        # 连接 Kafka
        await kafka_manager.connect()
        
        # 创建 Producer 封装
        raw_producer = await kafka_manager.get_producer()
        producer = KafkaProducer(raw_producer)
        
        # 创建测试消息
        message = IndexStartMessage(
            user_id="test_user_001",
            file_id="test_file_001",
            s3_path="s3://test-bucket/test_user_001/test_file_001.pdf",
            filename="test_document.pdf",
            file_size=1024000,
            mime_type="application/pdf",
            file_extension=".pdf",
            parse_options={"ocr": True}
        )
        
        logger.info(f"准备发送消息: {message.file_id}")
        
        # 发送消息
        metadata = await producer.send_message(
            topic=KafkaTopics.INDEX_START,
            message=message
        )
        
        logger.success(
            f"✅ 消息发送成功: topic={metadata.topic}, "
            f"partition={metadata.partition}, offset={metadata.offset}"
        )
        
        # 测试批量发送
        messages = [
            IndexStartMessage(
                user_id="test_user_001",
                file_id=f"test_file_{i:03d}",
                s3_path=f"s3://test-bucket/test_user_001/test_file_{i:03d}.pdf",
                filename=f"document_{i}.pdf",
                file_size=1024000 + i * 1000,
                mime_type="application/pdf",
                file_extension=".pdf"
            )
            for i in range(2, 6)  # 生成 4 条消息
        ]
        
        logger.info(f"准备批量发送 {len(messages)} 条消息")
        results = await producer.send_messages(
            topic=KafkaTopics.INDEX_START,
            messages=messages
        )
        
        logger.success(f"✅ 批量发送成功: {len(results)} 条消息")
        
        # 刷新确保消息发送
        await producer.flush()
        logger.info("消息已刷新到 Kafka")
        
        await kafka_manager.disconnect()
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        await kafka_manager.disconnect()
        raise


async def test_consumer():
    """
    测试 2: Consumer 消费消息
    """
    logger.info("=" * 60)
    logger.info("测试 2: Consumer 消费消息")
    logger.info("=" * 60)
    
    kafka_manager = get_kafka_manager()
    
    try:
        # 连接 Kafka
        await kafka_manager.connect()
        
        # 创建 Producer（用于 Consumer 内部发送消息）
        raw_producer = await kafka_manager.get_producer()
        producer = KafkaProducer(raw_producer)
        
        # 创建 Consumer
        raw_consumer = await kafka_manager.get_consumer(
            group_id="test-file-parser-group",
            topics=[KafkaTopics.INDEX_START]
        )
        
        consumer = TestFileParserConsumer(
            aiokafka_consumer=raw_consumer,
            producer=producer
        )
        
        logger.info("Consumer 已创建，开始消费...")
        logger.info("将处理前面测试中发送的消息（约 5 条）")
        logger.info("按 Ctrl+C 停止...")
        
        # 启动 Consumer（这是一个阻塞调用）
        # 在实际应用中，应该在独立的任务或进程中运行
        try:
            # 设置一个超时，避免无限等待
            await asyncio.wait_for(consumer.start(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.info("测试超时，停止 Consumer")
            await consumer.stop()
        
        # 显示统计信息
        stats = consumer.get_stats()
        logger.info("=" * 60)
        logger.info("Consumer 统计信息:")
        logger.info(f"  处理成功: {stats['processed_count']}")
        logger.info(f"  处理失败: {stats['failed_count']}")
        logger.info(f"  成功率: {stats['success_rate']:.2%}")
        logger.info("=" * 60)
        
        if stats['processed_count'] > 0:
            logger.success("✅ Consumer 测试成功")
        else:
            logger.warning("⚠️ 没有消费到消息（可能之前已被其他 Consumer 消费）")
        
        await kafka_manager.disconnect()
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        await kafka_manager.disconnect()
        raise


async def test_message_serialization():
    """
    测试 3: 消息序列化和反序列化
    """
    logger.info("=" * 60)
    logger.info("测试 3: 消息序列化和反序列化")
    logger.info("=" * 60)
    
    try:
        # 创建消息
        original = IndexStartMessage(
            user_id="test_user_123",
            file_id="test_file_456",
            s3_path="s3://bucket/path/file.pdf",
            filename="document.pdf",
            file_size=2048000,
            mime_type="application/pdf",
            file_extension=".pdf"
        )
        
        logger.info("原始消息:")
        logger.info(f"  user_id: {original.user_id}")
        logger.info(f"  file_id: {original.file_id}")
        logger.info(f"  event_id: {original.metadata.event_id}")
        
        # 序列化
        json_str = original.to_json()
        logger.info(f"序列化为 JSON: {len(json_str)} 字符")
        
        bytes_data = original.to_bytes()
        logger.info(f"序列化为 bytes: {len(bytes_data)} 字节")
        
        # 反序列化
        deserialized = IndexStartMessage.from_bytes(bytes_data)
        logger.info("反序列化成功")
        
        # 验证
        assert deserialized.user_id == original.user_id
        assert deserialized.file_id == original.file_id
        assert deserialized.s3_path == original.s3_path
        assert deserialized.metadata.event_id == original.metadata.event_id
        
        logger.success("✅ 序列化/反序列化测试通过")
        
        # 测试 Message Key
        key = original.get_message_key()
        logger.info(f"Message Key: {key}")
        assert key == "test_user_123:test_file_456"
        logger.success("✅ Message Key 测试通过")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        raise


async def test_parse_end_consumer():
    """
    测试 4: 验证 ParseEndMessage 被正确发送和接收
    """
    logger.info("=" * 60)
    logger.info("测试 4: 验证 ParseEndMessage")
    logger.info("=" * 60)
    
    kafka_manager = get_kafka_manager()
    
    try:
        await kafka_manager.connect()
        
        # 创建 Consumer 监听 ParseEndMessage
        raw_consumer = await kafka_manager.get_consumer(
            group_id="test-parse-end-group",
            topics=[KafkaTopics.PARSE_END]
        )
        
        logger.info("开始监听 ParseEndMessage（5秒超时）...")
        
        # 简单地拉取几条消息
        data = await raw_consumer.getmany(timeout_ms=5000, max_records=10)
        
        message_count = 0
        for partition_records in data.values():
            for record in partition_records:
                message = ParseEndMessage.from_bytes(record.value)
                message_count += 1
                logger.info(f"收到 ParseEndMessage:")
                logger.info(f"  user_id: {message.user_id}")
                logger.info(f"  file_id: {message.file_id}")
                logger.info(f"  parser: {message.parser_name}")
                logger.info(f"  language: {message.language}")
        
        if message_count > 0:
            logger.success(f"✅ 接收到 {message_count} 条 ParseEndMessage")
        else:
            logger.warning("⚠️ 没有接收到 ParseEndMessage（可能之前已被消费）")
        
        await kafka_manager.disconnect()
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        await kafka_manager.disconnect()
        raise


async def run_all_tests():
    """运行所有测试"""
    logger.info("开始运行 Kafka Producer/Consumer 测试套件")
    logger.info("")
    
    try:
        # 测试 1: 消息序列化
        await test_message_serialization()
        logger.info("")
        
        # 测试 2: Producer
        await test_producer()
        logger.info("")
        
        # 等待消息在 Kafka 中稳定
        logger.info("等待 2 秒，让消息在 Kafka 中稳定...")
        await asyncio.sleep(2)
        
        # 测试 3: Consumer
        await test_consumer()
        logger.info("")
        
        # 测试 4: 验证 ParseEndMessage
        await test_parse_end_consumer()
        logger.info("")
        
        logger.success("=" * 60)
        logger.success("✅ 所有测试通过！")
        logger.success("=" * 60)
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())
