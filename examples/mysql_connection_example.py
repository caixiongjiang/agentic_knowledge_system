#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : mysql_connection_example.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    MySQL 连接层使用示例，演示如何使用新的连接层
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


from src.db.mysql.connection.factory import get_mysql_manager


def example_sqlite():
    """SQLite 连接示例"""
    print("=" * 50)
    print("SQLite 连接示例")
    print("=" * 50)
    
    # 使用文件数据库
    manager = get_mysql_manager("sqlite", db_path="data/test_sqlite.db")
    print(f"数据库 URL: {manager.get_db_url()}")
    
    # 健康检查
    if manager.health_check():
        print("✓ SQLite 连接正常")
    else:
        print("✗ SQLite 连接失败")


def example_mysql_server():
    """MySQL Server 连接示例"""
    print("\n" + "=" * 50)
    print("MySQL Server 连接示例")
    print("=" * 50)
    
    # 从配置文件读取配置
    manager = get_mysql_manager("mysql")
    print(f"数据库 URL: {manager.get_db_url().split('@')[1] if '@' in manager.get_db_url() else manager.get_db_url()}")
    
    # 健康检查
    if manager.health_check():
        print("✓ MySQL Server 连接正常")
    else:
        print("✗ MySQL Server 连接失败（请检查配置和数据库服务）")


def example_session_usage():
    """会话使用示例"""
    print("\n" + "=" * 50)
    print("会话使用示例")
    print("=" * 50)
    
    # 使用 SQLite 文件数据库
    manager = get_mysql_manager("sqlite", db_path="data/test_sqlite.db")
    
    # 使用上下文管理器获取会话
    with manager.get_session() as session:
        from sqlalchemy import text
        result = session.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        print(f"✓ 查询结果: {row[0] if row else None}")


def example_init_database():
    """初始化数据库示例"""
    print("\n" + "=" * 50)
    print("初始化数据库示例")
    print("=" * 50)
    
    # 使用 SQLite 文件数据库
    manager = get_mysql_manager("sqlite", db_path="data/test_init.db")
    
    try:
        # 初始化数据库和表结构
        manager.init_db()
        print("✓ 数据库初始化成功")
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")


if __name__ == "__main__":
    # SQLite 示例
    example_sqlite()
    
    # MySQL Server 示例（需要配置和数据库服务）
    example_mysql_server()
    
    # 会话使用示例
    example_session_usage()
    
    # 初始化数据库示例
    example_init_database()
    
    print("\n" + "=" * 50)
    print("示例完成")
    print("=" * 50)
