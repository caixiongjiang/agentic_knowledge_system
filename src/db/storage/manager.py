#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : manager.py
@Author  : caixiongjiang
@Date    : 2026/2/4 15:00
@Function: 
    对象存储统一管理器
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional
from loguru import logger

from src.db.storage.base import BaseStorageAdapter
from src.db.storage.factory import StorageFactory
from src.utils.config_manager import get_config_manager


class StorageManager:
    """
    对象存储统一管理器
    
    提供统一的存储操作接口，屏蔽底层存储差异
    支持文件的上传、下载、删除、预览等操作
    必须使用异步上下文管理器: async with StorageManager() as manager
    """
    
    def __init__(self, adapter: Optional[BaseStorageAdapter] = None):
        """
        初始化存储管理器
        
        Args:
            adapter: 存储适配器实例，如果为 None，自动从配置创建
        """
        if adapter is None:
            self._adapter = StorageFactory.create_adapter()
        else:
            self._adapter = adapter
        
        self._closed = False
        logger.info(f"存储管理器初始化完成: {self._adapter.__class__.__name__}")
    
    async def __aenter__(self):
        """
        进入异步上下文
        
        Returns:
            StorageManager: 管理器实例
        """
        # 确保适配器也进入上下文
        await self._adapter.__aenter__()
        logger.debug("存储管理器进入上下文")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        退出异步上下文，清理资源
        
        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪
            
        Returns:
            bool: False (不抑制异常)
        """
        await self.close()
        return False
    
    async def close(self):
        """
        关闭存储管理器，清理资源
        
        自动关闭底层适配器
        """
        if self._closed:
            return
        
        try:
            # 关闭适配器
            await self._adapter.close()
            self._closed = True
            logger.info("存储管理器已关闭")
        except Exception as e:
            logger.error(f"关闭存储管理器时出错: {e}")
            raise
    
    def _check_closed(self):
        """检查管理器是否已关闭"""
        if self._closed:
            raise RuntimeError("存储管理器已关闭，无法执行操作")
    
    # ========== 基础操作 ==========
    
    async def download_file(self, storage_path: str) -> bytes:
        """
        下载文件
        
        Args:
            storage_path: 存储路径
            
        Returns:
            bytes: 文件字节内容
        """
        self._check_closed()
        logger.debug(f"下载文件: {storage_path}")
        return await self._adapter.download_file(storage_path)
    
    async def upload_file(
        self,
        file_bytes: bytes,
        bucket: str,
        object_path: str
    ) -> str:
        """
        上传文件
        
        Args:
            file_bytes: 文件字节内容
            bucket: 桶/容器名称
            object_path: 对象路径
            
        Returns:
            str: 完整存储路径
        """
        self._check_closed()
        logger.debug(f"上传文件: {bucket}/{object_path}")
        return await self._adapter.upload_file(file_bytes, bucket, object_path)
    
    async def delete_file(self, storage_path: str) -> bool:
        """
        删除文件
        
        Args:
            storage_path: 存储路径
            
        Returns:
            bool: 是否删除成功
        """
        self._check_closed()
        logger.debug(f"删除文件: {storage_path}")
        return await self._adapter.delete_file(storage_path)
    
    async def file_exists(self, storage_path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            storage_path: 存储路径
            
        Returns:
            bool: 文件是否存在
        """
        self._check_closed()
        return await self._adapter.file_exists(storage_path)
    
    async def get_preview_url(
        self,
        storage_path: str,
        expires: int = 3600
    ) -> str:
        """
        获取文件预览 URL
        
        Args:
            storage_path: 存储路径
            expires: URL 过期时间（秒），默认 1 小时
            
        Returns:
            str: 预签名 URL
        """
        self._check_closed()
        logger.debug(f"生成预览 URL: {storage_path}, 过期时间: {expires}秒")
        return await self._adapter.get_presigned_url(storage_path, expires)
    
    # ========== 高级操作 ==========
    
    async def upload_raw_file(
        self,
        file_bytes: bytes,
        user_id: str,
        session_id: str,
        file_id: str,
        filename: str,
        folder_path: str = "/",
    ) -> str:
        """
        上传原始文件
        
        自动构建路径: {user_id}/{session_id}{folder_path}{filename}
        
        Args:
            file_bytes: 文件字节内容
            user_id: 用户ID
            session_id: 会话ID
            file_id: 文件ID
            filename: 文件名
            folder_path: 文件夹路径（如 /默认上传/），默认根目录
            
        Returns:
            str: 完整存储路径
        """
        object_path = self._adapter.build_raw_file_path(
            user_id, session_id, file_id, filename, folder_path
        )
        bucket = self._get_bucket_name()
        
        logger.info(f"上传原始文件: {bucket}/{object_path}")
        return await self.upload_file(file_bytes, bucket, object_path)
    
    async def upload_image(
        self,
        image_bytes: bytes,
        user_id: str,
        session_id: str,
        file_id: str,
        image_name: str
    ) -> str:
        """
        上传图片到 parsed 目录
        
        自动构建路径: users/{user_id}/sessions/{session_id}/parsed/{file_id}/images/{image_name}
        
        Args:
            image_bytes: 图片字节内容
            user_id: 用户ID
            session_id: 会话ID
            file_id: 文件ID
            image_name: 图片名称
            
        Returns:
            str: 图片存储路径
        """
        object_path = self._adapter.build_image_path(
            user_id, session_id, file_id, image_name
        )
        bucket = self._get_bucket_name()
        
        logger.debug(f"上传图片: {bucket}/{object_path}")
        return await self.upload_file(image_bytes, bucket, object_path)
    
    async def get_raw_file_preview_url(
        self,
        user_id: str,
        session_id: str,
        file_id: str,
        filename: str,
        expires: int = 3600
    ) -> str:
        """
        获取原始文件的预览 URL
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            file_id: 文件ID
            filename: 文件名
            expires: URL 过期时间（秒），默认 1 小时
            
        Returns:
            str: 预签名 URL
        """
        object_path = self._adapter.build_raw_file_path(
            user_id, session_id, file_id, filename
        )
        bucket = self._get_bucket_name()
        storage_path = f"{bucket}/{object_path}"
        
        return await self.get_preview_url(storage_path, expires)
    
    async def get_image_preview_url(
        self,
        user_id: str,
        session_id: str,
        file_id: str,
        image_name: str,
        expires: int = 3600
    ) -> str:
        """
        获取图片的预览 URL
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            file_id: 文件ID
            image_name: 图片名称
            expires: URL 过期时间（秒），默认 1 小时
            
        Returns:
            str: 预签名 URL
        """
        object_path = self._adapter.build_image_path(
            user_id, session_id, file_id, image_name
        )
        bucket = self._get_bucket_name()
        storage_path = f"{bucket}/{object_path}"
        
        return await self.get_preview_url(storage_path, expires)
    
    # ========== 辅助方法 ==========
    
    def _get_bucket_name(self) -> str:
        """
        获取默认桶名称
        
        Returns:
            str: 桶名称
        """
        config = get_config_manager()
        return config.get("minio.default_bucket", "knowledge-files")
