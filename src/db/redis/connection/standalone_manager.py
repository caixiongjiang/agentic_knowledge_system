#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : standalone_manager.py
@Author  : caixiongjiang
@Date    : 2026/01/22
@Function: 
    Redis Standalone 单机模式连接管理器
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional, Any
from urllib.parse import quote_plus
from loguru import logger
from redis import asyncio as aioredis

from src.db.redis.connection.base import BaseRedisManager
from src.utils.env_manager import get_env_manager
from src.utils.config_manager import get_config_manager

env_manager = get_env_manager()
config_manager = get_config_manager()


class StandaloneRedisManager(BaseRedisManager):
    """Redis Standalone 单机模式连接管理器"""
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        max_connections: Optional[int] = None,
        socket_timeout: Optional[float] = None,
        socket_connect_timeout: Optional[float] = None,
        decode_responses: bool = True,
        encoding: str = "utf-8",
        **kwargs
    ):
        """
        初始化 Redis Standalone 连接管理器
        
        Args:
            host: Redis 主机地址
            port: Redis 端口
            db: 数据库编号（0-15）
            username: Redis 用户名（Redis 6.0+）
            password: Redis 密码
            max_connections: 连接池最大连接数
            socket_timeout: Socket 超时时间（秒）
            socket_connect_timeout: Socket 连接超时时间（秒）
            decode_responses: 是否自动解码为字符串（默认 True）
            encoding: 字符编码（默认 utf-8）
            **kwargs: 其他连接参数
        """
        super().__init__()
        
        # 从配置文件读取 Redis 配置
        redis_config = config_manager.get_redis_config()
        redis_auth = env_manager.get_redis_auth()
        
        # 优先使用参数，其次使用配置文件，最后使用默认值
        self.host = host or redis_config.get("host", "localhost")
        self.port = port or redis_config.get("port", 6379)
        self.db = db if db is not None else redis_config.get("db", 0)
        
        # 认证信息：优先从参数获取，其次从环境变量获取
        self.username = username or redis_auth.get("username", "")
        
        if password:
            self.password = password
        else:
            self.password = redis_auth.get("password", "")
        
        # 连接池配置
        self.max_connections = (
            max_connections if max_connections is not None
            else redis_config.get("max_connections", 50)
        )
        self.socket_timeout = (
            socket_timeout if socket_timeout is not None
            else redis_config.get("socket_timeout", 5.0)
        )
        self.socket_connect_timeout = (
            socket_connect_timeout if socket_connect_timeout is not None
            else redis_config.get("socket_connect_timeout", 5.0)
        )
        
        # 编码配置
        self.decode_responses = decode_responses
        self.encoding = encoding
        
        # 其他配置
        self.extra_kwargs = kwargs
        
        logger.info(
            f"Redis Standalone 连接管理器配置完成: "
            f"{self.host}:{self.port}/{self.db}"
        )
    
    def get_redis_url(self) -> str:
        """
        获取 Redis 连接 URL
        
        Returns:
            Redis 连接 URL（格式：redis://[[username:]password@]host:port/db）
        """
        # 构建认证部分
        auth_part = ""
        if self.password:
            password_encoded = quote_plus(self.password)
            if self.username:
                username_encoded = quote_plus(self.username)
                auth_part = f"{username_encoded}:{password_encoded}@"
            else:
                auth_part = f":{password_encoded}@"
        elif self.username:
            username_encoded = quote_plus(self.username)
            auth_part = f"{username_encoded}@"
        
        return f"redis://{auth_part}{self.host}:{self.port}/{self.db}"
    
    async def _create_pool(self) -> aioredis.ConnectionPool:
        """
        创建 Redis 连接池
        
        Returns:
            Redis 异步连接池对象
        """
        pool = aioredis.ConnectionPool(
            host=self.host,
            port=self.port,
            db=self.db,
            username=self.username if self.username else None,
            password=self.password if self.password else None,
            max_connections=self.max_connections,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
            decode_responses=self.decode_responses,
            encoding=self.encoding,
            **self.extra_kwargs
        )
        
        logger.info(
            f"Redis 连接池创建成功: {self.host}:{self.port}/{self.db}, "
            f"最大连接数: {self.max_connections}"
        )
        
        return pool
    
    async def _close_pool(self) -> None:
        """关闭 Redis 连接池"""
        if self.pool:
            await self.pool.aclose()
            await self.pool.disconnect()
            self.pool = None
            logger.info("Redis 连接池已关闭")
    
    async def select_db(self, db: int) -> bool:
        """
        切换到指定的数据库
        
        Args:
            db: 数据库编号（0-15）
        
        Returns:
            操作是否成功
        """
        try:
            result = await self.execute("SELECT", db)
            if result:
                self.db = db
                logger.info(f"已切换到数据库: {db}")
                return True
            return False
        except Exception as e:
            logger.error(f"切换数据库失败: {e}")
            return False
    
    async def get_client_list(self) -> list:
        """
        获取所有连接到服务器的客户端列表
        
        Returns:
            客户端信息列表
        """
        return await self.execute("CLIENT", "LIST")
    
    async def get_memory_stats(self) -> dict:
        """
        获取内存统计信息
        
        Returns:
            内存统计字典
        """
        return await self.execute("MEMORY", "STATS")
