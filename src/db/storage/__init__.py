#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/2/4 15:00
@Function: 
    对象存储模块，支持多种存储方式（MinIO/OSS/GCS/S3）
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.db.storage.base import (
    BaseStorageAdapter,
    StorageError,
    FileNotFoundError,
    UploadError,
    DownloadError
)
from src.db.storage.factory import StorageFactory
from src.db.storage.manager import StorageManager
from src.db.storage.adapters.minio_adapter import MinIOAdapter

__all__ = [
    "BaseStorageAdapter",
    "StorageError",
    "FileNotFoundError",
    "UploadError",
    "DownloadError",
    "StorageFactory",
    "StorageManager",
    "MinIOAdapter",
]
