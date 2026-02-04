#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_base.py
@Author  : caixiongjiang
@Date    : 2026/2/4 16:00
@Function: 
    测试存储基类和异常定义
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.db.storage.base import (
    BaseStorageAdapter,
    StorageError,
    FileNotFoundError,
    UploadError,
    DownloadError
)


class TestStorageExceptions:
    """测试存储异常类"""
    
    def test_storage_error(self):
        """测试 StorageError"""
        error = StorageError("Storage error occurred")
        assert isinstance(error, Exception)
        assert str(error) == "Storage error occurred"
        print("✓ StorageError 测试通过")
    
    def test_file_not_found_error(self):
        """测试 FileNotFoundError"""
        error = FileNotFoundError("File not found")
        assert isinstance(error, StorageError)
        assert str(error) == "File not found"
        print("✓ FileNotFoundError 测试通过")
    
    def test_upload_error(self):
        """测试 UploadError"""
        error = UploadError("Upload failed")
        assert isinstance(error, StorageError)
        assert str(error) == "Upload failed"
        print("✓ UploadError 测试通过")
    
    def test_download_error(self):
        """测试 DownloadError"""
        error = DownloadError("Download failed")
        assert isinstance(error, StorageError)
        assert str(error) == "Download failed"
        print("✓ DownloadError 测试通过")


class TestBaseStorageAdapter:
    """测试存储适配器基类"""
    
    def test_base_adapter_is_abstract(self):
        """测试基类是抽象类"""
        from abc import ABC
        
        assert issubclass(BaseStorageAdapter, ABC)
        print("✓ BaseStorageAdapter 是抽象基类")
    
    def test_required_methods(self):
        """测试必需实现的方法"""
        required_methods = [
            'download_file',
            'upload_file',
            'delete_file',
            'file_exists',
            'get_presigned_url',
            'build_raw_file_path',
            'build_image_path',
        ]
        
        for method_name in required_methods:
            assert hasattr(BaseStorageAdapter, method_name)
            print(f"✓ 方法 {method_name} 存在")


def run_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("测试存储基类和异常")
    print("=" * 60 + "\n")
    
    # 测试异常
    exception_test = TestStorageExceptions()
    exception_test.test_storage_error()
    exception_test.test_file_not_found_error()
    exception_test.test_upload_error()
    exception_test.test_download_error()
    
    print()
    
    # 测试基类
    base_test = TestBaseStorageAdapter()
    base_test.test_base_adapter_is_abstract()
    base_test.test_required_methods()
    
    print("\n" + "=" * 60)
    print("所有测试通过！✓")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_tests()
