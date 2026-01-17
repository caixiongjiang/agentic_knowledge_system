#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : milvus_lite_manager.py
@Author  : caixiongjiang
@Date    : 2026/01/03
@Function: 
    Milvus Lite 本地版连接管理器
    - 用于开发、测试和小规模部署
    - 数据存储在本地文件（milvus.db）
    - 无需启动独立Milvus服务
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import os
import threading
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from pymilvus import connections, utility
from pymilvus.exceptions import MilvusException

from src.db.milvus.connection.base import BaseMilvusManager
from src.utils.env_manager import get_env_manager
from src.utils.config_manager import get_config_manager


class MilvusLiteManager(BaseMilvusManager):
    """Milvus Lite 本地版连接管理器
    
    连接到本地文件数据库，适合开发和测试环境。
    
    特点:
        - 数据存储在本地文件 (milvus.db)
        - 无需启动独立服务
        - 适合开发和测试
        - 支持并发控制（信号量机制）
    """
    
    def __init__(self):
        """初始化Milvus Lite连接管理器"""
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            # 日志记录器（必须在最前面初始化，因为其他方法会用到）
            self.logger = logger
            
            self._config_manager = get_config_manager()
            self._env_manager = get_env_manager()
            
            self._load_config()
            
            self._connected = False
            self._connection_checked = False
            
            # Lite版特有：确保数据目录存在
            self._ensure_data_directory()
            
            # Lite版特有：并发控制信号量
            self._connection_semaphore = threading.Semaphore(self.max_connections)
            
            # 连接到本地数据库
            self._connect()
            
            self._initialized = True
    
    def _load_config(self) -> None:
        """加载Lite版配置"""
        config = self._config_manager.get_milvus_config()
        
        # Lite版使用本地文件路径
        self.db_path = config.get("lite_db_path", "./data/milvus.db")
        
        # 规范化路径（转换为绝对路径）
        self.db_path = os.path.abspath(self.db_path)
        self.uri = self.db_path
        
        # 数据库名称
        self.db_name = config.get("database", "default")
        
        # 连接超时
        self.timeout = config.get("timeout", 30)
        
        # 生成连接别名（使用进程ID确保唯一性）
        alias_prefix = config.get("alias_prefix", "aks_milvus")
        self.alias = f"{alias_prefix}_lite_{os.getpid()}"
        
        # Lite版特有配置：最大连接数
        self.max_connections = config.get("lite_max_connections", 10)
        
        self.logger.debug(
            f"Milvus Lite 配置加载完成: db_path={self.db_path}, "
            f"alias={self.alias}, max_connections={self.max_connections}"
        )
    
    def _ensure_data_directory(self) -> None:
        """确保数据目录存在"""
        db_dir = Path(self.db_path).parent
        
        if not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"创建数据目录: {db_dir}")
    
    def _connect(self) -> bool:
        """连接到Milvus Lite本地数据库
        
        Returns:
            bool: 连接成功返回True，失败返回False
        """
        try:
            if self._connected:
                self.logger.warning("检测到已存在的连接，先断开")
                self._disconnect_internal()
            
            # Lite版连接参数
            connect_params = {
                "alias": self.alias,
                "uri": self.uri,  # 本地文件路径
            }
            
            if self.timeout:
                connect_params["timeout"] = self.timeout
            
            self.logger.debug(f"正在连接 Milvus Lite: {self.uri}")
            
            # 创建连接
            connections.connect(**connect_params)
            
            # 验证连接
            if not self._verify_connection():
                self.logger.error("连接创建成功但验证失败")
                self._connected = False
                return False
            
            self._connected = True
            self._connection_checked = True
            self.logger.info(
                f"成功连接到 Milvus Lite: {self.uri}, "
                f"别名: {self.alias}"
            )
            return True
            
        except MilvusException as e:
            self._connected = False
            self._connection_checked = False
            self.logger.error(f"连接 Milvus Lite 失败 (MilvusException): {e}")
            return False
        except Exception as e:
            self._connected = False
            self._connection_checked = False
            self.logger.error(f"连接 Milvus Lite 失败 (未知异常): {e}", exc_info=True)
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
                self.logger.debug(f"已断开Milvus Lite连接: {self.alias}")
        except Exception as e:
            self.logger.error(f"断开连接时出错: {e}")
    
    def disconnect(self) -> None:
        """断开与Milvus Lite的连接
        
        安全地断开连接并清理资源。
        """
        with self._lock:
            if self._connected:
                try:
                    self._disconnect_internal()
                    self._connected = False
                    self._connection_checked = False
                    self.logger.info(f"已断开Milvus Lite连接: {self.alias}")
                except Exception as e:
                    self.logger.error(f"断开连接时出错: {e}", exc_info=True)
            else:
                self.logger.debug("连接已经是断开状态")
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息（重写基类方法，添加Lite版特有信息）
        
        Returns:
            dict: 包含连接详情的字典
        """
        base_info = super().get_connection_info()
        base_info.update({
            "db_path": self.db_path,
            "database": self.db_name,
            "max_connections": self.max_connections,
        })
        return base_info
    
    # ========== Lite版特有方法 ==========
    
    def has_collection(self, collection_name: str) -> bool:
        """检查集合是否存在
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 存在返回True，不存在返回False
        """
        if not self._ensure_connected():
            self.logger.error("无法连接到Milvus Lite，无法检查集合")
            return False
            
        try:
            exists = utility.has_collection(collection_name, using=self.alias)
            self.logger.debug(f"集合 '{collection_name}' {'存在' if exists else '不存在'}")
            return exists
        except MilvusException as e:
            self.logger.error(f"检查集合是否存在失败: {e}")
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
            self.logger.error("无法连接到Milvus Lite，无法列出集合")
            return []
            
        try:
            collections = utility.list_collections(using=self.alias)
            self.logger.debug(f"当前有 {len(collections)} 个集合")
            return collections
        except Exception as e:
            self.logger.error(f"列出集合失败: {e}")
            self._connection_checked = False
            return []
    
    def acquire_connection(self) -> bool:
        """获取连接（阻塞直到有可用连接）
        
        用于并发控制，防止过多连接同时操作本地数据库。
        
        Returns:
            bool: 成功获取返回True
        """
        self._connection_semaphore.acquire()
        self.logger.debug("获取连接许可")
        return True
    
    def release_connection(self) -> None:
        """释放连接"""
        self._connection_semaphore.release()
        self.logger.debug("释放连接许可")
    
    def backup_database(self, backup_path: str) -> bool:
        """备份数据库文件
        
        Args:
            backup_path: 备份文件保存路径
            
        Returns:
            bool: 备份成功返回True，失败返回False
        """
        import shutil
        
        try:
            if not os.path.exists(self.db_path):
                self.logger.error(f"数据库文件不存在: {self.db_path}")
                return False
            
            # 确保备份目录存在
            backup_dir = os.path.dirname(backup_path)
            if backup_dir and not os.path.exists(backup_dir):
                os.makedirs(backup_dir, exist_ok=True)
            
            shutil.copy2(self.db_path, backup_path)
            self.logger.info(f"数据库备份成功: {self.db_path} -> {backup_path}")
            return True
        except Exception as e:
            self.logger.error(f"备份数据库失败: {e}", exc_info=True)
            return False
    
    def get_database_size(self) -> int:
        """获取数据库文件大小
        
        Returns:
            int: 文件大小（字节），失败返回-1
        """
        try:
            if os.path.exists(self.db_path):
                size = os.path.getsize(self.db_path)
                self.logger.debug(f"数据库文件大小: {size} 字节")
                return size
            else:
                self.logger.warning(f"数据库文件不存在: {self.db_path}")
                return -1
        except Exception as e:
            self.logger.error(f"获取数据库大小失败: {e}")
            return -1
