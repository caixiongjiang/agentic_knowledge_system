#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_factory.py
@Author  : caixiongjiang
@Date    : 2026/2/4 16:00
@Function: 
    测试存储工厂类
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path
import asyncio

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.db.storage.factory import StorageFactory
from src.db.storage.base import BaseStorageAdapter
from src.db.storage.adapters.minio_adapter import MinIOAdapter


class TestStorageFactory:
    """测试存储工厂类（使用上下文管理器）"""
    
    def test_register_adapter(self):
        """测试注册适配器"""
        # MinIO 适配器应该已经注册
        available_types = StorageFactory.get_available_types()
        assert "minio" in available_types
        print(f"✓ MinIO 适配器已注册，可用类型: {available_types}")
    
    async def test_create_minio_adapter(self):
        """测试创建 MinIO 适配器（使用上下文管理器）"""
        async with StorageFactory.create_adapter("minio") as adapter:
            assert isinstance(adapter, BaseStorageAdapter)
            assert isinstance(adapter, MinIOAdapter)
            print("✓ 成功创建 MinIO 适配器")
    
    async def test_create_adapter_from_config(self):
        """测试从配置创建适配器（使用上下文管理器）"""
        # 不传参数，应该从配置文件读取（默认 minio）
        async with StorageFactory.create_adapter() as adapter:
            assert isinstance(adapter, BaseStorageAdapter)
            print("✓ 从配置文件创建适配器成功")
    
    def test_invalid_storage_type(self):
        """测试无效的存储类型"""
        try:
            StorageFactory.create_adapter("invalid_type")
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "不支持的存储类型" in str(e)
            print(f"✓ 正确处理无效存储类型: {e}")
    
    def test_get_available_types(self):
        """测试获取可用存储类型"""
        types = StorageFactory.get_available_types()
        assert isinstance(types, list)
        assert len(types) > 0
        assert "minio" in types
        print(f"✓ 可用存储类型: {types}")


async def run_tests():
    """运行所有测试（支持异步）"""
    print("\n" + "=" * 60)
    print("测试存储工厂类")
    print("=" * 60 + "\n")
    
    test = TestStorageFactory()
    test.test_register_adapter()
    await test.test_create_minio_adapter()
    await test.test_create_adapter_from_config()
    test.test_invalid_storage_type()
    test.test_get_available_types()
    
    print("\n" + "=" * 60)
    print("所有测试通过！✓")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
