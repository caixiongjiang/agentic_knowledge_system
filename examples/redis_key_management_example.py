#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : redis_key_management_example.py
@Author  : caixiongjiang
@Date    : 2026/01/22
@Function: 
    Redis Key 统一管理使用示例
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from loguru import logger

from src.db.redis import (
    get_redis_manager,
    RedisNamespace,
    RedisKeys,
    register_custom_key
)


async def example_1_basic_usage():
    """示例 1：基础使用 - 使用统一的 Key 定义"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 1：基础使用 - 使用统一的 Key 定义")
    logger.info("=" * 60)
    
    manager = await get_redis_manager()
    
    # ❌ 旧的方式：手动拼接 key，容易出错
    # old_key = f"user:profile:{user_id}"
    
    # ✅ 新的方式：使用统一的 Key 定义
    user_id = "123"
    key = RedisKeys.USER.PROFILE.format(user_id=user_id)
    logger.info(f"生成的 key: {key}")
    
    # 获取过期时间
    ttl = RedisKeys.USER.PROFILE.ttl
    logger.info(f"默认过期时间: {ttl}秒")
    
    # 存储数据
    async with manager.get_connection() as conn:
        await conn.set(key, "用户资料数据", ex=ttl)
        value = await conn.get(key)
        logger.success(f"存储和读取成功: {value}")


async def example_2_namespace_with_keys():
    """示例 2：结合命名空间使用"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 2：结合命名空间使用")
    logger.info("=" * 60)
    
    manager = await get_redis_manager()
    
    # 创建用户相关的命名空间
    user_ns = RedisNamespace(manager, RedisKeys.USER.PROFILE.namespace)
    
    # 使用 Key 模式生成实际的 key（去掉命名空间前缀）
    user_id = "456"
    # 方式 1：使用完整 key
    full_key = RedisKeys.USER.PROFILE.format(user_id=user_id)
    logger.info(f"完整 key: {full_key}")
    
    # 方式 2：使用命名空间（key 不包含命名空间前缀）
    key_without_ns = RedisKeys.USER.PROFILE.pattern.format(user_id=user_id)
    await user_ns.set(key_without_ns, "用户资料", ex=RedisKeys.USER.PROFILE.ttl)
    logger.success(f"通过命名空间存储: {key_without_ns}")


async def example_3_different_key_types():
    """示例 3：不同类型的 Key 使用"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 3：不同类型的 Key 使用")
    logger.info("=" * 60)
    
    manager = await get_redis_manager()
    
    async with manager.get_connection() as conn:
        # 1. 用户会话
        session_key = RedisKeys.USER.SESSION.format(user_id="789")
        await conn.hset(
            session_key,
            mapping={
                "token": "abc123",
                "login_time": "2026-01-22 15:00:00"
            }
        )
        await conn.expire(session_key, RedisKeys.USER.SESSION.ttl)
        logger.success(f"会话 key: {session_key}, TTL: {RedisKeys.USER.SESSION.ttl}秒")
        
        # 2. 缓存
        doc_id = "doc_123"
        cache_key = RedisKeys.CACHE.DOCUMENT.format(doc_id=doc_id)
        await conn.set(cache_key, "文档内容", ex=RedisKeys.CACHE.DOCUMENT.ttl)
        logger.success(f"缓存 key: {cache_key}, TTL: {RedisKeys.CACHE.DOCUMENT.ttl}秒")
        
        # 3. 任务队列
        queue_key = RedisKeys.QUEUE.TASK_QUEUE.format(queue_name="email")
        await conn.rpush(queue_key, "task1", "task2")
        logger.success(f"队列 key: {queue_key}, TTL: {RedisKeys.QUEUE.TASK_QUEUE.ttl}")
        
        # 4. 分布式锁
        lock_key = RedisKeys.LOCK.RESOURCE_LOCK.format(
            resource_type="document",
            resource_id="123"
        )
        await conn.set(lock_key, "locked", ex=RedisKeys.LOCK.RESOURCE_LOCK.ttl, nx=True)
        logger.success(f"锁 key: {lock_key}, TTL: {RedisKeys.LOCK.RESOURCE_LOCK.ttl}秒")
        
        # 5. 限流
        import time
        window = int(time.time() / 60)  # 1分钟窗口
        rate_limit_key = RedisKeys.RATE_LIMIT.API_RATE_LIMIT.format(
            user_id="user123",
            endpoint="/search",
            window=window
        )
        await conn.incr(rate_limit_key)
        await conn.expire(rate_limit_key, RedisKeys.RATE_LIMIT.API_RATE_LIMIT.ttl)
        logger.success(f"限流 key: {rate_limit_key}")


async def example_4_custom_keys():
    """示例 4：注册自定义 Key"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 4：注册自定义 Key")
    logger.info("=" * 60)
    
    # 注册自定义业务的 key
    MY_BUSINESS_KEY = register_custom_key(
        category="CUSTOM",
        name="MY_BUSINESS",
        namespace="mybiz",
        pattern="data:{entity_type}:{entity_id}",
        description="自定义业务数据",
        ttl=7200,  # 2 小时
        examples=["mybiz:data:order:12345"]
    )
    
    # 使用自定义 key
    key = MY_BUSINESS_KEY.format(entity_type="order", entity_id="12345")
    logger.success(f"自定义 key: {key}, TTL: {MY_BUSINESS_KEY.ttl}秒")
    
    manager = await get_redis_manager()
    async with manager.get_connection() as conn:
        await conn.set(key, "订单数据", ex=MY_BUSINESS_KEY.ttl)
        value = await conn.get(key)
        logger.info(f"存储数据: {value}")


async def example_5_list_all_keys():
    """示例 5：查看所有已注册的 Key"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 5：查看所有已注册的 Key")
    logger.info("=" * 60)
    
    # 打印所有 key
    RedisKeys.list_all()
    
    # 检查 key 冲突
    logger.info("\n检查 key 冲突...")
    conflicts = RedisKeys.check_conflicts()
    if not conflicts:
        logger.success("✓ 未发现 key 冲突")


async def example_6_real_world_scenario():
    """示例 6：真实场景 - 用户登录系统"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 6：真实场景 - 用户登录系统")
    logger.info("=" * 60)
    
    manager = await get_redis_manager()
    user_id = "user_001"
    
    async with manager.get_connection() as conn:
        # 1. 创建用户会话
        session_key = RedisKeys.USER.SESSION.format(user_id=user_id)
        await conn.hset(
            session_key,
            mapping={
                "user_id": user_id,
                "username": "张三",
                "login_time": "2026-01-22 15:30:00",
                "ip": "192.168.1.100"
            }
        )
        await conn.expire(session_key, RedisKeys.USER.SESSION.ttl)
        logger.success(f"✓ 创建会话: {session_key}")
        
        # 2. 缓存用户资料
        profile_key = RedisKeys.USER.PROFILE.format(user_id=user_id)
        await conn.hset(
            profile_key,
            mapping={
                "username": "张三",
                "email": "zhangsan@example.com",
                "age": "28"
            }
        )
        await conn.expire(profile_key, RedisKeys.USER.PROFILE.ttl)
        logger.success(f"✓ 缓存资料: {profile_key}")
        
        # 3. 设置在线状态
        online_key = RedisKeys.USER.ONLINE_STATUS.format(user_id=user_id)
        await conn.set(online_key, "1", ex=RedisKeys.USER.ONLINE_STATUS.ttl)
        logger.success(f"✓ 设置在线: {online_key}")
        
        # 4. 记录登录统计
        import time
        date = time.strftime("%Y-%m-%d")
        stats_key = RedisKeys.STATS.USER_ACTIVITY.format(
            user_id=user_id,
            date=date
        )
        await conn.incr(stats_key)
        await conn.expire(stats_key, RedisKeys.STATS.USER_ACTIVITY.ttl)
        logger.success(f"✓ 记录统计: {stats_key}")
        
        # 5. 查看所有相关的 key
        logger.info(f"\n用户 {user_id} 相关的所有 key:")
        all_keys = await conn.keys(f"*{user_id}*")
        for key in all_keys:
            ttl = await conn.ttl(key)
            logger.info(f"  - {key} (TTL: {ttl}秒)")


async def example_7_key_benefits():
    """示例 7：统一 Key 管理的好处"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 7：统一 Key 管理的好处")
    logger.info("=" * 60)
    
    logger.info("""
统一 Key 管理的优势：

1. ✅ 避免命名冲突
   - 所有 key 都在一个地方定义
   - 可以自动检测冲突

2. ✅ 统一命名风格
   - 一致的命名规范
   - 易于理解和维护

3. ✅ 便于文档和查看
   - 一目了然所有的 key
   - 自带描述和示例

4. ✅ 统一过期时间管理
   - 每种 key 都有明确的 TTL
   - 便于调整和优化

5. ✅ 类型安全
   - 使用 IDE 自动补全
   - 减少拼写错误

6. ✅ 便于重构
   - 修改 key 模式时只需改一处
   - 所有使用的地方自动更新

7. ✅ 代码可读性
   - RedisKeys.USER.PROFILE 比 "user:profile:{id}" 更清晰
    """)


async def main():
    """主函数"""
    try:
        await example_1_basic_usage()
        await example_2_namespace_with_keys()
        await example_3_different_key_types()
        await example_4_custom_keys()
        await example_5_list_all_keys()
        await example_6_real_world_scenario()
        await example_7_key_benefits()
        
        logger.info("\n" + "=" * 60)
        logger.success("所有示例执行完成！")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"示例执行失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
