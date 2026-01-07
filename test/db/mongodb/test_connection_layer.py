#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_connection_layer.py
@Author  : caixiongjiang
@Date    : 2026/1/7
@Function: 
    测试MongoDB连接层
    - 测试 MongoDBManager 单例模式
    - 测试连接初始化
    - 测试 Beanie ODM 初始化
    - 测试健康检查
    - 测试异步上下文管理器
    - 测试数据库访问
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


async def test_manager_singleton():
    """测试1: MongoDBManager 单例模式"""
    print("\n" + "="*70)
    print("测试1: MongoDBManager 单例模式")
    print("="*70)
    
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    
    # 获取两个管理器实例
    print("\n✓ 获取第一个 MongoDBManager 实例...")
    manager1 = await get_mongodb_manager()
    print(f"  实例类型: {type(manager1).__name__}")
    
    print("\n✓ 获取第二个 MongoDBManager 实例...")
    manager2 = await get_mongodb_manager()
    print(f"  实例类型: {type(manager2).__name__}")
    
    # 验证是否为同一实例
    is_singleton = manager1 is manager2
    print(f"\n✓ 两个实例是同一对象: {is_singleton}")
    
    if is_singleton:
        print("  ✅ 单例模式工作正常")
    else:
        print("  ❌ 单例模式失败")
        return False
    
    print("\n✅ 单例模式测试通过!")
    return True


async def test_manager_initialization():
    """测试2: 管理器初始化"""
    print("\n" + "="*70)
    print("测试2: 管理器初始化")
    print("="*70)
    
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    
    print("\n✓ 初始化 MongoDBManager...")
    manager = await get_mongodb_manager()
    
    # 检查基础属性
    print(f"  数据库主机: {manager.host}")
    print(f"  数据库端口: {manager.port}")
    print(f"  数据库名称: {manager.database_name}")
    
    # 检查连接池配置
    print(f"  最大连接池大小: {manager.max_pool_size}")
    print(f"  最小连接池大小: {manager.min_pool_size}")
    
    # 检查初始化状态
    is_initialized = manager._initialized
    print(f"\n✓ 初始化状态: {is_initialized}")
    
    if is_initialized:
        print("  ✅ 管理器初始化成功")
    else:
        print("  ❌ 管理器未正确初始化")
        return False
    
    print("\n✅ 管理器初始化测试通过!")
    return True


async def test_health_check():
    """测试3: 健康检查"""
    print("\n" + "="*70)
    print("测试3: 健康检查")
    print("="*70)
    
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    
    manager = await get_mongodb_manager()
    
    print("\n✓ 执行健康检查...")
    is_connected = await manager.is_connected()
    
    print(f"  连接状态: {'正常' if is_connected else '异常'}")
    
    if is_connected:
        print("  ✅ MongoDB 连接健康")
    else:
        print("  ❌ MongoDB 连接异常")
        return False
    
    print("\n✅ 健康检查测试通过!")
    return True


async def test_database_access():
    """测试4: 数据库访问"""
    print("\n" + "="*70)
    print("测试4: 数据库访问")
    print("="*70)
    
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    
    manager = await get_mongodb_manager()
    
    print("\n✓ 获取数据库对象...")
    database = await manager.get_database()
    
    print(f"  数据库名称: {database.name}")
    
    # 列出集合
    print("\n✓ 列出数据库集合...")
    collections = await database.list_collection_names()
    
    print(f"  集合数量: {len(collections)}")
    
    if collections:
        print(f"  集合列表:")
        for i, coll_name in enumerate(collections[:10], 1):
            print(f"    {i}. {coll_name}")
        if len(collections) > 10:
            print(f"    ... 还有 {len(collections) - 10} 个集合")
    else:
        print("  （数据库为空，这是正常的）")
    
    print("\n✅ 数据库访问测试通过!")
    return True


async def test_beanie_initialization():
    """测试5: Beanie ODM 初始化"""
    print("\n" + "="*70)
    print("测试5: Beanie ODM 初始化")
    print("="*70)
    
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    from src.db.mongodb.models.chunk_data import ChunkData
    from src.db.mongodb.models.section_data import SectionData
    from src.db.mongodb.models.document_data import DocumentData
    
    manager = await get_mongodb_manager()
    
    print("\n✓ 验证 Beanie 模型已注册...")
    
    # 验证 ChunkData
    print(f"  ChunkData 集合: {ChunkData.Settings.name}")
    
    # 验证 SectionData
    print(f"  SectionData 集合: {SectionData.Settings.name}")
    
    # 验证 DocumentData
    print(f"  DocumentData 集合: {DocumentData.Settings.name}")
    
    # 尝试执行一个简单的查询
    print("\n✓ 执行测试查询...")
    try:
        count = await ChunkData.find({"deleted": 0}).count()
        print(f"  ChunkData 记录数: {count}")
        print("  ✅ Beanie 查询正常工作")
    except Exception as e:
        print(f"  ❌ Beanie 查询失败: {e}")
        return False
    
    print("\n✅ Beanie 初始化测试通过!")
    return True


async def test_context_manager():
    """测试6: 异步上下文管理器"""
    print("\n" + "="*70)
    print("测试6: 异步上下文管理器")
    print("="*70)
    
    from src.db.mongodb.mongodb_manager import MongoDBManager
    
    print("\n✓ 测试管理器的 async with 语句...")
    try:
        async with await MongoDBManager.get_instance() as manager:
            print(f"  管理器类型: {type(manager).__name__}")
            
            # 执行健康检查
            is_connected = await manager.is_connected()
            print(f"  连接状态: {'正常' if is_connected else '异常'}")
            
            if not is_connected:
                print("  ❌ 上下文中连接异常")
                return False
        
        print("  ✅ 上下文管理器正常退出")
    except Exception as e:
        print(f"  ❌ 上下文管理器失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ 上下文管理器测试通过!")
    return True


async def test_concurrent_access():
    """测试7: 并发访问"""
    print("\n" + "="*70)
    print("测试7: 并发访问")
    print("="*70)
    
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    from src.db.mongodb.models.chunk_data import ChunkData
    
    manager = await get_mongodb_manager()
    results = []
    errors = []
    
    async def query_in_task(task_id: int):
        """在异步任务中执行查询"""
        try:
            count = await ChunkData.find({"deleted": 0}).count()
            results.append((task_id, count))
        except Exception as e:
            errors.append((task_id, str(e)))
    
    print("\n✓ 创建 5 个并发任务...")
    tasks = [query_in_task(i+1) for i in range(5)]
    
    # 等待所有任务完成
    await asyncio.gather(*tasks)
    
    print(f"  成功查询: {len(results)} 次")
    print(f"  失败查询: {len(errors)} 次")
    
    if errors:
        print(f"  ❌ 有任务出错:")
        for task_id, error in errors:
            print(f"    任务 {task_id}: {error}")
        return False
    
    if len(results) == 5:
        print("  ✅ 所有并发查询成功")
    else:
        print(f"  ❌ 预期 5 次查询，实际 {len(results)} 次")
        return False
    
    print("\n✅ 并发访问测试通过!")
    return True


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("MongoDB 连接层测试")
    print("="*70)
    print(f"项目根目录: {project_root}")
    
    tests = [
        ("单例模式", test_manager_singleton),
        ("管理器初始化", test_manager_initialization),
        ("健康检查", test_health_check),
        ("数据库访问", test_database_access),
        ("Beanie 初始化", test_beanie_initialization),
        ("上下文管理器", test_context_manager),
        ("并发访问", test_concurrent_access),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result if result is not None else True))
        except Exception as e:
            print(f"\n❌ {test_name} 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 显示测试结果汇总
    print("\n" + "="*70)
    print("测试结果汇总")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


def main():
    """主函数"""
    try:
        exit_code = asyncio.run(run_all_tests())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
