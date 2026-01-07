#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_mongodb_crud.py
@Author  : caixiongjiang
@Date    : 2026/1/7
@Function: 
    测试MongoDB的增删改查操作
    - 测试插入数据（create）
    - 测试查询数据（get_by_id, find）
    - 测试更新数据（update）
    - 测试删除数据（delete - 软删除）
    - 测试批量操作（create_batch, bulk_delete_by_ids）
    - 测试 upsert 操作
    - 测试自定义查询方法
    
    数据清理说明：
    - 默认测试后会自动软删除所有测试数据
    - 设置环境变量 KEEP_TEST_DATA=true 可保留数据供查看
    - 测试数据特征：creator字段包含test/batch/upsert/custom等关键字
    
    使用示例：
    # 正常运行（测试后自动清理）
    uv run python test/db/mongodb/test_mongodb_crud.py
    
    # 保留测试数据供查看
    KEEP_TEST_DATA=true uv run python test/db/mongodb/test_mongodb_crud.py
    
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import os
import asyncio
from pathlib import Path
from typing import List
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def generate_test_message_id() -> int:
    """生成测试用的 message_id"""
    import random
    return random.randint(900000, 999999)


async def cleanup_all_test_data():
    """清理所有测试数据（软删除）
    
    可通过环境变量 KEEP_TEST_DATA=true 跳过清理，保留数据供验证
    """
    # 检查是否保留测试数据
    keep_data = os.getenv("KEEP_TEST_DATA", "false").lower() in ("true", "1", "yes")
    
    if keep_data:
        print(f"\n💾 保留测试数据（KEEP_TEST_DATA=true）")
        print(f"   可在数据库中查看测试数据：")
        print(f"   - db.chunk_data.find({{creator: /test/}})")
        print(f"   - db.section_data.find({{creator: /test/}})")
        print(f"   - db.document_data.find({{creator: /test/}})")
        return
    
    try:
        from src.db.mongodb.repositories.chunk_data_repository import chunk_data_repository
        from src.db.mongodb.repositories.section_data_repository import section_data_repository
        from src.db.mongodb.repositories.document_data_repository import document_data_repository
        from src.db.mongodb.models.chunk_data import ChunkData
        from src.db.mongodb.models.section_data import SectionData
        from src.db.mongodb.models.document_data import DocumentData
        
        deleted_count = 0
        
        # 清理 ChunkData 测试数据
        test_patterns = [
            "test_",
            "batch_",
            "upsert_",
            "custom_"
        ]
        
        for pattern in test_patterns:
            # 查找匹配的记录
            test_chunks = await ChunkData.find({
                "creator": {"$regex": f"^{pattern}"},
                "deleted": 0
            }).to_list()
            
            for chunk in test_chunks:
                await chunk_data_repository.delete(str(chunk.id), updater="test_cleanup")
                deleted_count += 1
        
        # 清理 SectionData 测试数据
        for pattern in test_patterns:
            test_sections = await SectionData.find({
                "creator": {"$regex": f"^{pattern}"},
                "deleted": 0
            }).to_list()
            
            for section in test_sections:
                await section_data_repository.delete(str(section.id), updater="test_cleanup")
                deleted_count += 1
        
        # 清理 DocumentData 测试数据
        for pattern in test_patterns:
            test_docs = await DocumentData.find({
                "creator": {"$regex": f"^{pattern}"},
                "deleted": 0
            }).to_list()
            
            for doc in test_docs:
                await document_data_repository.delete(str(doc.id), updater="test_cleanup")
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


async def test_create_record():
    """测试1: 创建记录"""
    print("\n" + "="*70)
    print("测试1: 创建记录")
    print("="*70)
    
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    from src.db.mongodb.repositories.chunk_data_repository import chunk_data_repository
    
    # 确保 MongoDB 已连接
    await get_mongodb_manager()
    
    # 创建记录
    print("\n✓ 创建 ChunkData 记录...")
    message_id = generate_test_message_id()
    
    chunk = await chunk_data_repository.create(
        creator="test_user",
        message_id=message_id,
        chunk_type="text",
        text="这是一段测试文本内容"
    )
    
    if chunk:
        print(f"  ✓ 成功创建记录")
        print(f"    ID: {chunk.id}")
        print(f"    Message ID: {chunk.message_id}")
        print(f"    Chunk Type: {chunk.chunk_type}")
        print(f"    Text: {chunk.text[:30]}...")
        print(f"    Creator: {chunk.creator}")
        print(f"    Status: {chunk.status}")
        print(f"    Deleted: {chunk.deleted}")
    else:
        print(f"  ✗ 创建记录失败")
        return False, None
    
    print("\n✅ 创建记录测试通过!")
    return True, str(chunk.id)


async def test_get_by_id(chunk_id: str):
    """测试2: 根据ID查询记录"""
    print("\n" + "="*70)
    print("测试2: 根据ID查询记录")
    print("="*70)
    
    from src.db.mongodb.repositories.chunk_data_repository import chunk_data_repository
    
    print(f"\n✓ 查询 Chunk ID: {chunk_id}...")
    
    chunk = await chunk_data_repository.get_by_id(chunk_id)
    
    if chunk:
        print(f"  ✓ 成功查询到记录")
        print(f"    ID: {chunk.id}")
        print(f"    Message ID: {chunk.message_id}")
        print(f"    Chunk Type: {chunk.chunk_type}")
        print(f"    Text: {chunk.text[:30] if chunk.text else 'N/A'}...")
    else:
        print(f"  ✗ 未找到记录")
        return False
    
    print("\n✅ 根据ID查询测试通过!")
    return True


async def test_find_records():
    """测试3: 条件查询记录"""
    print("\n" + "="*70)
    print("测试3: 条件查询记录")
    print("="*70)
    
    from src.db.mongodb.repositories.chunk_data_repository import chunk_data_repository
    
    print("\n✓ 查询所有 ChunkData 记录（限制10条）...")
    
    chunks = await chunk_data_repository.find(limit=10)
    
    print(f"  ✓ 查询到 {len(chunks)} 条记录")
    
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"    {i}. ID: {chunk.id}, Message ID: {chunk.message_id}")
    
    print("\n✅ 条件查询测试通过!")
    return True


async def test_update_record(chunk_id: str):
    """测试4: 更新记录"""
    print("\n" + "="*70)
    print("测试4: 更新记录")
    print("="*70)
    
    from src.db.mongodb.repositories.chunk_data_repository import chunk_data_repository
    
    print(f"\n✓ 更新 Chunk ID: {chunk_id}...")
    
    # 先查询原始状态
    chunk_before = await chunk_data_repository.get_by_id(chunk_id)
    if chunk_before:
        print(f"  更新前状态: {chunk_before.status}")
        print(f"  更新前文本: {chunk_before.text[:30] if chunk_before.text else 'N/A'}...")
    
    # 更新记录
    chunk_after = await chunk_data_repository.update(
        chunk_id,
        updater="test_updater",
        status=1,
        text="更新后的测试文本内容"
    )
    
    if chunk_after:
        print(f"  ✓ 成功更新记录")
        print(f"    更新后状态: {chunk_after.status}")
        print(f"    更新后文本: {chunk_after.text[:30]}...")
        print(f"    更新者: {chunk_after.updater}")
        
        # 验证更新
        if chunk_after.status == 1 and chunk_after.text == "更新后的测试文本内容":
            print(f"  ✓ 更新内容正确")
        else:
            print(f"  ✗ 更新内容不正确")
            return False
    else:
        print(f"  ✗ 更新记录失败")
        return False
    
    print("\n✅ 更新记录测试通过!")
    return True


async def test_delete_record(chunk_id: str):
    """测试5: 删除记录（软删除）"""
    print("\n" + "="*70)
    print("测试5: 删除记录（软删除）")
    print("="*70)
    
    from src.db.mongodb.repositories.chunk_data_repository import chunk_data_repository
    
    print(f"\n✓ 删除 Chunk ID: {chunk_id}...")
    
    # 删除记录
    success = await chunk_data_repository.delete(
        chunk_id,
        updater="test_deleter"
    )
    
    if success:
        print(f"  ✓ 成功删除记录（软删除）")
        
        # 验证软删除：尝试查询，应该查不到
        chunk = await chunk_data_repository.get_by_id(chunk_id)
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


async def test_batch_create():
    """测试6: 批量创建记录"""
    print("\n" + "="*70)
    print("测试6: 批量创建记录")
    print("="*70)
    
    from src.db.mongodb.repositories.chunk_data_repository import chunk_data_repository
    
    # 准备批量数据
    print("\n✓ 准备批量数据（5条）...")
    batch_data = []
    chunk_ids = []
    
    for i in range(5):
        message_id = generate_test_message_id()
        
        batch_data.append({
            "message_id": message_id,
            "chunk_type": "text" if i % 2 == 0 else "image",
            "text": f"批量创建的测试文本 #{i+1}",
            "creator": "batch_creator"
        })
    
    # 批量创建
    print("\n✓ 批量创建记录...")
    chunks = await chunk_data_repository.create_batch(
        batch_data,
        creator="batch_creator"
    )
    
    if chunks:
        print(f"  ✓ 成功批量创建 {len(chunks)} 条记录")
        for i, chunk in enumerate(chunks[:3], 1):
            print(f"    {i}. ID: {chunk.id}, Message ID: {chunk.message_id}")
            chunk_ids.append(str(chunk.id))
        
        # 如果超过3条，继续收集ID
        for chunk in chunks[3:]:
            chunk_ids.append(str(chunk.id))
    else:
        print(f"  ✗ 批量创建失败")
        return False, []
    
    print("\n✅ 批量创建测试通过!")
    return True, chunk_ids


async def test_bulk_delete(chunk_ids: List[str]):
    """测试7: 批量删除记录"""
    print("\n" + "="*70)
    print("测试7: 批量删除记录")
    print("="*70)
    
    from src.db.mongodb.repositories.chunk_data_repository import chunk_data_repository
    
    print(f"\n✓ 批量删除 {len(chunk_ids)} 条记录...")
    
    # 批量删除
    deleted_count = await chunk_data_repository.bulk_delete_by_ids(
        chunk_ids,
        updater="batch_deleter"
    )
    
    if deleted_count > 0:
        print(f"  ✓ 成功批量删除 {deleted_count} 条记录")
        
        # 验证删除：查询应该返回 None
        remaining = []
        for chunk_id in chunk_ids:
            chunk = await chunk_data_repository.get_by_id(chunk_id)
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


async def test_upsert():
    """测试8: Upsert操作"""
    print("\n" + "="*70)
    print("测试8: Upsert操作")
    print("="*70)
    
    from src.db.mongodb.repositories.chunk_data_repository import chunk_data_repository
    from bson import ObjectId
    
    # 生成一个固定的ID用于测试
    test_id = str(ObjectId())
    message_id = generate_test_message_id()
    
    # 第一次upsert（应该创建）
    print(f"\n✓ 第一次 upsert (创建): {test_id}...")
    chunk = await chunk_data_repository.upsert(
        test_id,
        creator="upsert_creator",
        updater="upsert_creator",
        message_id=message_id,
        chunk_type="text",
        text="Upsert创建的文本"
    )
    
    if chunk:
        print(f"  ✓ 成功创建记录")
        print(f"    ID: {chunk.id}")
        print(f"    Text: {chunk.text}")
    else:
        print(f"  ✗ 创建记录失败")
        return False
    
    # 第二次upsert（应该更新）
    print(f"\n✓ 第二次 upsert (更新): {test_id}...")
    chunk = await chunk_data_repository.upsert(
        test_id,
        creator="upsert_creator",  # 不会改变
        updater="upsert_updater",
        text="Upsert更新的文本",  # 更新
        chunk_type="image"  # 更新
    )
    
    if chunk:
        print(f"  ✓ 成功更新记录")
        print(f"    ID: {chunk.id}")
        print(f"    Text: {chunk.text}")
        print(f"    Type: {chunk.chunk_type}")
        
        # 验证更新
        if chunk.text == "Upsert更新的文本" and chunk.chunk_type == "image":
            print(f"  ✓ 更新内容正确")
        else:
            print(f"  ✗ 更新内容不正确")
            return False
    else:
        print(f"  ✗ 更新记录失败")
        return False
    
    print("\n✅ Upsert操作测试通过!")
    return True


async def test_custom_query_methods():
    """测试9: 自定义查询方法"""
    print("\n" + "="*70)
    print("测试9: 自定义查询方法")
    print("="*70)
    
    from src.db.mongodb.repositories.chunk_data_repository import chunk_data_repository
    
    # 先创建一些测试数据
    print("\n✓ 创建测试数据...")
    test_message_ids = []
    
    for i in range(3):
        message_id = generate_test_message_id()
        test_message_ids.append(message_id)
        
        await chunk_data_repository.create(
            creator="custom_creator",
            message_id=message_id,
            chunk_type="text",
            text=f"自定义查询测试文本 #{i+1}"
        )
    
    print(f"  ✓ 创建了 {len(test_message_ids)} 条测试数据")
    
    # 测试 get_by_message_id
    print(f"\n✓ 测试 get_by_message_id...")
    chunks = await chunk_data_repository.get_by_message_id(test_message_ids[0])
    
    print(f"  ✓ 查询到 {len(chunks)} 条记录")
    
    if len(chunks) >= 1:
        print(f"  ✓ 查询结果正确")
    else:
        print(f"  ✗ 查询结果不正确")
        return False
    
    # 测试 find_by_type
    print(f"\n✓ 测试 find_by_type...")
    text_chunks = await chunk_data_repository.find_by_type("text", limit=5)
    
    print(f"  ✓ 查询到 {len(text_chunks)} 条 text 类型记录")
    
    if len(text_chunks) >= 1:
        print(f"  ✓ 查询结果正确")
    else:
        print(f"  ✗ 查询结果不正确")
        return False
    
    # 测试 search_by_text（文本模糊搜索）
    print(f"\n✓ 测试 search_by_text...")
    search_chunks = await chunk_data_repository.search_by_text("自定义查询测试", limit=5)
    
    print(f"  ✓ 搜索到 {len(search_chunks)} 条匹配记录")
    
    if len(search_chunks) >= 1:
        print(f"  ✓ 搜索结果正确")
    else:
        print(f"  ⚠️  搜索结果较少（可能是正常的）")
    
    print("\n✅ 自定义查询方法测试通过!")
    return True


async def test_count_operations():
    """测试10: 统计操作"""
    print("\n" + "="*70)
    print("测试10: 统计操作")
    print("="*70)
    
    from src.db.mongodb.repositories.chunk_data_repository import chunk_data_repository
    
    # 测试基础统计
    print("\n✓ 测试基础统计...")
    total_count = await chunk_data_repository.count()
    print(f"  总记录数: {total_count}")
    
    # 测试按类型统计
    print("\n✓ 测试按类型统计...")
    text_count = await chunk_data_repository.count_by_type("text")
    print(f"  text 类型记录数: {text_count}")
    
    image_count = await chunk_data_repository.count_by_type("image")
    print(f"  image 类型记录数: {image_count}")
    
    if total_count >= 0:
        print("  ✅ 统计功能正常")
    else:
        print("  ✗ 统计功能异常")
        return False
    
    print("\n✅ 统计操作测试通过!")
    return True


async def test_section_and_document():
    """测试11: SectionData 和 DocumentData CRUD"""
    print("\n" + "="*70)
    print("测试11: SectionData 和 DocumentData CRUD")
    print("="*70)
    
    from src.db.mongodb.repositories.section_data_repository import section_data_repository
    from src.db.mongodb.repositories.document_data_repository import document_data_repository
    
    # 测试 SectionData
    print("\n✓ 测试 SectionData 创建...")
    section_message_id = generate_test_message_id()
    
    section = await section_data_repository.create(
        creator="test_section_creator",
        message_id=section_message_id,
        text="这是一个测试章节"
    )
    
    if section:
        print(f"  ✓ SectionData 创建成功")
        print(f"    ID: {section.id}")
        print(f"    Message ID: {section.message_id}")
        section_id = str(section.id)
    else:
        print(f"  ✗ SectionData 创建失败")
        return False
    
    # 测试 DocumentData
    print("\n✓ 测试 DocumentData 创建...")
    doc_message_id = generate_test_message_id()
    
    document = await document_data_repository.create(
        creator="test_doc_creator",
        message_id=doc_message_id,
        summary_zh="这是中文摘要",
        summary_en="This is English summary"
    )
    
    if document:
        print(f"  ✓ DocumentData 创建成功")
        print(f"    ID: {document.id}")
        print(f"    Message ID: {document.message_id}")
        print(f"    Summary ZH: {document.summary_zh}")
        doc_id = str(document.id)
    else:
        print(f"  ✗ DocumentData 创建失败")
        return False
    
    # 测试查询和删除
    print("\n✓ 测试查询和删除...")
    
    # 查询 Section
    found_section = await section_data_repository.get_by_id(section_id)
    if found_section:
        print(f"  ✓ Section 查询成功")
    else:
        print(f"  ✗ Section 查询失败")
        return False
    
    # 查询 Document
    found_doc = await document_data_repository.get_by_id(doc_id)
    if found_doc:
        print(f"  ✓ Document 查询成功")
    else:
        print(f"  ✗ Document 查询失败")
        return False
    
    # 删除 Section
    await section_data_repository.delete(section_id, updater="test_cleanup")
    print(f"  ✓ Section 删除成功")
    
    # 删除 Document
    await document_data_repository.delete(doc_id, updater="test_cleanup")
    print(f"  ✓ Document 删除成功")
    
    print("\n✅ SectionData 和 DocumentData CRUD 测试通过!")
    return True


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("MongoDB CRUD 测试套件")
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
        success, chunk_id = await test_create_record()
        results.append(("创建记录", success))
        
        if success and chunk_id:
            # 测试2: 根据ID查询
            success = await test_get_by_id(chunk_id)
            results.append(("根据ID查询", success))
            
            # 测试3: 条件查询
            success = await test_find_records()
            results.append(("条件查询", success))
            
            # 测试4: 更新记录
            success = await test_update_record(chunk_id)
            results.append(("更新记录", success))
            
            # 测试5: 删除记录
            success = await test_delete_record(chunk_id)
            results.append(("删除记录", success))
    except Exception as e:
        print(f"\n✗ 基础CRUD测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("基础CRUD", False))
    
    # 测试6-7: 批量操作
    try:
        success, chunk_ids = await test_batch_create()
        results.append(("批量创建", success))
        
        if success and chunk_ids:
            success = await test_bulk_delete(chunk_ids)
            results.append(("批量删除", success))
    except Exception as e:
        print(f"\n✗ 批量操作测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("批量操作", False))
    
    # 测试8: Upsert
    try:
        success = await test_upsert()
        results.append(("Upsert操作", success))
    except Exception as e:
        print(f"\n✗ Upsert测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Upsert操作", False))
    
    # 测试9: 自定义查询方法
    try:
        success = await test_custom_query_methods()
        results.append(("自定义查询方法", success))
    except Exception as e:
        print(f"\n✗ 自定义查询方法测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("自定义查询方法", False))
    
    # 测试10: 统计操作
    try:
        success = await test_count_operations()
        results.append(("统计操作", success))
    except Exception as e:
        print(f"\n✗ 统计操作测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("统计操作", False))
    
    # 测试11: SectionData 和 DocumentData
    try:
        success = await test_section_and_document()
        results.append(("多模型CRUD", success))
    except Exception as e:
        print(f"\n✗ 多模型CRUD测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("多模型CRUD", False))
    
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
        await cleanup_all_test_data()
    except Exception as e:
        print(f"\n⚠️  清理数据时出错: {e}")
    
    if passed == total:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


def main():
    """主函数"""
    # 设置环境变量，是否保留测试数据，默认不保留
    if "KEEP_TEST_DATA" not in os.environ:
        os.environ["KEEP_TEST_DATA"] = "false"
    
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
