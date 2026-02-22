#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_storage_manager.py
@Author  : caixiongjiang
@Date    : 2026/2/4 15:30
@Function: 
    存储管理器测试脚本
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


class StorageManagerTest:
    """存储管理器测试类"""
    
    def __init__(self, cleanup: bool = False):
        """
        初始化测试
        
        Args:
            cleanup: 是否在测试后清理文件（默认 False，保留文件以便在 GUI 中查看）
        """
        self.storage = None  # 将在上下文管理器中初始化
        self.cleanup = cleanup
        self.created_files = []  # 记录创建的文件
        
        # 测试文件路径
        self.test_files_dir = project_root / "tmp_files"
        self.test_pdf = self.test_files_dir / "pdf" / "demo1.pdf"
        self.test_large_pdf = self.test_files_dir / "pdf" / "FastSegFormer.pdf"
        self.test_image = self.test_files_dir / "image" / "image.png"
        
        logger.info(f"存储管理器测试初始化完成 (cleanup={cleanup})")
    
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
        
        logger.debug(f"读取测试文件: {file_path.name}, 大小: {len(content)} bytes")
        return content
    
    async def test_upload_download(self):
        """测试上传和下载功能（使用真实 PDF 文件）"""
        logger.info("=" * 60)
        logger.info("测试 1: 上传和下载功能（真实 PDF 文件）")
        logger.info("=" * 60)
        
        try:
            # 读取真实的 PDF 文件
            pdf_content = self._read_file(self.test_pdf)
            logger.info(f"读取测试 PDF: {self.test_pdf.name}, 大小: {len(pdf_content)} bytes ({len(pdf_content)/1024:.2f} KB)")
            
            user_id = "demo_user"
            session_id = "session_20260204"
            file_id = "file_001"
            filename = "demo_document.pdf"
            
            # 测试上传
            logger.info(f"上传测试 PDF: {filename}")
            storage_path = await self.storage.upload_raw_file(
                file_bytes=pdf_content,
                user_id=user_id,
                session_id=session_id,
                file_id=file_id,
                file_suffix=".pdf"
            )
            self.created_files.append(storage_path)
            logger.success(f"✓ 上传成功: {storage_path}")
            
            # 测试文件是否存在
            exists = await self.storage.file_exists(storage_path)
            logger.info(f"检查文件是否存在: {exists}")
            assert exists, "文件应该存在"
            logger.success("✓ 文件存在性检查通过")
            
            # 测试下载
            logger.info("下载测试 PDF...")
            downloaded_content = await self.storage.download_file(storage_path)
            logger.success(f"✓ 下载成功: {len(downloaded_content)} bytes ({len(downloaded_content)/1024:.2f} KB)")
            
            # 验证内容
            assert downloaded_content == pdf_content, "下载的内容应该与上传的内容一致"
            logger.success("✓ 内容验证通过（文件完整性校验成功）")
            
            return storage_path
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_preview_url(self, storage_path: str):
        """测试预览 URL 生成功能"""
        logger.info("=" * 60)
        logger.info("测试 2: 预览 URL 生成功能")
        logger.info("=" * 60)
        
        try:
            # 生成预览 URL (默认 1 小时过期)
            logger.info("生成预览 URL (过期时间: 3600秒)...")
            preview_url = await self.storage.get_preview_url(storage_path, expires=3600)
            logger.success(f"✓ 预览 URL 生成成功")
            logger.info(f"预览 URL: {preview_url}")
            
            # 生成短期预览 URL (5分钟过期)
            logger.info("生成短期预览 URL (过期时间: 300秒)...")
            short_url = await self.storage.get_preview_url(storage_path, expires=300)
            logger.success(f"✓ 短期预览 URL 生成成功")
            logger.info(f"短期预览 URL: {short_url}")
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_image_upload(self):
        """测试图片上传功能（使用真实图片）"""
        logger.info("=" * 60)
        logger.info("测试 3: 图片上传功能（真实图片）")
        logger.info("=" * 60)
        
        try:
            # 读取真实的图片文件
            image_content = self._read_file(self.test_image)
            logger.info(f"读取测试图片: {self.test_image.name}, 大小: {len(image_content)} bytes ({len(image_content)/1024:.2f} KB)")
            
            user_id = "demo_user"
            session_id = "session_20260204"
            file_id = "file_001"
            image_name = "sample_image.png"
            
            # 上传图片
            logger.info(f"上传测试图片: {image_name}")
            image_path = await self.storage.upload_image(
                image_bytes=image_content,
                user_id=user_id,
                session_id=session_id,
                file_id=file_id,
                image_name=image_name
            )
            self.created_files.append(image_path)
            logger.success(f"✓ 图片上传成功: {image_path}")
            
            # 验证文件是否存在
            exists = await self.storage.file_exists(image_path)
            assert exists, "图片应该存在"
            logger.success("✓ 图片存在性检查通过")
            
            # 生成图片预览 URL
            logger.info("生成图片预览 URL...")
            image_url = await self.storage.get_image_preview_url(
                user_id=user_id,
                session_id=session_id,
                file_id=file_id,
                image_name=image_name,
                expires=7200  # 2小时
            )
            logger.success(f"✓ 图片预览 URL 生成成功")
            logger.info(f"图片预览 URL: {image_url}")
            logger.info("💡 可以在浏览器中打开此 URL 查看图片")
            
            return image_path
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_large_file_upload(self):
        """测试大文件上传（使用真实的大 PDF）"""
        logger.info("=" * 60)
        logger.info("测试 4: 大文件上传（2MB PDF）")
        logger.info("=" * 60)
        
        try:
            # 读取大 PDF 文件
            large_pdf_content = self._read_file(self.test_large_pdf)
            logger.info(f"读取大型 PDF: {self.test_large_pdf.name}, 大小: {len(large_pdf_content)} bytes ({len(large_pdf_content)/1024/1024:.2f} MB)")
            
            user_id = "demo_user"
            session_id = "session_20260204"
            file_id = "file_002"
            filename = "FastSegFormer_paper.pdf"
            
            # 测试上传
            logger.info(f"上传大型 PDF: {filename}")
            import time
            start_time = time.time()
            
            storage_path = await self.storage.upload_raw_file(
                file_bytes=large_pdf_content,
                user_id=user_id,
                session_id=session_id,
                file_id=file_id,
                file_suffix=".pdf"
            )
            
            upload_time = time.time() - start_time
            self.created_files.append(storage_path)
            logger.success(f"✓ 大文件上传成功: {storage_path}")
            logger.info(f"⏱️  上传耗时: {upload_time:.2f} 秒")
            logger.info(f"📊 上传速度: {len(large_pdf_content)/1024/1024/upload_time:.2f} MB/s")
            
            # 验证文件完整性
            logger.info("验证大文件完整性...")
            start_time = time.time()
            downloaded_content = await self.storage.download_file(storage_path)
            download_time = time.time() - start_time
            
            assert downloaded_content == large_pdf_content, "大文件内容应该一致"
            logger.success(f"✓ 大文件完整性验证通过")
            logger.info(f"⏱️  下载耗时: {download_time:.2f} 秒")
            logger.info(f"📊 下载速度: {len(downloaded_content)/1024/1024/download_time:.2f} MB/s")
            
            return storage_path
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def test_delete(self, storage_path: str):
        """测试删除功能"""
        logger.info("=" * 60)
        logger.info("测试 5: 删除功能")
        logger.info("=" * 60)
        
        if not self.cleanup:
            logger.info("ℹ 跳过删除测试（保留模式）")
            return
        
        try:
            # 删除文件
            logger.info(f"删除测试文件: {storage_path}")
            success = await self.storage.delete_file(storage_path)
            assert success, "删除应该成功"
            logger.success("✓ 文件删除成功")
            
            # 验证文件已被删除
            exists = await self.storage.file_exists(storage_path)
            assert not exists, "文件不应该存在"
            logger.success("✓ 文件已确认删除")
            
            # 从记录中移除
            if storage_path in self.created_files:
                self.created_files.remove(storage_path)
            
        except Exception as e:
            logger.error(f"✗ 测试失败: {e}")
            raise
    
    async def run_all_tests(self):
        """运行所有测试（使用上下文管理器）"""
        logger.info("\n" + "=" * 60)
        logger.info("开始存储管理器测试（使用真实文件）")
        logger.info(f"清理模式: {'开启' if self.cleanup else '关闭（保留文件）'}")
        logger.info("=" * 60 + "\n")
        
        # 使用异步上下文管理器
        async with StorageManager() as storage:
            self.storage = storage
            
            try:
                # 测试 1: 上传和下载（真实 PDF）
                pdf_path = await self.test_upload_download()
                
                # 测试 2: 预览 URL
                await self.test_preview_url(pdf_path)
                
                # 测试 3: 图片上传（真实图片）
                image_path = await self.test_image_upload()
                
                # 测试 4: 大文件上传（2MB PDF）
                large_file_path = await self.test_large_file_upload()
                
                # 测试 5: 删除功能（仅在 cleanup 模式）
                await self.test_delete(pdf_path)
                await self.test_delete(image_path)
                await self.test_delete(large_file_path)
                
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
                    
                    # 显示文件统计
                    logger.info("\n文件统计:")
                    pdf_count = sum(1 for p in self.created_files if p.endswith('.pdf'))
                    img_count = sum(1 for p in self.created_files if p.endswith('.png'))
                    logger.info(f"  📄 PDF 文件: {pdf_count} 个")
                    logger.info(f"  🖼️  图片文件: {img_count} 个")
                    
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
    test = StorageManagerTest(cleanup=cleanup)
    await test.run_all_tests()


if __name__ == "__main__":
    # 检查命令行参数
    cleanup_mode = "--cleanup" in sys.argv or "-c" in sys.argv
    
    if cleanup_mode:
        logger.info("🗑️  清理模式已开启，测试完成后将删除所有文件")
    else:
        logger.info("💾 保留模式（默认），测试文件将保留以便在 MinIO GUI 查看")
        logger.info("   提示: 使用 --cleanup 或 -c 参数开启清理模式")
        logger.info("   测试使用真实文件：PDF (demo1.pdf, FastSegFormer.pdf) 和图片 (image.png)\n")
    
    asyncio.run(main(cleanup=cleanup_mode))
