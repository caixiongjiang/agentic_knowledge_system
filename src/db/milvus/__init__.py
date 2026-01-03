#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2025/12/31 14:44
@Function: 
    Milvus模块统一导出
    - 连接层：工厂函数、管理器类
    - 提供简洁的导入接口
@Modify History:
    2026/01/03: 重构连接层，添加工厂模式和Lite版支持
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

# ========== 连接层导出 ==========

# 抽象基类
from src.db.milvus.milvus_base import BaseMilvusManager

# 具体实现
from src.db.milvus.milvus_manager import MilvusManager
from src.db.milvus.milvus_lite_manager import MilvusLiteManager

# 工厂函数（推荐使用）
from src.db.milvus.milvus_factory import (
    get_milvus_manager,           # 主要接口：自动选择Server/Lite
    get_milvus_server_manager,    # 强制获取Server版
    get_milvus_lite_manager,      # 强制获取Lite版
    reset_manager,                # 重置管理器实例
    get_manager_type,             # 获取当前管理器类型
    is_manager_initialized,       # 检查是否已初始化
)


__all__ = [
    # 基类
    "BaseMilvusManager",
    
    # 具体实现
    "MilvusManager",
    "MilvusLiteManager",
    
    # 工厂函数（推荐使用）
    "get_milvus_manager",
    "get_milvus_server_manager",
    "get_milvus_lite_manager",
    "reset_manager",
    "get_manager_type",
    "is_manager_initialized",
]


# ========== 使用示例 ==========
"""
基本使用:
    >>> from src.db.milvus import get_milvus_manager
    >>> 
    >>> # 自动选择（根据配置）
    >>> manager = get_milvus_manager()
    >>> collections = manager.list_collections()
    >>> 
    >>> # 使用上下文管理器
    >>> with get_milvus_manager() as manager:
    ...     info = manager.get_connection_info()
    ...     print(info)

强制指定模式:
    >>> from src.db.milvus import get_milvus_lite_manager
    >>> 
    >>> # 使用Lite版（开发/测试）
    >>> lite_manager = get_milvus_lite_manager()
    >>> size = lite_manager.get_database_size()
    >>> 
    >>> # 备份数据库
    >>> lite_manager.backup_database("./backup/milvus.db.bak")

Server版使用:
    >>> from src.db.milvus import get_milvus_server_manager
    >>> 
    >>> # 使用Server版（生产环境）
    >>> server_manager = get_milvus_server_manager()
    >>> info = server_manager.get_connection_info()
    >>> print(f"连接到: {info['uri']}")

测试场景:
    >>> from src.db.milvus import reset_manager, get_manager_type
    >>> 
    >>> # 检查当前管理器类型
    >>> print(get_manager_type())  # "server" 或 "lite"
    >>> 
    >>> # 重置管理器（测试用）
    >>> reset_manager()
"""
