#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_file_parser.py
@Author  : caixiongjiang
@Date    : 2026/01/18
@Function: 
    FileParser 功能测试 - 验证文件解析和数据存储
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import sys
import asyncio
from datetime import datetime

from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

from src.client.mineru import Mineru2Client
from src.index.common_file_extract.parser.pdf_parser import PDFParser
from src.index.common_file_extract.parser.file_parser import FileParser
from src.db.mysql.connection import MySQLServerManager
from src.db.mysql.models.base.element_meta_info import ElementMetaInfo
from src.db.mysql.models.base_model import Base
from src.db.mongodb import MongoDBManager
from src.db.mongodb.models.element_data import ElementData
from src.utils.env_manager import get_env_manager
from src.utils.config_manager import get_config_manager


async def setup_mongodb():
    """
    初始化 MongoDB 连接
    使用 MongoDBManager 自动从环境变量和配置文件读取配置
    """
    # 使用 MongoDBManager 初始化（自动读取配置和认证信息）
    manager = await MongoDBManager.get_instance()
    
    logger.info(f"✅ MongoDB 连接成功: {manager.database_name}")
    logger.info(f"   主机: {manager.host}:{manager.port}")
    if manager.username:
        logger.info(f"   认证用户: {manager.username}")
    
    return manager


def create_mysql_tables(mysql_manager, drop_existing=True):
    """
    创建 MySQL 表结构
    
    :param mysql_manager: MySQL 管理器实例
    :param drop_existing: 是否删除已存在的表（默认 True，用于测试环境）
    """
    try:
        logger.info("📋 检查并创建 MySQL 表结构...")
        
        if drop_existing:
            logger.warning("⚠️  测试模式：将删除已存在的表")
            # 删除所有表（注意：这会删除数据！）
            Base.metadata.drop_all(mysql_manager.engine)
            logger.info("✅ 旧表已删除")
        
        # 创建所有表
        Base.metadata.create_all(mysql_manager.engine)
        
        logger.info("✅ MySQL 表结构创建完成")
        
    except Exception as e:
        logger.error(f"❌ 创建 MySQL 表结构失败: {e}")
        raise


async def cleanup_test_data(mysql_manager, test_knowledge_base_id: str):
    """清理测试数据"""
    try:
        # 清理 MySQL 测试数据
        with mysql_manager.get_session() as session:
            session.query(ElementMetaInfo).filter(
                ElementMetaInfo.knowledge_base_id == test_knowledge_base_id
            ).delete()
            session.commit()
            logger.info(f"✅ MySQL 测试数据清理完成")
        
        # 清理 MongoDB 测试数据
        await ElementData.find().delete()
        logger.info(f"✅ MongoDB 测试数据清理完成")
        
    except Exception as e:
        logger.error(f"❌ 清理测试数据失败: {e}")


async def test_parse_and_store(file_parser: FileParser, test_pdf: Path, knowledge_base_info: dict):
    """
    测试1: 解析文件并存储到数据库
    
    验证：
    1. 文件成功解析
    2. 数据成功存储到 MySQL
    3. 数据成功存储到 MongoDB
    4. 统计信息正确
    """
    logger.info("=" * 80)
    logger.info("测试1: 文件解析与存储")
    logger.info("=" * 80)
    
    try:
        # 执行解析和存储
        result = await file_parser.parse_and_store(
            file_path=test_pdf,
            knowledge_base_info=knowledge_base_info,
            creator="test_user",
            store_images=False  # 暂不测试图片存储
        )
        
        logger.info(f"\n📊 解析结果:")
        logger.info(f"  状态: {result['status']}")
        logger.info(f"  文件名: {result['file_name']}")
        logger.info(f"  文件类型: {result['file_type']}")
        logger.info(f"  总页数: {result['total_pages']}")
        logger.info(f"  总元素数: {result['total_elements']}")
        logger.info(f"  元素类型分布:")
        for elem_type, count in result['elements_by_type'].items():
            logger.info(f"    - {elem_type}: {count}")
        logger.info(f"  MySQL 存储: {result['stored_mysql']} 条")
        logger.info(f"  MongoDB 存储: {result['stored_mongodb']} 条")
        
        # 断言基本验证
        assert result['status'] == 'success', "解析状态应为 success"
        assert result['total_elements'] > 0, "应至少有一个元素"
        assert result['stored_mysql'] == result['total_elements'], "MySQL 存储数量应等于总元素数"
        assert result['stored_mongodb'] == result['total_elements'], "MongoDB 存储数量应等于总元素数"
        
        logger.info("\n✅✅✅ 测试1通过！")
        return result
        
    except Exception as e:
        logger.error(f"\n❌ 测试1失败")
        logger.error(f"错误: {e}")
        import traceback
        traceback.print_exc()
        raise


async def test_verify_mysql_data(
    mysql_manager, 
    knowledge_base_id: str,
    expected_count: int
):
    """
    测试2: 验证 MySQL 数据完整性
    
    验证：
    1. 记录数量正确
    2. 必填字段不为空
    3. 知识库信息正确
    4. 关系字段正确
    """
    logger.info("\n" + "=" * 80)
    logger.info("测试2: 验证 MySQL 数据")
    logger.info("=" * 80)
    
    try:
        # 查询所有测试数据
        with mysql_manager.get_session() as session:
            records = session.query(ElementMetaInfo).filter(
                ElementMetaInfo.knowledge_base_id == knowledge_base_id
            ).all()
        
        logger.info(f"\n📊 MySQL 数据验证:")
        logger.info(f"  预期记录数: {expected_count}")
        logger.info(f"  实际记录数: {len(records)}")
        
        # 验证记录数
        assert len(records) == expected_count, f"记录数不匹配: 期望 {expected_count}, 实际 {len(records)}"
        
        # 验证每条记录
        element_types = {}
        for record in records:
            # 验证必填字段
            assert record.element_id is not None, "element_id 不能为空"
            assert record.element_type is not None, "element_type 不能为空"
            assert record.knowledge_base_id == knowledge_base_id, "knowledge_base_id 不匹配"
            assert record.creator == "test_user", "creator 不匹配"
            assert record.status == 0, "status 应为 0（正常）"
            assert record.deleted == 0, "deleted 应为 0"
            
            # 统计元素类型
            element_types[record.element_type] = element_types.get(record.element_type, 0) + 1
            
            # 验证类型特定字段
            if record.element_type == "text":
                # text_level 可以为 None（普通段落）或 >= 1（标题等有层级的文本）
                if record.text_level is not None:
                    assert record.text_level >= 1, \
                        f"text 类型元素 {record.element_id} 的 text_level 应该 >= 1, 实际: {record.text_level}"
            
            if record.element_type == "image":
                # image 类型应有图片相关字段
                pass  # 暂时图片字段可能为空
        
            logger.info(f"\n  元素类型分布:")
            for elem_type, count in element_types.items():
                logger.info(f"    - {elem_type}: {count}")
            
            logger.info(f"\n  ✅ 所有记录字段验证通过")
            logger.info(f"  ✅ 知识库信息验证通过")
            logger.info(f"  ✅ 状态字段验证通过")
        
        logger.info("\n✅✅✅ 测试2通过！")
        
    except Exception as e:
        logger.error(f"\n❌ 测试2失败")
        logger.error(f"错误: {e}")
        import traceback
        traceback.print_exc()
        raise


async def test_verify_mongodb_data(expected_count: int):
    """
    测试3: 验证 MongoDB 数据完整性
    
    验证：
    1. 记录数量正确
    2. 内容字段完整
    3. 不同类型元素的内容结构正确
    """
    logger.info("\n" + "=" * 80)
    logger.info("测试3: 验证 MongoDB 数据")
    logger.info("=" * 80)
    
    try:
        # 查询所有记录
        records = await ElementData.find().to_list()
        
        logger.info(f"\n📊 MongoDB 数据验证:")
        logger.info(f"  预期记录数: {expected_count}")
        logger.info(f"  实际记录数: {len(records)}")
        
        # 验证记录数
        assert len(records) == expected_count, f"记录数不匹配: 期望 {expected_count}, 实际 {len(records)}"
        
        # 验证每条记录
        element_types = {}
        text_count = 0
        image_count = 0
        table_count = 0
        
        for record in records:
            # 验证必填字段
            assert record.id is not None, "id 不能为空"
            assert record.type is not None, "type 不能为空"
            assert record.content is not None, "content 不能为空"
            
            # 统计类型
            element_types[record.type] = element_types.get(record.type, 0) + 1
            
            # 验证内容结构
            if record.type == "text":
                text_count += 1
                assert "text" in record.content, "text 类型应包含 text 字段"
                assert isinstance(record.content["text"], str), "text 字段应为字符串"
                
            elif record.type == "image":
                image_count += 1
                assert "image_caption" in record.content, "image 类型应包含 image_caption 字段"
                assert "image_footnote" in record.content, "image 类型应包含 image_footnote 字段"
                
            elif record.type == "table":
                table_count += 1
                assert "table_caption" in record.content, "table 类型应包含 table_caption 字段"
                assert "table_footnote" in record.content, "table 类型应包含 table_footnote 字段"
                assert "table_body" in record.content, "table 类型应包含 table_body 字段"
        
        logger.info(f"\n  元素类型分布:")
        for elem_type, count in element_types.items():
            logger.info(f"    - {elem_type}: {count}")
        
        logger.info(f"\n  ✅ 所有记录字段验证通过")
        logger.info(f"  ✅ 内容结构验证通过")
        logger.info(f"  ✅ text 类型: {text_count} 条")
        logger.info(f"  ✅ image 类型: {image_count} 条")
        logger.info(f"  ✅ table 类型: {table_count} 条")
        
        # 显示示例数据
        if text_count > 0:
            text_sample = await ElementData.find_one({"type": "text"})
            logger.info(f"\n  📄 Text 元素示例:")
            logger.info(f"    ID: {text_sample.id}")
            text_content = text_sample.content.get("text", "")
            preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
            logger.info(f"    内容: {preview}")
        
        logger.info("\n✅✅✅ 测试3通过！")
        
    except Exception as e:
        logger.error(f"\n❌ 测试3失败")
        logger.error(f"错误: {e}")
        import traceback
        traceback.print_exc()
        raise


async def test_data_consistency(mysql_manager, knowledge_base_id: str):
    """
    测试4: 验证 MySQL 和 MongoDB 数据一致性
    
    验证：
    1. 两个数据库的记录数一致
    2. element_id 完全对应
    3. element_type 一致
    """
    logger.info("\n" + "=" * 80)
    logger.info("测试4: 验证数据一致性")
    logger.info("=" * 80)
    
    try:
        # 查询 MySQL 数据
        with mysql_manager.get_session() as session:
            mysql_records = session.query(ElementMetaInfo).filter(
                ElementMetaInfo.knowledge_base_id == knowledge_base_id
            ).all()
        
            # 查询 MongoDB 数据
            mongodb_records = await ElementData.find().to_list()
            
            logger.info(f"\n📊 数据一致性验证:")
            logger.info(f"  MySQL 记录数: {len(mysql_records)}")
            logger.info(f"  MongoDB 记录数: {len(mongodb_records)}")
            
            # 验证数量一致
            assert len(mysql_records) == len(mongodb_records), "两个数据库的记录数应该一致"
            
            # 构建 MongoDB 的 ID 集合
            mongodb_ids = {record.id for record in mongodb_records}
            mongodb_type_map = {record.id: record.type for record in mongodb_records}
            
            # 验证每个 MySQL 记录在 MongoDB 中都存在
            missing_ids = []
            type_mismatch = []
            
            for mysql_record in mysql_records:
                if mysql_record.element_id not in mongodb_ids:
                    missing_ids.append(mysql_record.element_id)
                elif mysql_record.element_type != mongodb_type_map[mysql_record.element_id]:
                    type_mismatch.append({
                        "element_id": mysql_record.element_id,
                        "mysql_type": mysql_record.element_type,
                        "mongodb_type": mongodb_type_map[mysql_record.element_id]
                    })
            
            if missing_ids:
                logger.error(f"  ❌ MongoDB 缺失的 ID: {missing_ids[:5]}...")
                raise AssertionError(f"MongoDB 缺失 {len(missing_ids)} 条记录")
            
            if type_mismatch:
                logger.error(f"  ❌ 类型不匹配: {type_mismatch[:5]}...")
                raise AssertionError(f"发现 {len(type_mismatch)} 条类型不匹配的记录")
            
            logger.info(f"  ✅ 记录数量一致: {len(mysql_records)} 条")
            logger.info(f"  ✅ 所有 element_id 对应")
            logger.info(f"  ✅ 所有 element_type 一致")
        
        logger.info("\n✅✅✅ 测试4通过！")
        
    except Exception as e:
        logger.error(f"\n❌ 测试4失败")
        logger.error(f"错误: {e}")
        import traceback
        traceback.print_exc()
        raise


async def main():
    """主测试流程"""
    logger.info("\n" + "=" * 80)
    logger.info("# FileParser 数据存储测试")
    logger.info("=" * 80)
    
    # 测试文件
    test_pdf = Path("tmp_files/pdf/demo1.pdf")
    if not test_pdf.exists():
        logger.error(f"❌ 测试文件不存在: {test_pdf}")
        logger.error("   请将测试 PDF 文件放到 tmp_files/pdf/ 目录")
        return
    
    # 知识库信息（测试用）
    test_knowledge_base_id = f"test_kb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    knowledge_base_info = {
        "knowledge_base_id": test_knowledge_base_id,
        "knowledge_base_name": "测试知识库",
        "parent_knowledge_base_id": None,
        "parent_knowledge_base_name": None,
        "knowledge_type": "common_file"
    }
    
    # 初始化组件
    mongodb_manager = None
    mysql_manager = None
    
    try:
        # 1. 初始化 MongoDB
        logger.info("\n📦 初始化 MongoDB...")
        mongodb_manager = await setup_mongodb()
        
        # 2. 初始化 MySQL
        logger.info("📦 初始化 MySQL...")
        mysql_manager = MySQLServerManager()
        logger.info("✅ MySQL 连接成功")
        
        # 2.1 创建表结构
        create_mysql_tables(mysql_manager)
        
        # 3. 读取 MinerU 配置
        logger.info("📦 读取 MinerU 配置...")
        config_manager = get_config_manager()
        mineru_raw_config = config_manager.get_mineru_config()
        
        # 适配配置格式（将 api_url 转换为 endpoint）
        mineru_config = {
            "endpoint": mineru_raw_config.get("api_url", "http://localhost:8000"),
            "timeout": mineru_raw_config.get("timeout", 600),
            "poll_interval": mineru_raw_config.get("poll_interval", 1),
            "params": {
                "backend": "pipeline",
                "lang": "ch",
                "method": "auto",
                "formula_enable": True,
                "table_enable": True,
                "priority": 0
            }
        }
        
        # 4. 初始化 MinerU 客户端
        logger.info(f"📦 初始化 MinerU 客户端: {mineru_config['endpoint']}")
        mineru_client = Mineru2Client(mineru_config=mineru_config)
        logger.info("✅ MinerU 客户端初始化完成")
        
        # 5. 初始化 PDFParser
        logger.info("📦 初始化 PDFParser...")
        pdf_parser = PDFParser(
            mineru_client=mineru_client,
            max_pages_per_request=4,
            max_concurrent_requests=3
        )
        logger.info("✅ PDFParser 初始化完成")
        
        # 清理之前的测试数据
        logger.info("\n🧹 清理旧测试数据...")
        await cleanup_test_data(mysql_manager, test_knowledge_base_id)
        
        # 运行测试
        logger.info("\n" + "=" * 80)
        logger.info("# 开始测试")
        logger.info("=" * 80)
        
        # 使用 with 语句获取 session 进行测试
        with mysql_manager.get_session() as mysql_session:
            # 6. 初始化 FileParser
            logger.info("📦 初始化 FileParser...")
            file_parser = FileParser(
                pdf_parser=pdf_parser,
                mysql_session=mysql_session,
                storage_client=None  # 暂不测试图片存储
            )
            logger.info("✅ FileParser 初始化完成")
            
            # 测试1: 解析并存储
            result = await test_parse_and_store(
                file_parser=file_parser,
                test_pdf=test_pdf,
                knowledge_base_info=knowledge_base_info
            )
            
            expected_count = result['total_elements']
        
        # 测试2: 验证 MySQL 数据
        await test_verify_mysql_data(
            mysql_manager=mysql_manager,
            knowledge_base_id=test_knowledge_base_id,
            expected_count=expected_count
        )
        
        # 测试3: 验证 MongoDB 数据
        await test_verify_mongodb_data(expected_count=expected_count)
        
        # 测试4: 验证数据一致性
        await test_data_consistency(
            mysql_manager=mysql_manager,
            knowledge_base_id=test_knowledge_base_id
        )
        
        # 测试总结
        logger.info("\n" + "=" * 80)
        logger.info("# 测试总结")
        logger.info("=" * 80)
        logger.info("\n✅ 通过: 测试1: 文件解析与存储")
        logger.info("✅ 通过: 测试2: 验证 MySQL 数据")
        logger.info("✅ 通过: 测试3: 验证 MongoDB 数据")
        logger.info("✅ 通过: 测试4: 验证数据一致性")
        logger.info("\n🎉🎉🎉 所有测试通过！")
        
    except Exception as e:
        logger.error(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 清理资源
        # 可选：清理测试数据
        # if mysql_manager:
        #     await cleanup_test_data(mysql_manager, test_knowledge_base_id)
        
        if mysql_manager:
            mysql_manager.close()
            logger.info("\n🧹 MySQL 连接已关闭")
        
        if mongodb_manager:
            await mongodb_manager.disconnect()
            logger.info("🧹 MongoDB 连接已关闭")


if __name__ == "__main__":
    asyncio.run(main())
