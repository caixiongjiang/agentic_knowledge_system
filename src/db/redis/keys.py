#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : keys.py
@Author  : caixiongjiang
@Date    : 2026/01/22
@Function: 
    Redis Key 统一管理器，定义所有 Redis key 的命名规范
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class KeyPattern:
    """Key 模式定义"""
    namespace: str              # 命名空间
    pattern: str                # key 模式（使用 {variable} 占位符）
    description: str            # 描述
    ttl: Optional[int] = None   # 默认过期时间（秒），None 表示永不过期
    examples: List[str] = field(default_factory=list)  # 示例
    
    def format(self, **kwargs) -> str:
        """
        格式化 key
        
        Args:
            **kwargs: 占位符的值
        
        Returns:
            完整的 key
        
        Examples:
            >>> pattern = KeyPattern("user", "profile:{user_id}", "用户资料")
            >>> pattern.format(user_id="123")
            'user:profile:123'
        """
        key = self.pattern.format(**kwargs)
        return f"{self.namespace}:{key}"
    
    def get_full_pattern(self) -> str:
        """获取完整的 pattern（包含命名空间）"""
        return f"{self.namespace}:{self.pattern}"


class RedisKeyRegistry:
    """
    Redis Key 注册中心
    
    统一管理所有 Redis key 的命名规范，提供：
    1. Key 命名的统一入口
    2. Key 过期时间的统一配置
    3. Key 文档和示例
    4. Key 冲突检测
    
    使用方法：
        # 1. 通过注册中心生成 key
        key = RedisKeys.USER.PROFILE.format(user_id="123")
        # 结果: "user:profile:123"
        
        # 2. 获取过期时间
        ttl = RedisKeys.USER.PROFILE.ttl
        
        # 3. 查看所有已注册的 key
        RedisKeys.list_all_keys()
    """
    
    def __init__(self):
        """初始化 Key 注册中心"""
        self._keys: Dict[str, Dict[str, KeyPattern]] = {}
    
    def register(
        self,
        category: str,
        name: str,
        namespace: str,
        pattern: str,
        description: str,
        ttl: Optional[int] = None,
        examples: Optional[List[str]] = None
    ) -> KeyPattern:
        """
        注册一个 key 模式
        
        Args:
            category: 分类（如 "USER", "CACHE"）
            name: 名称（如 "PROFILE", "SESSION"）
            namespace: 命名空间
            pattern: key 模式
            description: 描述
            ttl: 默认过期时间（秒）
            examples: 示例列表
        
        Returns:
            KeyPattern 实例
        """
        if category not in self._keys:
            self._keys[category] = {}
        
        if name in self._keys[category]:
            return self._keys[category][name]
        
        key_pattern = KeyPattern(
            namespace=namespace,
            pattern=pattern,
            description=description,
            ttl=ttl,
            examples=examples or []
        )
        
        self._keys[category][name] = key_pattern
        return key_pattern
    
    def get(self, category: str, name: str) -> Optional[KeyPattern]:
        """获取 key 模式"""
        return self._keys.get(category, {}).get(name)
    
    def list_all_keys(self) -> Dict[str, Dict[str, KeyPattern]]:
        """列出所有已注册的 key"""
        return self._keys
    
    def print_all_keys(self):
        """打印所有已注册的 key（用于文档和调试）"""
        print("\n" + "=" * 80)
        print("Redis Key 注册表")
        print("=" * 80)
        
        for category, keys in self._keys.items():
            print(f"\n[{category}]")
            for name, pattern in keys.items():
                print(f"  {name}:")
                print(f"    Pattern: {pattern.get_full_pattern()}")
                print(f"    描述: {pattern.description}")
                if pattern.ttl:
                    print(f"    过期时间: {pattern.ttl}秒")
                if pattern.examples:
                    print(f"    示例: {', '.join(pattern.examples)}")
        
        print("\n" + "=" * 80)
    
    def check_conflicts(self) -> List[str]:
        """
        检查 key 冲突
        
        Returns:
            冲突的 key 列表
        """
        conflicts = []
        all_patterns = []
        
        for category, keys in self._keys.items():
            for name, pattern in keys.items():
                full_pattern = pattern.get_full_pattern()
                if full_pattern in all_patterns:
                    conflicts.append(f"{category}.{name}: {full_pattern}")
                all_patterns.append(full_pattern)
        
        return conflicts


# 创建全局注册中心实例
_registry = RedisKeyRegistry()


# ==================== Key 定义区域 ====================

class UserKeys:
    """用户相关的 Key"""
    
    # 用户资料
    PROFILE = _registry.register(
        category="USER",
        name="PROFILE",
        namespace="user",
        pattern="profile:{user_id}",
        description="用户基本资料",
        ttl=86400,  # 1 天
        examples=["user:profile:123", "user:profile:456"]
    )
    
    # 用户会话
    SESSION = _registry.register(
        category="USER",
        name="SESSION",
        namespace="session",
        pattern="{user_id}",
        description="用户登录会话",
        ttl=604800,  # 7 天
        examples=["session:123", "session:456"]
    )
    
    # 用户设置
    SETTINGS = _registry.register(
        category="USER",
        name="SETTINGS",
        namespace="user",
        pattern="settings:{user_id}",
        description="用户个性化设置",
        ttl=None,  # 永不过期
        examples=["user:settings:123"]
    )
    
    # 用户权限
    PERMISSIONS = _registry.register(
        category="USER",
        name="PERMISSIONS",
        namespace="user",
        pattern="permissions:{user_id}",
        description="用户权限列表",
        ttl=3600,  # 1 小时
        examples=["user:permissions:123"]
    )
    
    # 用户在线状态
    ONLINE_STATUS = _registry.register(
        category="USER",
        name="ONLINE_STATUS",
        namespace="user",
        pattern="online:{user_id}",
        description="用户在线状态",
        ttl=300,  # 5 分钟
        examples=["user:online:123"]
    )


class CacheKeys:
    """缓存相关的 Key"""
    
    # 文档缓存
    DOCUMENT = _registry.register(
        category="CACHE",
        name="DOCUMENT",
        namespace="cache",
        pattern="doc:{doc_id}",
        description="文档内容缓存",
        ttl=3600,  # 1 小时
        examples=["cache:doc:abc123", "cache:doc:xyz789"]
    )
    
    # 查询结果缓存
    QUERY_RESULT = _registry.register(
        category="CACHE",
        name="QUERY_RESULT",
        namespace="cache",
        pattern="query:{query_hash}",
        description="查询结果缓存",
        ttl=1800,  # 30 分钟
        examples=["cache:query:md5hash123"]
    )
    
    # API 响应缓存
    API_RESPONSE = _registry.register(
        category="CACHE",
        name="API_RESPONSE",
        namespace="cache",
        pattern="api:{endpoint}:{params_hash}",
        description="API 响应缓存",
        ttl=600,  # 10 分钟
        examples=["cache:api:/users:hash123"]
    )
    
    # 向量检索结果缓存
    VECTOR_SEARCH = _registry.register(
        category="CACHE",
        name="VECTOR_SEARCH",
        namespace="cache",
        pattern="vector:{query_hash}",
        description="向量检索结果缓存",
        ttl=1800,  # 30 分钟
        examples=["cache:vector:hash123"]
    )


class QueueKeys:
    """队列相关的 Key"""
    
    # 任务队列
    TASK_QUEUE = _registry.register(
        category="QUEUE",
        name="TASK_QUEUE",
        namespace="queue",
        pattern="task:{queue_name}",
        description="异步任务队列",
        ttl=None,  # 永不过期
        examples=["queue:task:email", "queue:task:notification"]
    )
    
    # 延迟队列
    DELAYED_QUEUE = _registry.register(
        category="QUEUE",
        name="DELAYED_QUEUE",
        namespace="queue",
        pattern="delayed:{queue_name}",
        description="延迟任务队列",
        ttl=None,
        examples=["queue:delayed:retry"]
    )
    
    # 死信队列
    DEAD_LETTER = _registry.register(
        category="QUEUE",
        name="DEAD_LETTER",
        namespace="queue",
        pattern="dlq:{queue_name}",
        description="死信队列（失败任务）",
        ttl=604800,  # 7 天
        examples=["queue:dlq:email"]
    )


class LockKeys:
    """分布式锁相关的 Key"""
    
    # 资源锁
    RESOURCE_LOCK = _registry.register(
        category="LOCK",
        name="RESOURCE_LOCK",
        namespace="lock",
        pattern="resource:{resource_type}:{resource_id}",
        description="资源访问锁",
        ttl=30,  # 30 秒
        examples=["lock:resource:document:123"]
    )
    
    # 操作锁
    OPERATION_LOCK = _registry.register(
        category="LOCK",
        name="OPERATION_LOCK",
        namespace="lock",
        pattern="op:{operation_name}:{entity_id}",
        description="操作执行锁",
        ttl=60,  # 1 分钟
        examples=["lock:op:update:user:123"]
    )


class RateLimitKeys:
    """限流相关的 Key"""
    
    # API 限流
    API_RATE_LIMIT = _registry.register(
        category="RATE_LIMIT",
        name="API_RATE_LIMIT",
        namespace="ratelimit",
        pattern="api:{user_id}:{endpoint}:{window}",
        description="API 接口限流",
        ttl=60,  # 1 分钟
        examples=["ratelimit:api:user123:/search:1642800000"]
    )
    
    # IP 限流
    IP_RATE_LIMIT = _registry.register(
        category="RATE_LIMIT",
        name="IP_RATE_LIMIT",
        namespace="ratelimit",
        pattern="ip:{ip_address}:{window}",
        description="IP 地址限流",
        ttl=60,
        examples=["ratelimit:ip:192.168.1.1:1642800000"]
    )


class LeaderboardKeys:
    """排行榜相关的 Key"""
    
    # 全局排行榜
    GLOBAL = _registry.register(
        category="LEADERBOARD",
        name="GLOBAL",
        namespace="leaderboard",
        pattern="global:{board_type}",
        description="全局排行榜",
        ttl=None,  # 永不过期
        examples=["leaderboard:global:score"]
    )
    
    # 每日排行榜
    DAILY = _registry.register(
        category="LEADERBOARD",
        name="DAILY",
        namespace="leaderboard",
        pattern="daily:{date}:{board_type}",
        description="每日排行榜",
        ttl=86400 * 7,  # 保留 7 天
        examples=["leaderboard:daily:2026-01-22:score"]
    )


class StatsKeys:
    """统计相关的 Key"""
    
    # 访问统计
    PAGE_VIEW = _registry.register(
        category="STATS",
        name="PAGE_VIEW",
        namespace="stats",
        pattern="pv:{resource_type}:{resource_id}:{date}",
        description="页面/资源访问量统计",
        ttl=86400 * 30,  # 保留 30 天
        examples=["stats:pv:document:123:2026-01-22"]
    )
    
    # 用户活跃度
    USER_ACTIVITY = _registry.register(
        category="STATS",
        name="USER_ACTIVITY",
        namespace="stats",
        pattern="activity:{user_id}:{date}",
        description="用户活跃度统计",
        ttl=86400 * 30,  # 保留 30 天
        examples=["stats:activity:123:2026-01-22"]
    )


class ProgressKeys:
    """文件索引进度相关的 Key"""
    
    # 单文件索引进度（Hash 类型）
    FILE_PROGRESS = _registry.register(
        category="PROGRESS",
        name="FILE_PROGRESS",
        namespace="progress",
        pattern="file:{file_id}",
        description="单文件索引进度（Hash 类型，字段: user_id/file_name/progress/status/stage/message/updated_at）",
        ttl=86400,  # 24 小时
        examples=["progress:file:uuid-123", "progress:file:uuid-456"]
    )
    
    # 用户正在处理的文件集合（Set 类型）
    USER_FILES = _registry.register(
        category="PROGRESS",
        name="USER_FILES",
        namespace="progress",
        pattern="user:{user_id}",
        description="用户正在处理的文件ID集合（Set 类型）",
        ttl=86400,  # 24 小时
        examples=["progress:user:user_123"]
    )


# ==================== 统一的 Key 访问入口 ====================

class RedisKeys:
    """
    Redis Key 统一访问入口
    
    使用方法：
        # 生成 key
        key = RedisKeys.USER.PROFILE.format(user_id="123")
        
        # 获取过期时间
        ttl = RedisKeys.USER.PROFILE.ttl
        
        # 查看所有 key
        RedisKeys.list_all()
        
        # 检查冲突
        RedisKeys.check_conflicts()
    """
    
    USER = UserKeys
    CACHE = CacheKeys
    QUEUE = QueueKeys
    LOCK = LockKeys
    RATE_LIMIT = RateLimitKeys
    LEADERBOARD = LeaderboardKeys
    STATS = StatsKeys
    PROGRESS = ProgressKeys
    
    @staticmethod
    def list_all():
        """列出所有已注册的 key"""
        _registry.print_all_keys()
    
    @staticmethod
    def check_conflicts() -> List[str]:
        """检查 key 冲突"""
        conflicts = _registry.check_conflicts()
        if conflicts:
            logger.warning(f"发现 {len(conflicts)} 个 key 冲突:")
            for conflict in conflicts:
                logger.warning(f"  - {conflict}")
        else:
            logger.info("✓ 未发现 key 冲突")
        return conflicts
    
    @staticmethod
    def get_registry():
        """获取注册中心实例"""
        return _registry


# ==================== 便捷函数 ====================

def get_key_pattern(category: str, name: str) -> Optional[KeyPattern]:
    """
    获取 key 模式的便捷函数
    
    Args:
        category: 分类
        name: 名称
    
    Returns:
        KeyPattern 实例
    """
    return _registry.get(category, name)


def register_custom_key(
    category: str,
    name: str,
    namespace: str,
    pattern: str,
    description: str,
    ttl: Optional[int] = None,
    examples: Optional[List[str]] = None
) -> KeyPattern:
    """
    注册自定义 key 的便捷函数
    
    Args:
        category: 分类
        name: 名称
        namespace: 命名空间
        pattern: key 模式
        description: 描述
        ttl: 过期时间
        examples: 示例
    
    Returns:
        KeyPattern 实例
    """
    return _registry.register(
        category=category,
        name=name,
        namespace=namespace,
        pattern=pattern,
        description=description,
        ttl=ttl,
        examples=examples
    )
