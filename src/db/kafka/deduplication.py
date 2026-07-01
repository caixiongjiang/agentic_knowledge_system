#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Kafka 消息去重模块

实现基于 event_id 的消息去重，支持：
- 内存 LRU 缓存（快速查询）
- Redis 持久化（集群共享）
- 双层去重策略
- 自动过期清理
"""

import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from src.db.kafka.types import EventID
from src.db.redis.namespace import RedisNamespace
from src.utils.config_manager import get_config_manager


class LRUCache:
    """
    线程安全的 LRU 缓存
    
    用于本地快速去重检查，避免每次都查询 Redis。
    """
    
    def __init__(self, max_size: int = 10000):
        """
        初始化 LRU 缓存
        
        Args:
            max_size: 缓存最大容量
        """
        self.cache: OrderedDict[str, datetime] = OrderedDict()
        self.max_size = max_size
        self.lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[datetime]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存的时间戳，如果不存在返回 None
        """
        async with self.lock:
            if key in self.cache:
                # 移到最后（最近使用）
                self.cache.move_to_end(key)
                return self.cache[key]
            return None
    
    async def set(self, key: str, value: datetime) -> None:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值（时间戳）
        """
        async with self.lock:
            if key in self.cache:
                # 更新并移到最后
                self.cache.move_to_end(key)
            else:
                # 新增
                self.cache[key] = value
                # 检查是否超出容量
                if len(self.cache) > self.max_size:
                    # 删除最老的条目（第一个）
                    self.cache.popitem(last=False)
    
    async def delete(self, key: str) -> bool:
        """
        删除缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        async with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """清空缓存"""
        async with self.lock:
            self.cache.clear()
    
    async def size(self) -> int:
        """获取缓存大小"""
        async with self.lock:
            return len(self.cache)


class DeduplicationManager:
    """
    消息去重管理器
    
    实现双层去重策略：
    1. 内存 LRU 缓存（快速查询，单机）
    2. Redis 持久化（集群共享，可靠）
    
    去重逻辑：
    1. 先查内存缓存，命中则返回重复
    2. 再查 Redis，命中则返回重复并更新内存缓存
    3. 都未命中则标记为已处理，同时写入内存和 Redis
    """
    
    def __init__(
        self,
        redis_namespace: Optional[RedisNamespace] = None,
        ttl_seconds: Optional[int] = None,
        lru_cache_size: int = 10000,
        use_redis: Optional[bool] = None
    ):
        """
        初始化去重管理器
        
        Args:
            redis_namespace: Redis 命名空间实例（用于 Redis 去重）
            ttl_seconds: 去重记录过期时间（秒），默认从配置读取
            lru_cache_size: LRU 缓存大小
            use_redis: 是否使用 Redis，默认从配置读取
        """
        self.config = get_config_manager()
        
        # Redis 配置
        self._use_redis = use_redis if use_redis is not None else self.config.get("kafka.idempotency.use_redis", True)
        self.redis_namespace = redis_namespace
        
        # TTL 配置
        self.ttl_seconds = ttl_seconds or self.config.get("kafka.idempotency.dedup_cache_ttl", 86400)
        
        # 内存缓存
        self.lru_cache = LRUCache(max_size=lru_cache_size)
        
        logger.info(
            f"去重管理器初始化完成 - "
            f"使用Redis: {self._use_redis}, "
            f"Redis可用: {self.redis_namespace is not None}, "
            f"TTL: {self.ttl_seconds}s, "
            f"LRU大小: {lru_cache_size}"
        )
    
    def _get_redis_key(self, event_id: EventID) -> str:
        """
        生成 Redis key（不带命名空间前缀，由 RedisNamespace 自动添加）
        
        Args:
            event_id: 事件ID
            
        Returns:
            Redis key（仅 event_id 部分）
        """
        return str(event_id)
    
    async def is_duplicate(self, event_id: EventID) -> bool:
        """
        检查消息是否重复
        
        检查流程：
        1. 先查内存缓存
        2. 再查 Redis（如果启用）
        3. 都未命中则返回 False
        
        Args:
            event_id: 事件ID
            
        Returns:
            True 表示重复，False 表示首次处理
        """
        # 1. 检查内存缓存
        cached = await self.lru_cache.get(str(event_id))
        if cached is not None:
            logger.debug(f"消息已处理（内存缓存命中）: {event_id}")
            return True
        
        # 2. 检查 Redis（如果启用）
        if self._use_redis and self.redis_namespace is not None:
            try:
                redis_key = self._get_redis_key(event_id)
                exists = await self.redis_namespace.exists(redis_key)
                if exists:
                    # Redis 中存在，更新内存缓存
                    now = datetime.now(timezone.utc)
                    await self.lru_cache.set(str(event_id), now)
                    logger.debug(f"消息已处理（Redis命中）: {event_id}")
                    return True
            except Exception as e:
                logger.error(f"Redis查询失败: {e}，继续处理消息")
                # Redis 查询失败不应阻止消息处理
        
        return False
    
    async def mark_processed(self, event_id: EventID) -> bool:
        """
        标记消息已处理
        
        写入流程：
        1. 写入内存缓存
        2. 写入 Redis（如果启用）
        
        Args:
            event_id: 事件ID
            
        Returns:
            是否成功标记
        """
        now = datetime.now(timezone.utc)
        
        # 1. 写入内存缓存
        await self.lru_cache.set(str(event_id), now)
        
        # 2. 写入 Redis（如果启用）
        if self._use_redis and self.redis_namespace is not None:
            try:
                redis_key = self._get_redis_key(event_id)
                # 设置带 TTL 的记录
                await self.redis_namespace.set(
                    redis_key,
                    now.isoformat(),
                    ex=self.ttl_seconds
                )
                logger.debug(f"消息标记为已处理: {event_id}")
                return True
            except Exception as e:
                logger.error(f"Redis写入失败: {e}")
                # 即使 Redis 写入失败，内存缓存已写入，单机场景仍然有效
                return False
        
        logger.debug(f"消息标记为已处理（仅内存）: {event_id}")
        return True
    
    async def get_duplicates(self, event_ids: list) -> set:
        """批量检查一组 event_id 中哪些是重复（已处理）的。

        相比逐条 is_duplicate（N 次往返），这里：
        1. 先用本地 LRU 过滤掉命中的；
        2. 剩余的用 Redis MGET 一次往返批量查询。

        Args:
            event_ids: 事件ID列表

        Returns:
            重复（已处理）的 event_id 字符串集合
        """
        if not event_ids:
            return set()

        str_ids = [str(e) for e in event_ids]
        duplicates: set = set()

        # 1. 本地 LRU 命中
        remaining: list = []
        for sid in str_ids:
            if await self.lru_cache.get(sid) is not None:
                duplicates.add(sid)
            else:
                remaining.append(sid)

        # 2. Redis MGET 批量查询剩余（单次往返）
        if remaining and self._use_redis and self.redis_namespace is not None:
            try:
                values = await self.redis_namespace.mget(remaining)
                now = datetime.now(timezone.utc)
                for sid, val in zip(remaining, values):
                    if val is not None:
                        duplicates.add(sid)
                        await self.lru_cache.set(sid, now)
            except Exception as e:
                logger.error(f"Redis 批量去重查询失败: {e}，这些消息将被当作首次处理")

        if duplicates:
            logger.debug(f"批量去重命中 {len(duplicates)}/{len(str_ids)} 条")
        return duplicates

    async def mark_processed_batch(self, event_ids: list) -> None:
        """批量标记一组消息为已处理。

        本地 LRU 逐条写入（纯内存，无 IO）；Redis 侧用 asyncio.gather
        并发下发带 TTL 的 SET（MSET 不支持单 key TTL，故用并发 SET 替代）。

        Args:
            event_ids: 事件ID列表
        """
        if not event_ids:
            return

        str_ids = [str(e) for e in event_ids]
        now = datetime.now(timezone.utc)

        # 1. 写入本地 LRU
        for sid in str_ids:
            await self.lru_cache.set(sid, now)

        # 2. 并发写入 Redis（带 TTL）
        if self._use_redis and self.redis_namespace is not None:
            try:
                iso = now.isoformat()
                await asyncio.gather(*[
                    self.redis_namespace.set(sid, iso, ex=self.ttl_seconds)
                    for sid in str_ids
                ])
                logger.debug(f"批量标记已处理 {len(str_ids)} 条（含 Redis）")
            except Exception as e:
                logger.error(f"Redis 批量写入失败: {e}，本地 LRU 已写入")

    async def remove_processed(self, event_id: EventID) -> bool:
        """
        移除已处理标记（用于测试或重新处理）
        
        Args:
            event_id: 事件ID
            
        Returns:
            是否成功移除
        """
        # 1. 从内存缓存删除
        await self.lru_cache.delete(str(event_id))
        
        # 2. 从 Redis 删除（如果启用）
        if self._use_redis and self.redis_namespace is not None:
            try:
                redis_key = self._get_redis_key(event_id)
                await self.redis_namespace.delete(redis_key)
                logger.debug(f"移除已处理标记: {event_id}")
                return True
            except Exception as e:
                logger.error(f"Redis删除失败: {e}")
                return False
        
        logger.debug(f"移除已处理标记（仅内存）: {event_id}")
        return True
    
    async def clear_all(self) -> None:
        """
        清空所有去重记录（仅用于测试）
        
        警告：生产环境慎用！
        """
        # 清空内存缓存
        await self.lru_cache.clear()
        
        # 清空 Redis（如果启用）
        if self._use_redis and self.redis_namespace is not None:
            try:
                # 查找所有相关 key（使用 * 匹配所有）
                keys = await self.redis_namespace.keys("*")
                if keys:
                    await self.redis_namespace.delete(*keys)
                logger.warning("已清空所有去重记录（包括Redis）")
            except Exception as e:
                logger.error(f"清空Redis记录失败: {e}")
        else:
            logger.warning("已清空所有去重记录（仅内存）")
    
    async def get_stats(self) -> dict:
        """
        获取去重统计信息
        
        Returns:
            统计信息字典
        """
        stats = {
            "lru_cache_size": await self.lru_cache.size(),
            "lru_cache_max": self.lru_cache.max_size,
            "use_redis": self._use_redis,
            "ttl_seconds": self.ttl_seconds
        }
        
        # 尝试获取 Redis 统计
        if self._use_redis and self.redis_namespace is not None:
            try:
                keys = await self.redis_namespace.keys("*")
                stats["redis_keys_count"] = len(keys) if keys else 0
            except Exception as e:
                logger.error(f"获取Redis统计失败: {e}")
                stats["redis_keys_count"] = -1
        
        return stats


# 全局去重管理器实例（单例）
_dedup_manager: Optional[DeduplicationManager] = None
# 全局 Redis Manager（用于管理连接池生命周期）
_redis_manager: Optional[object] = None


async def get_deduplication_manager(
    redis_namespace: Optional[RedisNamespace] = None,
    force_new: bool = False
) -> DeduplicationManager:
    """
    获取全局去重管理器实例（单例）
    
    Args:
        redis_namespace: Redis 命名空间实例
        force_new: 是否强制创建新实例（测试用）
        
    Returns:
        去重管理器实例
    """
    global _dedup_manager, _redis_manager
    
    if _dedup_manager is None or force_new:
        # 如果没有传入 Redis，尝试自动创建
        if redis_namespace is None:
            try:
                from src.db.redis import get_redis_manager
                
                # 获取全局 Redis Manager（复用连接池）
                redis_manager = await get_redis_manager()
                
                # 初始化连接池（如果尚未初始化）
                if not redis_manager._initialized:
                    await redis_manager.initialize()
                    logger.info("Redis 连接池已初始化")
                
                # 保存全局 Manager 引用（用于后续关闭）
                _redis_manager = redis_manager
                
                # 使用 kafka:dedup 命名空间
                redis_namespace = RedisNamespace(redis_manager, "kafka:dedup")
                logger.info("已自动创建 Redis 命名空间用于去重: kafka:dedup")
            except Exception as e:
                logger.warning(f"无法创建 Redis 连接，将仅使用内存缓存: {e}")
                redis_namespace = None
        
        _dedup_manager = DeduplicationManager(redis_namespace=redis_namespace)
    
    return _dedup_manager


async def close_deduplication_manager() -> None:
    """
    关闭全局去重管理器
    
    注意：这不会关闭 Redis 连接池，因为连接池可能被其他模块共享。
    如需关闭 Redis 连接池，请使用 `close_redis_manager()`。
    """
    global _dedup_manager, _redis_manager
    
    if _dedup_manager is not None:
        # 不清空去重记录，保留状态供下次使用
        _dedup_manager = None
        logger.info("去重管理器已关闭")


async def close_redis_manager() -> None:
    """
    关闭 Redis 连接池（仅在应用完全退出时调用）
    
    警告：这会关闭全局的 Redis 连接池，影响所有使用该连接池的模块！
    """
    global _redis_manager
    
    if _redis_manager is not None:
        try:
            await _redis_manager.close()
            logger.info("Redis 连接池已关闭")
        except Exception as e:
            logger.error(f"关闭 Redis 连接池失败: {e}")
        finally:
            _redis_manager = None
