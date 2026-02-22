#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : minio_adapter.py
@Author  : caixiongjiang
@Date    : 2026/2/4 15:00
@Function: 
    MinIO 存储适配器
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from io import BytesIO
from typing import Optional
from minio import Minio
from minio.error import S3Error
from loguru import logger
import urllib3

from src.db.storage.base import (
    BaseStorageAdapter,
    StorageError,
    FileNotFoundError as StorageFileNotFoundError,
    UploadError,
    DownloadError
)
from src.utils.config_manager import get_config_manager
from src.utils.env_manager import get_env_manager


class MinIOAdapter(BaseStorageAdapter):
    """
    MinIO 存储适配器
    
    实现 BaseStorageAdapter 接口，提供 MinIO 特定的实现
    支持文件的上传、下载、删除、预览等操作
    必须使用异步上下文管理器: async with MinIOAdapter() as adapter
    """
    
    def __init__(self):
        """初始化 MinIO 客户端"""
        config = get_config_manager()
        env_manager = get_env_manager()
        
        # 获取完整的存储配置（会根据 storage.type 自动获取对应配置）
        storage_config = config.get_storage_full_config(env_manager)
        
        # 创建自定义的连接池管理器（用于后续清理）
        self._http_client = urllib3.PoolManager(
            timeout=urllib3.Timeout.DEFAULT_TIMEOUT,
            maxsize=10,
            cert_reqs='CERT_REQUIRED',
            ca_certs=None,
            retries=urllib3.Retry(
                total=5,
                backoff_factor=0.2,
                status_forcelist=[500, 502, 503, 504]
            )
        )
        
        # 创建 MinIO 客户端
        self._client = Minio(
            endpoint=storage_config.get("endpoint"),
            access_key=storage_config.get("access_key"),
            secret_key=storage_config.get("secret_key"),
            secure=storage_config.get("secure", False),
            region=storage_config.get("region", "us-east-1"),
            http_client=self._http_client
        )
        
        self._default_bucket = storage_config.get("default_bucket", "knowledge-files")
        self._closed = False
        
        logger.info(
            f"MinIO 客户端初始化完成: "
            f"endpoint={storage_config.get('endpoint')}, "
            f"bucket={self._default_bucket}"
        )
        
        # 确保默认 bucket 存在
        self._ensure_bucket_exists(self._default_bucket)
    
    async def __aenter__(self):
        """进入异步上下文"""
        logger.debug("MinIO 适配器进入上下文")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出异步上下文，清理资源"""
        await self.close()
        return False
    
    async def close(self):
        """
        关闭适配器，清理连接池资源
        
        清理 urllib3 连接池，释放所有连接
        """
        if self._closed:
            return
        
        try:
            # 清理连接池
            if self._http_client:
                self._http_client.clear()
                logger.debug("MinIO 连接池已清理")
            
            self._closed = True
            logger.info("MinIO 适配器已关闭")
        except Exception as e:
            logger.error(f"关闭 MinIO 适配器时出错: {e}")
            raise StorageError(f"关闭适配器失败: {e}")
    
    def _check_closed(self):
        """检查适配器是否已关闭"""
        if self._closed:
            raise StorageError("MinIO 适配器已关闭，无法执行操作")
    
    def _ensure_bucket_exists(self, bucket_name: str) -> None:
        """
        确保 bucket 存在，不存在则创建
        
        Args:
            bucket_name: bucket 名称
        """
        try:
            if not self._client.bucket_exists(bucket_name):
                self._client.make_bucket(bucket_name)
                logger.info(f"创建 MinIO bucket: {bucket_name}")
        except S3Error as e:
            logger.error(f"检查/创建 bucket 失败: {e}")
    
    def _parse_path(self, storage_path: str) -> tuple[str, str]:
        """
        解析存储路径为 (bucket, object_path)
        
        Args:
            storage_path: 存储路径，格式为 "bucket/object_path"
            
        Returns:
            tuple[str, str]: (bucket, object_path)
        """
        parts = storage_path.split('/', 1)
        bucket = parts[0]
        object_path = parts[1] if len(parts) > 1 else ''
        return bucket, object_path
    
    async def download_file(self, storage_path: str) -> bytes:
        """
        从 MinIO 下载文件
        
        Args:
            storage_path: 存储路径，格式为 "bucket/object_path"
            
        Returns:
            bytes: 文件字节内容
            
        Raises:
            FileNotFoundError: 文件不存在
            DownloadError: 下载失败
        """
        self._check_closed()
        
        try:
            bucket, object_path = self._parse_path(storage_path)
            
            # 获取对象
            response = self._client.get_object(bucket, object_path)
            try:
                data = response.read()
                logger.debug(f"成功下载文件: {storage_path}, 大小: {len(data)} bytes")
                return data
            finally:
                response.close()
                response.release_conn()
                
        except S3Error as e:
            if e.code == 'NoSuchKey':
                raise StorageFileNotFoundError(f"文件不存在: {storage_path}")
            else:
                logger.error(f"下载文件失败: {storage_path}, 错误: {e}")
                raise DownloadError(f"下载文件失败: {e}")
        except Exception as e:
            logger.error(f"下载文件失败: {storage_path}, 错误: {e}")
            raise DownloadError(f"下载文件失败: {e}")
    
    async def upload_file(
        self,
        file_bytes: bytes,
        bucket: str,
        object_path: str
    ) -> str:
        """
        上传文件到 MinIO
        
        Args:
            file_bytes: 文件字节内容
            bucket: 桶名称
            object_path: 对象路径
            
        Returns:
            str: 完整存储路径，格式为 "bucket/object_path"
            
        Raises:
            UploadError: 上传失败
        """
        self._check_closed()
        
        try:
            # 确保 bucket 存在
            self._ensure_bucket_exists(bucket)
            
            # 上传文件
            self._client.put_object(
                bucket,
                object_path,
                BytesIO(file_bytes),
                length=len(file_bytes)
            )
            
            storage_path = f"{bucket}/{object_path}"
            logger.debug(f"成功上传文件: {storage_path}, 大小: {len(file_bytes)} bytes")
            return storage_path
            
        except S3Error as e:
            logger.error(f"上传文件失败: {bucket}/{object_path}, 错误: {e}")
            raise UploadError(f"上传文件失败: {e}")
        except Exception as e:
            logger.error(f"上传文件失败: {bucket}/{object_path}, 错误: {e}")
            raise UploadError(f"上传文件失败: {e}")
    
    async def delete_file(self, storage_path: str) -> bool:
        """
        从 MinIO 删除文件
        
        Args:
            storage_path: 存储路径，格式为 "bucket/object_path"
            
        Returns:
            bool: 是否删除成功（如果文件不存在则返回 False）
        """
        self._check_closed()
        
        try:
            # 先检查文件是否存在
            exists = await self.file_exists(storage_path)
            if not exists:
                logger.warning(f"文件不存在，无法删除: {storage_path}")
                return False
            
            bucket, object_path = self._parse_path(storage_path)
            
            self._client.remove_object(bucket, object_path)
            logger.debug(f"成功删除文件: {storage_path}")
            return True
            
        except S3Error as e:
            logger.error(f"删除文件失败: {storage_path}, 错误: {e}")
            return False
        except Exception as e:
            logger.error(f"删除文件失败: {storage_path}, 错误: {e}")
            return False
    
    async def file_exists(self, storage_path: str) -> bool:
        """
        检查文件是否存在于 MinIO
        
        Args:
            storage_path: 存储路径，格式为 "bucket/object_path"
            
        Returns:
            bool: 文件是否存在
        """
        self._check_closed()
        
        try:
            bucket, object_path = self._parse_path(storage_path)
            
            # 使用 stat_object 检查对象是否存在
            self._client.stat_object(bucket, object_path)
            return True
            
        except S3Error as e:
            if e.code == 'NoSuchKey':
                return False
            logger.error(f"检查文件存在性失败: {storage_path}, 错误: {e}")
            return False
        except Exception as e:
            logger.error(f"检查文件存在性失败: {storage_path}, 错误: {e}")
            return False
    
    async def get_presigned_url(
        self,
        storage_path: str,
        expires: int = 3600
    ) -> str:
        """
        生成文件预签名 URL（用于预览）
        
        Args:
            storage_path: 存储路径，格式为 "bucket/object_path"
            expires: URL 过期时间（秒），默认 1 小时
            
        Returns:
            str: 预签名 URL
            
        Raises:
            StorageError: 生成失败
        """
        self._check_closed()
        
        try:
            bucket, object_path = self._parse_path(storage_path)
            
            from datetime import timedelta
            
            # 生成预签名 GET URL
            url = self._client.presigned_get_object(
                bucket,
                object_path,
                expires=timedelta(seconds=expires)
            )
            
            logger.debug(f"成功生成预签名 URL: {storage_path}, 过期时间: {expires}秒")
            return url
            
        except S3Error as e:
            logger.error(f"生成预签名 URL 失败: {storage_path}, 错误: {e}")
            raise StorageError(f"生成预签名 URL 失败: {e}")
        except Exception as e:
            logger.error(f"生成预签名 URL 失败: {storage_path}, 错误: {e}")
            raise StorageError(f"生成预签名 URL 失败: {e}")
    
    def build_raw_file_path(
        self,
        user_id: str,
        session_id: str,
        file_id: str,
        file_suffix: str,
        folder_path: str = "/",
    ) -> str:
        """
        构建原始文件路径
        
        格式: {user_id}/{session_id}{folder_path}{file_id}{file_suffix}
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            file_id: 文件ID
            file_suffix: 文件后缀（含点号，如 .pdf）
            folder_path: 文件夹路径（如 /默认上传/），默认根目录
            
        Returns:
            str: 对象路径 (不包含 bucket)
        """
        storage_filename = f"{file_id}{file_suffix}"
        clean_path = folder_path.strip("/")
        if clean_path:
            return f"{user_id}/{session_id}/{clean_path}/{storage_filename}"
        return f"{user_id}/{session_id}/{storage_filename}"
    
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
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            file_id: 文件ID
            image_name: 图片名称
            
        Returns:
            str: 对象路径 (不包含 bucket)
        """
        return f"users/{user_id}/sessions/{session_id}/parsed/{file_id}/images/{image_name}"


# 注册适配器到工厂
from src.db.storage.factory import StorageFactory
StorageFactory.register_adapter("minio", MinIOAdapter)
