#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : base.py
@Author  : caixiongjiang
@Date    : 2026/01/03
@Function: 
    Milvus连接管理器抽象基类
    - 定义统一的连接管理接口
    - Server和Lite版本都继承此基类
    - 实现内存泄漏防护和线程安全
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import threading
from abc import ABC, abstractmethod
from typing import Dict, Any
from loguru import logger


class BaseMilvusManager(ABC):
    """Milvus连接管理器抽象基类
    
    提供统一的连接管理接口，强制子类实现关键方法。
    
    特点:
        - 单例模式（线程安全）
        - 内存泄漏防护（析构函数、上下文管理器）
        - 线程安全（双重检查锁定）
        - 连接池管理
    
    子类必须实现:
        - _connect(): 连接到Milvus
        - _verify_connection(): 验证连接是否可用
        - disconnect(): 断开连接
    """
    
    _instance = None
    _lock = threading.RLock()  # 可重入锁
    
    def __new__(cls, *args, **kwargs):
        """单例模式实现（线程安全）- 双重检查锁定（DCL）"""
        if cls._instance is None:
            with cls._lock:  # 第一重锁
                if cls._instance is None:  # 第二重检查
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    @abstractmethod
    def _connect(self) -> bool:
        """连接到Milvus
        
        子类必须实现此方法，建立与Milvus的连接。
        
        Returns:
            bool: 连接成功返回True，失败返回False
        """
        pass
    
    @abstractmethod
    def _verify_connection(self) -> bool:
        """验证连接是否可用
        
        子类必须实现此方法，验证当前连接的有效性。
        
        Returns:
            bool: 连接可用返回True，否则返回False
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """断开连接
        
        子类必须实现此方法，安全地断开与Milvus的连接。
        """
        pass
    
    # ========== 公共方法（由基类实现） ==========
    
    def _ensure_connected(self) -> bool:
        """确保已连接到Milvus（线程安全）
        
        检查连接状态，如果未连接或连接失效则尝试重连。
        
        Returns:
            bool: 连接可用返回True，否则返回False
        """
        with self._lock:
            # 如果标记为未连接，尝试重连
            if not self._connected:
                logger.warning("连接已断开，尝试重新连接...")
                return self._connect()
            
            # 如果标记为已连接，但未验证过，验证连接
            if not self._connection_checked:
                if not self._verify_connection():
                    logger.warning("连接验证失败，尝试重新连接...")
                    return self._connect()
                self._connection_checked = True
            
            return True
    
    def check_connection(self) -> bool:
        """检查连接状态
        
        不会尝试重连，仅检查当前连接是否可用。
        
        Returns:
            bool: 连接可用返回True，否则返回False
        """
        if not self._connected:
            return False
        
        # 验证连接真实状态
        if self._verify_connection():
            self._connection_checked = True
            return True
        else:
            # 连接已失效，更新状态
            self._connected = False
            self._connection_checked = False
            return False
    
    def reconnect(self) -> bool:
        """强制重新连接
        
        Returns:
            bool: 重连成功返回True，失败返回False
        """
        with self._lock:
            logger.info("执行强制重连...")
            self._connected = False
            self._connection_checked = False
            return self._connect()
    
    def get_connection_alias(self) -> str:
        """获取连接别名
        
        Returns:
            str: 连接别名
        """
        return getattr(self, 'alias', 'default')
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息
        
        Returns:
            dict: 包含连接详情的字典
        """
        return {
            "connected": getattr(self, '_connected', False),
            "connection_checked": getattr(self, '_connection_checked', False),
            "alias": self.get_connection_alias(),
        }
    
    # ========== 内存泄漏防护 ==========
    
    def __del__(self):
        """析构函数 - 确保资源释放
        
        注意: 由于单例模式，此方法可能不会被调用，
        建议在应用退出时显式调用disconnect()
        """
        try:
            if hasattr(self, '_connected') and self._connected:
                logger.debug(f"{self.__class__.__name__} 析构，释放连接资源...")
                self.disconnect()
        except Exception:
            # 析构函数不应抛出异常
            pass
    
    def __enter__(self):
        """上下文管理器入口"""
        self._ensure_connected()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        # 单例模式不自动断开，但标记需要检查
        if exc_type is not None:
            self._connection_checked = False
