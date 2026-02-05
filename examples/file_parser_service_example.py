#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : file_parser_service_example.py
@Author  : caixiongjiang
@Date    : 2026/02/04
@Function: 
    FileParserService 使用示例
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import asyncio
from loguru import logger

from src.db.storage.manager import StorageManager
from src.service.knowledge.components import FileParserService


async def example_1_basic_usage():
    """示例 1: 基本用法"""
    print("\n" + "=" * 60)
    print("示例 1: 基本用法")
    print("=" * 60)
    
    from src.db.mysql.connection import get_mysql_session
    
    session = get_mysql_session()
    
    try:
        async with StorageManager() as storage:
            # 创建服务实例(需要 MySQL 会话)
            service = FileParserService(
                storage_manager=storage,
                mysql_session=session
            )
            
            # 解析 PDF 文件
            result = await service.parse_file(
                user_id="user_123",
                file_id="file_456",
                filename="document.pdf",
                storage_path="knowledge-files/users/user_123/sessions/session_789/raw/file_456/document.pdf",
                knowledge_base_id="kb_001",
                knowledge_base_name="我的知识库",
                creator="user_123",
                store_images=True
            )
            
            # 检查结果
            if result.is_success():
                print(f"✅ 解析成功!")
                print(f"\n文件信息:")
                print(f"  - 文件名: {result.filename}")
                print(f"  - 页数: {result.total_pages}")
                print(f"  - 状态: {result.status}")
                print(f"  - 解析工具: {result.parse_tool}")
            else:
                print(f"❌ 解析失败: {result.error_message}")
    finally:
        session.close()


async def example_2_error_handling():
    """示例 2: 错误处理"""
    print("\n" + "=" * 60)
    print("示例 2: 错误处理")
    print("=" * 60)
    
    async with StorageManager() as storage:
        service = FileParserService(storage_manager=storage)
        
        try:
            # 尝试解析不支持的文件类型
            result = await service.parse_file(
                user_id="user_123",
                file_id="file_789",
                filename="document.xyz",
                storage_path="knowledge-files/document.xyz",
                mime_type="application/unsupported",
                session_id="session_789"
            )
            
            if result.status.value == "failed":
                print(f"⚠️ 解析失败: {result.error_message}")
                
        except ValueError as e:
            print(f"⚠️ 文件类型错误: {e}")
        except Exception as e:
            print(f"❌ 解析过程出错: {e}")


async def example_3_multiple_files():
    """示例 3: 批量解析多个文件"""
    print("\n" + "=" * 60)
    print("示例 3: 批量解析多个文件")
    print("=" * 60)
    
    # 模拟文件列表
    files = [
        {
            "user_id": "user_123",
            "file_id": f"file_{i}",
            "filename": f"document_{i}.pdf",
            "storage_path": f"knowledge-files/document_{i}.pdf",
            "mime_type": "application/pdf",
            "session_id": "session_789"
        }
        for i in range(3)
    ]
    
    async with StorageManager() as storage:
        service = FileParserService(storage_manager=storage)
        
        # 并发解析所有文件
        tasks = [
            service.parse_file(
                user_id=f["user_id"],
                file_id=f["file_id"],
                filename=f["filename"],
                storage_path=f["storage_path"],
                mime_type=f["mime_type"],
                session_id=f["session_id"]
            )
            for f in files
        ]
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = 0
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ 文件 {i+1} 解析出错: {result}")
                failed_count += 1
            elif result.is_success():
                print(f"✅ 文件 {i+1} 解析成功: {result.filename}")
                success_count += 1
            else:
                print(f"⚠️ 文件 {i+1} 解析失败: {result.error_message}")
                failed_count += 1
        
        print(f"\n总结: 成功 {success_count} 个, 失败 {failed_count} 个")


async def example_4_custom_parser():
    """示例 4: 使用自定义 Parser"""
    print("\n" + "=" * 60)
    print("示例 4: 使用自定义 Parser")
    print("=" * 60)
    
    from src.index.common_file_extract.parser.pdf_parser import PDFParser
    from src.client.mineru import Mineru2Client
    
    # 创建自定义 Mineru 客户端
    mineru_client = Mineru2Client(
        api_url="http://localhost:8080",
        timeout=600
    )
    
    # 创建自定义 PDF Parser
    pdf_parser = PDFParser(
        mineru_client=mineru_client,
        max_pages_per_request=10,  # 单次请求最大页数
        max_concurrent_requests=3   # 最大并发请求数
    )
    
    async with StorageManager() as storage:
        # 使用自定义 Parser 创建服务
        service = FileParserService(
            storage_manager=storage,
            pdf_parser=pdf_parser
        )
        
        print("✅ 使用自定义 Parser 创建服务成功")
        print(f"  - 单次请求最大页数: {pdf_parser.max_pages_per_request}")
        print(f"  - 最大并发请求数: {pdf_parser.max_concurrent_requests}")


async def example_5_result_details():
    """示例 5: 查看详细解析结果"""
    print("\n" + "=" * 60)
    print("示例 5: 查看详细解析结果")
    print("=" * 60)
    
    async with StorageManager() as storage:
        service = FileParserService(storage_manager=storage)
        
        result = await service.parse_file(
            user_id="user_123",
            file_id="file_456",
            filename="document.pdf",
            storage_path="knowledge-files/document.pdf",
            mime_type="application/pdf",
            session_id="session_789"
        )
        
        if result.is_success():
            print("📄 文档摘要:")
            summary = result.get_summary()
            for key, value in summary.items():
                print(f"  - {key}: {value}")
            
            # 查看文本元素
            print(f"\n📝 文本元素 ({len(result.text_elements)} 个):")
            for elem in result.text_elements[:3]:  # 仅显示前3个
                print(f"  - [{elem.element_id}] {elem.text[:50]}...")
            
            # 查看图片元素
            if result.has_images():
                print(f"\n🖼️ 图片元素 ({len(result.image_elements)} 个):")
                for elem in result.image_elements[:3]:
                    print(f"  - [{elem.element_id}] {elem.image_file_name}")
            
            # 查看表格元素
            if result.has_tables():
                print(f"\n📊 表格元素 ({len(result.table_elements)} 个):")
                for elem in result.table_elements[:3]:
                    print(f"  - [{elem.element_id}] {elem.table_caption or 'No caption'}")
            
            # 获取数据库存储格式
            print(f"\n💾 数据库存储:")
            mysql_data = result.get_mysql_data()
            mongodb_data = result.get_mongodb_data()
            print(f"  - MySQL 记录数: {len(mysql_data)}")
            print(f"  - MongoDB 记录数: {len(mongodb_data)}")


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("FileParserService 使用示例")
    print("=" * 60)
    
    try:
        # 运行所有示例
        # await example_1_basic_usage()
        # await example_2_error_handling()
        # await example_3_multiple_files()
        # await example_4_custom_parser()
        # await example_5_result_details()
        
        print("\n" + "=" * 60)
        print("✅ 所有示例运行完成!")
        print("=" * 60)
        print("\n💡 提示:")
        print("  1. 取消注释上面的示例代码来运行")
        print("  2. 确保 MinIO 服务正在运行")
        print("  3. 确保 Mineru 服务正在运行")
        print("  4. 确保配置文件中的存储设置正确")
        
    except Exception as e:
        logger.error(f"示例运行失败: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
