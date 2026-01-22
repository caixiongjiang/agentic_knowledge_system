#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : factory.py
@Author  : caixiongjiang
@Date    : 2026/01/22
@Function: 
    Redis 连接管理器工厂，根据配置自动创建对应的连接管理器
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Literal, Optional, Dict, Any
from loguru import logger

from src.db.redis.connection.base import BaseRedisManager
from src.db.redis.connection.standalone_manager import StandaloneRedisManager
from src.db.redis.connection.cluster_manager import ClusterRedisManager
from src.utils.config_manager import get_config_manager
from src.utils.env_manager import get_env_manager

config_manager = get_config_manager()
env_manager = get_env_manager()

RedisType = Literal["standalone", "cluster"]


class RedisManagerFactory:
    """Redis 连接管理器工厂"""
    
    _managers: Dict[str, BaseRedisManager] = {}
    
    @classmethod
    def _generate_cache_key(
        cls,
        redis_type: str,
        **kwargs
    ) -> str:
        """
        生成缓存键，用于区分不同配置的管理器实例
        
        Args:
            redis_type: Redis 类型
            **kwargs: 配置参数
        
        Returns:
            缓存键字符串
        """
        # 从配置文件读取默认值
        redis_config = config_manager.get_redis_config()
        
        # 获取关键配置参数（用于区分不同的实例）
        host = kwargs.get("host", redis_config.get("host", "localhost"))
        port = kwargs.get("port", redis_config.get("port", 6379))
        db = kwargs.get("db", redis_config.get("db", 0))
        
        # 生成缓存键：redis_type:host:port:db
        cache_key = f"{redis_type}:{host}:{port}:{db}"
        return cache_key
    
    @classmethod
    async def get_manager(
        cls,
        redis_type: Optional[RedisType] = None,
        **kwargs
    ) -> BaseRedisManager:
        """
        获取 Redis 连接管理器
        
        Args:
            redis_type: Redis 类型（"standalone" 或 "cluster"）
                       如果不指定则从配置文件的 redis.mode 读取，默认为 "standalone"
            **kwargs: 传递给管理器的额外参数，会覆盖配置文件的值
        
        Returns:
            BaseRedisManager: Redis 连接管理器实例
        
        配置文件示例 (config.toml):
            [redis]
            mode = "standalone"  # 或 "cluster"
            
            # Standalone 配置
            host = "localhost"
            port = 6379
            db = 0
            max_connections = 50
            socket_timeout = 5.0
            socket_connect_timeout = 5.0
            
            # Cluster 配置（可选）
            # startup_nodes = [
            #     {host = "127.0.0.1", port = 7000},
            #     {host = "127.0.0.1", port = 7001},
            # ]
        
        Examples:
            # 使用 Standalone 模式
            manager = await RedisManagerFactory.get_manager("standalone")
            
            # 使用 Cluster 模式
            manager = await RedisManagerFactory.get_manager("cluster")
            
            # 从配置文件读取（读取 redis.mode）
            manager = await RedisManagerFactory.get_manager()
            
            # 使用自定义参数覆盖配置
            manager = await RedisManagerFactory.get_manager(
                "standalone",
                host="192.168.1.100",
                port=6380
            )
        """
        # 如果未指定类型，从配置文件读取
        if redis_type is None:
            redis_type = config_manager.get("redis.mode", "standalone")
            if redis_type not in ["standalone", "cluster"]:
                logger.warning(
                    f"配置中的 Redis 类型 '{redis_type}' 不支持，"
                    f"使用默认值 'standalone'"
                )
                redis_type = "standalone"
        
        # 生成缓存键（包含配置参数）
        cache_key = cls._generate_cache_key(redis_type, **kwargs)
        
        # 检查是否已创建该配置的管理器
        if cache_key in cls._managers:
            logger.debug(f"返回缓存的 Redis 管理器: {cache_key}")
            return cls._managers[cache_key]
        
        # 创建新的管理器
        if redis_type == "standalone":
            manager = await cls._create_standalone_manager(**kwargs)
        elif redis_type == "cluster":
            manager = await cls._create_cluster_manager(**kwargs)
        else:
            raise ValueError(
                f"不支持的 Redis 类型: {redis_type}，"
                f"支持的类型: standalone, cluster"
            )
        
        # 缓存管理器实例
        cls._managers[cache_key] = manager
        logger.info(f"创建 {redis_type} Redis 连接管理器: {cache_key}")
        
        return manager
    
    @classmethod
    async def _create_standalone_manager(cls, **kwargs) -> StandaloneRedisManager:
        """
        创建 Standalone 模式管理器
        
        Args:
            **kwargs: 覆盖配置文件的参数
        
        Returns:
            StandaloneRedisManager 实例
        """
        # 从配置文件读取 Redis 配置
        redis_config = config_manager.get_redis_config()
        redis_auth = env_manager.get_redis_auth()
        
        # 合并配置：kwargs > 配置文件
        config = {
            "host": kwargs.get("host", redis_config.get("host")),
            "port": kwargs.get("port", redis_config.get("port")),
            "db": kwargs.get("db", redis_config.get("db")),
            "username": kwargs.get("username", redis_auth.get("username")),
            "password": kwargs.get("password", redis_auth.get("password")),
            "max_connections": kwargs.get(
                "max_connections",
                redis_config.get("max_connections")
            ),
            "socket_timeout": kwargs.get(
                "socket_timeout",
                redis_config.get("socket_timeout")
            ),
            "socket_connect_timeout": kwargs.get(
                "socket_connect_timeout",
                redis_config.get("socket_connect_timeout")
            ),
            "decode_responses": kwargs.get(
                "decode_responses",
                redis_config.get("decode_responses", True)
            ),
            "encoding": kwargs.get(
                "encoding",
                redis_config.get("encoding", "utf-8")
            ),
        }
        
        # 过滤掉 None 值
        config = {k: v for k, v in config.items() if v is not None}
        
        # 创建管理器实例
        manager = StandaloneRedisManager(**config)
        
        # 初始化连接池
        await manager.initialize()
        
        return manager
    
    @classmethod
    async def _create_cluster_manager(cls, **kwargs) -> ClusterRedisManager:
        """
        创建 Cluster 模式管理器
        
        Args:
            **kwargs: 覆盖配置文件的参数
        
        Returns:
            ClusterRedisManager 实例
        """
        # 从配置文件读取 Redis Cluster 配置
        redis_config = config_manager.get_redis_config()
        redis_auth = env_manager.get_redis_auth()
        
        # 获取启动节点
        startup_nodes = kwargs.get(
            "startup_nodes",
            redis_config.get("startup_nodes", [])
        )
        
        if not startup_nodes:
            raise ValueError(
                "Redis Cluster 模式需要提供 startup_nodes 配置"
            )
        
        # 合并配置
        config = {
            "startup_nodes": startup_nodes,
            "password": kwargs.get("password", redis_auth.get("password")),
            "max_connections": kwargs.get(
                "max_connections",
                redis_config.get("max_connections", 50)
            ),
            "decode_responses": kwargs.get(
                "decode_responses",
                redis_config.get("decode_responses", True)
            ),
        }
        
        # 创建管理器实例
        manager = ClusterRedisManager(**config)
        
        # 初始化连接池
        await manager.initialize()
        
        return manager
    
    @classmethod
    async def close_all(cls) -> None:
        """关闭所有连接管理器"""
        for redis_type, manager in cls._managers.items():
            await manager.close()
            logger.info(f"关闭 {redis_type} Redis 连接管理器")
        cls._managers.clear()
    
    @classmethod
    async def get_or_create(
        cls,
        redis_type: Optional[RedisType] = None,
        **kwargs
    ) -> BaseRedisManager:
        """
        获取或创建 Redis 连接管理器（别名方法）
        
        Args:
            redis_type: Redis 类型
            **kwargs: 额外参数
        
        Returns:
            Redis 连接管理器实例
        """
        return await cls.get_manager(redis_type, **kwargs)


async def get_redis_manager(
    redis_type: Optional[RedisType] = None,
    **kwargs
) -> BaseRedisManager:
    """
    获取 Redis 连接管理器（便捷函数）
    
    Args:
        redis_type: Redis 类型（"standalone" 或 "cluster"）
        **kwargs: 传递给管理器的额外参数
    
    Returns:
        BaseRedisManager: Redis 连接管理器实例
    
    Examples:
        # 使用 Standalone 模式
        manager = await get_redis_manager("standalone")
        
        # 使用默认配置
        manager = await get_redis_manager()
        
        # 使用上下文管理器
        async with await get_redis_manager() as manager:
            await manager.execute("SET", "key", "value")
    """
    return await RedisManagerFactory.get_manager(redis_type, **kwargs)
