#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : base.py
@Author  : caixiongjiang
@Date    : 2026/2/4 15:00
@Function: 
    对象存储适配器抽象基类
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from abc import ABC, abstractmethod
from typing import Optional


class BaseStorageAdapter(ABC):
    """
    对象存储适配器抽象基类
    
    所有存储适配器必须实现此接口，确保接口统一
    支持异步上下文管理器，必须使用 async with 语句
    """
    
    @abstractmethod
    async def __aenter__(self):
        """
        进入异步上下文
        
        Returns:
            BaseStorageAdapter: 适配器实例
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def close(self):
        """
        关闭适配器，清理资源
        
        注意：通常通过上下文管理器自动调用，也可手动调用
        """
        pass
    
    @abstractmethod
    async def download_file(self, storage_path: str) -> bytes:
        """
        下载文件
        
        Args:
            storage_path: 存储路径 (格式由具体适配器决定)
            
        Returns:
            bytes: 文件字节内容
            
        Raises:
            FileNotFoundError: 文件不存在
            StorageError: 下载失败
        """
        pass
    
    @abstractmethod
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
            
        Raises:
            StorageError: 上传失败
        """
        pass
    
    @abstractmethod
    async def delete_file(self, storage_path: str) -> bool:
        """
        删除文件
        
        Args:
            storage_path: 存储路径
            
        Returns:
            bool: 是否删除成功
        """
        pass
    
    @abstractmethod
    async def file_exists(self, storage_path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            storage_path: 存储路径
            
        Returns:
            bool: 文件是否存在
        """
        pass
    
    @abstractmethod
    async def get_presigned_url(
        self,
        storage_path: str,
        expires: int = 3600
    ) -> str:
        """
        生成文件预签名 URL（用于预览）
        
        Args:
            storage_path: 存储路径
            expires: URL 过期时间（秒），默认 1 小时
            
        Returns:
            str: 预签名 URL
            
        Raises:
            StorageError: 生成失败
        """
        pass
    
    @abstractmethod
    def build_raw_file_path(
        self,
        user_id: str,
        session_id: str,
        file_id: str,
        filename: str,
        folder_path: str = "/",
    ) -> str:
        """
        构建原始文件路径
        
        格式: {user_id}/{session_id}{folder_path}{filename}
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            file_id: 文件ID
            filename: 文件名
            folder_path: 文件夹路径（如 /默认上传/、/项目A/文档/），默认根目录
        
        Returns:
            str: 对象路径 (不包含 bucket)
        """
        pass
    
    @abstractmethod
    def build_image_path(
        self,
        user_id: str,
        session_id: str,
        file_id: str,
        image_name: str
    ) -> str:
        """
        构建图片路径
        
        格式: users/{user_id}/sessions/{session_id}/parsed/{file_id}/images/{image_name}
        
        Returns:
            str: 对象路径 (不包含 bucket)
        """
        pass


class StorageError(Exception):
    """存储操作异常基类"""
    pass


class FileNotFoundError(StorageError):
    """文件不存在异常"""
    pass


class UploadError(StorageError):
    """上传失败异常"""
    pass


class DownloadError(StorageError):
    """下载失败异常"""
    pass
