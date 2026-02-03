#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka Phase 3 功能测试

测试内容：
1. 幂等性保证（DeduplicationManager）
2. 重试管理（RetryManager）
3. DLQ 管理（DLQManager）
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio

from loguru import logger

from src.db.kafka import (
    get_kafka_manager,
    KafkaTopics,
    KafkaProducer,
    get_deduplication_manager,
    get_retry_manager,
    get_dlq_manager
)
from src.db.kafka.deduplication import close_redis_manager
from src.types.messages import IndexStartMessage
from src.db.kafka.types import EventID


class Phase3Tests:
    """Phase 3 测试类"""
    
    def __init__(self):
        self.kafka_manager = None
        self.producer = None
        self.dedup_manager = None
        self.retry_manager = None
        self.dlq_manager = None
    
    async def setup(self):
        """初始化测试环境"""
        logger.info("=" * 60)
        logger.info("开始初始化测试环境...")
        logger.info("=" * 60)
        
        try:
            # 1. 连接 Kafka
            self.kafka_manager = get_kafka_manager()
            await self.kafka_manager.connect()
            logger.info("✅ Kafka 连接成功")
            
            # 2. 创建 Topics（如果不存在）
            await self.kafka_manager.create_topics(KafkaTopics.get_topic_configs_dict())
            logger.info("✅ Topics 创建/验证完成")
            
            # 3. 创建 Producer
            aiokafka_producer = await self.kafka_manager.get_producer()
            self.producer = KafkaProducer(aiokafka_producer)
            logger.info("✅ Producer 创建成功")
            
            # 4. 初始化去重管理器（自动尝试连接 Redis）
            self.dedup_manager = await get_deduplication_manager(
                redis_namespace=None,  # 自动创建
                force_new=True
            )
            logger.info("✅ 去重管理器创建成功")
            
            # 5. 初始化 DLQ 管理器
            self.dlq_manager = await get_dlq_manager(
                producer=self.producer,
                force_new=True
            )
            logger.info("✅ DLQ 管理器创建成功")
            
            # 6. 初始化重试管理器
            self.retry_manager = await get_retry_manager(
                producer=self.producer,
                dlq_manager=self.dlq_manager,
                force_new=True
            )
            logger.info("✅ 重试管理器创建成功")
            
            logger.info("=" * 60)
            logger.info("测试环境初始化完成！")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}", exc_info=True)
            raise
    
    async def cleanup(self):
        """清理测试环境"""
        logger.info("\n清理测试环境...")
        
        try:
            # 1. 停止重试管理器
            if self.retry_manager:
                await self.retry_manager.stop()
                logger.info("✅ 重试管理器已停止")
            
            # 2. 断开 Kafka 连接
            if self.kafka_manager:
                await self.kafka_manager.disconnect()
                logger.info("✅ Kafka 连接已断开")
            
            # 3. 关闭 Redis 连接池（仅在测试结束时）
            await close_redis_manager()
            logger.info("✅ Redis 连接池已关闭")
            
            logger.info("✅ 测试环境清理完成")
        except Exception as e:
            logger.error(f"❌ 清理失败: {e}")
    
    async def test_deduplication(self):
        """测试幂等性保证"""
        logger.info("\n" + "=" * 60)
        logger.info("测试 1: 幂等性保证（DeduplicationManager）")
        logger.info("=" * 60)
        
        try:
            # 创建测试消息
            message = IndexStartMessage(
                user_id="test_user_001",
                file_id="test_file_001",
                s3_path="s3://test-bucket/test.pdf",
                filename="test.pdf",
                file_size=1024,
                mime_type="application/pdf",
                file_extension=".pdf"
            )
            
            event_id = message.metadata.event_id
            logger.info(f"测试消息 event_id: {event_id}")
            
            # 测试 1.1: 首次检查（应该不重复）
            is_dup = await self.dedup_manager.is_duplicate(event_id)
            assert not is_dup, "首次检查应该返回 False"
            logger.info("✅ 首次检查：消息未处理过")
            
            # 测试 1.2: 标记为已处理
            success = await self.dedup_manager.mark_processed(event_id)
            assert success, "标记失败"
            logger.info("✅ 标记消息为已处理")
            
            # 测试 1.3: 再次检查（应该重复）
            is_dup = await self.dedup_manager.is_duplicate(event_id)
            assert is_dup, "第二次检查应该返回 True"
            logger.info("✅ 再次检查：检测到重复消息")
            
            # 测试 1.4: 移除标记
            success = await self.dedup_manager.remove_processed(event_id)
            assert success, "移除失败"
            logger.info("✅ 移除已处理标记")
            
            # 测试 1.5: 第三次检查（应该不重复）
            is_dup = await self.dedup_manager.is_duplicate(event_id)
            assert not is_dup, "移除后检查应该返回 False"
            logger.info("✅ 移除后检查：消息可以重新处理")
            
            # 测试 1.6: 统计信息
            stats = await self.dedup_manager.get_stats()
            logger.info(f"✅ 去重统计: {stats}")
            
            logger.info("=" * 60)
            logger.info("✅ 幂等性保证测试通过！")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ 幂等性测试失败: {e}", exc_info=True)
            raise
    
    async def test_retry_manager(self):
        """测试重试管理"""
        logger.info("\n" + "=" * 60)
        logger.info("测试 2: 重试管理（RetryManager）")
        logger.info("=" * 60)
        
        try:
            # 启动重试管理器
            await self.retry_manager.start()
            logger.info("✅ 重试管理器已启动")
            
            # 创建测试消息
            message = IndexStartMessage(
                user_id="test_user_002",
                file_id="test_file_002",
                s3_path="s3://test-bucket/test2.pdf",
                filename="test2.pdf",
                file_size=2048,
                mime_type="application/pdf",
                file_extension=".pdf"
            )
            
            # 添加原始 topic 到 context
            message.metadata.context["original_topic"] = KafkaTopics.INDEX_START
            
            logger.info(f"测试消息 event_id: {message.metadata.event_id}")
            
            # 测试 2.1: 调度第一次重试
            success = await self.retry_manager.schedule_retry(
                message=message,
                original_topic=KafkaTopics.INDEX_START,
                error="测试错误: 模拟处理失败"
            )
            assert success, "第一次重试调度应该成功"
            logger.info(f"✅ 第一次重试已调度（retry_count: {message.metadata.retry_count}）")
            
            # 测试 2.2: 调度第二次重试
            success = await self.retry_manager.schedule_retry(
                message=message,
                original_topic=KafkaTopics.INDEX_START,
                error="测试错误: 第二次失败"
            )
            assert success, "第二次重试调度应该成功"
            logger.info(f"✅ 第二次重试已调度（retry_count: {message.metadata.retry_count}）")
            
            # 测试 2.3: 调度第三次重试
            success = await self.retry_manager.schedule_retry(
                message=message,
                original_topic=KafkaTopics.INDEX_START,
                error="测试错误: 第三次失败"
            )
            assert success, "第三次重试调度应该成功"
            logger.info(f"✅ 第三次重试已调度（retry_count: {message.metadata.retry_count}）")
            
            # 测试 2.4: 超过最大重试次数（应该发送到 DLQ）
            success = await self.retry_manager.schedule_retry(
                message=message,
                original_topic=KafkaTopics.INDEX_START,
                error="测试错误: 第四次失败"
            )
            assert not success, "超过最大重试次数应该返回 False"
            logger.info("✅ 超过最大重试次数，已发送到 DLQ")
            
            # 测试 2.5: 统计信息
            stats = await self.retry_manager.get_stats()
            logger.info(f"✅ 重试统计: {stats}")
            
            # 等待一段时间，让重试队列处理
            logger.info("等待重试队列处理...")
            await asyncio.sleep(3)
            
            # 再次查看统计
            stats = await self.retry_manager.get_stats()
            logger.info(f"✅ 重试统计（3秒后）: {stats}")
            
            logger.info("=" * 60)
            logger.info("✅ 重试管理测试通过！")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ 重试管理测试失败: {e}", exc_info=True)
            raise
        finally:
            await self.retry_manager.stop()
    
    async def test_dlq_manager(self):
        """测试 DLQ 管理"""
        logger.info("\n" + "=" * 60)
        logger.info("测试 3: DLQ 管理（DLQManager）")
        logger.info("=" * 60)
        
        try:
            # 清空 DLQ 统计（避免前面测试的影响）
            await self.dlq_manager.clear_stats()
            
            # 创建测试消息
            message = IndexStartMessage(
                user_id="test_user_003",
                file_id="test_file_003",
                s3_path="s3://test-bucket/test3.pdf",
                filename="test3.pdf",
                file_size=4096,
                mime_type="application/pdf",
                file_extension=".pdf"
            )
            
            logger.info(f"测试消息 event_id: {message.metadata.event_id}")
            
            # 测试 3.1: 发送到 DLQ
            success = await self.dlq_manager.send_to_dlq(
                message=message,
                original_topic=KafkaTopics.INDEX_START,
                error="测试错误: 模拟致命错误",
                stack_trace="Traceback (most recent call last):\n  File test.py, line 123\n    raise ValueError('测试错误')",
                context={"test_key": "test_value"}
            )
            assert success, "发送到 DLQ 应该成功"
            logger.info("✅ 消息已发送到 DLQ")
            
            # 测试 3.2: 再发送几条消息
            for i in range(3):
                msg = IndexStartMessage(
                    user_id=f"test_user_{i:03d}",
                    file_id=f"test_file_{i:03d}",
                    s3_path=f"s3://test-bucket/test{i}.pdf",
                    filename=f"test{i}.pdf",
                    file_size=1024 * (i + 1),
                    mime_type="application/pdf",
                    file_extension=".pdf"
                )
                
                await self.dlq_manager.send_to_dlq(
                    message=msg,
                    original_topic=KafkaTopics.INDEX_START,
                    error=f"测试错误类型 {i % 2}"
                )
            
            logger.info("✅ 批量发送 DLQ 消息完成")
            
            # 测试 3.3: 统计信息
            stats = await self.dlq_manager.get_stats()
            logger.info(f"✅ DLQ 统计: {stats}")
            
            assert stats["total_dlq_messages"] == 4, "应该有 4 条 DLQ 消息"
            logger.info(f"✅ DLQ 消息总数: {stats['total_dlq_messages']}")
            logger.info(f"✅ 按 Topic 统计: {stats['dlq_by_topic']}")
            logger.info(f"✅ 按错误类型统计: {stats['dlq_by_error_type']}")
            logger.info(f"✅ Top 错误类型: {stats['top_error_types']}")
            
            logger.info("=" * 60)
            logger.info("✅ DLQ 管理测试通过！")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ DLQ 管理测试失败: {e}", exc_info=True)
            raise
    
    async def test_integration(self):
        """集成测试：幂等性 + 重试 + DLQ"""
        logger.info("\n" + "=" * 60)
        logger.info("测试 4: 集成测试（幂等性 + 重试 + DLQ）")
        logger.info("=" * 60)
        
        try:
            # 启动重试管理器
            await self.retry_manager.start()
            
            # 创建测试消息
            message = IndexStartMessage(
                user_id="test_user_integration",
                file_id="test_file_integration",
                s3_path="s3://test-bucket/integration.pdf",
                filename="integration.pdf",
                file_size=8192,
                mime_type="application/pdf",
                file_extension=".pdf"
            )
            
            # 添加原始 topic 到 context
            message.metadata.context["original_topic"] = KafkaTopics.INDEX_START
            
            event_id = message.metadata.event_id
            logger.info(f"测试消息 event_id: {event_id}")
            
            # 步骤 1: 检查是否重复（首次应该不重复）
            is_dup = await self.dedup_manager.is_duplicate(event_id)
            assert not is_dup, "首次处理应该不重复"
            logger.info("✅ 步骤 1: 幂等性检查通过（首次处理）")
            
            # 步骤 2: 模拟处理失败，调度重试
            for i in range(3):
                success = await self.retry_manager.schedule_retry(
                    message=message,
                    original_topic=KafkaTopics.INDEX_START,
                    error=f"集成测试错误: 第 {i+1} 次失败"
                )
                logger.info(f"✅ 步骤 2.{i+1}: 第 {i+1} 次重试已调度")
            
            # 步骤 3: 第四次失败，应该进入 DLQ
            success = await self.retry_manager.schedule_retry(
                message=message,
                original_topic=KafkaTopics.INDEX_START,
                error="集成测试错误: 第 4 次失败"
            )
            assert not success, "第四次应该进入 DLQ"
            logger.info("✅ 步骤 3: 超过最大重试次数，已进入 DLQ")
            
            # 步骤 4: 标记为已处理（模拟成功处理）
            await self.dedup_manager.mark_processed(event_id)
            logger.info("✅ 步骤 4: 标记为已处理")
            
            # 步骤 5: 再次检查是否重复（应该重复）
            is_dup = await self.dedup_manager.is_duplicate(event_id)
            assert is_dup, "已处理的消息应该被识别为重复"
            logger.info("✅ 步骤 5: 幂等性检查通过（检测到重复）")
            
            # 等待重试队列处理
            logger.info("等待重试队列处理...")
            await asyncio.sleep(3)
            
            # 查看所有统计信息
            logger.info("\n最终统计信息：")
            logger.info("-" * 60)
            
            dedup_stats = await self.dedup_manager.get_stats()
            logger.info(f"去重统计: {dedup_stats}")
            
            retry_stats = await self.retry_manager.get_stats()
            logger.info(f"重试统计: {retry_stats}")
            
            dlq_stats = await self.dlq_manager.get_stats()
            logger.info(f"DLQ 统计: {dlq_stats}")
            
            logger.info("=" * 60)
            logger.info("✅ 集成测试通过！")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ 集成测试失败: {e}", exc_info=True)
            raise
        finally:
            await self.retry_manager.stop()
    
    async def run_all_tests(self):
        """运行所有测试"""
        try:
            await self.setup()
            
            # 运行各个测试
            await self.test_deduplication()
            await self.test_retry_manager()
            await self.test_dlq_manager()
            await self.test_integration()
            
            logger.info("\n" + "=" * 60)
            logger.info("🎉 所有测试通过！Phase 3 开发完成！")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"\n❌ 测试失败: {e}")
            raise
        finally:
            await self.cleanup()


async def main():
    """主函数"""
    tests = Phase3Tests()
    await tests.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
