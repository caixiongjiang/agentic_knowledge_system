#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_manager.py
@Author  : caixiongjiang
@Date    : 2026/2/4 16:00
@Function: 
    测试存储管理器
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

from src.db.storage.manager import StorageManager


class TestStorageManager:
    """测试存储管理器"""
    
    def __init__(self, cleanup: bool = False):
        """
        初始化测试
        
        Args:
            cleanup: 是否在测试后清理文件（默认 False，保留文件以便在 GUI 中查看）
        """
        self.storage = None  # 将在上下文管理器中初始化
        self.cleanup = cleanup
        self.created_files = []  # 记录创建的文件
        logger.info(f"存储管理器测试初始化完成 (cleanup={cleanup})")
    
    async def test_basic_operations(self):
        """测试基础操作"""
        logger.info("=" * 60)
        logger.info("测试 1: 基础操作（上传、下载、删除）")
        logger.info("=" * 60)
        
        try:
            # 上传文件
            test_content = b"Storage manager test content"
            storage_path = await self.storage.upload_file(
                file_bytes=test_content,
                bucket="knowledge-files",
                object_path="test/manager_basic_test.txt"
            )
            self.created_files.append(storage_path)
            logger.success(f"✓ 上传成功: {storage_path}")
            
            # 检查文件是否存在
            exists = await self.storage.file_exists(storage_path)
            assert exists is True
            logger.success("✓ 文件存在性检查通过")
            
            # 下载文件
            downloaded = await self.storage.download_file(storage_path)
            assert downloaded == test_content
            logger.success("✓ 下载和验证通过")
            
            if self.cleanup:
                # 仅在 cleanup 模式下删除文件
                success = await self.storage.delete_file(storage_path)
                assert success is True
                logger.success("✓ 删除成功")
                self.created_files.remove(storage_path)
            else:
                logger.info("ℹ 保留文件以便在 GUI 中查看")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_raw_file_operations(self):
        """测试原始文件操作"""
        logger.info("=" * 60)
        logger.info("测试 2: 原始文件操作")
        logger.info("=" * 60)
        
        try:
            # 上传原始文件
            test_content = b"Raw file content - This is a test PDF document"
            storage_path = await self.storage.upload_raw_file(
                file_bytes=test_content,
                user_id="demo_user",
                session_id="session_001",
                file_id="file_001",
                file_suffix=".pdf"
            )
            self.created_files.append(storage_path)
            logger.success(f"✓ 原始文件上传成功: {storage_path}")
            
            # 验证路径格式
            assert "users/demo_user/sessions/session_001/raw/file_001/sample_document.pdf" in storage_path
            logger.success("✓ 路径格式验证通过")
            
            # 生成预览 URL
            preview_url = await self.storage.get_raw_file_preview_url(
                user_id="demo_user",
                session_id="session_001",
                file_id="file_001",
                filename="sample_document.pdf"
            )
            assert preview_url.startswith("http")
            logger.success(f"✓ 预览 URL 生成成功")
            logger.info(f"预览 URL: {preview_url}")
            
            if self.cleanup:
                await self.storage.delete_file(storage_path)
                logger.success("✓ 文件清理完成")
                self.created_files.remove(storage_path)
            else:
                logger.info("ℹ 保留原始文件以便在 GUI 中查看")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_image_operations(self):
        """测试图片操作"""
        logger.info("=" * 60)
        logger.info("测试 3: 图片操作")
        logger.info("=" * 60)
        
        try:
            # 上传图片（模拟 PNG 文件头）
            image_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            image_path = await self.storage.upload_image(
                image_bytes=image_content,
                user_id="demo_user",
                session_id="session_001",
                file_id="file_001",
                image_name="figure_1.png"
            )
            self.created_files.append(image_path)
            logger.success(f"✓ 图片上传成功: {image_path}")
            
            # 验证路径格式
            assert "users/demo_user/sessions/session_001/parsed/file_001/images/figure_1.png" in image_path
            logger.success("✓ 图片路径格式验证通过")
            
            # 生成图片预览 URL
            image_url = await self.storage.get_image_preview_url(
                user_id="demo_user",
                session_id="session_001",
                file_id="file_001",
                image_name="figure_1.png",
                expires=7200
            )
            assert image_url.startswith("http")
            logger.success(f"✓ 图片预览 URL 生成成功")
            logger.info(f"图片预览 URL: {image_url}")
            
            if self.cleanup:
                await self.storage.delete_file(image_path)
                logger.success("✓ 图片清理完成")
                self.created_files.remove(image_path)
            else:
                logger.info("ℹ 保留图片以便在 GUI 中查看")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_preview_url_with_different_expires(self):
        """测试不同过期时间的预览 URL"""
        logger.info("=" * 60)
        logger.info("测试 4: 不同过期时间的预览 URL")
        logger.info("=" * 60)
        
        try:
            # 上传测试文件
            test_content = b"Preview URL test - This file is used to test different URL expiration times"
            storage_path = await self.storage.upload_file(
                file_bytes=test_content,
                bucket="knowledge-files",
                object_path="test/preview_url_demo.txt"
            )
            self.created_files.append(storage_path)
            
            # 测试不同过期时间
            expires_times = [300, 3600, 7200, 86400]  # 5分钟、1小时、2小时、24小时
            
            for expires in expires_times:
                url = await self.storage.get_preview_url(storage_path, expires)
                assert url.startswith("http")
                logger.success(f"✓ {expires}秒({expires//60}分钟)过期时间的 URL 生成成功")
            
            if self.cleanup:
                await self.storage.delete_file(storage_path)
                logger.success("✓ 测试文件清理完成")
                self.created_files.remove(storage_path)
            else:
                logger.info("ℹ 保留文件以便测试预览 URL")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_batch_image_upload(self):
        """测试批量图片上传"""
        logger.info("=" * 60)
        logger.info("测试 5: 批量图片上传")
        logger.info("=" * 60)
        
        try:
            # 准备多个图片（模拟 PNG 文件）
            images = [
                (b"\x89PNG\r\n\x1a\n - Image 1", "figure_1.png"),
                (b"\x89PNG\r\n\x1a\n - Image 2", "figure_2.png"),
                (b"\x89PNG\r\n\x1a\n - Image 3", "figure_3.png"),
                (b"\x89PNG\r\n\x1a\n - Image 4", "chart_1.png"),
                (b"\x89PNG\r\n\x1a\n - Image 5", "diagram_1.png"),
            ]
            
            # 并发上传
            logger.info("批量上传图片...")
            tasks = [
                self.storage.upload_image(
                    image_bytes=img_data,
                    user_id="demo_user",
                    session_id="session_001",
                    file_id="file_001",
                    image_name=img_name
                )
                for img_data, img_name in images
            ]
            
            image_paths = await asyncio.gather(*tasks)
            self.created_files.extend(image_paths)
            logger.success(f"✓ 批量上传成功: {len(image_paths)} 张图片")
            
            for i, path in enumerate(image_paths, 1):
                logger.info(f"  图片 {i}: {path}")
            
            if self.cleanup:
                # 批量删除
                logger.info("批量删除图片...")
                delete_tasks = [
                    self.storage.delete_file(path)
                    for path in image_paths
                ]
                results = await asyncio.gather(*delete_tasks)
                assert all(results)
                logger.success(f"✓ 批量删除成功: {len(results)} 张图片")
                for path in image_paths:
                    self.created_files.remove(path)
            else:
                logger.info("ℹ 保留批量上传的图片以便在 GUI 中查看")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_error_handling(self):
        """测试错误处理"""
        logger.info("=" * 60)
        logger.info("测试 6: 错误处理")
        logger.info("=" * 60)
        
        from src.db.storage.base import FileNotFoundError
        
        try:
            # 下载不存在的文件
            try:
                await self.storage.download_file("knowledge-files/non-existent.txt")
                assert False, "应该抛出异常"
            except FileNotFoundError:
                logger.success("✓ 正确处理文件不存在的情况")
            
            # 检查不存在的文件
            exists = await self.storage.file_exists("knowledge-files/non-existent.txt")
            assert exists is False
            logger.success("✓ 不存在的文件返回 False")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def run_all_tests(self):
        """运行所有测试（使用上下文管理器）"""
        logger.info("\n" + "=" * 60)
        logger.info("开始存储管理器测试")
        logger.info(f"清理模式: {'开启' if self.cleanup else '关闭（保留文件）'}")
        logger.info("=" * 60 + "\n")
        
        # 使用异步上下文管理器
        async with StorageManager() as storage:
            self.storage = storage
            
            try:
                # 测试 1: 基础操作
                await self.test_basic_operations()
                
                # 测试 2: 原始文件操作
                await self.test_raw_file_operations()
                
                # 测试 3: 图片操作
                await self.test_image_operations()
                
                # 测试 4: 不同过期时间的预览 URL
                await self.test_preview_url_with_different_expires()
                
                # 测试 5: 批量图片上传
                await self.test_batch_image_upload()
            
                # 测试 6: 错误处理
                await self.test_error_handling()
                
                logger.info("\n" + "=" * 60)
                logger.success("所有测试通过！✓")
                logger.info("=" * 60)
                
                # 显示保留的文件清单
                if not self.cleanup and self.created_files:
                    logger.info("\n" + "=" * 60)
                    logger.info("保留的测试文件清单（可在 MinIO GUI 查看）")
                    logger.info("=" * 60)
                    logger.info(f"总计: {len(self.created_files)} 个文件\n")
                    
                    for i, path in enumerate(self.created_files, 1):
                        logger.info(f"  {i}. {path}")
                    
                    logger.info("\n" + "=" * 60)
                    logger.info("访问 MinIO GUI 查看文件:")
                    logger.info("  URL: http://localhost:9001")
                    logger.info("  用户名: minioadmin")
                    logger.info("  密码: minioadmin")
                    logger.info("=" * 60 + "\n")
                
            except Exception as e:
                logger.error("\n" + "=" * 60)
                logger.error(f"测试失败: {e}")
                logger.error("=" * 60 + "\n")
                raise
        
        # 上下文退出后自动清理资源
        logger.debug("存储管理器资源已自动清理")


async def main(cleanup: bool = False):
    """
    主函数
    
    Args:
        cleanup: 是否清理测试文件（默认 False，保留文件以便在 GUI 查看）
    """
    test = TestStorageManager(cleanup=cleanup)
    await test.run_all_tests()


if __name__ == "__main__":
    import sys
    
    # 检查命令行参数
    cleanup_mode = "--cleanup" in sys.argv or "-c" in sys.argv
    
    if cleanup_mode:
        logger.info("🗑️  清理模式已开启，测试完成后将删除所有文件")
    else:
        logger.info("💾 保留模式（默认），测试文件将保留以便在 MinIO GUI 查看")
        logger.info("   提示: 使用 --cleanup 或 -c 参数开启清理模式")
    
    asyncio.run(main(cleanup=cleanup_mode))
