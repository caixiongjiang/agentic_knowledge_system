#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_milvus_crud.py
@Author  : caixiongjiang
@Date    : 2026/1/6 11:22
@Function: 
    测试Milvus表的增删改查操作
    - 测试插入数据
    - 测试查询数据
    - 测试向量搜索
    - 测试更新数据（upsert）
    - 测试删除数据
    - 测试批量操作
    - 分别测试Lite和Server两种模式
    - 不依赖外部配置文件，手动设置测试配置
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import os
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


class TestConfig:
    """测试配置类 - 不依赖外部配置文件"""
    
    # Lite模式配置
    LITE_CONFIG = {
        "mode": "lite",
        "lite_db_path": None,  # 会在运行时设置
        "lite_max_connections": 10,
    }
    
    # Server模式配置
    SERVER_CONFIG = {
        "mode": "server",
        "host": "192.168.201.14",
        "port": 19530,
        "database": "default",
        "timeout": 30,
        "alias_prefix": "test_milvus",
    }
    
    @classmethod
    def setup_lite_config(cls):
        """设置Lite模式配置（使用项目data目录）"""
        # 使用项目根目录下的 data/milvus.db
        data_dir = project_root / "data"
        data_dir.mkdir(exist_ok=True)  # 确保目录存在
        
        db_path = str(data_dir / "milvus.db")
        cls.LITE_CONFIG["lite_db_path"] = db_path
        
        # 设置环境变量（允许自动创建集合）
        os.environ["MILVUS_AUTO_CREATE_COLLECTION"] = "true"
        
        return str(data_dir)
    
    @classmethod
    def setup_server_config(cls):
        """设置Server模式配置"""
        # 设置环境变量（允许自动创建集合）
        os.environ["MILVUS_AUTO_CREATE_COLLECTION"] = "true"
    
    @classmethod
    def cleanup_config(cls):
        """清理配置"""
        env_keys = ["MILVUS_AUTO_CREATE_COLLECTION"]
        for key in env_keys:
            if key in os.environ:
                del os.environ[key]


def generate_test_vector(dim: int = 1536) -> List[float]:
    """生成测试用向量"""
    import random
    return [random.random() for _ in range(dim)]


def generate_test_data(count: int = 5, prefix: str = "test") -> List[Dict[str, Any]]:
    """生成测试数据"""
    data = []
    base_time = int(time.time())
    
    for i in range(count):
        item = {
            "id": f"{prefix}_{uuid.uuid4().hex[:8]}",
            "vector": generate_test_vector(1536),
            "user_id": f"{prefix}_user_001",
            "knowledge_base_id": f"{prefix}_kb_001",
            "knowledge_base_name": "测试知识库",
            "parent_knowledge_base_id": "",
            "parent_knowledge_base_name": "",
            "agent_ids": {
                "session_id": 1000 + i,
                "task_id": 2000 + i,
                "agent_id": f"{prefix}_agent_{i}",
                "message_id": 3000 + i,
            },
            "type": "text",
            "role": "user",
            "knowledge_type": f"{prefix}_knowledge",
            "document_id": f"{prefix}_doc_{i % 3}",  # 3个文档
            "label_id": f"label_{i % 2}",  # 2个标签
            "timestamp": base_time + i,
            "create_time": base_time + i,
            "update_time": base_time + i,
        }
        data.append(item)
    
    return data


def setup_test_repository(mode: str = "lite", temp_dir: str = None):
    """设置测试Repository
    
    Args:
        mode: "lite" 或 "server"
        temp_dir: Lite模式的临时目录
    """
    if mode == "lite":
        if temp_dir is None:
            temp_dir = TestConfig.setup_lite_config()
        else:
            TestConfig.setup_lite_config()
    else:
        TestConfig.setup_server_config()
    
    from src.db.milvus import get_milvus_manager, reset_manager
    from src.db.milvus.repositories import ChunkRepository
    
    # 重置管理器
    reset_manager()
    
    # 获取管理器（强制指定模式）
    manager = get_milvus_manager(mode=mode)
    
    # 检查连接
    if not manager.check_connection():
        raise ConnectionError(f"无法连接到Milvus ({mode}模式)")
    
    # 创建Repository
    repo = ChunkRepository(manager=manager)
    
    return repo, manager, temp_dir


def cleanup_test_data(repo, prefix: str = "test"):
    """清理测试数据
    
    可通过环境变量 KEEP_TEST_DATA=true 跳过清理，保留数据供验证
    """
    # 检查是否保留测试数据
    keep_data = os.getenv("KEEP_TEST_DATA", "false").lower() in ("true", "1", "yes")
    
    if keep_data:
        print(f"\n💾 保留测试数据（KEEP_TEST_DATA=true）")
        print(f"   可通过 user_id == '{prefix}_user_001' 查询这些数据")
        return
    
    try:
        # 删除所有测试数据
        repo.delete(f'user_id == "{prefix}_user_001"')
        print(f"\n🧹 已清理测试数据（user_id: {prefix}_user_001）")
    except Exception as e:
        pass  # 忽略清理错误


def run_crud_tests_for_mode(mode: str, prefix: str):
    """为指定模式运行CRUD测试
    
    Args:
        mode: "lite" 或 "server"
        prefix: 测试数据前缀，用于区分不同模式的数据
    """
    print("\n" + "="*70)
    print(f"运行 {mode.upper()} 模式的 CRUD 测试")
    print("="*70)
    
    temp_dir = None
    results = []
    
    try:
        # 设置Repository
        if mode == "lite":
            temp_dir = TestConfig.setup_lite_config()
            print(f"✓ 使用Lite数据库: {TestConfig.LITE_CONFIG['lite_db_path']}")
        else:
            TestConfig.setup_server_config()
            print(f"✓ 使用Server: {TestConfig.SERVER_CONFIG['host']}:{TestConfig.SERVER_CONFIG['port']}")
        
        repo, manager, temp_dir = setup_test_repository(mode, temp_dir)
        print(f"✓ 连接成功: {type(manager).__name__}")
        print(f"✓ 使用集合: {repo.collection_name}")
        
        # 运行各项测试
        tests = [
            ("插入数据", lambda: test_insert_data(repo, prefix)),
            ("查询数据", lambda: test_query_data(repo, prefix)),
            ("向量搜索", lambda: test_vector_search(repo, prefix)),
            ("更新数据（Upsert）", lambda: test_upsert_data(repo, prefix)),
            ("删除数据", lambda: test_delete_data(repo, prefix)),
            ("批量操作", lambda: test_batch_operations(repo, prefix)),
        ]
        
        for test_name, test_func in tests:
            try:
                print(f"\n{'='*60}")
                print(f"{mode.upper()} - {test_name}")
                print('='*60)
                result = test_func()
                results.append((f"{mode} - {test_name}", result))
            except Exception as e:
                print(f"\n✗ 测试失败: {e}")
                import traceback
                traceback.print_exc()
                results.append((f"{mode} - {test_name}", False))
        
        return results
        
    except ConnectionError as e:
        print(f"\n⚠️  {e}")
        if mode == "server":
            print("   提示: Server模式需要Milvus服务正在运行")
        return [(f"{mode} - 连接测试", False)]
    except Exception as e:
        print(f"\n✗ 模式初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return [(f"{mode} - 初始化", False)]
    finally:
        # 清理
        try:
            if 'repo' in locals():
                cleanup_test_data(repo, prefix)
        except:
            pass
        
        try:
            from src.db.milvus import reset_manager
            reset_manager()
        except:
            pass
        
        TestConfig.cleanup_config()
        
        # 注意：数据库文件保留在 data/milvus.db 供后续查看
        # 如需清理，可手动删除 data/milvus.db 文件
        if temp_dir:
            print(f"\n💾 数据库文件位置: {temp_dir}/milvus.db")


def test_insert_data(repo, prefix: str):
    """测试: 插入数据"""
    # 生成测试数据
    test_data = generate_test_data(5, prefix)
    print(f"\n✓ 生成 {len(test_data)} 条测试数据")
    
    # 插入数据
    print(f"✓ 开始插入数据...")
    inserted_ids = repo.insert(test_data)
    
    print(f"  ✓ 成功插入 {len(inserted_ids)} 条数据")
    print(f"  ✓ 插入的ID: {inserted_ids[:3]}{'...' if len(inserted_ids) > 3 else ''}")
    
    # 验证插入
    time.sleep(1)  # 等待数据同步
    count = repo.count()
    print(f"  ✓ 集合当前记录数: {count}")
    
    print("\n✅ 插入数据测试通过!")
    return True


def test_query_data(repo, prefix: str):
    """测试: 查询数据"""
    # 插入测试数据
    test_data = generate_test_data(5, prefix)
    inserted_ids = repo.insert(test_data)
    time.sleep(1)
    
    print(f"\n✓ 已插入 {len(inserted_ids)} 条测试数据")
    
    # 测试按ID查询
    print(f"\n✓ 测试按ID查询...")
    query_ids = inserted_ids[:2]
    results = repo.query_by_ids(query_ids)
    
    print(f"  查询ID数量: {len(query_ids)}")
    print(f"  返回结果数量: {len(results)}")
    
    if len(results) == len(query_ids):
        print(f"  ✓ 查询结果数量正确")
    else:
        print(f"  ✗ 查询结果数量不匹配")
        return False
    
    # 测试条件查询
    print(f"\n✓ 测试条件查询...")
    expr = f'user_id == "{prefix}_user_001"'
    results = repo.query(expr, limit=10)
    
    print(f"  查询表达式: {expr}")
    print(f"  返回结果数量: {len(results)}")
    
    if len(results) > 0:
        print(f"  ✓ 查询成功")
    else:
        print(f"  ✗ 查询无结果")
        return False
    
    # 测试专用查询方法
    print(f"\n✓ 测试专用查询方法...")
    doc_results = repo.get_chunks_by_document(f"{prefix}_doc_0")
    print(f"  按文档ID查询结果: {len(doc_results)} 条")
    
    kb_results = repo.get_chunks_by_knowledge_base(f"{prefix}_kb_001")
    print(f"  按知识库ID查询结果: {len(kb_results)} 条")
    
    print("\n✅ 查询数据测试通过!")
    return True


def test_vector_search(repo, prefix: str):
    """测试: 向量搜索"""
    # 插入测试数据
    test_data = generate_test_data(10, prefix)
    inserted_ids = repo.insert(test_data)
    time.sleep(1)
    
    print(f"\n✓ 已插入 {len(inserted_ids)} 条测试数据")
    
    # 生成查询向量
    query_vector = test_data[0]["vector"]
    
    # 测试基础向量搜索
    print(f"\n✓ 测试基础向量搜索...")
    results = repo.search(
        vectors=[query_vector],
        vector_field="vector",
        top_k=5
    )
    
    if results and len(results) > 0:
        top_results = results[0]
        print(f"  Top-K结果数: {len(top_results)}")
        
        print(f"\n  Top-3 结果:")
        for i, hit in enumerate(top_results[:3], 1):
            print(f"    {i}. ID: {hit.get('id')}, Score: {hit.get('score'):.4f}")
    else:
        print(f"  ✗ 搜索无结果")
        return False
    
    # 测试带过滤的搜索
    print(f"\n✓ 测试带过滤条件的向量搜索...")
    filtered_results = repo.search(
        vectors=[query_vector],
        vector_field="vector",
        top_k=3,
        filter_expr=f'document_id == "{prefix}_doc_0"'
    )
    
    if filtered_results and len(filtered_results) > 0:
        print(f"  过滤后结果数: {len(filtered_results[0])}")
    
    # 测试专用搜索方法
    print(f"\n✓ 测试专用搜索方法...")
    search_results = repo.search_by_vector(
        query_vector=query_vector,
        top_k=5,
        user_id=f"{prefix}_user_001"
    )
    
    print(f"  返回结果数: {len(search_results)}")
    
    print("\n✅ 向量搜索测试通过!")
    return True


def test_upsert_data(repo, prefix: str):
    """测试: 更新数据（Upsert）"""
    # 插入初始数据
    test_data = generate_test_data(3, prefix)
    inserted_ids = repo.insert(test_data)
    time.sleep(1)
    
    print(f"\n✓ 已插入 {len(inserted_ids)} 条初始数据")
    
    # 准备更新数据
    print(f"\n✓ 测试Upsert更新现有数据...")
    update_data = [{
        "id": inserted_ids[0],
        "vector": generate_test_vector(1536),
        "user_id": f"{prefix}_user_001",
        "knowledge_base_id": f"{prefix}_kb_001",
        "knowledge_base_name": "测试知识库",
        "parent_knowledge_base_id": "",
        "parent_knowledge_base_name": "",
        "agent_ids": {"session_id": 9999},
        "type": "updated_text",
        "role": "assistant",
        "knowledge_type": f"{prefix}_knowledge",
        "document_id": f"{prefix}_doc_0",
        "label_id": "label_0",
        "timestamp": int(time.time()),
        "create_time": int(time.time()),
        "update_time": int(time.time()),
    }]
    
    upsert_ids = repo.upsert(update_data)
    time.sleep(1)
    
    print(f"  ✓ Upsert完成，ID: {upsert_ids[0]}")
    
    # 验证更新
    updated_results = repo.query_by_ids([inserted_ids[0]])
    if updated_results:
        updated_type = updated_results[0].get('type')
        if updated_type == "updated_text":
            print(f"  ✓ 数据更新成功: type={updated_type}")
        else:
            print(f"  ✗ 数据更新失败")
            return False
    
    # 测试插入新数据
    print(f"\n✓ 测试Upsert插入新数据...")
    new_data = [{
        "id": f"{prefix}_new_{uuid.uuid4().hex[:8]}",
        "vector": generate_test_vector(1536),
        "user_id": f"{prefix}_user_001",
        "knowledge_base_id": f"{prefix}_kb_001",
        "knowledge_base_name": "测试知识库",
        "parent_knowledge_base_id": "",
        "parent_knowledge_base_name": "",
        "agent_ids": {"session_id": 8888},
        "type": "new_text",
        "role": "system",
        "knowledge_type": f"{prefix}_knowledge",
        "document_id": f"{prefix}_doc_new",
        "label_id": "label_new",
        "timestamp": int(time.time()),
        "create_time": int(time.time()),
        "update_time": int(time.time()),
    }]
    
    new_ids = repo.upsert(new_data)
    time.sleep(1)
    
    print(f"  ✓ 新数据插入完成，ID: {new_ids[0]}")
    
    print("\n✅ Upsert数据测试通过!")
    return True


def test_delete_data(repo, prefix: str):
    """测试: 删除数据"""
    # 插入测试数据
    test_data = generate_test_data(10, prefix)
    inserted_ids = repo.insert(test_data)
    time.sleep(1)
    
    initial_count = repo.count()
    print(f"\n✓ 已插入 {len(inserted_ids)} 条测试数据")
    print(f"  初始记录数: {initial_count}")
    
    # 测试按ID删除
    print(f"\n✓ 测试按ID删除...")
    delete_ids = inserted_ids[:2]
    repo.delete_by_ids(delete_ids)
    time.sleep(1)
    
    # 验证删除
    remaining = repo.query_by_ids(delete_ids)
    if len(remaining) == 0:
        print(f"  ✓ 成功删除 {len(delete_ids)} 条数据")
    else:
        print(f"  ✗ 删除失败")
        return False
    
    # 测试按条件删除
    print(f"\n✓ 测试按条件删除...")
    repo.delete(f'document_id == "{prefix}_doc_0"')
    time.sleep(1)
    
    doc_results = repo.get_chunks_by_document(f"{prefix}_doc_0")
    if len(doc_results) == 0:
        print(f"  ✓ 成功删除文档的所有数据")
    else:
        print(f"  ✗ 删除失败")
        return False
    
    print("\n✅ 删除数据测试通过!")
    return True


def test_batch_operations(repo, prefix: str):
    """测试: 批量操作"""
    # 测试大批量插入
    print(f"\n✓ 测试大批量插入...")
    large_batch = generate_test_data(50, prefix)
    
    start_time = time.time()
    inserted_ids = repo.insert(large_batch)
    insert_time = time.time() - start_time
    
    print(f"  插入 {len(inserted_ids)} 条数据")
    print(f"  耗时: {insert_time:.2f} 秒")
    print(f"  速度: {len(inserted_ids)/insert_time:.2f} 条/秒")
    
    time.sleep(2)
    
    # 测试批量查询
    print(f"\n✓ 测试批量查询...")
    query_ids = inserted_ids[:20]
    
    start_time = time.time()
    results = repo.query_by_ids(query_ids)
    query_time = time.time() - start_time
    
    print(f"  查询 {len(query_ids)} 条数据")
    print(f"  返回 {len(results)} 条结果")
    print(f"  耗时: {query_time:.2f} 秒")
    
    print("\n✅ 批量操作测试通过!")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("Milvus CRUD 操作测试套件")
    print("="*70)
    print(f"项目根目录: {project_root}")
    print(f"测试模式: 独立配置（不依赖外部配置文件）")
    
    # 检查是否保留数据
    keep_data = os.getenv("KEEP_TEST_DATA", "false").lower() in ("true", "1", "yes")
    if keep_data:
        print(f"💾 数据保留模式: 测试数据将被保留（KEEP_TEST_DATA=true）")
    else:
        print(f"🧹 数据清理模式: 测试后将自动清理数据")
        print(f"   提示: 如需保留数据验证，可设置 KEEP_TEST_DATA=true")
    
    all_results = []
    
    # 测试Lite模式
    print("\n" + "🔹"*35)
    print("开始测试 LITE 模式")
    print("🔹"*35)
    lite_results = run_crud_tests_for_mode("lite", "lite_test")
    all_results.extend(lite_results)
    
    # 测试Server模式
    print("\n" + "🔹"*35)
    print("开始测试 SERVER 模式")
    print("🔹"*35)
    server_results = run_crud_tests_for_mode("server", "server_test")
    all_results.extend(server_results)
    
    # 显示测试结果汇总
    print("\n" + "="*70)
    print("测试结果汇总")
    print("="*70)
    
    passed = sum(1 for _, result in all_results if result)
    total = len(all_results)
    
    # 按模式分组显示
    print("\n【LITE 模式】")
    for test_name, result in all_results:
        if test_name.startswith("lite"):
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{status}: {test_name}")
    
    print("\n【SERVER 模式】")
    for test_name, result in all_results:
        if test_name.startswith("server"):
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
    # 设置环境变量，是否保留测试数据，默认不保留
    os.environ["KEEP_TEST_DATA"] = "false"
    exit_code = run_all_tests()
    sys.exit(exit_code)
