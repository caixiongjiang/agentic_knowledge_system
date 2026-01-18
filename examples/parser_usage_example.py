#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : parser_usage_example.py
@Author  : caixiongjiang
@Date    : 2026/01/18
@Function: 
    文件解析器使用示例
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import asyncio
import concurrent.futures
from pathlib import Path

from loguru import logger

from src.client.mineru import Mineru2Client
from src.index.common_file_extract.parser.pdf_parser import PDFParser
from src.index.common_file_extract.parser.file_parser import FileParser
from src.utils.config_manager import ConfigManager
from src.db.mysql.connection import MySQLServerManager
from src.db.mysql.models.base_model import Base
from src.db.mongodb.models.element_data import ElementData
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient


async def example_pdf_parser_only():
    """
    示例1: 仅使用 PDF 解析器（不存储）
    """
    logger.info("="*60)
    logger.info("示例1: 仅使用 PDF 解析器")
    logger.info("="*60)
    
    # 1. 加载配置
    config_manager = ConfigManager()
    mineru_config = config_manager.get_mineru_config()
    
    # 2. 创建 Mineru2Client
    mineru_client = Mineru2Client(mineru_config)
    
    # 3. 创建 PDF 解析器（自动分页：超过4页则分页并发请求）
    pdf_parser = PDFParser(
        mineru_client=mineru_client,
        max_pages_per_request=4,    # 单次请求最大4页
        max_concurrent_requests=5    # 最大并发5个请求
    )
    
    # 4. 解析 PDF 文件
    pdf_path = "path/to/your/file.pdf"
    result = await pdf_parser.parse(pdf_path)
    
    # 5. 查看解析结果
    logger.info(f"解析状态: {result['status']}")
    logger.info(f"总页数: {result['pages']}")
    logger.info(f"Markdown内容长度: {len(result['content'])}")
    
    # 6. 遍历结构化内容
    struct_content = result['struct_content']
    for page in struct_content['root']:
        page_idx = page['page_idx']
        page_info = page['page_info']
        logger.info(f"第 {page_idx} 页包含 {len(page_info)} 个元素")
        
        for element in page_info:
            element_type = element['type']
            element_id = element['id']
            logger.info(f"  - 元素 {element_id}: {element_type}")


async def example_file_parser_with_storage():
    """
    示例2: 使用完整的文件解析器（解析并存储）
    """
    logger.info("="*60)
    logger.info("示例2: 使用完整的文件解析器（解析并存储）")
    logger.info("="*60)
    
    # 1. 加载配置
    config_manager = ConfigManager()
    mineru_config = config_manager.get_mineru_config()
    mysql_config = config_manager.get_mysql_config()
    mongodb_config = config_manager.get_mongodb_config()
    
    # 2. 初始化数据库连接
    # MySQL
    mysql_manager = MySQLServerManager(mysql_config)
    
    # 创建表结构（如果不存在）
    logger.info("📋 创建 MySQL 表结构...")
    Base.metadata.create_all(mysql_manager.engine)
    
    mysql_session = mysql_manager.get_session()
    
    # MongoDB
    mongo_client = AsyncIOMotorClient(mongodb_config["uri"])
    mongo_db = mongo_client[mongodb_config["database"]]
    await init_beanie(database=mongo_db, document_models=[ElementData])
    
    # 3. 创建客户端和解析器
    mineru_client = Mineru2Client(mineru_config)
    pdf_parser = PDFParser(
        mineru_client=mineru_client,
        max_pages_per_request=4,
        max_concurrent_requests=5
    )
    
    # 4. 创建文件解析器
    file_parser = FileParser(
        pdf_parser=pdf_parser,
        mysql_session=mysql_session,
        storage_client=None  # 暂不使用存储服务（MinIO/S3/OSS等）
    )
    
    # 5. 准备知识库信息
    knowledge_base_info = {
        "knowledge_base_id": "kb_001",
        "knowledge_base_name": "技术文档",
        "parent_knowledge_base_id": None,
        "parent_knowledge_base_name": None,
        "knowledge_type": "pdf"
    }
    
    # 6. 解析并存储文件
    pdf_path = "path/to/your/file.pdf"
    result = await file_parser.parse_and_store(
        file_path=pdf_path,
        knowledge_base_info=knowledge_base_info,
        creator="admin",
        store_images=False  # 暂不存储图片到存储服务
    )
    
    # 7. 查看存储结果
    logger.info(f"文件名: {result['file_name']}")
    logger.info(f"文件类型: {result['file_type']}")
    logger.info(f"总页数: {result['total_pages']}")
    logger.info(f"总元素数: {result['total_elements']}")
    logger.info(f"元素类型分布: {result['elements_by_type']}")
    logger.info(f"MySQL存储: {result['stored_mysql']} 条")
    logger.info(f"MongoDB存储: {result['stored_mongodb']} 条")
    
    # 8. 清理连接
    mysql_manager.close()
    mongo_client.close()


async def example_batch_parse():
    """
    示例3: 批量解析多个文件（使用线程池）
    
    注意：PDFParser 只负责单文件解析
    批量处理使用线程池，一个线程处理一个文件
    """
    logger.info("="*60)
    logger.info("示例3: 批量解析多个文件（线程池方式）")
    logger.info("="*60)
    
    # 1. 准备文件列表
    file_paths = [
        "path/to/file1.pdf",
        "path/to/file2.pdf",
        "path/to/file3.pdf",
    ]
    
    knowledge_base_info = {
        "knowledge_base_id": "kb_002",
        "knowledge_base_name": "批量导入",
        "knowledge_type": "pdf"
    }
    
    # 2. 定义单文件处理任务
    async def process_single_file(file_path: str) -> dict:
        """每个线程执行的任务"""
        # 每个线程创建独立的客户端和解析器
        config_manager = ConfigManager()
        mineru_config = config_manager.get_mineru_config()
        mysql_config = config_manager.get_mysql_config()
        mongodb_config = config_manager.get_mongodb_config()
        
        # 初始化数据库连接
        mysql_manager = MySQLServerManager(mysql_config)
        
        # 创建表结构（如果不存在）- 使用锁避免并发创建冲突
        Base.metadata.create_all(mysql_manager.engine)
        
        mysql_session = mysql_manager.get_session()
        
        mongo_client = AsyncIOMotorClient(mongodb_config["uri"])
        mongo_db = mongo_client[mongodb_config["database"]]
        await init_beanie(database=mongo_db, document_models=[ElementData])
        
        # 创建解析器实例
        mineru_client = Mineru2Client(mineru_config)
        pdf_parser = PDFParser(
            mineru_client=mineru_client,
            max_pages_per_request=4,
            max_concurrent_requests=5
        )
        file_parser = FileParser(
            pdf_parser=pdf_parser,
            mysql_session=mysql_session
        )
        
        try:
            # 解析并存储
            result = await file_parser.parse_and_store(
                file_path=file_path,
                knowledge_base_info=knowledge_base_info,
                creator="admin"
            )
            return result
        finally:
            # 清理连接
            mysql_manager.close()
            mongo_client.close()
    
    # 3. 使用线程池执行批量处理
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # 提交任务
        futures = [
            executor.submit(asyncio.run, process_single_file(file_path))
            for file_path in file_paths
        ]
        
        # 等待结果
        results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"❌ 任务失败: {e}")
                results.append({
                    "status": "failed",
                    "error": str(e)
                })
    
    # 4. 统计结果
    success_count = sum(1 for r in results if r.get('status') == 'success')
    failed_count = sum(1 for r in results if r.get('status') == 'failed')
    
    logger.info(f"批量解析完成:")
    logger.info(f"  成功: {success_count} 个")
    logger.info(f"  失败: {failed_count} 个")
    
    for result in results:
        if result.get('status') == 'success':
            logger.info(f"✅ {result['file_name']}: {result['total_elements']} 个元素")
        else:
            logger.error(f"❌ 失败: {result.get('error', 'Unknown error')}")


async def main():
    """
    运行所有示例
    """
    # 选择要运行的示例
    
    # 示例1: 仅解析（推荐先试这个）
    # await example_pdf_parser_only()
    
    # 示例2: 解析并存储
    # await example_file_parser_with_storage()
    
    # 示例3: 批量解析
    # await example_batch_parse()
    
    logger.info("请取消注释要运行的示例")


if __name__ == "__main__":
    asyncio.run(main())
