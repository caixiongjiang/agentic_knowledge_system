#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : mysql_context_manager_example.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    演示 MySQL 连接池的上下文管理器用法
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.mysql.connection.factory import get_mysql_manager


def example_basic_usage():
    """基础用法：手动管理连接"""
    print("=" * 50)
    print("基础用法：手动管理连接")
    print("=" * 50)
    
    manager = get_mysql_manager("sqlite", db_path="data/basic_example.db")
    manager.init_db()
    
    # 使用会话
    with manager.get_session() as session:
        from sqlalchemy import text
        result = session.execute(text("SELECT 1 as test"))
        print(f"✓ 查询结果: {result.fetchone()[0]}")
    
    # 手动关闭连接池
    manager.close()
    print("✓ 连接池已关闭")


def example_context_manager():
    """推荐用法：使用 with 上下文管理器"""
    print("\n" + "=" * 50)
    print("推荐用法：使用 with 上下文管理器")
    print("=" * 50)
    
    # 连接池会在 with 块结束时自动关闭
    with get_mysql_manager("sqlite", db_path="data/context_example.db") as manager:
        manager.init_db()
        
        # 嵌套使用会话上下文管理器
        with manager.get_session() as session:
            from sqlalchemy import text
            result = session.execute(text("SELECT 'Hello' as message"))
            print(f"✓ 查询结果: {result.fetchone()[0]}")
        
        print("✓ 会话已自动关闭")
    
    print("✓ 连接池已自动关闭")


def example_multiple_sessions():
    """多个会话示例"""
    print("\n" + "=" * 50)
    print("多个会话示例")
    print("=" * 50)
    
    with get_mysql_manager("sqlite", db_path="data/multi_session.db") as manager:
        manager.init_db()
        
        # 第一个会话
        with manager.get_session() as session1:
            from sqlalchemy import text
            session1.execute(text("SELECT 1"))
            print("✓ 会话1完成")
        
        # 第二个会话（独立的）
        with manager.get_session() as session2:
            from sqlalchemy import text
            session2.execute(text("SELECT 2"))
            print("✓ 会话2完成")
        
        print("✓ 所有会话已完成")


def example_error_handling():
    """错误处理示例"""
    print("\n" + "=" * 50)
    print("错误处理示例")
    print("=" * 50)
    
    try:
        with get_mysql_manager("sqlite", db_path="data/error_example.db") as manager:
            manager.init_db()
            
            with manager.get_session() as session:
                from sqlalchemy import text
                # 故意执行错误的 SQL
                session.execute(text("SELECT * FROM non_existent_table"))
    except Exception as e:
        print(f"✓ 捕获到异常: {type(e).__name__}")
        print("✓ 连接池已在异常后自动关闭")


def example_singleton_behavior():
    """单例模式验证"""
    print("\n" + "=" * 50)
    print("单例模式验证")
    print("=" * 50)
    
    # 第一次获取
    manager1 = get_mysql_manager("sqlite", db_path="data/singleton_test.db")
    print(f"Manager1 ID: {id(manager1)}")
    print(f"Manager1 db_path: {manager1.db_path}")
    
    # 第二次获取（应该是同一个实例）
    manager2 = get_mysql_manager("sqlite", db_path="data/another.db")
    print(f"Manager2 ID: {id(manager2)}")
    print(f"Manager2 db_path: {manager2.db_path}")
    
    if manager1 is manager2:
        print("✓ 确认是单例模式：两次获取的是同一个实例")
        print("✓ 注意：后续调用的参数会被忽略（单例已初始化）")
    else:
        print("✗ 不是单例模式")


if __name__ == "__main__":
    # 基础用法
    example_basic_usage()
    
    # 推荐用法：with 上下文管理器
    example_context_manager()
    
    # 多个会话
    example_multiple_sessions()
    
    # 错误处理
    example_error_handling()
    
    # 单例验证
    example_singleton_behavior()
    
    print("\n" + "=" * 50)
    print("示例完成")
    print("=" * 50)
