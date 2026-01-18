#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : mongodb_manager.py
@Author  : caixiongjiang
@Date    : 2025/12/31 14:46
@Function: 
    MongoDB 异步连接管理器
    使用 Beanie ODM 和 motor 驱动
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import asyncio
from typing import Optional
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from beanie import init_beanie

from src.utils.env_manager import get_env_manager
from src.utils.config_manager import get_config_manager


class MongoDBManager:
    """
    MongoDB 异步连接管理器（单例模式）
    
    特点：
    - 异步单例模式
    - 自动初始化 Beanie
    - 支持异步上下文管理器
    - 优化的连接池配置
    - 内存安全
    """
    
    _instance: Optional["MongoDBManager"] = None
    _lock = asyncio.Lock()
    _initialized = False
    
    def __new__(cls):
        """防止直接实例化"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    async def get_instance(cls) -> "MongoDBManager":
        """
        获取单例实例（异步）
        
        Returns:
            MongoDBManager 实例
            
        Examples:
            >>> manager = await MongoDBManager.get_instance()
        """
        if cls._instance is None or not cls._instance._initialized:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                
                if not cls._instance._initialized:
                    await cls._instance.initialize()
        
        return cls._instance
    
    async def initialize(self) -> None:
        """
        初始化连接管理器
        
        执行步骤：
        1. 加载配置
        2. 创建异步客户端
        3. 初始化 Beanie
        4. 执行健康检查
        
        注意：此方法应该在 get_instance() 的锁保护下调用
        """
        if self._initialized:
            return
        
        try:
            self.logger = logger
            
            # 1. 加载配置
            self._load_config()
            
            # 2. 创建异步客户端
            await self._connect()
            
            # 3. 初始化 Beanie
            await self._init_beanie()
            
            # 4. 健康检查
            await self._health_check()
            
            self._initialized = True
            self.logger.info("MongoDB连接管理器初始化成功")
        
        except Exception as e:
            self.logger.error(f"MongoDB连接管理器初始化失败: {e}", exc_info=True)
            raise
    
    def _load_config(self) -> None:
        """加载配置"""
        config_manager = get_config_manager()
        env_manager = get_env_manager()
        
        # 从配置文件获取基础配置
        mongodb_config = config_manager.get_mongodb_config()
        
        # 从环境变量获取认证配置
        mongodb_auth = env_manager.get_mongodb_auth()
        
        # 基础配置
        self.host = mongodb_config.get("host", "localhost")
        self.port = mongodb_config.get("port", 27017)
        self.database_name = mongodb_config.get("database", "knowledge_base")
        
        # 认证配置（从环境变量）
        self.username = mongodb_auth.get("user", "")  # 注意：是 'user' 不是 'username'
        self.password = mongodb_auth.get("password", "")
        self.auth_source = mongodb_auth.get("auth_source", "admin")
        
        # 连接池配置
        self.max_pool_size = mongodb_config.get("max_pool_size", 100)
        self.min_pool_size = mongodb_config.get("min_pool_size", 10)
        self.max_idle_time_ms = mongodb_config.get("max_idle_time_ms", 45000)
        self.connect_timeout_ms = mongodb_config.get("connect_timeout_ms", 10000)
        self.server_selection_timeout_ms = mongodb_config.get(
            "server_selection_timeout_ms", 5000
        )
        
        # 日志输出（隐藏敏感信息）
        if self.username:
            self.logger.debug(
                f"MongoDB配置加载完成: {self.host}:{self.port}/{self.database_name} "
                f"(用户: {self.username})"
            )
        else:
            self.logger.debug(
                f"MongoDB配置加载完成: {self.host}:{self.port}/{self.database_name} "
                f"(无认证)"
            )
    
    async def _connect(self) -> None:
        """创建异步客户端连接"""
        try:
            # 构建连接 URI
            if self.username and self.password:
                # 使用认证信息构建 URI
                connection_uri = (
                    f"mongodb://{self.username}:{self.password}@"
                    f"{self.host}:{self.port}/"
                    f"?authSource={self.auth_source}"
                )
                self.logger.debug(f"使用认证连接: {self.username}@{self.host}:{self.port}")
            else:
                # 无认证连接
                connection_uri = f"mongodb://{self.host}:{self.port}/"
                self.logger.debug(f"使用无认证连接: {self.host}:{self.port}")
            
            # 创建异步客户端
            self.client = AsyncIOMotorClient(
                connection_uri,
                maxPoolSize=self.max_pool_size,
                minPoolSize=self.min_pool_size,
                maxIdleTimeMS=self.max_idle_time_ms,
                connectTimeoutMS=self.connect_timeout_ms,
                serverSelectionTimeoutMS=self.server_selection_timeout_ms,
                socketTimeoutMS=20000,
            )
            
            # 获取数据库对象
            self.database: AsyncIOMotorDatabase = self.client[self.database_name]
            
            self.logger.info(f"MongoDB异步客户端创建成功: {self.host}:{self.port}")
        
        except Exception as e:
            self.logger.error(f"创建MongoDB客户端失败: {e}", exc_info=True)
            raise
    
    async def _init_beanie(self) -> None:
        """初始化 Beanie ODM"""
        try:
            self.logger.debug("开始导入 Document 模型...")
            
            # 导入所有 Document 模型
            from src.db.mongodb.models.element_data import ElementData
            from src.db.mongodb.models.chunk_data import ChunkData
            from src.db.mongodb.models.section_data import SectionData
            from src.db.mongodb.models.document_data import DocumentData
            
            self.logger.debug("Document 模型导入完成")
            self.logger.debug("开始初始化 Beanie ODM...")
            
            # 初始化 Beanie（禁用自动索引创建以加快初始化速度）
            # 索引可以在后台异步创建或按需创建
            await asyncio.wait_for(
                init_beanie(
                    database=self.database,
                    document_models=[
                        ElementData,
                        ChunkData,
                        SectionData,
                        DocumentData,
                    ],
                    # 注意：如果索引创建很慢，可以设置 allow_index_dropping=False
                    # 来跳过索引的自动管理
                ),
                timeout=30.0  # 30秒超时
            )
            
            self.logger.info("Beanie ODM 初始化成功")
            self.logger.debug("已注册的模型: ElementData, ChunkData, SectionData, DocumentData")
        
        except asyncio.TimeoutError:
            self.logger.error("Beanie 初始化超时（30秒）")
            self.logger.warning("可能是索引创建过慢，考虑优化索引配置")
            raise TimeoutError("Beanie 初始化超时")
        except Exception as e:
            self.logger.error(f"初始化 Beanie 失败: {e}", exc_info=True)
            raise
    
    async def _health_check(self) -> None:
        """健康检查"""
        try:
            # 执行 ping 命令
            await self.client.admin.command("ping")
            self.logger.debug("MongoDB 健康检查通过")
        
        except Exception as e:
            self.logger.error(f"MongoDB 健康检查失败: {e}", exc_info=True)
            raise
    
    async def disconnect(self) -> None:
        """
        关闭连接
        
        通常在应用退出时调用。
        """
        if hasattr(self, "client"):
            self.client.close()
            self.logger.info("MongoDB 连接已关闭")
    
    async def get_database(self) -> AsyncIOMotorDatabase:
        """
        获取数据库对象
        
        Returns:
            AsyncIOMotorDatabase 实例
        """
        if not self._initialized:
            await self.initialize()
        return self.database
    
    async def is_connected(self) -> bool:
        """
        检查连接状态
        
        Returns:
            连接正常返回 True，否则返回 False
        """
        try:
            await self.client.admin.command("ping")
            return True
        except Exception:
            return False
    
    # ========== 异步上下文管理器 ==========
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        if not self._initialized:
            await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        # 单例模式下不自动断开连接
        # 但可以在异常时记录日志
        if exc_type is not None:
            self.logger.error(
                f"Context manager exit with exception: {exc_val}",
                exc_info=True
            )
    
    # ========== 析构函数 ==========
    
    def __del__(self):
        """析构函数 - 确保资源释放"""
        try:
            if hasattr(self, "client"):
                # 注意：__del__ 中不能使用 await
                # 这里只是记录，实际关闭需要显式调用 disconnect()
                self.logger.warning(
                    "MongoDBManager 被销毁，建议显式调用 disconnect()"
                )
        except Exception:
            pass  # 析构函数不应抛出异常


# ========== 全局实例访问函数 ==========

async def get_mongodb_manager() -> MongoDBManager:
    """
    获取 MongoDB 管理器的便捷函数
    
    Returns:
        MongoDBManager 单例实例
        
    Examples:
        >>> manager = await get_mongodb_manager()
    """
    return await MongoDBManager.get_instance() 