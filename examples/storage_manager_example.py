#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : storage_manager_example.py
@Author  : caixiongjiang
@Date    : 2026/2/4 15:30
@Function: 
    存储管理器使用示例
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import asyncio
from pathlib import Path
from loguru import logger

from src.db.storage.manager import StorageManager


async def example_basic_operations():
    """示例 1: 基础操作（上传、下载、删除）- 使用上下文管理器"""
    logger.info("\n=== 示例 1: 基础操作 ===\n")
    
    async with StorageManager() as storage:
        # 1. 上传文件
        test_content = b"Hello, MinIO Storage!"
        storage_path = await storage.upload_file(
            file_bytes=test_content,
            bucket="knowledge-files",
            object_path="examples/test.txt"
        )
        logger.info(f"上传成功: {storage_path}")
        
        # 2. 下载文件
        downloaded = await storage.download_file(storage_path)
        logger.info(f"下载成功: {downloaded.decode('utf-8')}")
        
        # 3. 检查文件是否存在
        exists = await storage.file_exists(storage_path)
        logger.info(f"文件存在: {exists}")
        
        # 4. 删除文件
        deleted = await storage.delete_file(storage_path)
        logger.info(f"删除成功: {deleted}")
    
    # 上下文退出后自动清理资源


async def example_raw_file_operations():
    """示例 2: 原始文件操作（自动路径构建）- 使用上下文管理器"""
    logger.info("\n=== 示例 2: 原始文件操作 ===\n")
    
    async with StorageManager() as storage:
        # 上传原始文件（路径会自动构建）
        file_content = b"This is a PDF document content."
        storage_path = await storage.upload_raw_file(
            file_bytes=file_content,
            user_id="user_123",
            session_id="session_456",
            file_id="file_789",
            filename="document.pdf"
        )
        logger.info(f"原始文件上传成功: {storage_path}")
        
        # 生成预览 URL
        preview_url = await storage.get_raw_file_preview_url(
            user_id="user_123",
            session_id="session_456",
            file_id="file_789",
            filename="document.pdf",
            expires=3600
        )
        logger.info(f"预览 URL: {preview_url}")
        
        # 清理
        await storage.delete_file(storage_path)


async def example_image_operations():
    """示例 3: 图片操作 - 使用上下文管理器"""
    logger.info("\n=== 示例 3: 图片操作 ===\n")
    
    async with StorageManager() as storage:
        # 模拟图片数据
        image_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        
        # 上传图片（路径会自动构建）
        image_path = await storage.upload_image(
            image_bytes=image_data,
            user_id="user_123",
            session_id="session_456",
            file_id="file_789",
            image_name="figure_1.png"
        )
        logger.info(f"图片上传成功: {image_path}")
        
        # 生成图片预览 URL
        image_url = await storage.get_image_preview_url(
            user_id="user_123",
            session_id="session_456",
            file_id="file_789",
            image_name="figure_1.png",
            expires=7200  # 2小时
        )
        logger.info(f"图片预览 URL: {image_url}")
        
        # 清理
        await storage.delete_file(image_path)


async def example_batch_upload():
    """示例 4: 批量上传（并发）- 使用上下文管理器"""
    logger.info("\n=== 示例 4: 批量上传 ===\n")
    
    async with StorageManager() as storage:
        # 准备多个图片
        images = [
            (b"image1_data", "image_1.png"),
            (b"image2_data", "image_2.png"),
            (b"image3_data", "image_3.png"),
        ]
        
        # 并发上传
        tasks = [
            storage.upload_image(
                image_bytes=img_data,
                user_id="user_123",
                session_id="session_456",
                file_id="file_789",
                image_name=img_name
            )
            for img_data, img_name in images
        ]
        
        results = await asyncio.gather(*tasks)
        
        for i, path in enumerate(results):
            logger.info(f"图片 {i+1} 上传成功: {path}")
        
        # 清理
        for path in results:
            await storage.delete_file(path)


async def example_error_handling():
    """示例 5: 错误处理 - 使用上下文管理器"""
    logger.info("\n=== 示例 5: 错误处理 ===\n")
    
    from src.db.storage.base import (
        FileNotFoundError,
        UploadError,
        DownloadError
    )
    
    async with StorageManager() as storage:
        # 1. 下载不存在的文件
        try:
            await storage.download_file("non-existent-bucket/non-existent-file.txt")
        except FileNotFoundError:
            logger.warning("文件不存在（预期行为）")
        
        # 2. 检查不存在的文件
        exists = await storage.file_exists("non-existent-bucket/non-existent-file.txt")
        logger.info(f"文件存在: {exists}")


async def example_service_integration():
    """示例 6: Service 层集成 - 使用上下文管理器"""
    logger.info("\n=== 示例 6: Service 层集成 ===\n")
    
    class FileParserService:
        """文件解析服务示例"""
        
        def __init__(self, storage_manager: StorageManager):
            self._storage = storage_manager
        
        async def parse_file(
            self,
            user_id: str,
            session_id: str,
            file_id: str,
            filename: str,
            storage_path: str
        ):
            """解析文件的完整流程"""
            # 1. 下载文件
            logger.info(f"下载文件: {storage_path}")
            file_bytes = await self._storage.download_file(storage_path)
            
            # 2. 模拟解析过程
            logger.info("解析文件...")
            # parse_result = some_parser.parse(file_bytes)
            
            # 3. 提取图片并上传
            logger.info("上传提取的图片...")
            extracted_images = [
                (b"extracted_image_1", "extracted_1.png"),
                (b"extracted_image_2", "extracted_2.png"),
            ]
            
            image_paths = []
            for img_data, img_name in extracted_images:
                path = await self._storage.upload_image(
                    image_bytes=img_data,
                    user_id=user_id,
                    session_id=session_id,
                    file_id=file_id,
                    image_name=img_name
                )
                image_paths.append(path)
                logger.info(f"图片上传成功: {path}")
            
            return image_paths
    
    # 使用 Service（在上下文管理器中）
    async with StorageManager() as storage:
        service = FileParserService(storage)
        
        # 先上传一个测试文件
        test_file = b"Test document content"
        storage_path = await storage.upload_raw_file(
            file_bytes=test_file,
            user_id="user_123",
            session_id="session_456",
            file_id="file_789",
            filename="test.pdf"
        )
        
        # 调用 Service 解析
        image_paths = await service.parse_file(
            user_id="user_123",
            session_id="session_456",
            file_id="file_789",
            filename="test.pdf",
            storage_path=storage_path
        )
        
        logger.info(f"解析完成，提取了 {len(image_paths)} 张图片")
        
        # 清理
        await storage.delete_file(storage_path)
        for path in image_paths:
            await storage.delete_file(path)


async def main():
    """运行所有示例"""
    logger.info("=" * 60)
    logger.info("存储管理器使用示例")
    logger.info("=" * 60)
    
    # 运行所有示例
    await example_basic_operations()
    await example_raw_file_operations()
    await example_image_operations()
    await example_batch_upload()
    await example_error_handling()
    await example_service_integration()
    
    logger.info("\n" + "=" * 60)
    logger.success("所有示例运行完成！")
    logger.info("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
