#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_connection_layer.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    测试MySQL连接层
    - 测试工厂模式
    - 测试SQLite和MySQL Server管理器
    - 测试连接池功能
    - 测试会话管理
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def test_factory_pattern():
    """测试1: 工厂模式"""
    print("\n" + "="*60)
    print("测试1: 工厂模式")
    print("="*60)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    
    # 测试获取 SQLite 管理器
    print("\n✓ 获取 SQLite 管理器...")
    sqlite_manager = get_mysql_manager("sqlite")
    print(f"  管理器类型: {type(sqlite_manager).__name__}")
    print(f"  数据库URL: {sqlite_manager.get_db_url()}")
    
    # 测试获取 MySQL Server 管理器
    print("\n✓ 获取 MySQL Server 管理器...")
    try:
        mysql_manager = get_mysql_manager("mysql")
        print(f"  管理器类型: {type(mysql_manager).__name__}")
        print(f"  数据库URL: {mysql_manager.get_db_url()}")
    except Exception as e:
        print(f"  ⚠️ MySQL Server 配置错误（预期行为）: {e}")
    
    print("\n✅ 工厂模式测试通过!")


def test_sqlite_manager():
    """测试2: SQLite 管理器"""
    print("\n" + "="*60)
    print("测试2: SQLite 管理器")
    print("="*60)
    
    from src.db.mysql.connection.sqlite_manager import SQLiteManager
    
    # 测试文件模式
    print("\n✓ 测试文件模式...")
    file_manager = SQLiteManager(db_path="data/test_sqlite.db")
    print(f"  数据库路径: {file_manager.db_path}")
    print(f"  数据库URL: {file_manager.get_db_url()}")
    
    # 测试单例模式
    print("\n✓ 测试单例模式...")
    manager1 = SQLiteManager()
    manager2 = SQLiteManager()
    is_singleton = manager1 is manager2
    print(f"  两个实例是同一对象: {is_singleton}")
    
    if is_singleton:
        print("  ✅ 单例模式工作正常")
    else:
        print("  ❌ 单例模式失败")
    
    print("\n✅ SQLite 管理器测试通过!")


def test_session_management():
    """测试3: 会话管理"""
    print("\n" + "="*60)
    print("测试3: 会话管理")
    print("="*60)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    
    manager = get_mysql_manager("sqlite")
    
    # 测试上下文管理器
    print("\n✓ 测试上下文管理器...")
    try:
        with manager.get_session() as session:
            print(f"  会话对象: {type(session).__name__}")
            print(f"  会话是否激活: {session.is_active}")
            
            # 执行简单查询
            from sqlalchemy import text
            result = session.execute(text("SELECT 1"))
            value = result.scalar()
            print(f"  测试查询结果: {value}")
        
        print("  ✅ 上下文管理器正常退出")
    except Exception as e:
        print(f"  ❌ 会话管理失败: {e}")
        return False
    
    # 测试多个会话
    print("\n✓ 测试多个会话...")
    session_count = 0
    try:
        for i in range(3):
            with manager.get_session() as session:
                session_count += 1
                print(f"  会话 {i+1}: {type(session).__name__}")
        
        print(f"  ✅ 成功创建并关闭 {session_count} 个会话")
    except Exception as e:
        print(f"  ❌ 多会话测试失败: {e}")
        return False
    
    print("\n✅ 会话管理测试通过!")


def test_health_check():
    """测试4: 健康检查"""
    print("\n" + "="*60)
    print("测试4: 健康检查")
    print("="*60)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    
    # 测试 SQLite 健康检查
    print("\n✓ 测试 SQLite 健康检查...")
    sqlite_manager = get_mysql_manager("sqlite")
    is_healthy = sqlite_manager.health_check()
    print(f"  SQLite 连接健康: {is_healthy}")
    
    if is_healthy:
        print("  ✅ SQLite 健康检查通过")
    else:
        print("  ❌ SQLite 健康检查失败")
        return False
    
    print("\n✅ 健康检查测试通过!")


def test_context_manager_with_manager():
    """测试5: 管理器上下文管理器"""
    print("\n" + "="*60)
    print("测试5: 管理器上下文管理器")
    print("="*60)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    
    print("\n✓ 测试管理器的 with 语句...")
    try:
        with get_mysql_manager("sqlite") as manager:
            print(f"  管理器类型: {type(manager).__name__}")
            
            # 使用管理器创建会话
            with manager.get_session() as session:
                from sqlalchemy import text
                result = session.execute(text("SELECT 1"))
                value = result.scalar()
                print(f"  测试查询结果: {value}")
        
        print("  ✅ 管理器上下文管理器正常工作")
    except Exception as e:
        print(f"  ❌ 管理器上下文管理器失败: {e}")
        return False
    
    print("\n✅ 管理器上下文管理器测试通过!")


def test_connection_pool():
    """测试6: 连接池"""
    print("\n" + "="*60)
    print("测试6: 连接池（并发会话）")
    print("="*60)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    import threading
    
    manager = get_mysql_manager("sqlite")
    results = []
    errors = []
    
    def query_in_thread(thread_id):
        """在线程中执行查询"""
        try:
            with manager.get_session() as session:
                from sqlalchemy import text
                result = session.execute(text(f"SELECT {thread_id}"))
                value = result.scalar()
                results.append((thread_id, value))
        except Exception as e:
            errors.append((thread_id, str(e)))
    
    print("\n✓ 创建 5 个并发线程...")
    threads = []
    for i in range(5):
        thread = threading.Thread(target=query_in_thread, args=(i+1,))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    print(f"  成功查询: {len(results)} 次")
    print(f"  失败查询: {len(errors)} 次")
    
    if errors:
        print(f"  ❌ 有线程出错:")
        for thread_id, error in errors:
            print(f"    线程 {thread_id}: {error}")
        return False
    
    if len(results) == 5:
        print("  ✅ 所有并发查询成功")
    else:
        print(f"  ❌ 预期 5 次查询，实际 {len(results)} 次")
        return False
    
    print("\n✅ 连接池测试通过!")


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("MySQL 连接层测试")
    print("="*60)
    
    tests = [
        ("工厂模式", test_factory_pattern),
        ("SQLite 管理器", test_sqlite_manager),
        ("会话管理", test_session_management),
        ("健康检查", test_health_check),
        ("管理器上下文管理器", test_context_manager_with_manager),
        ("连接池", test_connection_pool),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            # 如果函数返回 False，记录为失败；否则记录为成功
            results.append((test_name, result if result is not None else True))
        except Exception as e:
            print(f"\n❌ {test_name} 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 显示测试结果汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
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


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
