#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : factory.py
@Author  : caixiongjiang
@Date    : 2026/2/4 15:00
@Function: 
    对象存储工厂类
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Dict, Type, Optional
from loguru import logger

from src.db.storage.base import BaseStorageAdapter
from src.utils.config_manager import get_config_manager


class StorageFactory:
    """
    对象存储工厂类
    
    根据配置创建对应的存储适配器，支持工厂模式
    """
    
    _adapters: Dict[str, Type[BaseStorageAdapter]] = {}
    
    @classmethod
    def register_adapter(
        cls,
        storage_type: str,
        adapter_class: Type[BaseStorageAdapter]
    ):
        """
        注册存储适配器
        
        Args:
            storage_type: 存储类型标识 (minio/oss/gcs/s3)
            adapter_class: 适配器类
        """
        cls._adapters[storage_type] = adapter_class
        logger.info(f"已注册存储适配器: {storage_type} -> {adapter_class.__name__}")
    
    @classmethod
    def create_adapter(
        cls,
        storage_type: Optional[str] = None
    ) -> BaseStorageAdapter:
        """
        创建存储适配器
        
        Args:
            storage_type: 存储类型，如果为 None，从配置文件读取
        
        Returns:
            BaseStorageAdapter: 存储适配器实例
            
        Raises:
            ValueError: 不支持的存储类型
        """
        if storage_type is None:
            config = get_config_manager()
            # 目前默认使用 minio，后续可以从配置文件中读取 storage.type
            storage_type = config.get("storage.type", "minio")
        
        adapter_class = cls._adapters.get(storage_type)
        if adapter_class is None:
            raise ValueError(
                f"不支持的存储类型: {storage_type}. "
                f"可用类型: {list(cls._adapters.keys())}"
            )
        
        logger.info(f"创建存储适配器: {storage_type}")
        return adapter_class()
    
    @classmethod
    def get_available_types(cls) -> list[str]:
        """
        获取所有已注册的存储类型
        
        Returns:
            list[str]: 存储类型列表
        """
        return list(cls._adapters.keys())
