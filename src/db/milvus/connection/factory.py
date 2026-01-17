#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : factory.py
@Author  : caixiongjiang
@Date    : 2026/01/03
@Function: 
    Milvus连接管理器工厂
    - 根据配置自动选择Server版或Lite版
    - 提供统一的获取管理器接口
    - 对使用者透明
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Union, Optional
from loguru import logger

from src.utils.config_manager import get_config_manager
from src.db.milvus.connection.base import BaseMilvusManager
from src.db.milvus.connection.milvus_manager import MilvusManager
from src.db.milvus.connection.milvus_lite_manager import MilvusLiteManager


# 缓存已创建的实例
_manager_instance: Optional[Union[MilvusManager, MilvusLiteManager]] = None


def get_milvus_manager(mode: Optional[str] = None) -> BaseMilvusManager:
    """获取Milvus连接管理器（工厂函数）
    
    根据配置自动选择Server版或Lite版。
    
    Args:
        mode: 强制指定模式 "server" 或 "lite"，None则从配置读取
        
    Returns:
        BaseMilvusManager: Milvus管理器实例（Server或Lite）
        
    Examples:
        >>> # 自动选择（根据config.toml中的配置）
        >>> manager = get_milvus_manager()
        
        >>> # 强制使用Lite版
        >>> manager = get_milvus_manager(mode="lite")
        
        >>> # 强制使用Server版
        >>> manager = get_milvus_manager(mode="server")
        
        >>> # 使用上下文管理器
        >>> with get_milvus_manager() as manager:
        ...     collections = manager.list_collections()
    """
    global _manager_instance
    
    # 如果已有实例且模式匹配，直接返回
    if _manager_instance is not None:
        if mode is None:
            return _manager_instance
        
        # 检查类型是否匹配
        if mode == "lite" and isinstance(_manager_instance, MilvusLiteManager):
            return _manager_instance
        elif mode == "server" and isinstance(_manager_instance, MilvusManager):
            return _manager_instance
        else:
            logger.warning(
                f"请求的模式({mode})与现有实例不匹配，"
                f"将使用现有实例: {type(_manager_instance).__name__}"
            )
            return _manager_instance
    
    # 确定使用的模式
    if mode is None:
        config = get_config_manager()
        mode = config.get("milvus.mode", "lite").lower()
    
    mode = mode.lower()
    
    # 创建相应的管理器实例
    if mode == "lite":
        logger.info("创建 Milvus Lite 连接管理器")
        _manager_instance = MilvusLiteManager()
    elif mode == "server":
        logger.info("创建 Milvus Server 连接管理器")
        _manager_instance = MilvusManager()
    else:
        raise ValueError(
            f"不支持的Milvus模式: {mode}，"
            f"请使用 'server' 或 'lite'"
        )
    
    return _manager_instance


def get_milvus_server_manager() -> MilvusManager:
    """强制获取Server版管理器
    
    Returns:
        MilvusManager: Server版管理器实例
        
    Examples:
        >>> manager = get_milvus_server_manager()
        >>> info = manager.get_connection_info()
        >>> print(info['uri'])
    """
    return get_milvus_manager(mode="server")


def get_milvus_lite_manager() -> MilvusLiteManager:
    """强制获取Lite版管理器
    
    Returns:
        MilvusLiteManager: Lite版管理器实例
        
    Examples:
        >>> manager = get_milvus_lite_manager()
        >>> size = manager.get_database_size()
        >>> print(f"数据库大小: {size} 字节")
    """
    return get_milvus_manager(mode="lite")


def reset_manager() -> None:
    """重置管理器实例（主要用于测试）
    
    断开当前连接并清空实例缓存。
    
    Warning:
        此函数会断开所有现有连接，请谨慎使用。
        主要用于单元测试中切换不同的管理器实例。
        
    Examples:
        >>> # 测试中切换管理器
        >>> manager1 = get_milvus_manager(mode="lite")
        >>> reset_manager()
        >>> manager2 = get_milvus_manager(mode="server")
    """
    global _manager_instance
    
    if _manager_instance is not None:
        try:
            _manager_instance.disconnect()
            logger.info(f"已断开 {type(_manager_instance).__name__} 连接")
        except Exception as e:
            logger.error(f"断开连接时出错: {e}")
        finally:
            _manager_instance = None
            logger.info("管理器实例已重置")


def get_manager_type() -> Optional[str]:
    """获取当前管理器类型
    
    Returns:
        str: "server" 或 "lite"，如果未初始化返回None
        
    Examples:
        >>> manager = get_milvus_manager()
        >>> manager_type = get_manager_type()
        >>> print(f"当前使用: {manager_type}")
    """
    global _manager_instance
    
    if _manager_instance is None:
        return None
    elif isinstance(_manager_instance, MilvusLiteManager):
        return "lite"
    elif isinstance(_manager_instance, MilvusManager):
        return "server"
    else:
        return "unknown"


def is_manager_initialized() -> bool:
    """检查管理器是否已初始化
    
    Returns:
        bool: 已初始化返回True，否则返回False
        
    Examples:
        >>> if not is_manager_initialized():
        ...     manager = get_milvus_manager()
    """
    global _manager_instance
    return _manager_instance is not None
