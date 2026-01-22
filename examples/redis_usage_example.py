#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : redis_usage_example.py
@Author  : caixiongjiang
@Date    : 2026/01/22
@Function: 
    Redis 连接管理器使用示例
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from datetime import datetime
from typing import Optional, Dict, List
from loguru import logger

from src.db.redis import get_redis_manager, RedisNamespace


# ==================== 示例 1：用户会话管理 ====================

class UserSessionManager:
    """用户会话管理器"""
    
    def __init__(self):
        self.session_ns: Optional[RedisNamespace] = None
    
    async def initialize(self):
        """初始化会话管理器"""
        manager = await get_redis_manager()
        self.session_ns = RedisNamespace(manager, "session")
        logger.info("用户会话管理器初始化完成")
    
    async def create_session(
        self,
        user_id: str,
        token: str,
        user_info: Dict
    ) -> bool:
        """
        创建用户会话
        
        Args:
            user_id: 用户 ID
            token: 会话 token
            user_info: 用户信息
        
        Returns:
            是否创建成功
        """
        try:
            # 存储会话数据（使用哈希表）
            await self.session_ns.hset(
                user_id,
                mapping={
                    "token": token,
                    "username": user_info.get("username", ""),
                    "email": user_info.get("email", ""),
                    "login_time": datetime.now().isoformat(),
                    "last_active": datetime.now().isoformat()
                }
            )
            
            # 设置会话过期时间（7 天）
            await self.session_ns.expire(user_id, 7 * 24 * 3600)
            
            logger.info(f"创建用户会话: user_id={user_id}")
            return True
        except Exception as e:
            logger.error(f"创建用户会话失败: {e}")
            return False
    
    async def get_session(self, user_id: str) -> Optional[Dict]:
        """
        获取用户会话
        
        Args:
            user_id: 用户 ID
        
        Returns:
            会话数据字典
        """
        try:
            session_data = await self.session_ns.hgetall(user_id)
            if session_data:
                logger.info(f"获取用户会话: user_id={user_id}")
                return session_data
            return None
        except Exception as e:
            logger.error(f"获取用户会话失败: {e}")
            return None
    
    async def update_last_active(self, user_id: str) -> bool:
        """
        更新用户最后活跃时间
        
        Args:
            user_id: 用户 ID
        
        Returns:
            是否更新成功
        """
        try:
            await self.session_ns.hset(
                user_id,
                "last_active",
                datetime.now().isoformat()
            )
            return True
        except Exception as e:
            logger.error(f"更新最后活跃时间失败: {e}")
            return False
    
    async def delete_session(self, user_id: str) -> bool:
        """
        删除用户会话（登出）
        
        Args:
            user_id: 用户 ID
        
        Returns:
            是否删除成功
        """
        try:
            count = await self.session_ns.delete(user_id)
            if count > 0:
                logger.info(f"删除用户会话: user_id={user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除用户会话失败: {e}")
            return False


# ==================== 示例 2：缓存管理 ====================

class CacheManager:
    """缓存管理器"""
    
    def __init__(self):
        self.cache_ns: Optional[RedisNamespace] = None
    
    async def initialize(self):
        """初始化缓存管理器"""
        manager = await get_redis_manager()
        self.cache_ns = RedisNamespace(manager, "cache")
        logger.info("缓存管理器初始化完成")
    
    async def set_cache(
        self,
        key: str,
        value: str,
        expire: int = 3600
    ) -> bool:
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间（秒），默认 1 小时
        
        Returns:
            是否设置成功
        """
        try:
            await self.cache_ns.set(key, value, ex=expire)
            logger.debug(f"设置缓存: key={key}, expire={expire}s")
            return True
        except Exception as e:
            logger.error(f"设置缓存失败: {e}")
            return False
    
    async def get_cache(self, key: str) -> Optional[str]:
        """
        获取缓存
        
        Args:
            key: 缓存键
        
        Returns:
            缓存值，不存在则返回 None
        """
        try:
            value = await self.cache_ns.get(key)
            if value:
                logger.debug(f"缓存命中: key={key}")
            else:
                logger.debug(f"缓存未命中: key={key}")
            return value
        except Exception as e:
            logger.error(f"获取缓存失败: {e}")
            return None
    
    async def delete_cache(self, *keys: str) -> int:
        """
        删除缓存
        
        Args:
            *keys: 缓存键列表
        
        Returns:
            删除的键数量
        """
        try:
            count = await self.cache_ns.delete(*keys)
            logger.debug(f"删除缓存: keys={keys}, count={count}")
            return count
        except Exception as e:
            logger.error(f"删除缓存失败: {e}")
            return 0
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        清除匹配模式的缓存
        
        Args:
            pattern: 匹配模式（如 "user:*"）
        
        Returns:
            删除的键数量
        """
        try:
            keys = await self.cache_ns.keys(pattern)
            if keys:
                count = await self.cache_ns.delete(*keys)
                logger.info(f"清除缓存: pattern={pattern}, count={count}")
                return count
            return 0
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
            return 0


# ==================== 示例 3：任务队列 ====================

class TaskQueue:
    """任务队列管理器"""
    
    def __init__(self, queue_name: str = "default"):
        self.queue_name = queue_name
        self.queue_ns: Optional[RedisNamespace] = None
    
    async def initialize(self):
        """初始化任务队列"""
        manager = await get_redis_manager()
        self.queue_ns = RedisNamespace(manager, f"queue:{self.queue_name}")
        logger.info(f"任务队列初始化完成: {self.queue_name}")
    
    async def enqueue(self, task_data: str) -> bool:
        """
        添加任务到队列
        
        Args:
            task_data: 任务数据（JSON 字符串）
        
        Returns:
            是否添加成功
        """
        try:
            await self.queue_ns.rpush("tasks", task_data)
            logger.debug(f"任务入队: queue={self.queue_name}")
            return True
        except Exception as e:
            logger.error(f"任务入队失败: {e}")
            return False
    
    async def dequeue(self) -> Optional[str]:
        """
        从队列获取任务
        
        Returns:
            任务数据，队列为空则返回 None
        """
        try:
            task_data = await self.queue_ns.lpop("tasks")
            if task_data:
                logger.debug(f"任务出队: queue={self.queue_name}")
            return task_data
        except Exception as e:
            logger.error(f"任务出队失败: {e}")
            return None
    
    async def get_queue_size(self) -> int:
        """
        获取队列长度
        
        Returns:
            队列中的任务数量
        """
        try:
            size = await self.queue_ns.llen("tasks")
            return size
        except Exception as e:
            logger.error(f"获取队列长度失败: {e}")
            return 0
    
    async def peek(self, count: int = 10) -> List[str]:
        """
        查看队列前 N 个任务（不移除）
        
        Args:
            count: 查看数量
        
        Returns:
            任务列表
        """
        try:
            tasks = await self.queue_ns.lrange("tasks", 0, count - 1)
            return tasks
        except Exception as e:
            logger.error(f"查看队列失败: {e}")
            return []


# ==================== 示例 4：排行榜 ====================

class Leaderboard:
    """排行榜管理器"""
    
    def __init__(self, board_name: str = "global"):
        self.board_name = board_name
        self.board_ns: Optional[RedisNamespace] = None
    
    async def initialize(self):
        """初始化排行榜"""
        manager = await get_redis_manager()
        self.board_ns = RedisNamespace(manager, f"leaderboard:{self.board_name}")
        logger.info(f"排行榜初始化完成: {self.board_name}")
    
    async def update_score(self, user_id: str, score: float) -> bool:
        """
        更新用户分数
        
        Args:
            user_id: 用户 ID
            score: 分数
        
        Returns:
            是否更新成功
        """
        try:
            await self.board_ns.zadd("scores", {user_id: score})
            logger.debug(f"更新分数: user_id={user_id}, score={score}")
            return True
        except Exception as e:
            logger.error(f"更新分数失败: {e}")
            return False
    
    async def get_top_n(self, n: int = 10) -> List[tuple]:
        """
        获取排行榜前 N 名
        
        Args:
            n: 数量
        
        Returns:
            [(user_id, score), ...] 列表（降序）
        """
        try:
            # ZRANGE 默认升序，使用 ZREVRANGE 获取降序
            top_users = await self.board_ns.zrange(
                "scores",
                0,
                n - 1,
                withscores=True
            )
            # 反转列表使其降序
            top_users.reverse()
            return top_users
        except Exception as e:
            logger.error(f"获取排行榜失败: {e}")
            return []
    
    async def get_user_rank(self, user_id: str) -> Optional[Dict]:
        """
        获取用户排名和分数
        
        Args:
            user_id: 用户 ID
        
        Returns:
            {"rank": 排名, "score": 分数}
        """
        try:
            score = await self.board_ns.zscore("scores", user_id)
            if score is None:
                return None
            
            # 获取比该用户分数高的用户数量（即排名）
            # TODO: 使用 ZREVRANK 命令获取排名
            return {
                "score": score,
                "rank": None  # 需要实现 ZREVRANK
            }
        except Exception as e:
            logger.error(f"获取用户排名失败: {e}")
            return None


# ==================== 示例 5：限流器 ====================

class RateLimiter:
    """基于 Redis 的限流器"""
    
    def __init__(self, window_seconds: int = 60, max_requests: int = 100):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.limiter_ns: Optional[RedisNamespace] = None
    
    async def initialize(self):
        """初始化限流器"""
        manager = await get_redis_manager()
        self.limiter_ns = RedisNamespace(manager, "rate_limiter")
        logger.info(f"限流器初始化完成: {self.max_requests}次/{self.window_seconds}秒")
    
    async def is_allowed(self, identifier: str) -> bool:
        """
        检查是否允许请求
        
        Args:
            identifier: 请求标识（如用户 ID、IP 地址等）
        
        Returns:
            是否允许
        """
        try:
            key = f"{identifier}:{int(datetime.now().timestamp() / self.window_seconds)}"
            
            # 增加计数
            count = await self.limiter_ns.incr(key)
            
            # 第一次请求时设置过期时间
            if count == 1:
                await self.limiter_ns.expire(key, self.window_seconds)
            
            # 判断是否超过限制
            allowed = count <= self.max_requests
            
            if not allowed:
                logger.warning(f"限流触发: identifier={identifier}, count={count}")
            
            return allowed
        except Exception as e:
            logger.error(f"限流检查失败: {e}")
            return True  # 出错时允许请求


# ==================== 主函数：演示所有示例 ====================

async def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Redis 连接管理器使用示例")
    logger.info("=" * 60)
    
    try:
        # 示例 1：用户会话管理
        logger.info("\n[示例 1] 用户会话管理")
        session_mgr = UserSessionManager()
        await session_mgr.initialize()
        
        # 创建会话
        await session_mgr.create_session(
            "user123",
            "token_abc123",
            {"username": "张三", "email": "zhangsan@example.com"}
        )
        
        # 获取会话
        session = await session_mgr.get_session("user123")
        logger.info(f"会话数据: {session}")
        
        # 更新活跃时间
        await session_mgr.update_last_active("user123")
        
        # 删除会话
        await session_mgr.delete_session("user123")
        
        # 示例 2：缓存管理
        logger.info("\n[示例 2] 缓存管理")
        cache_mgr = CacheManager()
        await cache_mgr.initialize()
        
        # 设置缓存
        await cache_mgr.set_cache("user:123:profile", "用户资料数据", expire=300)
        
        # 获取缓存
        cached_data = await cache_mgr.get_cache("user:123:profile")
        logger.info(f"缓存数据: {cached_data}")
        
        # 删除缓存
        await cache_mgr.delete_cache("user:123:profile")
        
        # 示例 3：任务队列
        logger.info("\n[示例 3] 任务队列")
        task_queue = TaskQueue("email")
        await task_queue.initialize()
        
        # 添加任务
        await task_queue.enqueue('{"type": "email", "to": "user@example.com"}')
        await task_queue.enqueue('{"type": "email", "to": "admin@example.com"}')
        
        # 获取队列大小
        size = await task_queue.get_queue_size()
        logger.info(f"队列大小: {size}")
        
        # 查看队列
        tasks = await task_queue.peek(5)
        logger.info(f"队列任务: {tasks}")
        
        # 处理任务
        task = await task_queue.dequeue()
        logger.info(f"处理任务: {task}")
        
        # 示例 4：排行榜
        logger.info("\n[示例 4] 排行榜")
        leaderboard = Leaderboard("game_score")
        await leaderboard.initialize()
        
        # 更新分数
        await leaderboard.update_score("user1", 1000)
        await leaderboard.update_score("user2", 950)
        await leaderboard.update_score("user3", 900)
        
        # 获取排行榜
        top_users = await leaderboard.get_top_n(3)
        logger.info(f"排行榜前3名: {top_users}")
        
        # 示例 5：限流器
        logger.info("\n[示例 5] 限流器")
        rate_limiter = RateLimiter(window_seconds=10, max_requests=3)
        await rate_limiter.initialize()
        
        # 模拟请求
        for i in range(5):
            allowed = await rate_limiter.is_allowed("user123")
            logger.info(f"请求 {i+1}: {'允许' if allowed else '拒绝'}")
        
        logger.info("\n" + "=" * 60)
        logger.success("所有示例执行完成")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"示例执行失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
