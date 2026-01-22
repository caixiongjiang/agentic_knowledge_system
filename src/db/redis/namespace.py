#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : namespace.py
@Author  : caixiongjiang
@Date    : 2026/01/22
@Function: 
    Redis 命名空间管理器，实现 key 值和连接的逻辑分离
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional, Any, Dict, List, Union
from loguru import logger

from src.db.redis.connection.base import BaseRedisManager


class RedisNamespace:
    """
    Redis 命名空间管理器
    
    核心功能：
    1. 共享同一个 Redis 连接池（节约连接资源）
    2. 通过 key 前缀区分不同业务模块
    3. 自动处理 key 的拼接和解析
    4. 支持嵌套命名空间
    
    使用场景：
    - 不同业务模块使用相同的 Redis 实例，但需要逻辑隔离
    - 避免 key 冲突
    - 统一管理某一类 key
    
    Examples:
        # 创建不同业务的命名空间
        user_redis = RedisNamespace(manager, "user")
        cache_redis = RedisNamespace(manager, "cache")
        session_redis = RedisNamespace(manager, "session")
        
        # 设置值（自动添加前缀）
        await user_redis.set("123", "user_data")  # 实际 key: "user:123"
        await cache_redis.set("123", "cache_data")  # 实际 key: "cache:123"
        
        # 创建子命名空间
        user_profile = user_redis.sub_namespace("profile")
        await user_profile.set("123", "profile_data")  # 实际 key: "user:profile:123"
    """
    
    def __init__(
        self,
        manager: BaseRedisManager,
        namespace: str,
        separator: str = ":"
    ):
        """
        初始化命名空间管理器
        
        Args:
            manager: Redis 连接管理器实例
            namespace: 命名空间名称（会作为 key 前缀）
            separator: 分隔符（默认为冒号 ":"）
        """
        self.manager = manager
        self.namespace = namespace
        self.separator = separator
        
        logger.debug(f"创建 Redis 命名空间: {namespace}")
    
    def _make_key(self, key: str) -> str:
        """
        生成带命名空间的完整 key
        
        Args:
            key: 原始 key
        
        Returns:
            带命名空间前缀的完整 key
        """
        return f"{self.namespace}{self.separator}{key}"
    
    def _make_keys(self, keys: List[str]) -> List[str]:
        """
        批量生成带命名空间的完整 key
        
        Args:
            keys: 原始 key 列表
        
        Returns:
            带命名空间前缀的完整 key 列表
        """
        return [self._make_key(key) for key in keys]
    
    # ==================== 字符串操作 ====================
    
    async def get(self, key: str) -> Optional[str]:
        """
        获取字符串值
        
        Args:
            key: 键名
        
        Returns:
            值，不存在则返回 None
        """
        full_key = self._make_key(key)
        return await self.manager.execute("GET", full_key)
    
    async def set(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """
        设置字符串值
        
        Args:
            key: 键名
            value: 值
            ex: 过期时间（秒）
            px: 过期时间（毫秒）
            nx: 仅在 key 不存在时设置
            xx: 仅在 key 存在时设置
        
        Returns:
            操作是否成功
        """
        full_key = self._make_key(key)
        result = await self.manager.execute(
            "SET", full_key, value, ex=ex, px=px, nx=nx, xx=xx
        )
        return result is not None
    
    async def mget(self, keys: List[str]) -> List[Optional[str]]:
        """
        批量获取字符串值
        
        Args:
            keys: 键名列表
        
        Returns:
            值列表
        """
        full_keys = self._make_keys(keys)
        return await self.manager.execute("MGET", *full_keys)
    
    async def mset(self, mapping: Dict[str, Any]) -> bool:
        """
        批量设置字符串值
        
        Args:
            mapping: 键值对字典
        
        Returns:
            操作是否成功
        """
        full_mapping = {
            self._make_key(k): v for k, v in mapping.items()
        }
        result = await self.manager.execute("MSET", full_mapping)
        return result is not None
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """
        递增整数值
        
        Args:
            key: 键名
            amount: 递增量（默认 1）
        
        Returns:
            递增后的值
        """
        full_key = self._make_key(key)
        return await self.manager.execute("INCRBY", full_key, amount)
    
    async def decr(self, key: str, amount: int = 1) -> int:
        """
        递减整数值
        
        Args:
            key: 键名
            amount: 递减量（默认 1）
        
        Returns:
            递减后的值
        """
        full_key = self._make_key(key)
        return await self.manager.execute("DECRBY", full_key, amount)
    
    # ==================== 哈希表操作 ====================
    
    async def hget(self, key: str, field: str) -> Optional[str]:
        """
        获取哈希表字段值
        
        Args:
            key: 键名
            field: 字段名
        
        Returns:
            字段值
        """
        full_key = self._make_key(key)
        return await self.manager.execute("HGET", full_key, field)
    
    async def hset(
        self,
        key: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        mapping: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        设置哈希表字段值
        
        Args:
            key: 键名
            field: 字段名（与 value 一起使用）
            value: 字段值（与 field 一起使用）
            mapping: 字段值字典（批量设置）
        
        Returns:
            新增的字段数量
        """
        full_key = self._make_key(key)
        if mapping:
            return await self.manager.execute("HSET", full_key, mapping=mapping)
        else:
            return await self.manager.execute("HSET", full_key, field, value)
    
    async def hgetall(self, key: str) -> Dict[str, str]:
        """
        获取哈希表所有字段和值
        
        Args:
            key: 键名
        
        Returns:
            字段值字典
        """
        full_key = self._make_key(key)
        return await self.manager.execute("HGETALL", full_key)
    
    async def hdel(self, key: str, *fields: str) -> int:
        """
        删除哈希表字段
        
        Args:
            key: 键名
            *fields: 字段名列表
        
        Returns:
            删除的字段数量
        """
        full_key = self._make_key(key)
        return await self.manager.execute("HDEL", full_key, *fields)
    
    async def hexists(self, key: str, field: str) -> bool:
        """
        检查哈希表字段是否存在
        
        Args:
            key: 键名
            field: 字段名
        
        Returns:
            是否存在
        """
        full_key = self._make_key(key)
        return await self.manager.execute("HEXISTS", full_key, field)
    
    async def hkeys(self, key: str) -> List[str]:
        """
        获取哈希表所有字段名
        
        Args:
            key: 键名
        
        Returns:
            字段名列表
        """
        full_key = self._make_key(key)
        return await self.manager.execute("HKEYS", full_key)
    
    async def hvals(self, key: str) -> List[str]:
        """
        获取哈希表所有字段值
        
        Args:
            key: 键名
        
        Returns:
            字段值列表
        """
        full_key = self._make_key(key)
        return await self.manager.execute("HVALS", full_key)
    
    async def hlen(self, key: str) -> int:
        """
        获取哈希表字段数量
        
        Args:
            key: 键名
        
        Returns:
            字段数量
        """
        full_key = self._make_key(key)
        return await self.manager.execute("HLEN", full_key)
    
    # ==================== 列表操作 ====================
    
    async def lpush(self, key: str, *values: Any) -> int:
        """
        从列表左侧插入元素
        
        Args:
            key: 键名
            *values: 值列表
        
        Returns:
            列表长度
        """
        full_key = self._make_key(key)
        return await self.manager.execute("LPUSH", full_key, *values)
    
    async def rpush(self, key: str, *values: Any) -> int:
        """
        从列表右侧插入元素
        
        Args:
            key: 键名
            *values: 值列表
        
        Returns:
            列表长度
        """
        full_key = self._make_key(key)
        return await self.manager.execute("RPUSH", full_key, *values)
    
    async def lpop(self, key: str, count: Optional[int] = None) -> Union[str, List[str], None]:
        """
        从列表左侧弹出元素
        
        Args:
            key: 键名
            count: 弹出数量（可选）
        
        Returns:
            弹出的元素或元素列表
        """
        full_key = self._make_key(key)
        if count:
            return await self.manager.execute("LPOP", full_key, count)
        else:
            return await self.manager.execute("LPOP", full_key)
    
    async def rpop(self, key: str, count: Optional[int] = None) -> Union[str, List[str], None]:
        """
        从列表右侧弹出元素
        
        Args:
            key: 键名
            count: 弹出数量（可选）
        
        Returns:
            弹出的元素或元素列表
        """
        full_key = self._make_key(key)
        if count:
            return await self.manager.execute("RPOP", full_key, count)
        else:
            return await self.manager.execute("RPOP", full_key)
    
    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        """
        获取列表指定范围的元素
        
        Args:
            key: 键名
            start: 起始索引
            end: 结束索引
        
        Returns:
            元素列表
        """
        full_key = self._make_key(key)
        return await self.manager.execute("LRANGE", full_key, start, end)
    
    async def llen(self, key: str) -> int:
        """
        获取列表长度
        
        Args:
            key: 键名
        
        Returns:
            列表长度
        """
        full_key = self._make_key(key)
        return await self.manager.execute("LLEN", full_key)
    
    # ==================== 集合操作 ====================
    
    async def sadd(self, key: str, *members: Any) -> int:
        """
        向集合添加成员
        
        Args:
            key: 键名
            *members: 成员列表
        
        Returns:
            新增的成员数量
        """
        full_key = self._make_key(key)
        return await self.manager.execute("SADD", full_key, *members)
    
    async def srem(self, key: str, *members: Any) -> int:
        """
        从集合移除成员
        
        Args:
            key: 键名
            *members: 成员列表
        
        Returns:
            移除的成员数量
        """
        full_key = self._make_key(key)
        return await self.manager.execute("SREM", full_key, *members)
    
    async def smembers(self, key: str) -> set:
        """
        获取集合所有成员
        
        Args:
            key: 键名
        
        Returns:
            成员集合
        """
        full_key = self._make_key(key)
        return await self.manager.execute("SMEMBERS", full_key)
    
    async def sismember(self, key: str, member: Any) -> bool:
        """
        检查成员是否在集合中
        
        Args:
            key: 键名
            member: 成员
        
        Returns:
            是否存在
        """
        full_key = self._make_key(key)
        return await self.manager.execute("SISMEMBER", full_key, member)
    
    async def scard(self, key: str) -> int:
        """
        获取集合成员数量
        
        Args:
            key: 键名
        
        Returns:
            成员数量
        """
        full_key = self._make_key(key)
        return await self.manager.execute("SCARD", full_key)
    
    # ==================== 有序集合操作 ====================
    
    async def zadd(
        self,
        key: str,
        mapping: Dict[Any, float],
        nx: bool = False,
        xx: bool = False
    ) -> int:
        """
        向有序集合添加成员
        
        Args:
            key: 键名
            mapping: 成员-分数字典
            nx: 仅在成员不存在时添加
            xx: 仅在成员存在时更新
        
        Returns:
            新增的成员数量
        """
        full_key = self._make_key(key)
        return await self.manager.execute("ZADD", full_key, mapping, nx=nx, xx=xx)
    
    async def zrange(
        self,
        key: str,
        start: int,
        end: int,
        withscores: bool = False
    ) -> List:
        """
        获取有序集合指定范围的成员
        
        Args:
            key: 键名
            start: 起始索引
            end: 结束索引
            withscores: 是否返回分数
        
        Returns:
            成员列表或成员-分数元组列表
        """
        full_key = self._make_key(key)
        return await self.manager.execute(
            "ZRANGE", full_key, start, end, withscores=withscores
        )
    
    async def zrem(self, key: str, *members: Any) -> int:
        """
        从有序集合移除成员
        
        Args:
            key: 键名
            *members: 成员列表
        
        Returns:
            移除的成员数量
        """
        full_key = self._make_key(key)
        return await self.manager.execute("ZREM", full_key, *members)
    
    async def zscore(self, key: str, member: Any) -> Optional[float]:
        """
        获取有序集合成员的分数
        
        Args:
            key: 键名
            member: 成员
        
        Returns:
            分数
        """
        full_key = self._make_key(key)
        return await self.manager.execute("ZSCORE", full_key, member)
    
    async def zcard(self, key: str) -> int:
        """
        获取有序集合成员数量
        
        Args:
            key: 键名
        
        Returns:
            成员数量
        """
        full_key = self._make_key(key)
        return await self.manager.execute("ZCARD", full_key)
    
    # ==================== 通用键操作 ====================
    
    async def exists(self, *keys: str) -> int:
        """
        检查键是否存在
        
        Args:
            *keys: 键名列表
        
        Returns:
            存在的键数量
        """
        full_keys = self._make_keys(list(keys))
        return await self.manager.execute("EXISTS", *full_keys)
    
    async def delete(self, *keys: str) -> int:
        """
        删除键
        
        Args:
            *keys: 键名列表
        
        Returns:
            删除的键数量
        """
        full_keys = self._make_keys(list(keys))
        return await self.manager.execute("DEL", *full_keys)
    
    async def expire(self, key: str, seconds: int) -> bool:
        """
        设置键的过期时间
        
        Args:
            key: 键名
            seconds: 过期时间（秒）
        
        Returns:
            操作是否成功
        """
        full_key = self._make_key(key)
        return await self.manager.execute("EXPIRE", full_key, seconds)
    
    async def ttl(self, key: str) -> int:
        """
        获取键的剩余过期时间
        
        Args:
            key: 键名
        
        Returns:
            剩余秒数（-1 表示永不过期，-2 表示键不存在）
        """
        full_key = self._make_key(key)
        return await self.manager.execute("TTL", full_key)
    
    async def persist(self, key: str) -> bool:
        """
        移除键的过期时间
        
        Args:
            key: 键名
        
        Returns:
            操作是否成功
        """
        full_key = self._make_key(key)
        return await self.manager.execute("PERSIST", full_key)
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """
        查找匹配模式的键
        
        Args:
            pattern: 匹配模式（默认 "*" 匹配所有）
        
        Returns:
            键名列表（会自动移除命名空间前缀）
        """
        full_pattern = self._make_key(pattern)
        full_keys = await self.manager.execute("KEYS", full_pattern)
        
        # 移除命名空间前缀
        prefix_len = len(self.namespace) + len(self.separator)
        return [key[prefix_len:] for key in full_keys]
    
    # ==================== 命名空间管理 ====================
    
    def sub_namespace(self, sub_ns: str) -> "RedisNamespace":
        """
        创建子命名空间
        
        Args:
            sub_ns: 子命名空间名称
        
        Returns:
            新的 RedisNamespace 实例
        
        Examples:
            user_redis = RedisNamespace(manager, "user")
            user_profile = user_redis.sub_namespace("profile")
            # user_profile 的命名空间为 "user:profile"
        """
        new_namespace = f"{self.namespace}{self.separator}{sub_ns}"
        return RedisNamespace(self.manager, new_namespace, self.separator)
    
    def get_full_key(self, key: str) -> str:
        """
        获取完整的 key（包含命名空间前缀）
        
        Args:
            key: 原始 key
        
        Returns:
            完整的 key
        """
        return self._make_key(key)
    
    async def clear_namespace(self) -> int:
        """
        清空当前命名空间下的所有键
        
        警告：此操作会删除命名空间下的所有数据，请谨慎使用！
        
        Returns:
            删除的键数量
        """
        # 获取命名空间下的所有 key
        pattern = f"{self.namespace}{self.separator}*"
        keys = await self.manager.execute("KEYS", pattern)
        
        if not keys:
            return 0
        
        # 批量删除
        count = await self.manager.execute("DEL", *keys)
        logger.warning(f"已清空命名空间 '{self.namespace}' 下的 {count} 个键")
        return count
