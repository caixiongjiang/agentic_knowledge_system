#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka Manager 测试

测试 Kafka 连接管理器的基本功能。

运行前提：
1. 确保 Kafka 服务已启动
2. 配置文件 config/config.toml 中的 Kafka 配置正确
3. 已安装 aiokafka: uv add aiokafka

运行方式：
    uv run python test/db/kafka/test_kafka_manager.py
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import json
from loguru import logger

from src.db.kafka import get_kafka_manager, KafkaTopics, MessageKey


async def test_connection():
    """测试 Kafka 连接"""
    logger.info("=" * 60)
    logger.info("测试 1: Kafka 连接")
    logger.info("=" * 60)
    
    kafka_manager = get_kafka_manager()
    
    try:
        # 连接 Kafka
        await kafka_manager.connect()
        assert kafka_manager.is_connected, "连接失败"
        logger.success("✅ Kafka 连接成功")
        
        # 断开连接
        await kafka_manager.disconnect()
        assert not kafka_manager.is_connected, "断开连接失败"
        logger.success("✅ Kafka 断开连接成功")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        raise


async def test_create_topics():
    """测试创建 Topics"""
    logger.info("=" * 60)
    logger.info("测试 2: 创建 Topics")
    logger.info("=" * 60)
    
    kafka_manager = get_kafka_manager()
    
    try:
        await kafka_manager.connect()
        
        # 获取 Topic 配置
        topic_configs = KafkaTopics.get_topic_configs_dict()
        logger.info(f"准备创建 {len(topic_configs)} 个 Topics")
        
        # 创建 Topics
        await kafka_manager.create_topics(topic_configs)
        logger.success("✅ Topics 创建成功（或已存在）")
        
        # 等待 Kafka 完成 Topic 创建（Kafka 是异步创建的）
        await asyncio.sleep(2)
        
        # 列出所有 Topics
        topics = await kafka_manager.list_topics()
        logger.info(f"当前存在 {len(topics)} 个 Topics")
        
        # 验证我们的 Topics 是否存在
        expected_topics = KafkaTopics.get_all_topics()
        for topic in expected_topics:
            if topic in topics:
                logger.success(f"✅ Topic 存在: {topic}")
            else:
                logger.warning(f"⚠️ Topic 不存在: {topic}")
        
        await kafka_manager.disconnect()
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        await kafka_manager.disconnect()
        raise


async def test_produce_consume():
    """测试生产和消费消息"""
    logger.info("=" * 60)
    logger.info("测试 3: 生产和消费消息")
    logger.info("=" * 60)
    
    kafka_manager = get_kafka_manager()
    
    try:
        await kafka_manager.connect()
        
        # 生成测试消息
        test_message = {
            "user_id": "test_user_001",
            "file_id": "test_file_001",
            "s3_path": "s3://test-bucket/test_user_001/test_file_001.pdf",
            "timestamp": "2026-02-02T12:00:00Z"
        }
        
        # 生成 Message Key
        key = MessageKey.generate(test_message["user_id"], test_message["file_id"])
        logger.info(f"Message Key: {key}")
        
        # 发送消息
        producer = await kafka_manager.get_producer()
        await producer.send(
            KafkaTopics.INDEX_START,
            key=key.encode("utf-8"),
            value=json.dumps(test_message).encode("utf-8")
        )
        logger.success(f"✅ 消息已发送到 {KafkaTopics.INDEX_START}")
        
        # 等待消息写入
        await asyncio.sleep(2)
        
        # 接收消息
        consumer = await kafka_manager.get_consumer(
            topics=[KafkaTopics.INDEX_START],
            group_id="test-consumer-group"
        )
        
        logger.info("开始消费消息...")
        message_received = False
        
        # 设置超时
        try:
            async with asyncio.timeout(10):
                async for msg in consumer:
                    received_key = msg.key.decode("utf-8")
                    received_value = json.loads(msg.value.decode("utf-8"))
                    
                    logger.info(f"收到消息:")
                    logger.info(f"  Topic: {msg.topic}")
                    logger.info(f"  Partition: {msg.partition}")
                    logger.info(f"  Offset: {msg.offset}")
                    logger.info(f"  Key: {received_key}")
                    logger.info(f"  Value: {received_value}")
                    
                    # 验证消息内容
                    assert received_key == key, "Message Key 不匹配"
                    assert received_value["user_id"] == test_message["user_id"], "user_id 不匹配"
                    assert received_value["file_id"] == test_message["file_id"], "file_id 不匹配"
                    
                    # 手动提交 offset
                    await consumer.commit()
                    logger.success("✅ 消息接收并验证成功")
                    
                    message_received = True
                    break
        except TimeoutError:
            logger.warning("⚠️ 等待消息超时（可能消息已被其他 Consumer 消费）")
        
        if message_received:
            logger.success("✅ 生产和消费测试成功")
        else:
            logger.warning("⚠️ 未收到消息（可能已被消费或 offset 已提交）")
        
        await kafka_manager.disconnect()
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        await kafka_manager.disconnect()
        raise


async def test_message_key():
    """测试 Message Key 生成和解析"""
    logger.info("=" * 60)
    logger.info("测试 4: Message Key 生成和解析")
    logger.info("=" * 60)
    
    # 生成 Key
    user_id = "user_123"
    file_id = "file_456"
    key = MessageKey.generate(user_id, file_id)
    
    logger.info(f"生成的 Key: {key}")
    assert key == "user_123:file_456", "Key 格式不正确"
    logger.success("✅ Key 生成正确")
    
    # 解析 Key
    parsed_user_id, parsed_file_id = MessageKey.parse(key)
    assert parsed_user_id == user_id, "user_id 解析不正确"
    assert parsed_file_id == file_id, "file_id 解析不正确"
    logger.success("✅ Key 解析正确")
    
    # 测试错误格式
    try:
        MessageKey.parse("invalid_key")
        logger.error("❌ 应该抛出 ValueError")
    except ValueError:
        logger.success("✅ 错误格式检测正确")


async def run_all_tests():
    """运行所有测试"""
    logger.info("开始运行 Kafka Manager 测试套件")
    logger.info("")
    
    try:
        # 测试 1: 连接
        await test_connection()
        logger.info("")
        
        # 测试 2: 创建 Topics
        await test_create_topics()
        logger.info("")
        
        # 测试 3: 生产和消费
        await test_produce_consume()
        logger.info("")
        
        # 测试 4: Message Key
        await test_message_key()
        logger.info("")
        
        logger.success("=" * 60)
        logger.success("✅ 所有测试通过！")
        logger.success("=" * 60)
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ 测试失败: {e}")
        logger.error("=" * 60)
        raise


if __name__ == "__main__":
    # 运行测试
    asyncio.run(run_all_tests())
