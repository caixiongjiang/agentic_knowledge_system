#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : base.py
@Author  : caixiongjiang
@Date    : 2026/01/22
@Function: 
    Redis 连接管理器基类，定义统一的 Redis 连接管理接口
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Any, Dict
import asyncio
from loguru import logger


class BaseRedisManager(ABC):
    """Redis 连接管理器基类（抽象类）"""
    
    # Redis 命令到 redis-py 方法的映射表
    # 用于处理命令名和方法名不一致的情况
    COMMAND_MAPPING = {
        "DEL": "delete",           # DEL -> delete (del 是 Python 关键字)
        "EXEC": "execute",         # EXEC -> execute
        "CONFIG": "config_get",    # CONFIG GET -> config_get
        "OBJECT": "object",        # OBJECT -> object
        "SCRIPT": "script",        # SCRIPT -> script
    }
    
    def __init__(self):
        """初始化连接管理器"""
        self.pool: Optional[Any] = None
        self._initialized: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()
    
    @abstractmethod
    async def _create_pool(self) -> Any:
        """
        创建 Redis 连接池（子类实现）
        
        Returns:
            连接池对象
        """
        pass
    
    @abstractmethod
    def get_redis_url(self) -> str:
        """
        获取 Redis 连接 URL（子类实现）
        
        Returns:
            Redis 连接 URL
        """
        pass
    
    @abstractmethod
    async def _close_pool(self) -> None:
        """关闭连接池（子类实现）"""
        pass
    
    async def initialize(self) -> None:
        """
        初始化连接池（幂等操作）
        
        使用异步锁确保只初始化一次
        """
        if self._initialized:
            return
        
        async with self._lock:
            # 双重检查锁定模式
            if self._initialized:
                return
            
            self.pool = await self._create_pool()
            self._initialized = True
            logger.info(f"Redis 连接池初始化成功: {self.get_redis_url()}")
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Any, None]:
        """
        获取 Redis 连接的异步上下文管理器
        
        使用方法:
        ```python
        async with manager.get_connection() as conn:
            await conn.set("key", "value")
            value = await conn.get("key")
        ```
        
        Yields:
            Redis 连接对象
        """
        if not self._initialized:
            await self.initialize()
        
        # redis.asyncio 使用连接池自动管理连接
        from redis import asyncio as aioredis
        
        conn = aioredis.Redis(connection_pool=self.pool)
        try:
            yield conn
        except Exception as e:
            logger.error(f"Redis 连接发生错误: {e}")
            raise
        finally:
            await conn.aclose()
    
    async def execute(self, command: str, *args, **kwargs) -> Any:
        """
        执行 Redis 命令的通用方法
        
        Args:
            command: Redis 命令名称（如 "GET", "SET", "HGET" 等）
            *args: 命令参数
            **kwargs: 命令关键字参数
        
        Returns:
            命令执行结果
        
        Examples:
            >>> await manager.execute("SET", "key", "value", ex=3600)
            >>> await manager.execute("GET", "key")
            >>> await manager.execute("HGET", "hash_key", "field")
        """
        async with self.get_connection() as conn:
            # 检查是否需要映射命令名
            command_upper = command.upper()
            if command_upper in self.COMMAND_MAPPING:
                method_name = self.COMMAND_MAPPING[command_upper]
            else:
                method_name = command.lower()
            
            # 获取对应的方法
            method = getattr(conn, method_name, None)
            if method is None:
                raise ValueError(f"不支持的 Redis 命令: {command} (方法名: {method_name})")
            
            return await method(*args, **kwargs)
    
    async def ping(self) -> bool:
        """
        测试 Redis 连接是否正常（PING 命令）
        
        Returns:
            连接正常返回 True，否则返回 False
        """
        try:
            result = await self.execute("PING")
            return result == True or result == b'PONG' or result == 'PONG'
        except Exception as e:
            logger.error(f"Redis PING 失败: {e}")
            return False
    
    async def health_check(self) -> bool:
        """
        健康检查：验证 Redis 连接是否正常
        
        Returns:
            连接正常返回 True，否则返回 False
        """
        return await self.ping()
    
    async def close(self) -> None:
        """关闭 Redis 连接池"""
        if self.pool:
            await self._close_pool()
            self._initialized = False
            logger.info("Redis 连接池已关闭")
    
    async def __aenter__(self):
        """
        支持异步上下文管理器
        
        使用方法:
        ```python
        async with get_redis_manager() as manager:
            await manager.execute("SET", "key", "value")
        ```
        
        Returns:
            self: 管理器实例
        """
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        退出上下文时关闭连接池
        
        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪
        """
        await self.close()
        return False  # 不抑制异常
    
    async def get_info(self, section: Optional[str] = None) -> Dict[str, Any]:
        """
        获取 Redis 服务器信息
        
        Args:
            section: 信息节名称（如 "server", "clients", "memory" 等）
                    如果为 None，则返回所有信息
        
        Returns:
            服务器信息字典
        """
        if section:
            return await self.execute("INFO", section)
        else:
            return await self.execute("INFO")
    
    async def get_db_size(self) -> int:
        """
        获取当前数据库的键数量
        
        Returns:
            键数量
        """
        return await self.execute("DBSIZE")
    
    async def flush_db(self, asynchronous: bool = True) -> bool:
        """
        清空当前数据库的所有键
        
        Args:
            asynchronous: 是否异步清空（默认 True，不阻塞）
        
        Returns:
            操作是否成功
        """
        if asynchronous:
            result = await self.execute("FLUSHDB", "ASYNC")
        else:
            result = await self.execute("FLUSHDB")
        return result == True or result == b'OK' or result == 'OK'
