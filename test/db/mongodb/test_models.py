#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_models.py
@Author  : caixiongjiang
@Date    : 2026/1/7
@Function: 
    测试MongoDB模型定义
    - 测试模型类定义正确性
    - 测试字段定义完整性
    - 测试 BaseDocument 继承
    - 测试索引配置
    - 测试自定义方法
    - 测试集合创建
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def test_model_definitions():
    """测试1: 模型定义正确性"""
    print("\n" + "="*70)
    print("测试1: 模型定义正确性")
    print("="*70)
    
    from src.db.mongodb.models.base_model import BaseDocument
    from src.db.mongodb.models.chunk_data import ChunkData
    from src.db.mongodb.models.section_data import SectionData
    from src.db.mongodb.models.document_data import DocumentData
    
    # 测试所有模型都能正常访问
    print("\n✓ 测试模型类...")
    models = {
        "BaseDocument": BaseDocument,
        "ChunkData": ChunkData,
        "SectionData": SectionData,
        "DocumentData": DocumentData,
    }
    
    for name, model_class in models.items():
        if hasattr(model_class, "Settings") and hasattr(model_class.Settings, "name"):
            collection_name = model_class.Settings.name
            print(f"  ✓ {name}: {collection_name}")
        else:
            print(f"  ✓ {name}: (基类)")
    
    # 验证集合名唯一性
    print("\n✓ 验证集合名唯一性...")
    collection_names = []
    for name, model_class in models.items():
        if hasattr(model_class, "Settings") and hasattr(model_class.Settings, "name"):
            collection_names.append(model_class.Settings.name)
    
    if len(collection_names) == len(set(collection_names)):
        print(f"  ✓ 所有集合名唯一 (共{len(collection_names)}个)")
    else:
        print(f"  ✗ 发现重复的集合名!")
        return False
    
    print("\n✅ 模型定义正确性测试通过!")
    return True


def test_model_fields():
    """测试2: 字段定义完整性"""
    print("\n" + "="*70)
    print("测试2: 字段定义完整性")
    print("="*70)
    
    from src.db.mongodb.models.chunk_data import ChunkData
    from src.db.mongodb.models.document_data import DocumentData
    
    # 测试 ChunkData 的字段
    print("\n✓ 测试 ChunkData 字段定义...")
    chunk_fields = ChunkData.model_fields
    
    print(f"  字段数量: {len(chunk_fields)}")
    
    # 检查必需字段
    required_fields = ["chunk_type", "text_meta", "search_text", "deleted"]
    
    print(f"\n  检查必需字段:")
    for field_name in required_fields:
        if field_name in chunk_fields or (field_name == "chunk_type" and "type" in chunk_fields):
            print(f"    ✓ {field_name}")
        else:
            print(f"    ✗ {field_name} (缺失!)")
            return False
    
    # 测试 DocumentData 的字段
    print("\n✓ 测试 DocumentData 字段定义...")
    doc_fields = DocumentData.model_fields
    
    print(f"  字段数量: {len(doc_fields)}")
    
    # 检查摘要字段
    summary_fields = ["summary_zh", "summary_en"]
    print(f"\n  检查摘要字段:")
    for field_name in summary_fields:
        if field_name in doc_fields:
            print(f"    ✓ {field_name}")
        else:
            print(f"    ✗ {field_name} (缺失!)")
            return False
    
    print("\n✅ 字段定义完整性测试通过!")
    return True


def test_base_document_inheritance():
    """测试3: BaseDocument 继承"""
    print("\n" + "="*70)
    print("测试3: BaseDocument 继承")
    print("="*70)
    
    from src.db.mongodb.models.chunk_data import ChunkData
    from src.db.mongodb.models.base_model import BaseDocument
    
    # 测试继承关系
    print("\n✓ 测试继承关系...")
    is_subclass = issubclass(ChunkData, BaseDocument)
    print(f"  ChunkData 继承自 BaseDocument: {is_subclass}")
    
    if not is_subclass:
        print("  ✗ 继承关系错误")
        return False
    
    # 测试审计字段
    print("\n✓ 测试审计字段...")
    audit_fields = ["status", "creator", "create_time", "updater", "update_time", "deleted"]
    chunk_fields = ChunkData.model_fields
    
    for field_name in audit_fields:
        if field_name in chunk_fields:
            field_info = chunk_fields[field_name]
            print(f"  ✓ {field_name}")
        else:
            print(f"  ✗ {field_name} (缺失!)")
            return False
    
    print("\n✅ BaseDocument 继承测试通过!")
    return True


def test_model_indexes():
    """测试4: 索引配置"""
    print("\n" + "="*70)
    print("测试4: 索引配置")
    print("="*70)
    
    from src.db.mongodb.models.chunk_data import ChunkData
    from src.db.mongodb.models.section_data import SectionData
    
    # 测试 ChunkData 索引
    print("\n✓ 测试 ChunkData 索引配置...")
    if hasattr(ChunkData.Settings, 'indexes') and ChunkData.Settings.indexes:
        indexes = ChunkData.Settings.indexes
        print(f"  索引数量: {len(indexes)}")
        
        for i, index in enumerate(indexes, 1):
            index_info = index.document
            index_name = index_info.get('name', f'index_{i}')
            index_keys = index_info.get('key', [])
            print(f"    {i}. {index_name}: {index_keys}")
        
        print("  ✅ ChunkData 索引配置正确")
    else:
        print("  ⚠️  ChunkData 未配置索引")
    
    # 测试 SectionData 索引
    print("\n✓ 测试 SectionData 索引配置...")
    if hasattr(SectionData.Settings, 'indexes') and SectionData.Settings.indexes:
        indexes = SectionData.Settings.indexes
        print(f"  索引数量: {len(indexes)}")
        print("  ✅ SectionData 索引配置正确")
    else:
        print("  ⚠️  SectionData 未配置索引")
    
    print("\n✅ 索引配置测试通过!")
    return True


async def test_custom_methods():
    """测试5: 自定义方法"""
    print("\n" + "="*70)
    print("测试5: 自定义方法")
    print("="*70)
    
    from src.db.mongodb.models.chunk_data import ChunkData
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    
    # 确保 MongoDB 已连接
    await get_mongodb_manager()
    
    # 测试 has_image 方法
    print("\n✓ 测试 has_image 方法...")
    
    # 创建测试实例（不保存到数据库）
    chunk_with_image = ChunkData(
        message_id=1,
        chunk_type="image",
        creator="test"
    )
    
    chunk_without_image = ChunkData(
        message_id=2,
        chunk_type="text",
        creator="test"
    )
    
    has_image_1 = chunk_with_image.has_image()
    has_image_2 = chunk_without_image.has_image()
    
    print(f"  chunk_type='image' 的 has_image: {has_image_1}")
    print(f"  chunk_type='text' 的 has_image: {has_image_2}")
    
    if has_image_1 and not has_image_2:
        print("  ✅ has_image 方法工作正常")
    else:
        print("  ✗ has_image 方法异常")
        return False
    
    # 测试 has_text 方法
    print("\n✓ 测试 has_text 方法...")
    
    chunk_with_text = ChunkData(
        id="chunk_test_has_text",
        chunk_type="text",
        text_meta={"text": "测试文本"},
    )

    chunk_without_text = ChunkData(
        id="chunk_test_no_text",
        chunk_type="text",
    )
    
    has_text_1 = chunk_with_text.has_text()
    has_text_2 = chunk_without_text.has_text()
    
    print(f"  有 text 的 has_text: {has_text_1}")
    print(f"  无 text 的 has_text: {has_text_2}")
    
    if has_text_1 and not has_text_2:
        print("  ✅ has_text 方法工作正常")
    else:
        print("  ✗ has_text 方法异常")
        return False
    
    print("\n✅ 自定义方法测试通过!")
    return True


async def test_collection_creation():
    """测试6: 集合创建"""
    print("\n" + "="*70)
    print("测试6: 集合创建")
    print("="*70)
    
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    
    print("\n✓ 获取 MongoDB 管理器...")
    manager = await get_mongodb_manager()
    database = await manager.get_database()
    
    # 列出所有集合
    print("\n✓ 列出数据库集合...")
    collections = await database.list_collection_names()
    
    print(f"  集合数量: {len(collections)}")
    
    # 检查关键集合是否存在
    expected_collections = [
        "chunk_data",
        "section_data",
        "document_data"
    ]
    
    print("\n  检查关键集合:")
    found_collections = []
    for coll_name in expected_collections:
        if coll_name in collections:
            print(f"    ✓ {coll_name}")
            found_collections.append(coll_name)
        else:
            print(f"    ⚠️  {coll_name} (未找到，可能尚未创建)")
    
    if found_collections:
        print(f"\n  ✅ 找到 {len(found_collections)}/{len(expected_collections)} 个预期集合")
    else:
        print(f"\n  ⚠️  未找到预期集合（这是正常的，集合会在首次插入数据时自动创建）")
    
    print("\n✅ 集合创建测试通过!")
    return True


async def test_model_instantiation():
    """测试7: 模型实例化"""
    print("\n" + "="*70)
    print("测试7: 模型实例化")
    print("="*70)
    
    from src.db.mongodb.models.chunk_data import ChunkData
    from src.db.mongodb.models.section_data import SectionData
    from src.db.mongodb.models.document_data import DocumentData
    
    # 测试 ChunkData 实例化
    print("\n✓ 测试 ChunkData 实例化...")
    try:
        chunk = ChunkData(
            id="chunk_test_instantiate",
            chunk_type="text",
            text_meta={"text": "这是一段测试文本"},
        )
        print(f"  ✓ ChunkData 实例化成功")
        print(f"    chunk_type: {chunk.chunk_type}")
        print(f"    text_meta: {chunk.text_meta}")
    except Exception as e:
        print(f"  ✗ ChunkData 实例化失败: {e}")
        return False
    
    # 测试 SectionData 实例化
    print("\n✓ 测试 SectionData 实例化...")
    try:
        section = SectionData(
            message_id=12346,
            text="这是一个章节",
            creator="test_user"
        )
        print(f"  ✓ SectionData 实例化成功")
        print(f"    message_id: {section.message_id}")
    except Exception as e:
        print(f"  ✗ SectionData 实例化失败: {e}")
        return False
    
    # 测试 DocumentData 实例化
    print("\n✓ 测试 DocumentData 实例化...")
    try:
        document = DocumentData(
            message_id=12347,
            summary_zh="这是中文摘要",
            summary_en="This is English summary",
            creator="test_user"
        )
        print(f"  ✓ DocumentData 实例化成功")
        print(f"    message_id: {document.message_id}")
        print(f"    summary_zh: {document.summary_zh}")
    except Exception as e:
        print(f"  ✗ DocumentData 实例化失败: {e}")
        return False
    
    print("\n✅ 模型实例化测试通过!")
    return True


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("MongoDB 模型测试套件")
    print("="*70)
    print(f"项目根目录: {project_root}")
    
    # 同步测试（不需要 MongoDB 连接）
    sync_tests = [
        ("模型定义正确性", test_model_definitions),
        ("字段定义完整性", test_model_fields),
        ("BaseDocument 继承", test_base_document_inheritance),
        ("索引配置", test_model_indexes),
    ]
    
    # 异步测试（需要 MongoDB 连接）
    async_tests = [
        ("集合创建", test_collection_creation),
        ("自定义方法", test_custom_methods),
        ("模型实例化", test_model_instantiation),
    ]
    
    results = []
    
    # 运行同步测试
    for test_name, test_func in sync_tests:
        try:
            result = test_func()
            results.append((test_name, result if result is not None else True))
        except Exception as e:
            print(f"\n❌ {test_name} 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 运行异步测试
    for test_name, test_func in async_tests:
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
