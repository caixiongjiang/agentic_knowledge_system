#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_connection_layer.py
@Author  : caixiongjiang
@Date    : 2026/01/03
@Function: 
    测试Milvus连接层
    - 测试工厂模式
    - 测试Server版和Lite版管理器
    - 测试连接管理功能
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""


import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def test_factory_pattern():
    """测试工厂模式"""
    print("\n" + "="*60)
    print("测试1: 工厂模式")
    print("="*60)
    
    from src.db.milvus import (
        get_milvus_manager,
        get_manager_type,
        is_manager_initialized,
        reset_manager
    )
    
    # 测试初始状态
    print(f"管理器是否已初始化: {is_manager_initialized()}")
    
    # 获取管理器（自动选择模式）
    manager = get_milvus_manager()
    print(f"管理器类型: {type(manager).__name__}")
    print(f"当前模式: {get_manager_type()}")
    print(f"管理器是否已初始化: {is_manager_initialized()}")
    
    # 获取连接信息
    info = manager.get_connection_info()
    print(f"\n连接信息:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # 重置管理器
    print("\n重置管理器...")
    reset_manager()
    print(f"重置后是否已初始化: {is_manager_initialized()}")


def test_server_manager():
    """测试Server版管理器"""
    print("\n" + "="*60)
    print("测试2: Server版管理器")
    print("="*60)
    
    from src.db.milvus import get_milvus_server_manager, reset_manager
    
    try:
        # 重置以确保干净的状态
        reset_manager()
        
        # 获取Server版管理器
        manager = get_milvus_server_manager()
        print(f"管理器类型: {type(manager).__name__}")
        
        # 检查连接
        is_connected = manager.check_connection()
        print(f"连接状态: {'已连接' if is_connected else '未连接'}")
        
        if is_connected:
            # 列出集合
            collections = manager.list_collections()
            print(f"集合数量: {len(collections)}")
            if collections:
                print(f"集合列表: {collections}")
        
        # 获取连接信息
        info = manager.get_connection_info()
        print(f"\n连接信息:")
        for key, value in info.items():
            print(f"  {key}: {value}")
            
    except Exception as e:
        print(f"Server版测试失败（可能服务未启动）: {e}")
    finally:
        reset_manager()


def test_lite_manager():
    """测试Lite版管理器"""
    print("\n" + "="*60)
    print("测试3: Lite版管理器")
    print("="*60)
    
    from src.db.milvus import get_milvus_lite_manager, reset_manager
    
    try:
        # 重置以确保干净的状态
        reset_manager()
        
        # 获取Lite版管理器
        manager = get_milvus_lite_manager()
        print(f"管理器类型: {type(manager).__name__}")
        
        # 检查连接
        is_connected = manager.check_connection()
        print(f"连接状态: {'已连接' if is_connected else '未连接'}")
        
        if is_connected:
            # 列出集合
            collections = manager.list_collections()
            print(f"集合数量: {len(collections)}")
            if collections:
                print(f"集合列表: {collections}")
            
            # 获取数据库大小
            size = manager.get_database_size()
            if size >= 0:
                print(f"数据库大小: {size} 字节 ({size/1024:.2f} KB)")
        
        # 获取连接信息
        info = manager.get_connection_info()
        print(f"\n连接信息:")
        for key, value in info.items():
            print(f"  {key}: {value}")
            
    except Exception as e:
        print(f"Lite版测试失败: {e}")
    finally:
        reset_manager()


def test_context_manager():
    """测试上下文管理器"""
    print("\n" + "="*60)
    print("测试4: 上下文管理器")
    print("="*60)
    
    from src.db.milvus import get_milvus_manager, reset_manager
    
    try:
        reset_manager()
        
        # 使用with语句
        with get_milvus_manager() as manager:
            print(f"管理器类型: {type(manager).__name__}")
            is_connected = manager.check_connection()
            print(f"连接状态: {'已连接' if is_connected else '未连接'}")
            
            if is_connected:
                collections = manager.list_collections()
                print(f"集合数量: {len(collections)}")
        
        print("上下文管理器退出成功")
        
    except Exception as e:
        print(f"上下文管理器测试失败: {e}")
    finally:
        reset_manager()


def test_thread_safety():
    """测试线程安全（简单测试）"""
    print("\n" + "="*60)
    print("测试5: 线程安全（单例模式）")
    print("="*60)
    
    from src.db.milvus import get_milvus_manager, reset_manager
    import threading
    
    try:
        reset_manager()
        
        instances = []
        
        def get_instance():
            manager = get_milvus_manager()
            instances.append(manager)
        
        # 创建多个线程同时获取管理器
        threads = [threading.Thread(target=get_instance) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # 检查是否都是同一个实例
        first_instance = instances[0]
        all_same = all(inst is first_instance for inst in instances)
        
        print(f"创建了 {len(instances)} 个引用")
        print(f"所有引用指向同一实例: {all_same}")
        print(f"实例ID: {id(first_instance)}")
        
        if all_same:
            print("✅ 单例模式工作正常")
        else:
            print("❌ 单例模式失败")
            
    except Exception as e:
        print(f"线程安全测试失败: {e}")
    finally:
        reset_manager()


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Milvus连接层测试")
    print("="*60)
    
    try:
        # 测试1: 工厂模式
        test_factory_pattern()
        
        # 测试2: Server版管理器
        test_server_manager()
        
        # 测试3: Lite版管理器
        test_lite_manager()
        
        # 测试4: 上下文管理器
        test_context_manager()
        
        # 测试5: 线程安全
        test_thread_safety()
        
        print("\n" + "="*60)
        print("所有测试完成")
        print("="*60)
        
    except Exception as e:
        print(f"\n测试过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
