#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_minio_adapter.py
@Author  : caixiongjiang
@Date    : 2026/2/4 16:00
@Function: 
    测试 MinIO 适配器
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from loguru import logger

from src.db.storage.adapters.minio_adapter import MinIOAdapter
from src.db.storage.base import (
    FileNotFoundError,
    UploadError,
    DownloadError
)


class TestMinIOAdapter:
    """测试 MinIO 适配器（使用上下文管理器）"""
    
    def __init__(self):
        """初始化测试"""
        self.adapter = None  # 将在上下文管理器中初始化
        logger.info("MinIO 适配器测试初始化完成")
    
    async def test_upload_download(self):
        """测试上传和下载"""
        logger.info("=" * 60)
        logger.info("测试 1: 上传和下载")
        logger.info("=" * 60)
        
        try:
            # 准备测试数据
            test_content = b"MinIO adapter test content"
            bucket = "knowledge-files"
            object_path = "test/minio_adapter_test.txt"
            
            # 上传文件
            logger.info(f"上传测试文件: {bucket}/{object_path}")
            storage_path = await self.adapter.upload_file(
                file_bytes=test_content,
                bucket=bucket,
                object_path=object_path
            )
            logger.success(f"✓ 上传成功: {storage_path}")
            
            # 下载文件
            logger.info("下载测试文件...")
            downloaded = await self.adapter.download_file(storage_path)
            logger.success(f"✓ 下载成功: {len(downloaded)} bytes")
            
            # 验证内容
            assert downloaded == test_content
            logger.success("✓ 内容验证通过")
            
            return storage_path
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_file_exists(self, storage_path: str):
        """测试文件存在性检查"""
        logger.info("=" * 60)
        logger.info("测试 2: 文件存在性检查")
        logger.info("=" * 60)
        
        try:
            # 检查存在的文件
            exists = await self.adapter.file_exists(storage_path)
            assert exists is True
            logger.success(f"✓ 文件存在检查通过: {storage_path}")
            
            # 检查不存在的文件
            not_exists = await self.adapter.file_exists("knowledge-files/non-existent-file.txt")
            assert not_exists is False
            logger.success("✓ 不存在的文件检查通过")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_presigned_url(self, storage_path: str):
        """测试预签名 URL"""
        logger.info("=" * 60)
        logger.info("测试 3: 预签名 URL")
        logger.info("=" * 60)
        
        try:
            # 生成默认过期时间的 URL
            url = await self.adapter.get_presigned_url(storage_path)
            assert url.startswith("http")
            logger.success(f"✓ 预签名 URL 生成成功（默认过期时间）")
            logger.info(f"URL: {url}")
            
            # 生成自定义过期时间的 URL
            short_url = await self.adapter.get_presigned_url(storage_path, expires=300)
            assert short_url.startswith("http")
            logger.success(f"✓ 预签名 URL 生成成功（自定义过期时间: 300秒）")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_path_builders(self):
        """测试路径构建方法"""
        logger.info("=" * 60)
        logger.info("测试 4: 路径构建方法")
        logger.info("=" * 60)
        
        try:
            # 测试原始文件路径
            raw_path = self.adapter.build_raw_file_path(
                user_id="user123",
                session_id="session456",
                file_id="file789",
                file_suffix=".pdf"
            )
            expected_raw = "user123/session456/file789.pdf"
            assert raw_path == expected_raw
            logger.success(f"✓ 原始文件路径构建正确: {raw_path}")
            
            # 测试图片路径
            image_path = self.adapter.build_image_path(
                user_id="user123",
                session_id="session456",
                file_id="file789",
                image_name="figure1.png"
            )
            expected_image = "users/user123/sessions/session456/parsed/file789/images/figure1.png"
            assert image_path == expected_image
            logger.success(f"✓ 图片路径构建正确: {image_path}")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_delete(self, storage_path: str):
        """测试删除文件"""
        logger.info("=" * 60)
        logger.info("测试 5: 删除文件")
        logger.info("=" * 60)
        
        try:
            # 删除文件
            success = await self.adapter.delete_file(storage_path)
            assert success is True
            logger.success(f"✓ 文件删除成功: {storage_path}")
            
            # 验证文件已删除
            exists = await self.adapter.file_exists(storage_path)
            assert exists is False
            logger.success("✓ 文件已确认删除")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_error_handling(self):
        """测试错误处理"""
        logger.info("=" * 60)
        logger.info("测试 6: 错误处理")
        logger.info("=" * 60)
        
        try:
            # 测试下载不存在的文件
            try:
                await self.adapter.download_file("knowledge-files/non-existent-file.txt")
                assert False, "应该抛出 FileNotFoundError"
            except FileNotFoundError as e:
                logger.success(f"✓ 正确抛出 FileNotFoundError: {e}")
            
            # 测试删除不存在的文件（应该返回 False）
            result = await self.adapter.delete_file("knowledge-files/non-existent-file.txt")
            assert result is False
            logger.success("✓ 删除不存在的文件返回 False")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_batch_operations(self):
        """测试批量操作"""
        logger.info("=" * 60)
        logger.info("测试 7: 批量上传和删除")
        logger.info("=" * 60)
        
        try:
            # 准备多个测试文件
            files = [
                (b"file1 content", "test/batch_1.txt"),
                (b"file2 content", "test/batch_2.txt"),
                (b"file3 content", "test/batch_3.txt"),
            ]
            
            # 并发上传
            logger.info("批量上传文件...")
            upload_tasks = [
                self.adapter.upload_file(content, "knowledge-files", path)
                for content, path in files
            ]
            storage_paths = await asyncio.gather(*upload_tasks)
            logger.success(f"✓ 批量上传成功: {len(storage_paths)} 个文件")
            
            # 批量删除
            logger.info("批量删除文件...")
            delete_tasks = [
                self.adapter.delete_file(path)
                for path in storage_paths
            ]
            results = await asyncio.gather(*delete_tasks)
            assert all(results)
            logger.success(f"✓ 批量删除成功: {len(results)} 个文件")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def run_all_tests(self):
        """运行所有测试（使用上下文管理器）"""
        logger.info("\n" + "=" * 60)
        logger.info("开始 MinIO 适配器测试")
        logger.info("=" * 60 + "\n")
        
        # 使用异步上下文管理器
        async with MinIOAdapter() as adapter:
            self.adapter = adapter
            
            try:
                # 测试 1: 上传和下载
                storage_path = await self.test_upload_download()
                
                # 测试 2: 文件存在性检查
                await self.test_file_exists(storage_path)
                
                # 测试 3: 预签名 URL
                await self.test_presigned_url(storage_path)
                
                # 测试 4: 路径构建
                await self.test_path_builders()
                
                # 测试 5: 删除文件
                await self.test_delete(storage_path)
                
                # 测试 6: 错误处理
                await self.test_error_handling()
                
                # 测试 7: 批量操作
                await self.test_batch_operations()
                
                logger.info("\n" + "=" * 60)
                logger.success("所有测试通过！✓")
                logger.info("=" * 60 + "\n")
                
            except Exception as e:
                logger.error("\n" + "=" * 60)
                logger.error(f"测试失败: {e}")
                logger.error("=" * 60 + "\n")
                raise
        
        # 上下文退出后自动清理资源
        logger.debug("MinIO 适配器资源已自动清理")


async def main():
    """主函数"""
    test = TestMinIOAdapter()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
