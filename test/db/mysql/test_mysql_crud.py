#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_mysql_crud.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    测试MySQL表的增删改查操作
    - 测试插入数据（create）
    - 测试查询数据（get_by_id, get_all）
    - 测试更新数据（update）
    - 测试删除数据（delete - 软删除）
    - 测试批量操作（bulk_create, bulk_delete）
    - 测试 upsert 操作
    - 测试自定义查询方法
    
    数据清理说明：
    - 默认测试后会自动软删除所有测试数据
    - 设置环境变量 KEEP_TEST_DATA=true 可保留数据供查看
    - 测试数据特征：creator字段包含test/batch/upsert/custom等关键字
    
    使用示例：
    # 正常运行（测试后自动清理）
    python test/db/mysql/test_mysql_crud.py
    
    # 保留测试数据供查看
    KEEP_TEST_DATA=true python test/db/mysql/test_mysql_crud.py
    
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import os
import uuid
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def generate_test_chunk_id(prefix: str = "test") -> str:
    """生成测试用的 chunk_id"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def cleanup_all_test_data():
    """清理所有测试数据（软删除）
    
    可通过环境变量 KEEP_TEST_DATA=true 跳过清理，保留数据供验证
    """
    # 检查是否保留测试数据
    keep_data = os.getenv("KEEP_TEST_DATA", "false").lower() in ("true", "1", "yes")
    
    if keep_data:
        print(f"\n💾 保留测试数据（KEEP_TEST_DATA=true）")
        print(f"   可在数据库中查看测试数据：")
        print(f"   - SELECT * FROM chunk_section_document WHERE creator LIKE '%creator' OR creator LIKE '%user' OR creator LIKE '%deleter';")
        print(f"   - SELECT * FROM workspace_file_system WHERE creator = 'test_user';")
        return
    
    try:
        from src.db.mysql.connection.factory import get_mysql_manager
        from src.db.mysql.repositories.base import chunk_section_document_repo
        from src.db.mysql.repositories.business import workspace_file_system_repo
        from src.db.mysql.models.base import ChunkSectionDocument
        from src.db.mysql.models.business import WorkspaceFileSystem
        
        manager = get_mysql_manager("mysql")
        deleted_count = 0
        
        with manager.get_session() as session:
            # 清理 ChunkSectionDocument 测试数据
            # 识别测试数据的特征：creator包含test关键字或以batch/upsert/custom开头
            test_patterns = [
                "test_%",
                "batch_%",
                "upsert_%",
                "custom_%",
                "%_creator",
                "%_user",
                "%_deleter",
                "%_updater"
            ]
            
            for pattern in test_patterns:
                test_chunks = session.query(ChunkSectionDocument).filter(
                    ChunkSectionDocument.creator.like(pattern),
                    ChunkSectionDocument.deleted == 0
                ).all()
                
                for chunk in test_chunks:
                    chunk_section_document_repo.delete(
                        session,
                        chunk.chunk_id,
                        updater="test_cleanup"
                    )
                    deleted_count += 1
            
            # 清理 WorkspaceFileSystem 测试数据
            test_files = session.query(WorkspaceFileSystem).filter(
                WorkspaceFileSystem.creator == "test_user",
                WorkspaceFileSystem.deleted == 0
            ).all()
            
            for file_obj in test_files:
                workspace_file_system_repo.delete_by_user_and_file(
                    session,
                    file_obj.user_id,
                    file_obj.file_id,
                    updater="test_cleanup"
                )
                deleted_count += 1
        
        if deleted_count > 0:
            print(f"\n🧹 已软删除 {deleted_count} 条测试数据")
        else:
            print(f"\n✓ 数据库中没有需要清理的测试数据")
                
    except Exception as e:
        print(f"\n⚠️  清理数据时出错: {e}")
        import traceback
        traceback.print_exc()
        # 忽略清理错误，不影响测试结果


def test_create_record():
    """测试1: 创建记录"""
    print("\n" + "="*70)
    print("测试1: 创建记录")
    print("="*70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.base import chunk_section_document_repo
    
    # 获取管理器并初始化数据库
    manager = get_mysql_manager("mysql")
    manager.init_db()
    
    # 创建记录
    print("\n✓ 创建 ChunkSectionDocument 记录...")
    chunk_id = generate_test_chunk_id()
    
    with manager.get_session() as session:
        chunk = chunk_section_document_repo.create(
            session,
            chunk_id=chunk_id,
            section_id="section-001",
            document_id="doc-001",
            creator="test_user",
            role="user",
            knowledge_type="common_file"
        )
        
        if chunk:
            print(f"  ✓ 成功创建记录")
            print(f"    Chunk ID: {chunk.chunk_id}")
            print(f"    Section ID: {chunk.section_id}")
            print(f"    Document ID: {chunk.document_id}")
            print(f"    Creator: {chunk.creator}")
            print(f"    Status: {chunk.status}")
            print(f"    Deleted: {chunk.deleted}")
        else:
            print(f"  ✗ 创建记录失败")
            return False, None
    
    print("\n✅ 创建记录测试通过!")
    return True, chunk_id


def test_get_by_id(chunk_id: str):
    """测试2: 根据ID查询记录"""
    print("\n" + "="*70)
    print("测试2: 根据ID查询记录")
    print("="*70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.base import chunk_section_document_repo
    
    manager = get_mysql_manager("mysql")
    
    print(f"\n✓ 查询 Chunk ID: {chunk_id}...")
    
    with manager.get_session() as session:
        chunk = chunk_section_document_repo.get_by_id(session, chunk_id)
        
        if chunk:
            print(f"  ✓ 成功查询到记录")
            print(f"    Chunk ID: {chunk.chunk_id}")
            print(f"    Section ID: {chunk.section_id}")
            print(f"    Document ID: {chunk.document_id}")
        else:
            print(f"  ✗ 未找到记录")
            return False
    
    print("\n✅ 根据ID查询测试通过!")
    return True


def test_get_all():
    """测试3: 查询所有记录"""
    print("\n" + "="*70)
    print("测试3: 查询所有记录")
    print("="*70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.base import chunk_section_document_repo
    
    manager = get_mysql_manager("mysql")
    
    print("\n✓ 查询所有 ChunkSectionDocument 记录...")
    
    with manager.get_session() as session:
        chunks = chunk_section_document_repo.get_all(session, limit=10)
        
        print(f"  ✓ 查询到 {len(chunks)} 条记录")
        
        for i, chunk in enumerate(chunks[:3], 1):
            print(f"    {i}. Chunk ID: {chunk.chunk_id}, Document ID: {chunk.document_id}")
    
    print("\n✅ 查询所有记录测试通过!")
    return True


def test_update_record(chunk_id: str):
    """测试4: 更新记录"""
    print("\n" + "="*70)
    print("测试4: 更新记录")
    print("="*70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.base import chunk_section_document_repo
    
    manager = get_mysql_manager("mysql")
    
    print(f"\n✓ 更新 Chunk ID: {chunk_id}...")
    
    with manager.get_session() as session:
        # 先查询原始状态
        chunk_before = chunk_section_document_repo.get_by_id(session, chunk_id)
        if chunk_before:
            print(f"  更新前状态: {chunk_before.status}")
        
        # 更新记录
        chunk_after = chunk_section_document_repo.update(
            session,
            chunk_id,
            updater="test_updater",
            status=1,
            section_id="section-002"
        )
        
        if chunk_after:
            print(f"  ✓ 成功更新记录")
            print(f"    更新后状态: {chunk_after.status}")
            print(f"    更新后 Section ID: {chunk_after.section_id}")
            print(f"    更新者: {chunk_after.updater}")
            
            # 验证更新
            if chunk_after.status == 1 and chunk_after.section_id == "section-002":
                print(f"  ✓ 更新内容正确")
            else:
                print(f"  ✗ 更新内容不正确")
                return False
        else:
            print(f"  ✗ 更新记录失败")
            return False
    
    print("\n✅ 更新记录测试通过!")
    return True


def test_delete_record(chunk_id: str):
    """测试5: 删除记录（软删除）"""
    print("\n" + "="*70)
    print("测试5: 删除记录（软删除）")
    print("="*70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.base import chunk_section_document_repo
    
    manager = get_mysql_manager("mysql")
    
    print(f"\n✓ 删除 Chunk ID: {chunk_id}...")
    
    with manager.get_session() as session:
        # 删除记录
        success = chunk_section_document_repo.delete(
            session,
            chunk_id,
            updater="test_deleter"
        )
        
        if success:
            print(f"  ✓ 成功删除记录（软删除）")
            
            # 验证软删除：尝试查询，应该查不到
            chunk = chunk_section_document_repo.get_by_id(session, chunk_id)
            if chunk is None:
                print(f"  ✓ 查询不到已删除的记录（符合预期）")
            else:
                print(f"  ✗ 仍能查询到已删除的记录")
                return False
        else:
            print(f"  ✗ 删除记录失败")
            return False
    
    print("\n✅ 删除记录测试通过!")
    return True


def test_bulk_create():
    """测试6: 批量创建记录"""
    print("\n" + "="*70)
    print("测试6: 批量创建记录")
    print("="*70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.base import chunk_section_document_repo
    
    manager = get_mysql_manager("mysql")
    
    # 准备批量数据
    print("\n✓ 准备批量数据（5条）...")
    batch_data = []
    chunk_ids = []
    
    for i in range(5):
        chunk_id = generate_test_chunk_id(f"batch")
        chunk_ids.append(chunk_id)
        
        batch_data.append({
            "chunk_id": chunk_id,
            "section_id": f"section-batch-{i % 2}",
            "document_id": "doc-batch-001",
            "creator": "batch_creator",
            "role": "user",
            "knowledge_type": "common_file"
        })
    
    # 批量创建
    print("\n✓ 批量创建记录...")
    with manager.get_session() as session:
        chunks = chunk_section_document_repo.bulk_create(session, batch_data)
        
        if chunks:
            print(f"  ✓ 成功批量创建 {len(chunks)} 条记录")
            for i, chunk in enumerate(chunks[:3], 1):
                print(f"    {i}. Chunk ID: {chunk.chunk_id}")
        else:
            print(f"  ✗ 批量创建失败")
            return False, []
    
    print("\n✅ 批量创建测试通过!")
    return True, chunk_ids


def test_bulk_delete(chunk_ids: List[str]):
    """测试7: 批量删除记录"""
    print("\n" + "="*70)
    print("测试7: 批量删除记录")
    print("="*70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.base import chunk_section_document_repo
    
    manager = get_mysql_manager("mysql")
    
    print(f"\n✓ 批量删除 {len(chunk_ids)} 条记录...")
    
    with manager.get_session() as session:
        # 批量删除
        success = chunk_section_document_repo.bulk_delete_by_ids(
            session,
            chunk_ids,
            updater="batch_deleter"
        )
        
        if success:
            print(f"  ✓ 成功批量删除记录")
            
            # 验证删除：查询应该返回空列表
            remaining = []
            for chunk_id in chunk_ids:
                chunk = chunk_section_document_repo.get_by_id(session, chunk_id)
                if chunk:
                    remaining.append(chunk_id)
            
            if not remaining:
                print(f"  ✓ 所有记录已被删除（符合预期）")
            else:
                print(f"  ✗ 仍有 {len(remaining)} 条记录未删除")
                return False
        else:
            print(f"  ✗ 批量删除失败")
            return False
    
    print("\n✅ 批量删除测试通过!")
    return True


def test_upsert():
    """测试8: Upsert操作"""
    print("\n" + "="*70)
    print("测试8: Upsert操作")
    print("="*70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.base import chunk_section_document_repo
    
    manager = get_mysql_manager("mysql")
    
    chunk_id = generate_test_chunk_id("upsert")
    
    # 第一次upsert（应该创建）
    print(f"\n✓ 第一次 upsert (创建): {chunk_id}...")
    with manager.get_session() as session:
        chunk = chunk_section_document_repo.upsert(
            session,
            chunk_id,
            creator="upsert_creator",
            updater="upsert_creator",
            section_id="section-upsert-001",
            document_id="doc-upsert-001"
        )
        
        if chunk:
            print(f"  ✓ 成功创建记录")
            print(f"    Section ID: {chunk.section_id}")
        else:
            print(f"  ✗ 创建记录失败")
            return False
    
    # 第二次upsert（应该更新）
    print(f"\n✓ 第二次 upsert (更新): {chunk_id}...")
    with manager.get_session() as session:
        chunk = chunk_section_document_repo.upsert(
            session,
            chunk_id,
            creator="upsert_creator",  # 不会改变
            updater="upsert_updater",
            section_id="section-upsert-002",  # 更新
            document_id="doc-upsert-002"  # 更新
        )
        
        if chunk:
            print(f"  ✓ 成功更新记录")
            print(f"    Section ID: {chunk.section_id}")
            print(f"    Document ID: {chunk.document_id}")
            
            # 验证更新
            if chunk.section_id == "section-upsert-002":
                print(f"  ✓ 更新内容正确")
            else:
                print(f"  ✗ 更新内容不正确")
                return False
        else:
            print(f"  ✗ 更新记录失败")
            return False
    
    print("\n✅ Upsert操作测试通过!")
    return True


def test_custom_query_methods():
    """测试9: 自定义查询方法"""
    print("\n" + "="*70)
    print("测试9: 自定义查询方法")
    print("="*70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.base import chunk_section_document_repo
    
    manager = get_mysql_manager("mysql")
    
    # 先创建一些测试数据
    print("\n✓ 创建测试数据...")
    test_doc_id = "doc-custom-query-001"
    chunk_ids = []
    
    with manager.get_session() as session:
        for i in range(3):
            chunk_id = generate_test_chunk_id(f"custom")
            chunk_ids.append(chunk_id)
            
            chunk_section_document_repo.create(
                session,
                chunk_id=chunk_id,
                section_id=f"section-custom-{i}",
                document_id=test_doc_id,
                creator="custom_creator"
            )
        
        print(f"  ✓ 创建了 {len(chunk_ids)} 条测试数据")
    
    # 测试 get_by_document_id
    print(f"\n✓ 测试 get_by_document_id...")
    with manager.get_session() as session:
        chunks = chunk_section_document_repo.get_by_document_id(session, test_doc_id)
        
        print(f"  ✓ 查询到 {len(chunks)} 条记录")
        
        if len(chunks) >= 3:
            print(f"  ✓ 查询结果数量正确")
        else:
            print(f"  ✗ 查询结果数量不正确")
            return False
    
    # 测试 get_by_section_id
    print(f"\n✓ 测试 get_by_section_id...")
    with manager.get_session() as session:
        chunks = chunk_section_document_repo.get_by_section_id(session, "section-custom-0")
        
        print(f"  ✓ 查询到 {len(chunks)} 条记录")
        
        if len(chunks) >= 1:
            print(f"  ✓ 查询结果正确")
        else:
            print(f"  ✗ 查询结果不正确")
            return False
    
    print("\n✅ 自定义查询方法测试通过!")
    return True


def test_workspace_file_system():
    """测试10: WorkspaceFileSystem（联合主键表）"""
    print("\n" + "="*70)
    print("测试10: WorkspaceFileSystem（联合主键表）")
    print("="*70)
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.business import workspace_file_system_repo
    
    manager = get_mysql_manager("mysql")
    
    user_id = "test_user_001"
    file_id = f"file-{uuid.uuid4().hex[:8]}"
    
    # 创建记录
    print(f"\n✓ 创建 WorkspaceFileSystem 记录...")
    print(f"  User ID: {user_id}")
    print(f"  File ID: {file_id}")
    
    with manager.get_session() as session:
        file_obj = workspace_file_system_repo.create(
            session,
            user_id=user_id,
            file_id=file_id,
            file_name="test_document.pdf",
            folder_path="/workspace/documents",
            file_size=1024000,
            document_id="doc-001",
            creator="test_user"
        )
        
        if file_obj:
            print(f"  ✓ 成功创建记录")
            print(f"    文件名: {file_obj.file_name}")
            print(f"    文件夹: {file_obj.folder_path}")
        else:
            print(f"  ✗ 创建记录失败")
            return False
    
    # 使用联合主键查询
    print(f"\n✓ 使用联合主键查询...")
    with manager.get_session() as session:
        file_obj = workspace_file_system_repo.get_by_user_and_file(
            session, user_id, file_id
        )
        
        if file_obj:
            print(f"  ✓ 成功查询到记录")
            print(f"    文件名: {file_obj.file_name}")
        else:
            print(f"  ✗ 查询失败")
            return False
    
    # 根据 user_id 查询所有文件
    print(f"\n✓ 查询该用户的所有文件...")
    with manager.get_session() as session:
        files = workspace_file_system_repo.get_by_user_id(session, user_id)
        print(f"  ✓ 查询到 {len(files)} 个文件")
    
    print("\n✅ WorkspaceFileSystem测试通过!")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("MySQL CRUD 测试套件")
    print("="*70)
    print(f"项目根目录: {project_root}")
    
    # 检查是否保留数据
    keep_data = os.getenv("KEEP_TEST_DATA", "false").lower() in ("true", "1", "yes")
    if keep_data:
        print(f"💾 数据保留模式: 测试数据将被保留（KEEP_TEST_DATA=true）")
    else:
        print(f"🧹 数据清理模式: 测试后将自动软删除数据")
        print(f"   提示: 如需保留数据验证，可设置 KEEP_TEST_DATA=true")
    
    results = []
    
    # 测试1: 创建记录
    try:
        success, chunk_id = test_create_record()
        results.append(("创建记录", success))
        
        if success and chunk_id:
            # 测试2: 根据ID查询
            success = test_get_by_id(chunk_id)
            results.append(("根据ID查询", success))
            
            # 测试3: 查询所有记录
            success = test_get_all()
            results.append(("查询所有记录", success))
            
            # 测试4: 更新记录
            success = test_update_record(chunk_id)
            results.append(("更新记录", success))
            
            # 测试5: 删除记录
            success = test_delete_record(chunk_id)
            results.append(("删除记录", success))
    except Exception as e:
        print(f"\n✗ 基础CRUD测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("基础CRUD", False))
    
    # 测试6-7: 批量操作
    try:
        success, chunk_ids = test_bulk_create()
        results.append(("批量创建", success))
        
        if success and chunk_ids:
            success = test_bulk_delete(chunk_ids)
            results.append(("批量删除", success))
    except Exception as e:
        print(f"\n✗ 批量操作测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("批量操作", False))
    
    # 测试8: Upsert
    try:
        success = test_upsert()
        results.append(("Upsert操作", success))
    except Exception as e:
        print(f"\n✗ Upsert测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Upsert操作", False))
    
    # 测试9: 自定义查询方法
    try:
        success = test_custom_query_methods()
        results.append(("自定义查询方法", success))
    except Exception as e:
        print(f"\n✗ 自定义查询方法测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("自定义查询方法", False))
    
    # 测试10: 联合主键表
    try:
        success = test_workspace_file_system()
        results.append(("联合主键表", success))
    except Exception as e:
        print(f"\n✗ 联合主键表测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("联合主键表", False))
    
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
    
    # 清理测试数据
    try:
        cleanup_all_test_data()
    except Exception as e:
        print(f"\n⚠️  清理数据时出错: {e}")
    
    if passed == total:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    # 设置环境变量，是否保留测试数据，默认不保留
    # 如需保留数据供查看，可设置: os.environ["KEEP_TEST_DATA"] = "true"
    if "KEEP_TEST_DATA" not in os.environ:
        os.environ["KEEP_TEST_DATA"] = "false"
    
    exit_code = run_all_tests()
    sys.exit(exit_code)
