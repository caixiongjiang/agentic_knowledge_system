#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_split_service_e2e.py
@Author  : caixiongjiang
@Date    : 2026/02/06
@Function: 
    SplitService 端到端测试
    
    测试流程:
    1. 创建模拟的 ParseResult 数据（Element 数据）
    2. 将数据插入到 MySQL 和 MongoDB
    3. 调用 SplitService 进行切分
    4. 验证 SplitResult（Section 和 Chunk）
    5. 生成 Kafka 消息（db_write 消息 + split_end 消息）
    6. 验证消息格式
    7. 清理测试数据
    
    用法:
        # 基础测试
        uv run python test/service/knowledge/components/test_split_service_e2e.py
        
        # 保留测试数据（用于调试）
        uv run python test/service/knowledge/components/test_split_service_e2e.py --no-cleanup
        
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import asyncio
import json
import uuid
import argparse
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.service.knowledge.components.text_splitter_service import TextSplitterService
from src.index.common_file_extract.splitter.models import SplitConfig, SplitMethod
from src.types.models.parse_result import ParseResult, ElementInfo, ElementType, ParseStatus
from src.types.models.split_result import SplitResult, SplitStatus, ChunkType

# 数据库相关
from src.db.mysql.connection import get_mysql_manager
from src.db.mysql.repositories.base.element_meta_info_repo import element_meta_info_repo
from src.db.mongodb import get_mongodb_manager
from src.db.mongodb.repositories.element_data_repository import element_data_repository


class TextSplitterServiceE2ETest:
    """
    TextSplitterService 端到端测试
    
    核心功能:
    - 创建模拟的 Element 数据
    - 测试数据库读取
    - 测试文本切分
    - 测试 Kafka 消息生成
    """
    
    def __init__(self, cleanup: bool = True):
        """
        初始化测试
        
        Args:
            cleanup: 是否在测试后清理数据（默认 True）
        """
        self.cleanup = cleanup
        
        # 测试参数
        self.user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        self.session_id = f"session_{uuid.uuid4().hex[:8]}"
        self.file_id = f"file_{uuid.uuid4().hex[:8]}"
        self.document_id = f"doc_{uuid.uuid4().hex[:8]}"
        self.knowledge_base_id = f"kb_{uuid.uuid4().hex[:8]}"
        self.knowledge_base_name = "测试知识库_Split"
        self.filename = "test_document.pdf"
        
        # 服务
        self.split_service = None
        self.mysql_manager = None
        self.mysql_session = None
        self.mysql_session_context = None  # 保存上下文管理器
        
        # 测试数据
        self.created_element_ids = []
        
        logger.info(f"端到端测试初始化完成 (cleanup={cleanup})")
        logger.info(f"测试参数: user_id={self.user_id}, file_id={self.file_id}")
    
    async def setup(self):
        """初始化测试环境"""
        logger.info("=" * 80)
        logger.info("设置测试环境")
        logger.info("=" * 80)
        
        # 创建 MySQL Manager 并初始化数据库
        self.mysql_manager = get_mysql_manager()
        logger.success("✓ MySQL Manager 创建成功")
        
        # 初始化数据库表（如果需要）
        try:
            self.mysql_manager.init_db()
            logger.success("✓ 数据库表初始化成功")
        except Exception as e:
            # 如果表已存在，忽略错误
            logger.debug(f"数据库表可能已存在: {e}")
        
        # 创建 MySQL Session（使用上下文管理器）
        self.mysql_session_context = self.mysql_manager.get_session()
        self.mysql_session = self.mysql_session_context.__enter__()
        logger.success("✓ MySQL Session 创建成功")
        
        # 创建 TextSplitterService
        config = SplitConfig(
            split_method=SplitMethod.STRUCTURE_FIRST,
            chunk_size=800,
            chunk_overlap=100,
            enable_text_cleaning=True,
            enable_smart_table_split=True
        )
        self.split_service = TextSplitterService(config)
        logger.success("✓ TextSplitterService 初始化成功")
        
        # 初始化 MongoDB（使用 get_mongodb_manager）
        await get_mongodb_manager()
        logger.success("✓ MongoDB 初始化成功")
    
    async def teardown(self):
        """清理测试环境"""
        logger.info("=" * 80)
        logger.info("清理测试环境")
        logger.info("=" * 80)
        
        if self.cleanup:
            # 清理 MySQL 数据
            if self.mysql_session and self.created_element_ids:
                logger.info(f"清理 MySQL 中的 {len(self.created_element_ids)} 个 Element...")
                for element_id in self.created_element_ids:
                    element_meta_info_repo.delete(self.mysql_session, element_id, updater=self.user_id)
                self.mysql_session.commit()
                logger.success(f"✓ 清理了 {len(self.created_element_ids)} 个 Element")
            
            # 清理 MongoDB 数据
            if self.created_element_ids:
                logger.info(f"清理 MongoDB 中的 {len(self.created_element_ids)} 个 Element...")
                for element_id in self.created_element_ids:
                    await element_data_repository.delete(element_id, updater=self.user_id)
                logger.success(f"✓ 清理了 {len(self.created_element_ids)} 个 Element")
        else:
            logger.warning("⚠ 跳过清理，测试数据已保留")
        
        # 关闭 MySQL Session（使用上下文管理器的 __exit__）
        if self.mysql_session_context and self.mysql_session:
            try:
                self.mysql_session_context.__exit__(None, None, None)
                logger.success("✓ MySQL Session 已关闭")
            except Exception as e:
                logger.warning(f"关闭 MySQL Session 时出错: {e}")
        
        # 关闭 MySQL Manager
        if self.mysql_manager:
            self.mysql_manager.close()
            logger.success("✓ MySQL Manager 已关闭")
        
        logger.success("测试环境清理完成")
    
    def create_mock_elements(self) -> List[ElementInfo]:
        """
        创建模拟的 Element 数据
        
        包含：
        - 1个标题（H1）
        - 2个文本段落（较长，会被切分）
        - 1个表格
        - 1个图片
        
        Returns:
            ElementInfo 列表
        """
        logger.info("创建模拟的 Element 数据...")
        
        elements = []
        
        # Element 1: 标题
        element_id_1 = f"element-{uuid.uuid4()}"
        elements.append(ElementInfo(
            element_id=element_id_1,
            element_type=ElementType.TEXT,
            element_index=0,
            page_index=0,
            page_position=[50.0, 100.0, 500.0, 50.0],
            text="第一章 引言",
            text_level=1,  # H1 标题
        ))
        
        # Element 2: 长文本段落（会被切分成多个 Chunk）
        element_id_2 = f"element-{uuid.uuid4()}"
        long_text = (
            "人工智能（Artificial Intelligence, AI）是计算机科学的一个分支，"
            "致力于创造能够执行通常需要人类智能的任务的系统。" * 20  # 重复20次，确保超过 chunk_size
        )
        elements.append(ElementInfo(
            element_id=element_id_2,
            element_type=ElementType.TEXT,
            element_index=1,
            page_index=0,
            page_position=[50.0, 200.0, 500.0, 100.0],
            text=long_text,
            text_level=0,  # 普通文本
        ))
        
        # Element 3: 第二段文本
        element_id_3 = f"element-{uuid.uuid4()}"
        text_2 = (
            "深度学习是机器学习的一个子领域，它使用多层神经网络来学习数据的表示。"
            "深度学习在图像识别、语音识别、自然语言处理等领域取得了显著的成功。" * 10
        )
        elements.append(ElementInfo(
            element_id=element_id_3,
            element_type=ElementType.TEXT,
            element_index=2,
            page_index=0,
            page_position=[50.0, 350.0, 500.0, 80.0],
            text=text_2,
            text_level=0,
        ))
        
        # Element 4: 表格
        element_id_4 = f"element-{uuid.uuid4()}"
        table_body = """
| 框架 | 开发者 | 语言 | 发布年份 |
|------|--------|------|----------|
| TensorFlow | Google | Python/C++ | 2015 |
| PyTorch | Meta | Python/C++ | 2016 |
| JAX | Google | Python | 2018 |
        """
        elements.append(ElementInfo(
            element_id=element_id_4,
            element_type=ElementType.TABLE,
            element_index=3,
            page_index=1,
            page_position=[50.0, 100.0, 500.0, 150.0],
            table_body=table_body,
            table_caption="表1: 主流深度学习框架对比",
            table_footnote="数据来源：各框架官方网站",
        ))
        
        # Element 5: 图片
        element_id_5 = f"element-{uuid.uuid4()}"
        elements.append(ElementInfo(
            element_id=element_id_5,
            element_type=ElementType.IMAGE,
            element_index=4,
            page_index=1,
            page_position=[50.0, 300.0, 400.0, 300.0],
            bucket_name="test-bucket",
            image_file_path=f"/images/{self.file_id}/image_001.png",
            image_file_name="image_001.png",
            image_file_type="png",
            image_file_format="PNG",
            image_file_suffix=".png",
            image_caption="图1: 神经网络结构示意图",
            image_footnote="图片来源：测试数据",
        ))
        
        # 记录创建的 Element IDs
        self.created_element_ids = [e.element_id for e in elements]
        
        logger.success(f"✓ 创建了 {len(elements)} 个模拟 Element")
        for i, elem in enumerate(elements, 1):
            logger.debug(f"  Element {i}: {elem.element_type}, index={elem.element_index}")
        
        return elements
    
    async def insert_elements_to_db(self, elements: List[ElementInfo]):
        """
        将 Element 数据插入到数据库
        
        Args:
            elements: Element 列表
        """
        logger.info("将 Element 数据插入到数据库...")
        
        for element in elements:
            # 插入到 MySQL (element_meta_info)
            mysql_data = {
                "element_id": element.element_id,
                "element_type": element.element_type,  # ElementType 继承自 str，直接使用
                "element_index": element.element_index,
                "page_index": element.page_index,
                "page_position": str(element.page_position) if element.page_position else None,
                "text_level": element.text_level,
                # 知识库信息
                "knowledge_base_id": self.knowledge_base_id,
                "knowledge_base_name": self.knowledge_base_name,
                "status": 0,  # Integer: 0=正常
                "creator": self.user_id,
                "deleted": 0,  # Integer: 0=未删除
            }
            
            # 图片特定字段（仅 MinIO 存储信息，不包括 caption）
            if element.element_type == ElementType.IMAGE:
                mysql_data.update({
                    "bucket_name": element.bucket_name,
                    "image_file_path": element.image_file_path,
                    "image_file_name": element.image_file_name,
                    "image_file_type": element.image_file_type,
                    "image_file_format": element.image_file_format,
                    "image_file_suffix": element.image_file_suffix,
                })
            
            # 表格没有特定的 MySQL 字段，内容都在 MongoDB 中
            
            element_meta_info_repo.create(self.mysql_session, **mysql_data)
            
            # 插入到 MongoDB (element_data)
            # 注意：根据 MongoDB 模型，caption 和 footnote 字段都是 List[str]
            content = {}
            if element.element_type == ElementType.TEXT:
                content["text"] = element.text
            elif element.element_type == ElementType.TABLE:
                content["table_body"] = element.table_body
                # 转换为列表格式
                content["table_caption"] = [element.table_caption] if element.table_caption else []
                content["table_footnote"] = [element.table_footnote] if element.table_footnote else []
            elif element.element_type == ElementType.IMAGE:
                # 转换为列表格式
                content["image_caption"] = [element.image_caption] if element.image_caption else []
                content["image_footnote"] = [element.image_footnote] if element.image_footnote else []
            
            # MongoDB create() 方法使用关键字参数
            await element_data_repository.create(
                creator=self.user_id,
                _id=element.element_id,
                type=element.element_type,
                content=content
            )
        
        self.mysql_session.commit()
        logger.success(f"✓ 成功插入 {len(elements)} 个 Element 到数据库")
    
    async def test_load_from_db(self) -> ParseResult:
        """
        测试从数据库加载 ParseResult
        
        Returns:
            ParseResult
        """
        logger.info("-" * 80)
        logger.info("测试1: 从数据库加载 ParseResult")
        logger.info("-" * 80)
        
        parse_result = await self.split_service.load_parse_result_from_db(
            user_id=self.user_id,
            file_id=self.file_id,
            mysql_session=self.mysql_session,
            knowledge_base_id=self.knowledge_base_id
        )
        
        # 验证
        assert parse_result is not None, "ParseResult 不应为 None"
        assert parse_result.user_id == self.user_id
        assert parse_result.file_id == self.file_id
        assert len(parse_result.elements) == 5, f"应该有5个元素，实际有{len(parse_result.elements)}个"
        
        logger.success("✓ 成功从数据库加载 ParseResult")
        logger.info(f"  - user_id: {parse_result.user_id}")
        logger.info(f"  - file_id: {parse_result.file_id}")
        logger.info(f"  - elements: {len(parse_result.elements)}")
        
        return parse_result
    
    async def test_split_document(self, parse_result: ParseResult) -> SplitResult:
        """
        测试文档切分
        
        Args:
            parse_result: ParseResult
        
        Returns:
            SplitResult
        """
        logger.info("-" * 80)
        logger.info("测试2: 执行文档切分")
        logger.info("-" * 80)
        
        split_result = await self.split_service.split_document(
            parse_result=parse_result,
            document_id=self.document_id
        )
        
        # 验证
        assert split_result is not None, "SplitResult 不应为 None"
        assert split_result.status == SplitStatus.SUCCESS, f"切分状态应为 SUCCESS，实际为 {split_result.status}"
        assert len(split_result.sections) > 0, "应该至少有1个 Section"
        assert len(split_result.chunks) > 0, "应该至少有1个 Chunk"
        
        logger.success("✓ 文档切分成功")
        logger.info(f"  - status: {split_result.status}")
        logger.info(f"  - sections: {len(split_result.sections)}")
        logger.info(f"  - chunks: {len(split_result.chunks)}")
        logger.info(f"  - total_chars: {split_result.total_chars}")
        
        # 详细信息
        logger.info("\n  Section 列表:")
        for i, section in enumerate(split_result.sections, 1):
            logger.info(f"    {i}. {section.section_id[:20]}... | level={section.level} | content={section.content[:30]}...")
        
        logger.info("\n  Chunk 列表:")
        chunk_type_count = {}
        for chunk in split_result.chunks:
            chunk_type_count[chunk.chunk_type] = chunk_type_count.get(chunk.chunk_type, 0) + 1
        
        for chunk_type, count in chunk_type_count.items():
            logger.info(f"    {chunk_type}: {count} 个")
        
        return split_result
    
    def test_generate_kafka_messages(self, split_result: SplitResult):
        """
        测试生成 Kafka 消息
        
        Args:
            split_result: SplitResult
        """
        logger.info("-" * 80)
        logger.info("测试3: 生成 Kafka 消息")
        logger.info("-" * 80)
        
        # 1. 生成 MySQL 写入消息（Section 和 Chunk 元信息）
        mysql_messages = self.generate_mysql_write_messages(split_result)
        logger.success(f"✓ 生成 MySQL 写入消息: {len(mysql_messages)} 条")
        
        # 2. 生成 MongoDB 写入消息（Section 和 Chunk 内容数据）
        mongodb_messages = self.generate_mongodb_write_messages(split_result)
        logger.success(f"✓ 生成 MongoDB 写入消息: {len(mongodb_messages)} 条")
        
        # 3. 生成 Embedding 写入消息（Chunk 向量化）
        embedding_message = self.generate_embedding_write_message(split_result)
        logger.success(f"✓ 生成 Embedding 写入消息: {len(embedding_message['items'])} 个待向量化项")
        
        # 4. 生成 SplitEnd 消息
        split_end_message = self.generate_split_end_message(split_result)
        logger.success("✓ 生成 SplitEnd 消息")
        
        # 验证消息格式
        self.validate_messages(mysql_messages, mongodb_messages, embedding_message, split_end_message)
    
    def generate_mysql_write_messages(self, split_result: SplitResult) -> List[Dict[str, Any]]:
        """生成 MySQL 写入消息"""
        messages = []
        
        # Section 元信息
        for section in split_result.sections:
            messages.append({
                "table": "section_meta_info",
                "data": section.to_mysql_dict()
            })
        
        # Chunk 元信息
        for chunk in split_result.chunks:
            messages.append({
                "table": "chunk_meta_info",
                "data": chunk.to_mysql_dict()
            })
        
        return messages
    
    def generate_mongodb_write_messages(self, split_result: SplitResult) -> List[Dict[str, Any]]:
        """生成 MongoDB 写入消息"""
        messages = []
        
        # Section 内容数据
        for section in split_result.sections:
            messages.append({
                "collection": "section_data",
                "data": section.to_mongodb_dict()
            })
        
        # Chunk 内容数据
        for chunk in split_result.chunks:
            messages.append({
                "collection": "chunk_data",
                "data": chunk.to_mongodb_dict()
            })
        
        return messages
    
    def generate_embedding_write_message(self, split_result: SplitResult) -> Dict[str, Any]:
        """生成 Embedding 写入消息"""
        items = []
        
        # 只处理文本类型的 Chunk
        for chunk in split_result.chunks:
            if chunk.chunk_type in [ChunkType.TEXT, ChunkType.TABLE]:
                items.append(chunk.to_embedding_message_dict())
        
        return {
            "user_id": split_result.user_id,
            "file_id": split_result.file_id,
            "collection_type": "chunk",
            "items": items,
            "batch_size": 100,
            "priority": 3,
            "source_stage": "split_end",
            "need_embedding": True,
            "language": "zh"  # 默认语言为中文，实际应从文档信息中获取
        }
    
    def generate_split_end_message(self, split_result: SplitResult) -> Dict[str, Any]:
        """生成 SplitEnd 消息"""
        # 准备 chunks 数据
        chunks_data = []
        for chunk in split_result.chunks:
            chunk_dict = {
                "chunk_id": chunk.chunk_id,
                "chunk_type": chunk.chunk_type,
                "content": chunk.content,
                "page_index": chunk.page_index,
                "section_id": chunk.section_id,
                "element_ids": chunk.element_ids,
            }
            chunks_data.append(chunk_dict)
        
        return {
            "user_id": split_result.user_id,
            "file_id": split_result.file_id,
            "chunks": chunks_data,
            "split_strategy": "structure_first",
            "chunk_stats": {
                "total_chunks": len(split_result.chunks),
                "total_sections": len(split_result.sections),
                "text_chunks": sum(1 for c in split_result.chunks if c.chunk_type == ChunkType.TEXT),
                "table_chunks": sum(1 for c in split_result.chunks if c.chunk_type == ChunkType.TABLE),
                "image_chunks": sum(1 for c in split_result.chunks if c.chunk_type == ChunkType.IMAGE),
            },
            "total_length": split_result.total_chars,
            "language": "zh",  # 默认语言为中文，实际应从文档信息中获取
            "frontend_complete": True,
        }
    
    def validate_messages(
        self,
        mysql_messages: List[Dict[str, Any]],
        mongodb_messages: List[Dict[str, Any]],
        embedding_message: Dict[str, Any],
        split_end_message: Dict[str, Any]
    ):
        """验证消息格式"""
        logger.info("\n验证消息格式...")
        
        # 验证 MySQL 消息
        assert len(mysql_messages) > 0, "应该有 MySQL 写入消息"
        for msg in mysql_messages:
            assert "table" in msg, "MySQL 消息应包含 table 字段"
            assert "data" in msg, "MySQL 消息应包含 data 字段"
            assert msg["table"] in ["section_meta_info", "chunk_meta_info"]
        logger.success("  ✓ MySQL 消息格式正确")
        
        # 验证 MongoDB 消息
        assert len(mongodb_messages) > 0, "应该有 MongoDB 写入消息"
        for msg in mongodb_messages:
            assert "collection" in msg, "MongoDB 消息应包含 collection 字段"
            assert "data" in msg, "MongoDB 消息应包含 data 字段"
            assert msg["collection"] in ["section_data", "chunk_data"]
        logger.success("  ✓ MongoDB 消息格式正确")
        
        # 验证 Embedding 消息
        assert len(embedding_message["items"]) > 0, "应该有待向量化的项"
        assert embedding_message["collection_type"] == "chunk"
        assert embedding_message["source_stage"] == "split_end"
        logger.success("  ✓ Embedding 消息格式正确")
        
        # 验证 SplitEnd 消息
        assert len(split_end_message["chunks"]) > 0, "应该有 chunks"
        assert split_end_message["chunk_stats"]["total_chunks"] > 0
        assert split_end_message["chunk_stats"]["total_sections"] > 0
        logger.success("  ✓ SplitEnd 消息格式正确")
        
        # 打印消息示例
        logger.info("\n消息示例:")
        logger.info(f"\n  MySQL 消息示例 (共{len(mysql_messages)}条):")
        logger.info(json.dumps(mysql_messages[0], indent=2, ensure_ascii=False)[:500] + "...")
        
        logger.info(f"\n  MongoDB 消息示例 (共{len(mongodb_messages)}条):")
        logger.info(json.dumps(mongodb_messages[0], indent=2, ensure_ascii=False)[:500] + "...")
        
        logger.info(f"\n  Embedding 消息:")
        logger.info(json.dumps(embedding_message, indent=2, ensure_ascii=False)[:800] + "...")
        
        logger.info(f"\n  SplitEnd 消息:")
        logger.info(json.dumps(split_end_message, indent=2, ensure_ascii=False)[:1000] + "...")
    
    async def run(self):
        """运行完整测试"""
        try:
            # 设置环境
            await self.setup()
            
            # 创建模拟数据
            elements = self.create_mock_elements()
            await self.insert_elements_to_db(elements)
            
            # 测试1: 从数据库加载
            parse_result = await self.test_load_from_db()
            
            # 测试2: 执行切分
            split_result = await self.test_split_document(parse_result)
            
            # 测试3: 生成 Kafka 消息
            self.test_generate_kafka_messages(split_result)
            
            # 测试成功
            logger.info("=" * 80)
            logger.success("✅ 所有测试通过！")
            logger.info("=" * 80)
            
            # 测试总结
            logger.info("\n测试总结:")
            logger.info(f"  - 创建 Elements: {len(elements)}")
            logger.info(f"  - 生成 Sections: {len(split_result.sections)}")
            logger.info(f"  - 生成 Chunks: {len(split_result.chunks)}")
            logger.info(f"  - 总字符数: {split_result.total_chars}")
            logger.info(f"  - 切分方法: {self.split_service.config.split_method}")
            logger.info(f"  - Chunk 大小: {self.split_service.config.chunk_size}")
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            # 清理环境
            await self.teardown()


async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="TextSplitterService 端到端测试")
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="不清理测试数据（用于调试）"
    )
    args = parser.parse_args()
    
    # 运行测试
    test = TextSplitterServiceE2ETest(cleanup=not args.no_cleanup)
    await test.run()


if __name__ == "__main__":
    asyncio.run(main())
