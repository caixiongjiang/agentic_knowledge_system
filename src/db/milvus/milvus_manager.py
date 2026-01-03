#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : milvus_manager.py
@Author  : caixiongjiang
@Date    : 2025/12/31 14:46
@Function: 
    Milvus向量数据库连接管理器（Server版）
    - 单例模式管理连接
    - 支持连接池和连接状态检查
    - 自动重连机制
@Modify History:
    2026/01/01: 修复配置获取方式、连接管理和内存泄漏问题
    2026/01/03: 重构为继承BaseMilvusManager的Server版实现
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import uuid
from typing import Dict, Any
from loguru import logger

from pymilvus import connections, utility
from pymilvus.exceptions import MilvusException

from src.db.milvus.milvus_base import BaseMilvusManager
from src.utils.env_manager import get_env_manager
from src.utils.config_manager import get_config_manager


class MilvusManager(BaseMilvusManager):
    """Milvus数据库连接管理器（Server版）
    
    连接到远程Milvus服务器，支持完整的认证和连接池管理。
    
    特点:
        - 连接到远程Milvus服务器
        - 支持用户名/密码/Token认证
        - 完整的连接管理和健康检查
        - 继承BaseMilvusManager的线程安全单例实现
    """
    
    def __init__(self):
        """初始化Milvus连接管理器
        
        配置从ConfigManager和EnvManager中获取:
        - ConfigManager: host, port, database, timeout等非敏感配置
        - EnvManager: username, password, token等敏感认证信息
        """
        # 避免重复初始化
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            # 日志记录器（必须在最前面初始化，因为其他方法会用到）
            self.logger = logger
            
            # 获取配置管理器
            self._config_manager = get_config_manager()
            self._env_manager = get_env_manager()
            
            # 加载配置
            self._load_config()
            
            # 连接状态
            self._connected = False
            self._connection_checked = False
            
            # 连接到Milvus服务器
            self._connect()
            
            # 标记初始化完成
            self._initialized = True
    
    def _load_config(self) -> None:
        """从配置管理器加载Milvus配置"""
        # 从ConfigManager获取公共配置
        config = self._config_manager.get_milvus_config()
        
        # 从EnvManager获取认证信息
        auth = self._env_manager.get_milvus_auth()
        
        # 构建URI
        host = config.get("host", "localhost")
        port = config.get("port", 19530)
        self.uri = f"http://{host}:{port}"
        
        # 数据库名称
        self.db_name = config.get("database", "default")
        
        # 连接超时
        self.timeout = config.get("timeout", 30)
        
        # 认证信息
        self.username = auth.get("user", "")
        self.password = auth.get("password", "")
        self.token = auth.get("token", "")
        
        # 如果没有提供token但有用户名和密码，自动生成token
        if not self.token and self.username and self.password:
            self.token = f"{self.username}:{self.password}"
        
        # 生成连接别名
        alias_prefix = config.get("alias_prefix", "aks_milvus")
        self.alias = f"{alias_prefix}_{uuid.uuid4().hex[:8]}"
        
        self.logger.debug(
            f"Milvus配置加载完成: uri={self.uri}, "
            f"db={self.db_name}, alias={self.alias}"
        )
    
    def _connect(self) -> bool:
        """连接到Milvus服务器
        
        Returns:
            bool: 连接成功返回True，失败返回False
        """
        try:
            # 如果已经连接，先断开旧连接
            if self._connected:
                self.logger.warning("检测到已存在的连接，先断开旧连接")
                self._disconnect_internal()
            
            # 准备连接参数
            connect_params = {
                "alias": self.alias,
                "uri": self.uri,
                "db_name": self.db_name
            }
            
            # 添加超时配置
            if self.timeout:
                connect_params["timeout"] = self.timeout
            
            # 添加认证信息（如果提供）
            auth_method = "无认证"
            if self.token:
                connect_params["token"] = self.token
                auth_method = "token认证"
            elif self.username and self.password:
                connect_params["user"] = self.username
                connect_params["password"] = self.password
                auth_method = f"用户名/密码认证({self.username})"
            
            self.logger.debug(f"正在连接Milvus: {self.uri}, 认证方式: {auth_method}")
            
            # 创建连接
            connections.connect(**connect_params)
            
            # 验证连接是否真正建立
            if not self._verify_connection():
                self.logger.error("连接创建成功但验证失败")
                self._connected = False
                return False
            
            self._connected = True
            self._connection_checked = True
            self.logger.info(
                f"成功连接到Milvus服务器: {self.uri}, "
                f"数据库: {self.db_name}, 别名: {self.alias}"
            )
            return True
            
        except MilvusException as e:
            self._connected = False
            self._connection_checked = False
            self.logger.error(f"连接Milvus服务器失败 (MilvusException): {e}")
            return False
        except Exception as e:
            self._connected = False
            self._connection_checked = False
            self.logger.error(f"连接Milvus服务器失败 (未知异常): {e}", exc_info=True)
            return False
    
    def _verify_connection(self) -> bool:
        """验证连接是否真正可用
        
        Returns:
            bool: 连接可用返回True，否则返回False
        """
        try:
            # 尝试列出集合，验证连接
            utility.list_collections(using=self.alias)
            return True
        except Exception as e:
            self.logger.error(f"连接验证失败: {e}")
            return False
    
    def _disconnect_internal(self) -> None:
        """内部断开连接方法（不加锁）"""
        try:
            if connections.has_connection(self.alias):
                connections.disconnect(self.alias)
                self.logger.debug(f"已断开Milvus连接: {self.alias}")
        except Exception as e:
            self.logger.error(f"断开连接时出错: {e}")
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息（重写基类方法，添加Server版特有信息）
        
        Returns:
            dict: 包含连接详情的字典
        """
        base_info = super().get_connection_info()
        base_info.update({
            "uri": self.uri,
            "database": self.db_name,
            "has_auth": bool(self.username or self.token),
        })
        return base_info
    
    def has_collection(self, collection_name: str) -> bool:
        """检查集合是否存在
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 存在返回True，不存在返回False
        """
        if not self._ensure_connected():
            self.logger.error("无法连接到Milvus，无法检查集合")
            return False
            
        try:
            exists = utility.has_collection(collection_name, using=self.alias)
            self.logger.debug(f"集合 '{collection_name}' {'存在' if exists else '不存在'}")
            return exists
        except MilvusException as e:
            self.logger.error(f"检查集合是否存在失败: {e}")
            # 连接可能已失效，标记需要重新检查
            self._connection_checked = False
            return False
        except Exception as e:
            self.logger.error(f"检查集合时发生未知错误: {e}", exc_info=True)
            return False
    
    def list_collections(self) -> list:
        """列出所有集合
        
        Returns:
            list: 集合名称列表，失败返回空列表
        """
        if not self._ensure_connected():
            self.logger.error("无法连接到Milvus，无法列出集合")
            return []
            
        try:
            collections = utility.list_collections(using=self.alias)
            self.logger.debug(f"当前有 {len(collections)} 个集合")
            return collections
        except Exception as e:
            self.logger.error(f"列出集合失败: {e}")
            self._connection_checked = False
            return []
    
    def disconnect(self) -> None:
        """断开与Milvus的连接
        
        安全地断开连接并清理资源。
        """
        with self._lock:
            if self._connected:
                try:
                    self._disconnect_internal()
                    self._connected = False
                    self._connection_checked = False
                    self.logger.info(f"已断开Milvus连接: {self.alias}")
                except Exception as e:
                    self.logger.error(f"断开连接时出错: {e}", exc_info=True)
            else:
                self.logger.debug("连接已经是断开状态")
