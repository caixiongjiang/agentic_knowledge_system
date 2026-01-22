#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_redis_manager.py
@Author  : caixiongjiang
@Date    : 2026/01/22
@Function: 
    Redis 连接管理器测试
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from loguru import logger

from src.db.redis import (
    get_redis_manager,
    RedisNamespace,
    RedisManagerFactory
)


class TestRedisManager:
    """Redis 连接管理器测试类"""
    
    def __init__(self):
        self.manager = None
        self.test_passed = 0
        self.test_failed = 0
    
    def log_test(self, test_name: str, success: bool, message: str = ""):
        """记录测试结果"""
        if success:
            self.test_passed += 1
            logger.success(f"✓ {test_name}: {message}")
        else:
            self.test_failed += 1
            logger.error(f"✗ {test_name}: {message}")
    
    async def setup(self):
        """初始化测试环境"""
        logger.info("=" * 60)
        logger.info("开始 Redis 连接管理器测试")
        logger.info("=" * 60)
        
        try:
            # 获取 Redis 管理器
            self.manager = await get_redis_manager("standalone")
            self.log_test("管理器初始化", True, "成功创建 Redis 管理器")
        except Exception as e:
            self.log_test("管理器初始化", False, f"初始化失败: {e}")
            raise
    
    async def cleanup(self):
        """清理测试环境"""
        if self.manager:
            await self.manager.close()
            logger.info("已关闭 Redis 连接")
    
    async def test_basic_connection(self):
        """测试基本连接"""
        logger.info("\n[测试 1] 基本连接测试")
        
        try:
            # 测试 PING
            result = await self.manager.ping()
            self.log_test("PING 测试", result, "连接正常")
            
            # 测试健康检查
            result = await self.manager.health_check()
            self.log_test("健康检查", result, "健康检查通过")
            
        except Exception as e:
            self.log_test("基本连接测试", False, f"测试失败: {e}")
    
    async def test_string_operations(self):
        """测试字符串操作"""
        logger.info("\n[测试 2] 字符串操作测试")
        
        try:
            # SET 和 GET
            await self.manager.execute("SET", "test:string", "hello", ex=60)
            value = await self.manager.execute("GET", "test:string")
            self.log_test("SET/GET", value == "hello", f"值: {value}")
            
            # INCR
            await self.manager.execute("SET", "test:counter", "0")
            count = await self.manager.execute("INCR", "test:counter")
            self.log_test("INCR", count == 1, f"计数: {count}")
            
            # 清理
            await self.manager.execute("DEL", "test:string", "test:counter")
            
        except Exception as e:
            self.log_test("字符串操作", False, f"测试失败: {e}")
    
    async def test_namespace_operations(self):
        """测试命名空间操作"""
        logger.info("\n[测试 3] 命名空间操作测试")
        
        try:
            # 创建命名空间
            user_ns = RedisNamespace(self.manager, "test_user")
            cache_ns = RedisNamespace(self.manager, "test_cache")
            
            # 先清理命名空间
            await user_ns.clear_namespace()
            await cache_ns.clear_namespace()
            
            # 测试 key 隔离
            await user_ns.set("123", "user_data")
            await cache_ns.set("123", "cache_data")
            
            user_value = await user_ns.get("123")
            cache_value = await cache_ns.get("123")
            
            self.log_test(
                "命名空间隔离",
                user_value == "user_data" and cache_value == "cache_data",
                f"user: {user_value}, cache: {cache_value}"
            )
            
            # 测试子命名空间
            user_profile = user_ns.sub_namespace("profile")
            await user_profile.set("123", "profile_data")
            profile_value = await user_profile.get("123")
            
            self.log_test(
                "子命名空间",
                profile_value == "profile_data",
                f"profile: {profile_value}"
            )
            
            # 清理
            await user_ns.clear_namespace()
            await cache_ns.clear_namespace()
            
        except Exception as e:
            self.log_test("命名空间操作", False, f"测试失败: {e}")
    
    async def test_hash_operations(self):
        """测试哈希表操作"""
        logger.info("\n[测试 4] 哈希表操作测试")
        
        try:
            test_ns = RedisNamespace(self.manager, "test_hash")
            
            # 先清理命名空间
            await test_ns.clear_namespace()
            
            # HSET 和 HGET
            await test_ns.hset("user:1", "name", "张三")
            await test_ns.hset("user:1", "age", "25")
            
            name = await test_ns.hget("user:1", "name")
            self.log_test("HSET/HGET", name == "张三", f"name: {name}")
            
            # HGETALL
            user_data = await test_ns.hgetall("user:1")
            self.log_test(
                "HGETALL",
                user_data.get("name") == "张三" and user_data.get("age") == "25",
                f"user_data: {user_data}"
            )
            
            # 清理
            await test_ns.clear_namespace()
            
        except Exception as e:
            self.log_test("哈希表操作", False, f"测试失败: {e}")
    
    async def test_list_operations(self):
        """测试列表操作"""
        logger.info("\n[测试 5] 列表操作测试")
        
        try:
            test_ns = RedisNamespace(self.manager, "test_list")
            
            # 先清理命名空间，确保没有旧数据
            await test_ns.clear_namespace()
            
            # LPUSH 和 RPUSH
            await test_ns.lpush("queue", "task1", "task2")
            await test_ns.rpush("queue", "task3")
            
            # LRANGE
            tasks = await test_ns.lrange("queue", 0, -1)
            self.log_test(
                "LPUSH/RPUSH/LRANGE",
                len(tasks) == 3,
                f"tasks: {tasks}"
            )
            
            # LPOP
            task = await test_ns.lpop("queue")
            self.log_test("LPOP", task == "task2", f"task: {task}")
            
            # 清理
            await test_ns.clear_namespace()
            
        except Exception as e:
            self.log_test("列表操作", False, f"测试失败: {e}")
    
    async def test_set_operations(self):
        """测试集合操作"""
        logger.info("\n[测试 6] 集合操作测试")
        
        try:
            test_ns = RedisNamespace(self.manager, "test_set")
            
            # 先清理命名空间
            await test_ns.clear_namespace()
            
            # SADD
            await test_ns.sadd("tags", "python", "redis", "async")
            
            # SMEMBERS
            members = await test_ns.smembers("tags")
            self.log_test(
                "SADD/SMEMBERS",
                len(members) == 3,
                f"members: {members}"
            )
            
            # SISMEMBER
            exists = await test_ns.sismember("tags", "python")
            self.log_test("SISMEMBER", exists, "python 存在于集合中")
            
            # 清理
            await test_ns.clear_namespace()
            
        except Exception as e:
            self.log_test("集合操作", False, f"测试失败: {e}")
    
    async def test_zset_operations(self):
        """测试有序集合操作"""
        logger.info("\n[测试 7] 有序集合操作测试")
        
        try:
            test_ns = RedisNamespace(self.manager, "test_zset")
            
            # 先清理命名空间
            await test_ns.clear_namespace()
            
            # ZADD
            await test_ns.zadd("leaderboard", {"user1": 100, "user2": 95, "user3": 90})
            
            # ZRANGE
            top_users = await test_ns.zrange("leaderboard", 0, -1, withscores=True)
            self.log_test(
                "ZADD/ZRANGE",
                len(top_users) == 3,
                f"top_users: {top_users}"
            )
            
            # ZSCORE
            score = await test_ns.zscore("leaderboard", "user1")
            self.log_test("ZSCORE", score == 100.0, f"user1 score: {score}")
            
            # 清理
            await test_ns.clear_namespace()
            
        except Exception as e:
            self.log_test("有序集合操作", False, f"测试失败: {e}")
    
    async def test_key_operations(self):
        """测试键操作"""
        logger.info("\n[测试 8] 键操作测试")
        
        try:
            test_ns = RedisNamespace(self.manager, "test_keys")
            
            # 先清理命名空间
            await test_ns.clear_namespace()
            
            # 设置键
            await test_ns.set("temp_key", "temp_value")
            
            # EXISTS
            exists = await test_ns.exists("temp_key")
            self.log_test("EXISTS", exists == 1, "键存在")
            
            # EXPIRE 和 TTL
            await test_ns.expire("temp_key", 60)
            ttl = await test_ns.ttl("temp_key")
            self.log_test("EXPIRE/TTL", ttl > 0 and ttl <= 60, f"TTL: {ttl}")
            
            # PERSIST
            await test_ns.persist("temp_key")
            ttl = await test_ns.ttl("temp_key")
            self.log_test("PERSIST", ttl == -1, "过期时间已移除")
            
            # DELETE
            count = await test_ns.delete("temp_key")
            self.log_test("DELETE", count == 1, "键已删除")
            
            # 清理
            await test_ns.clear_namespace()
            
        except Exception as e:
            self.log_test("键操作", False, f"测试失败: {e}")
    
    async def test_context_manager(self):
        """测试上下文管理器"""
        logger.info("\n[测试 9] 上下文管理器测试")
        
        try:
            # 测试 get_connection
            async with self.manager.get_connection() as conn:
                await conn.set("test:ctx", "context_value")
                value = await conn.get("test:ctx")
                self.log_test(
                    "get_connection 上下文",
                    value == "context_value",
                    f"值: {value}"
                )
                await conn.delete("test:ctx")
            
            # 测试管理器上下文
            async with await get_redis_manager() as manager:
                result = await manager.ping()
                self.log_test("管理器上下文", result, "PING 成功")
            
        except Exception as e:
            self.log_test("上下文管理器", False, f"测试失败: {e}")
    
    async def test_factory_pattern(self):
        """测试工厂模式"""
        logger.info("\n[测试 10] 工厂模式测试")
        
        try:
            # 测试相同配置返回同一实例
            manager1 = await RedisManagerFactory.get_manager("standalone")
            manager2 = await RedisManagerFactory.get_manager("standalone")
            
            self.log_test(
                "相同配置缓存",
                manager1 is manager2,
                "相同配置返回同一实例"
            )
            
            # 获取 manager1 的配置（从配置文件读取的默认值）
            default_db = manager1.db
            
            # 测试不同配置创建不同实例（使用不同的 db）
            new_db = 1 if default_db != 1 else 0  # 确保与默认值不同
            manager3 = await get_redis_manager("standalone", db=new_db)
            
            self.log_test(
                "不同配置隔离",
                manager3 is not manager1,
                "不同配置创建新实例"
            )
            
            # 验证配置参数正确
            self.log_test(
                "配置参数正确",
                manager3.db == new_db and manager1.db == default_db,
                f"默认db={default_db}, 新db={manager3.db}"
            )
            
            # 测试相同配置复用
            manager4 = await get_redis_manager("standalone", db=new_db)
            self.log_test(
                "相同配置复用连接池",
                manager3 is manager4,
                f"db={new_db} 的管理器被复用"
            )
            
            # 清理 manager3
            await manager3.close()
            
        except Exception as e:
            self.log_test("工厂模式", False, f"测试失败: {e}")
    
    async def run_all_tests(self):
        """运行所有测试"""
        try:
            await self.setup()
            
            # 执行所有测试
            await self.test_basic_connection()
            await self.test_string_operations()
            await self.test_namespace_operations()
            await self.test_hash_operations()
            await self.test_list_operations()
            await self.test_set_operations()
            await self.test_zset_operations()
            await self.test_key_operations()
            await self.test_context_manager()
            await self.test_factory_pattern()
            
        except Exception as e:
            logger.error(f"测试过程发生错误: {e}")
        finally:
            await self.cleanup()
            
            # 输出测试结果
            logger.info("\n" + "=" * 60)
            logger.info("测试结果统计")
            logger.info("=" * 60)
            logger.info(f"通过: {self.test_passed}")
            logger.info(f"失败: {self.test_failed}")
            logger.info(f"总计: {self.test_passed + self.test_failed}")
            
            if self.test_failed == 0:
                logger.success("🎉 所有测试通过！")
            else:
                logger.warning(f"⚠️  有 {self.test_failed} 个测试失败")
            
            logger.info("=" * 60)


async def main():
    """主函数"""
    tester = TestRedisManager()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
