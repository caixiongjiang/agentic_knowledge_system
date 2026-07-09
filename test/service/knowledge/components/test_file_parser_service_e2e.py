#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_file_parser_service_e2e.py
@Author  : caixiongjiang
@Date    : 2026/02/05
@Function: 
    FileParserService 端到端测试（支持 Kafka 模式）
    
    测试模式:
    1. Service 模式（默认）: 直接调用 Service，快速测试
    2. Kafka 模式: 完整 Kafka 消息流程，需要启动 Worker
    
    测试流程:
    1. 上传测试 PDF 文件到 MinIO
    2. 解析文件（Service 直接调用 或 通过 Kafka）
    3. 验证解析结果 (ParseResult)
    4. 验证 MySQL 消息列表
    5. 验证 MongoDB 消息列表
    6. 验证图片是否成功上传到 MinIO
    7. 【Kafka 模式】验证下游 Kafka 消息
    8. 清理测试数据
    
    用法:
        # Service 模式（快速测试，不需要 Worker）
        uv run python test/service/knowledge/components/test_file_parser_service_e2e.py
        
        # Kafka 模式（完整测试，需要先启动 Worker）
        # 终端1: uv run python scripts/start_file_parser_worker.py
        # 终端2: uv run python test/service/knowledge/components/test_file_parser_service_e2e.py --kafka
        
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import asyncio
import json
import uuid
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.db.storage.manager import StorageManager
from src.service.knowledge.components.file_parser_service import FileParserService
from src.types.models.parse_result import ParseResult, ParseStatus
from src.db.kafka.producer import KafkaProducer
from src.db.kafka import get_kafka_manager
from src.db.kafka.topics import KafkaTopics
from src.types.messages.index import IndexStartMessage


class FileParserServiceE2ETest:
    """
    FileParserService 端到端测试（支持 Kafka 模式）
    
    核心功能:
    - Service 模式: 直接调用 Service 层，快速测试
    - Kafka 模式: 完整 Kafka 消息流程，测试 Worker
    - 图片上传验证
    - 数据结构验证
    """
    
    def __init__(self, cleanup: bool = False, kafka_mode: bool = False):
        """
        初始化测试
        
        Args:
            cleanup: 是否在测试后清理文件（默认 False，保留文件以便查看）
            kafka_mode: 是否启用 Kafka 模式（默认 False，仅测试 Service）
        """
        self.storage = None
        self.service = None
        self.kafka_manager = None
        self.producer = None
        self.consumers = {}
        self.cleanup = cleanup
        self.kafka_mode = kafka_mode
        self.created_files = []  # 记录创建的文件，用于清理
        
        # 测试文件路径
        self.test_files_dir = project_root / "tmp_files"
        self.test_pdf = self.test_files_dir / "pdf" / "TP-LoRA.pdf"
        
        # 测试参数（Kafka 模式使用随机 ID）
        if kafka_mode:
            self.user_id = f"test_user_{uuid.uuid4().hex[:8]}"
            self.session_id = f"session_{uuid.uuid4().hex[:8]}"
            self.file_id = f"file-{uuid.uuid4().hex[:8]}"
            self.knowledge_base_id = f"kb-{uuid.uuid4().hex[:8]}"
            self.knowledge_base_name = "测试知识库_Kafka"
        else:
            self.user_id = "test_user_001"
            self.session_id = "test_session_001"
            self.file_id = "test_file_001"
            self.knowledge_base_id = "kb_test_001"
            self.knowledge_base_name = "测试知识库_Service"
        
        self.filename = "TP-LoRA.pdf"
        
        # Kafka 模式：接收到的消息
        self.received_messages = {
            "parse_end": None,
            "mysql_messages": [],
            "mongodb_messages": []
        }
        
        mode_name = "Kafka 完整流程" if kafka_mode else "Service 快速"
        logger.info(f"端到端测试初始化完成 (mode={mode_name}, cleanup={cleanup})")
    
    def _read_file(self, file_path: Path) -> bytes:
        """
        读取测试文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bytes: 文件内容
        """
        if not file_path.exists():
            raise FileNotFoundError(f"测试文件不存在: {file_path}")
        
        with open(file_path, 'rb') as f:
            content = f.read()
        
        logger.debug(f"读取测试文件: {file_path.name}, 大小: {len(content)} bytes ({len(content)/1024:.2f} KB)")
        return content
    
    async def setup(self):
        """初始化测试环境"""
        logger.info("=" * 80)
        logger.info(f"设置测试环境 ({'Kafka 模式' if self.kafka_mode else 'Service 模式'})")
        logger.info("=" * 80)
        
        # 创建 StorageManager
        self.storage = StorageManager()
        await self.storage.__aenter__()
        logger.success("✓ StorageManager 初始化成功")
        
        if self.kafka_mode:
            # Kafka 模式：创建 Producer 和 Consumers
            self.kafka_manager = get_kafka_manager()
            await self.kafka_manager.connect()
            logger.success("✓ Kafka 连接成功")
            
            # 创建 Producer
            aiokafka_producer = await self.kafka_manager.get_producer()
            self.producer = KafkaProducer(aiokafka_producer)
            logger.success("✓ Kafka Producer 启动成功")
            
            # 创建 Consumers 监听下游消息
            await self._setup_kafka_consumers()
            logger.success("✓ Kafka Consumers 启动成功")
            
            logger.warning("⚠️  确保 FileParserWorker 正在运行！")
        else:
            # Service 模式：直接创建 Service
            self.service = FileParserService(storage_manager=self.storage)
            logger.success("✓ FileParserService 初始化成功")
    
    async def _setup_kafka_consumers(self):
        """设置 Kafka Consumers（仅 Kafka 模式）"""
        topics = [
            KafkaTopics.PARSE_END,
            KafkaTopics.DB_WRITE_META,
            KafkaTopics.DB_WRITE_MONGO
        ]
        
        for topic in topics:
            # 为每个 topic 创建独立的 consumer
            aiokafka_consumer = await self.kafka_manager.get_consumer(
                group_id=f"test_monitor_{topic.replace('.', '_')}_{uuid.uuid4().hex[:8]}",
                topics=[topic]
            )
            self.consumers[topic] = aiokafka_consumer
            logger.info(f"  - 监听 topic: {topic}")
    
    async def teardown(self):
        """清理测试环境"""
        logger.info("=" * 80)
        logger.info("清理测试环境")
        logger.info("=" * 80)
        
        # Kafka 模式：关闭 Consumers 和 Producer
        if self.kafka_mode:
            # 关闭 Consumers
            for topic, consumer in self.consumers.items():
                try:
                    await consumer.stop()
                    logger.debug(f"✓ Consumer 关闭: {topic}")
                except Exception as e:
                    logger.warning(f"关闭 Consumer 失败: {topic}, 错误: {e}")
            
            # 关闭 Kafka Manager（会自动关闭 Producer）
            if hasattr(self, 'kafka_manager') and self.kafka_manager:
                try:
                    await self.kafka_manager.disconnect()
                    logger.success("✓ Kafka 连接已关闭")
                except Exception as e:
                    logger.warning(f"关闭 Kafka Manager 失败: {e}")
        
        # 如果需要清理，删除创建的文件
        if self.cleanup and self.created_files:
            logger.info(f"清理 {len(self.created_files)} 个测试文件...")
            for storage_path in self.created_files:
                try:
                    await self.storage.delete_file(storage_path)
                    logger.debug(f"✓ 删除文件: {storage_path}")
                except Exception as e:
                    logger.warning(f"删除文件失败: {storage_path}, 错误: {e}")
            logger.success(f"✓ 已清理 {len(self.created_files)} 个文件")
        else:
            logger.info("跳过文件清理（保留文件以便查看）")
        
        # 关闭 StorageManager
        if self.storage:
            await self.storage.close()
            logger.success("✓ StorageManager 已关闭")
    
    async def test_01_upload_pdf_to_minio(self) -> str:
        """
        测试 1: 上传 PDF 文件到 MinIO
        
        Returns:
            str: 文件在 MinIO 中的存储路径
        """
        logger.info("=" * 80)
        logger.info("测试 1: 上传 PDF 文件到 MinIO")
        logger.info("=" * 80)
        
        try:
            # 读取 PDF 文件
            pdf_bytes = self._read_file(self.test_pdf)
            logger.info(f"读取测试 PDF: {self.test_pdf.name}, 大小: {len(pdf_bytes)} bytes ({len(pdf_bytes)/1024:.2f} KB)")
            
            # 上传到 MinIO
            logger.info(f"上传文件到 MinIO...")
            storage_path = await self.storage.upload_raw_file(
                file_bytes=pdf_bytes,
                user_id=self.user_id,
                session_id=self.session_id,
                file_id=self.file_id,
                file_suffix=".pdf",
            )
            self.created_files.append(storage_path)
            logger.success(f"✓ 上传成功: {storage_path}")
            
            # 验证文件是否存在
            exists = await self.storage.file_exists(storage_path)
            assert exists, "文件应该存在于 MinIO 中"
            logger.success("✓ 验证文件存在")
            
            # 验证文件大小
            downloaded = await self.storage.download_file(storage_path)
            assert len(downloaded) == len(pdf_bytes), "下载的文件大小应该与原文件一致"
            logger.success(f"✓ 验证文件大小: {len(downloaded)} bytes")
            
            logger.success("=" * 80)
            logger.success("✓ 测试 1 通过: PDF 成功上传到 MinIO")
            logger.success("=" * 80)
            
            return storage_path
            
        except Exception as e:
            logger.error(f"❌ 测试 1 失败: {e}", exc_info=True)
            raise
    
    async def test_02_parse_file(self, storage_path: str) -> Tuple[ParseResult, List[Dict], List[Dict]]:
        """
        测试 2: 解析文件（根据模式选择方式）
        
        Args:
            storage_path: 文件在 MinIO 中的路径
            
        Returns:
            Tuple[ParseResult, List[Dict], List[Dict]]: 解析结果、MySQL消息、MongoDB消息
        """
        logger.info("=" * 80)
        if self.kafka_mode:
            logger.info("测试 2: 通过 Kafka 发送解析请求")
        else:
            logger.info("测试 2: 直接调用 FileParserService 解析文件")
        logger.info("=" * 80)
        
        try:
            if self.kafka_mode:
                # Kafka 模式：发送消息到 Kafka，等待 Worker 处理
                result, mysql_messages, mongodb_messages, elements_payload = await self._parse_via_kafka(storage_path)
            else:
                # Service 模式：直接调用 Service
                result, mysql_messages, mongodb_messages, elements_payload = await self._parse_via_service(storage_path)
            
            # 打印解析结果摘要
            logger.info(f"\n{'=' * 60}")
            logger.info("解析结果摘要:")
            logger.info(f"{'=' * 60}")
            logger.info(f"状态: {result.status}")
            logger.info(f"文件名: {result.filename}")
            logger.info(f"总页数: {result.total_pages}")
            logger.info(f"解析工具: {result.parse_tool}")
            logger.info(f"MySQL 消息数: {len(mysql_messages)}")
            logger.info(f"MongoDB 消息数: {len(mongodb_messages)}")
            logger.info(f"elements_payload: {len(elements_payload)}")
            logger.info(f"{'=' * 60}\n")
            
            logger.success("=" * 80)
            logger.success("✓ 测试 2 通过: 文件解析成功")
            logger.success("=" * 80)
            
            return result, mysql_messages, mongodb_messages, elements_payload
            
        except Exception as e:
            logger.error(f"❌ 测试 2 失败: {e}", exc_info=True)
            raise
    
    async def _parse_via_service(self, storage_path: str) -> Tuple[ParseResult, List[Dict], List[Dict], List[Dict]]:
        """Service 模式：直接调用 Service"""
        logger.info("直接调用 FileParserService...")
        
        result, mysql_messages, mongodb_messages, elements_payload = await self.service.parse_file(
            user_id=self.user_id,
            file_id=self.file_id,
            filename=self.filename,
            storage_path=storage_path,
            knowledge_base_id=self.knowledge_base_id,
            knowledge_base_name=self.knowledge_base_name,
            session_id=self.session_id,
            creator=self.user_id,
            store_images=True
        )
        
        logger.success("✓ Service 调用完成")
        return result, mysql_messages, mongodb_messages, elements_payload
    
    async def _parse_via_kafka(self, storage_path: str) -> Tuple[ParseResult, List[Dict], List[Dict]]:
        """Kafka 模式：发送消息到 Kafka，等待 Worker 处理"""
        # 1. 发送消息到 Kafka
        message = IndexStartMessage(
            user_id=self.user_id,
            file_id=self.file_id,
            filename=self.filename,
            storage_path=storage_path,
            knowledge_base_id=self.knowledge_base_id,
            knowledge_base_name=self.knowledge_base_name,
            session_id=self.session_id,
            upload_time=datetime.now().isoformat()
        )
        
        logger.info(f"发送消息到 Kafka: {KafkaTopics.INDEX_START}")
        await self.producer.send_message(
            topic=KafkaTopics.INDEX_START,
            message=message
        )
        logger.success("✓ Kafka 消息已发送")
        
        # 2. 等待并接收下游消息
        logger.info("等待 Worker 处理（最多 5 分钟）...")
        await self._wait_for_kafka_messages(timeout=300)
        
        # 3. 构造返回结果
        if not self.received_messages["parse_end"]:
            raise Exception("未收到 ParseEndMessage，Worker 可能未启动或处理失败")
        
        # 从 ParseEndMessage 构造 ParseResult
        parse_end = self.received_messages["parse_end"]
        result = ParseResult(
            user_id=self.user_id,
            file_id=self.file_id,
            filename=parse_end.get("filename", self.filename),
            status=ParseStatus.SUCCESS if parse_end.get("status") == "success" else ParseStatus.FAILED,
            elements=[],
            parse_tool=parse_end.get("parse_tool", "mineru"),
            total_pages=parse_end.get("total_pages", 0),
            total_chars=parse_end.get("total_chars", 0),
            storage_path=storage_path,
            knowledge_base_id=self.knowledge_base_id,
            knowledge_base_name=self.knowledge_base_name,
            error_message=parse_end.get("error_message")
        )
        
        return (
            result,
            self.received_messages["mysql_messages"],
            self.received_messages["mongodb_messages"],
            parse_end.get("elements", []),
        )
    
    async def _wait_for_kafka_messages(self, timeout: int = 300):
        """等待并接收 Kafka 下游消息"""
        start_time = asyncio.get_event_loop().time()
        
        expected = {"parse_end": False, "mysql": False, "mongodb": False}
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.warning(f"⚠ 等待超时 ({timeout}秒)")
                break
            
            for topic, consumer in self.consumers.items():
                try:
                    # 从 aiokafka consumer 获取消息
                    msg = await asyncio.wait_for(consumer.getone(), timeout=1.0)
                    if msg:
                        # 反序列化消息
                        import json
                        message = json.loads(msg.value.decode('utf-8'))
                        
                        # 过滤消息：只接收本次测试的消息
                        if message.get("file_id") == self.file_id or message.get("_id", "").startswith("element_"):
                            if topic == KafkaTopics.PARSE_END:
                                self.received_messages["parse_end"] = message
                                expected["parse_end"] = True
                                logger.info(f"📨 收到 ParseEndMessage (total_pages={message.get('total_pages')})")
                            elif topic == KafkaTopics.DB_WRITE_META:
                                self.received_messages["mysql_messages"].append(message)
                                expected["mysql"] = True
                            elif topic == KafkaTopics.DB_WRITE_MONGO:
                                self.received_messages["mongodb_messages"].append(message)
                                expected["mongodb"] = True
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.debug(f"消费消息异常: {e}")
                    continue
            
            if all(expected.values()):
                logger.success("✓ 已接收所有预期消息")
                break
            
            await asyncio.sleep(0.5)
        
        logger.info(f"收到: ParseEnd={'✓' if expected['parse_end'] else '✗'}, "
                   f"MySQL={len(self.received_messages['mysql_messages'])}, "
                   f"MongoDB={len(self.received_messages['mongodb_messages'])}")
    
    async def test_03_verify_parse_result(self, result: ParseResult):
        """
        测试 3: 验证 ParseResult
        
        Args:
            result: 解析结果
        """
        logger.info("=" * 80)
        logger.info("测试 3: 验证 ParseResult")
        logger.info("=" * 80)
        
        try:
            # 验证状态
            assert result.status == ParseStatus.SUCCESS, f"解析状态应该是 SUCCESS，实际: {result.status}"
            logger.success("✓ 解析状态正确")
            
            # 验证基础字段
            assert result.user_id == self.user_id, "user_id 不匹配"
            assert result.file_id == self.file_id, "file_id 不匹配"
            assert result.filename == self.filename, "filename 不匹配"
            assert result.knowledge_base_id == self.knowledge_base_id, "knowledge_base_id 不匹配"
            logger.success("✓ 基础字段验证通过")
            
            # 验证解析统计
            assert result.total_pages > 0, "总页数应该大于 0"
            assert result.parse_tool == "mineru", f"解析工具应该是 mineru，实际: {result.parse_tool}"
            logger.success(f"✓ 解析统计验证通过: {result.total_pages} 页")
            
            # 验证无错误
            assert result.error_message is None or result.error_message == "", f"不应该有错误信息: {result.error_message}"
            logger.success("✓ 无错误信息")
            
            logger.success("=" * 80)
            logger.success("✓ 测试 3 通过: ParseResult 验证成功")
            logger.success("=" * 80)
            
        except AssertionError as e:
            logger.error(f"❌ 测试 3 失败: {e}")
            raise
    
    async def test_04_verify_mysql_messages(self, mysql_messages: List[Dict]):
        """
        测试 4: 验证 MySQL 消息列表
        
        Args:
            mysql_messages: MySQL 消息列表
        """
        logger.info("=" * 80)
        logger.info("测试 4: 验证 MySQL 消息列表")
        logger.info("=" * 80)
        
        try:
            # 验证消息数量
            assert len(mysql_messages) > 0, "MySQL 消息列表不应该为空"
            logger.success(f"✓ MySQL 消息数量: {len(mysql_messages)}")
            
            # 统计元素类型
            type_counts = {}
            for msg in mysql_messages:
                element_type = msg.get("element_type")
                type_counts[element_type] = type_counts.get(element_type, 0) + 1
            
            logger.info(f"\n元素类型统计:")
            for elem_type, count in type_counts.items():
                logger.info(f"  - {elem_type}: {count}")
            
            # 验证必要字段
            required_fields = [
                "element_id", "element_index", "page_index", "element_type",
                "knowledge_base_id", "knowledge_base_name", "creator"
            ]
            
            for i, msg in enumerate(mysql_messages[:3]):  # 检查前3条
                for field in required_fields:
                    assert field in msg, f"消息 {i} 缺少必要字段: {field}"
                
                # 验证 element_id 格式
                assert msg["element_id"].startswith("element_"), f"element_id 格式错误: {msg['element_id']}"
                
                # 验证 element_index
                assert isinstance(msg["element_index"], int), "element_index 应该是整数"
                
                # 验证 knowledge_base_id
                assert msg["knowledge_base_id"] == self.knowledge_base_id, "knowledge_base_id 不匹配"
            
            logger.success("✓ 必要字段验证通过")
            
            # 验证图片元素（如果有）
            image_messages = [msg for msg in mysql_messages if msg.get("element_type") == "image"]
            if image_messages:
                logger.info(f"\n找到 {len(image_messages)} 个图片元素")
                
                # 检查前几个图片元素
                for i, img_msg in enumerate(image_messages[:3]):
                    assert "image_file_path" in img_msg, f"图片消息 {i} 缺少 image_file_path"
                    assert "bucket_name" in img_msg, f"图片消息 {i} 缺少 bucket_name"
                    
                    if img_msg["image_file_path"]:
                        logger.info(f"  图片 {i+1}: {img_msg['bucket_name']}/{img_msg['image_file_path']}")
                        self.created_files.append(f"{img_msg['bucket_name']}/{img_msg['image_file_path']}")
                
                logger.success(f"✓ 图片元素验证通过: {len(image_messages)} 个")
            else:
                logger.warning("⚠ 未找到图片元素")
            
            logger.success("=" * 80)
            logger.success("✓ 测试 4 通过: MySQL 消息验证成功")
            logger.success("=" * 80)
            
        except AssertionError as e:
            logger.error(f"❌ 测试 4 失败: {e}")
            raise
    
    async def test_05_verify_mongodb_messages(self, mongodb_messages: List[Dict]):
        """
        测试 5: 验证 MongoDB 消息列表
        
        Args:
            mongodb_messages: MongoDB 消息列表
        """
        logger.info("=" * 80)
        logger.info("测试 5: 验证 MongoDB 消息列表")
        logger.info("=" * 80)
        
        try:
            # 验证消息数量
            assert len(mongodb_messages) > 0, "MongoDB 消息列表不应该为空"
            logger.success(f"✓ MongoDB 消息数量: {len(mongodb_messages)}")
            
            # 统计元素类型
            type_counts = {}
            for msg in mongodb_messages:
                element_type = msg.get("type")
                type_counts[element_type] = type_counts.get(element_type, 0) + 1
            
            logger.info(f"\n元素类型统计:")
            for elem_type, count in type_counts.items():
                logger.info(f"  - {elem_type}: {count}")
            
            # 验证必要字段
            for i, msg in enumerate(mongodb_messages[:3]):  # 检查前3条
                assert "_id" in msg, f"消息 {i} 缺少 _id 字段"
                assert "type" in msg, f"消息 {i} 缺少 type 字段"
                assert "content" in msg, f"消息 {i} 缺少 content 字段"
                
                # 验证 _id 格式
                assert msg["_id"].startswith("element_"), f"_id 格式错误: {msg['_id']}"
                
                # 验证 content 是字典
                assert isinstance(msg["content"], dict), "content 应该是字典类型"
            
            logger.success("✓ 必要字段验证通过")
            
            # 验证不同类型的内容结构
            text_messages = [msg for msg in mongodb_messages if msg.get("type") == "text"]
            if text_messages:
                # 检查文本内容
                sample = text_messages[0]
                assert "text" in sample["content"], "文本元素应该包含 text 字段"
                logger.success(f"✓ 文本元素验证通过: {len(text_messages)} 个")
            
            image_messages = [msg for msg in mongodb_messages if msg.get("type") == "image"]
            if image_messages:
                # 检查图片内容
                sample = image_messages[0]
                assert "image_caption" in sample["content"], "图片元素应该包含 image_caption 字段"
                assert "image_footnote" in sample["content"], "图片元素应该包含 image_footnote 字段"
                logger.success(f"✓ 图片元素验证通过: {len(image_messages)} 个")
            
            table_messages = [msg for msg in mongodb_messages if msg.get("type") == "table"]
            if table_messages:
                # 检查表格内容
                sample = table_messages[0]
                assert "table_body" in sample["content"], "表格元素应该包含 table_body 字段"
                logger.success(f"✓ 表格元素验证通过: {len(table_messages)} 个")
            
            logger.success("=" * 80)
            logger.success("✓ 测试 5 通过: MongoDB 消息验证成功")
            logger.success("=" * 80)
            
        except AssertionError as e:
            logger.error(f"❌ 测试 5 失败: {e}")
            raise
    
    async def test_06_verify_images_uploaded(self, mysql_messages: List[Dict]):
        """
        测试 6: 验证图片是否成功上传到 MinIO
        
        Args:
            mysql_messages: MySQL 消息列表（包含图片路径信息）
        """
        logger.info("=" * 80)
        logger.info("测试 6: 验证图片上传")
        logger.info("=" * 80)
        
        try:
            # 提取图片元素
            image_messages = [
                msg for msg in mysql_messages 
                if msg.get("element_type") == "image" and msg.get("image_file_path")
            ]
            
            if not image_messages:
                logger.warning("⚠ 未找到已上传的图片，跳过验证")
                logger.info("=" * 80)
                logger.info("✓ 测试 6 跳过: 无图片需要验证")
                logger.info("=" * 80)
                return
            
            logger.info(f"找到 {len(image_messages)} 个已上传的图片")
            
            # 验证每个图片是否存在（最多检查前5个）
            verified_count = 0
            for i, img_msg in enumerate(image_messages[:5]):
                bucket = img_msg.get("bucket_name")
                path = img_msg.get("image_file_path")
                
                if not bucket or not path:
                    logger.warning(f"⚠ 图片 {i+1} 缺少存储路径信息")
                    continue
                
                storage_path = f"{bucket}/{path}"
                
                # 检查文件是否存在
                exists = await self.storage.file_exists(storage_path)
                
                if exists:
                    verified_count += 1
                    logger.success(f"✓ 图片 {i+1} 存在: {storage_path}")
                else:
                    logger.warning(f"⚠ 图片 {i+1} 不存在: {storage_path}")
            
            logger.info(f"\n验证结果: {verified_count}/{min(len(image_messages), 5)} 个图片存在")
            
            if verified_count > 0:
                logger.success("=" * 80)
                logger.success(f"✓ 测试 6 通过: 成功验证 {verified_count} 个图片")
                logger.success("=" * 80)
            else:
                logger.warning("=" * 80)
                logger.warning("⚠ 测试 6 警告: 未能验证任何图片")
                logger.warning("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ 测试 6 失败: {e}", exc_info=True)
            raise
    
    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("=" * 80)
        logger.info(f"FileParserService 端到端测试 ({'Kafka 模式' if self.kafka_mode else 'Service 模式'})")
        logger.info("=" * 80)
        logger.info(f"测试文件: {self.test_pdf}")
        logger.info(f"测试模式: {'Kafka 完整流程' if self.kafka_mode else 'Service 快速测试'}")
        logger.info(f"清理模式: {'启用' if self.cleanup else '禁用（保留文件）'}")
        logger.info("=" * 80)
        
        if self.kafka_mode:
            logger.warning("\n⚠️  Kafka 模式前置条件:")
            logger.warning("1. 确保 FileParserWorker 正在运行")
            logger.warning("   启动命令: uv run python scripts/start_file_parser_worker.py")
            logger.warning("2. 确保 Kafka/MinIO/MinerU 服务正常")
            logger.warning("=" * 80 + "\n")
        
        try:
            # 设置环境
            await self.setup()
            
            # 测试 1: 上传 PDF
            storage_path = await self.test_01_upload_pdf_to_minio()
            
            # 测试 2: 解析文件
            result, mysql_messages, mongodb_messages = await self.test_02_parse_file(storage_path)
            
            # 测试 3: 验证 ParseResult
            await self.test_03_verify_parse_result(result)
            
            # 测试 4: 验证 MySQL 消息
            await self.test_04_verify_mysql_messages(mysql_messages)
            
            # 测试 5: 验证 MongoDB 消息
            await self.test_05_verify_mongodb_messages(mongodb_messages)
            
            # 测试 6: 验证图片上传
            await self.test_06_verify_images_uploaded(mysql_messages)
            
            # 所有测试通过
            logger.success("\n" + "=" * 80)
            logger.success("🎉 所有测试通过！")
            logger.success("=" * 80)
            
        except Exception as e:
            logger.error("\n" + "=" * 80)
            logger.error(f"❌ 测试失败: {e}")
            logger.error("=" * 80)
            raise
            
        finally:
            # 清理环境
            await self.teardown()


async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="FileParserService 端到端测试")
    parser.add_argument(
        "--kafka",
        action="store_true",
        help="启用 Kafka 模式（需要先启动 Worker）"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="测试后清理所有文件"
    )
    
    args = parser.parse_args()
    
    # 创建测试实例
    test = FileParserServiceE2ETest(
        cleanup=args.cleanup,
        kafka_mode=args.kafka
    )
    
    try:
        await test.run_all_tests()
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
