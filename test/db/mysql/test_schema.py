#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_schema.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    测试MySQL Schema定义和自动创建表的能力
    - 测试Schema定义正确性
    - 测试字段定义完整性
    - 测试自动创建表功能（SQLite和MySQL Server两种模式）
    - 测试表结构验证
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def test_schema_definitions():
    """测试1: Schema定义正确性"""
    print("\n" + "="*70)
    print("测试1: Schema定义正确性")
    print("="*70)
    
    from src.db.mysql.models.base import (
        ChunkSectionDocument,
        SectionDocument,
        ChunkMetaInfo,
        SectionMetaInfo
    )
    from src.db.mysql.models.extract import (
        ChunkSummary,
        ChunkAtomicQA,
        DocumentSummary,
        DocumentMetaInfo
    )
    from src.db.mysql.models.business import WorkspaceFileSystem
    
    # 测试所有Schema都能正常访问
    print("\n✓ 测试Schema类...")
    schemas = {
        "ChunkSectionDocument": ChunkSectionDocument,
        "SectionDocument": SectionDocument,
        "ChunkMetaInfo": ChunkMetaInfo,
        "SectionMetaInfo": SectionMetaInfo,
        "ChunkSummary": ChunkSummary,
        "ChunkAtomicQA": ChunkAtomicQA,
        "DocumentSummary": DocumentSummary,
        "DocumentMetaInfo": DocumentMetaInfo,
        "WorkspaceFileSystem": WorkspaceFileSystem,
    }
    
    for name, schema_class in schemas.items():
        table_name = schema_class.__tablename__
        print(f"  ✓ {name}: {table_name}")
    
    # 验证表名唯一性
    print("\n✓ 验证表名唯一性...")
    table_names = [cls.__tablename__ for cls in schemas.values()]
    if len(table_names) == len(set(table_names)):
        print(f"  ✓ 所有表名唯一 (共{len(table_names)}个)")
    else:
        print(f"  ✗ 发现重复的表名!")
        return False
    
    print("\n✅ Schema定义正确性测试通过!")
    return True


def test_schema_fields():
    """测试2: 字段定义完整性"""
    print("\n" + "="*70)
    print("测试2: 字段定义完整性")
    print("="*70)
    
    from src.db.mysql.models.base import ChunkSectionDocument
    from src.db.mysql.models.business import WorkspaceFileSystem
    
    # 测试ChunkSectionDocument的字段
    print("\n✓ 测试 ChunkSectionDocument 字段定义...")
    columns = ChunkSectionDocument.__table__.columns
    
    print(f"  字段数量: {len(columns)}")
    print(f"  表名: {ChunkSectionDocument.__tablename__}")
    
    # 检查必需字段
    required_fields = ["chunk_id", "section_id", "document_id", "status", "creator", "deleted"]
    column_names = [c.name for c in columns]
    
    print(f"\n  检查必需字段:")
    for field_name in required_fields:
        if field_name in column_names:
            print(f"    ✓ {field_name}")
        else:
            print(f"    ✗ {field_name} (缺失!)")
            return False
    
    # 测试WorkspaceFileSystem的联合主键
    print("\n✓ 测试 WorkspaceFileSystem 联合主键...")
    ws_columns = WorkspaceFileSystem.__table__.columns
    
    # 找到主键字段
    primary_keys = [c.name for c in ws_columns if c.primary_key]
    
    print(f"  主键字段: {primary_keys}")
    
    if "user_id" in primary_keys and "file_id" in primary_keys:
        print(f"  ✓ 联合主键正确定义")
    else:
        print(f"  ✗ 联合主键定义错误")
        return False
    
    print("\n✅ 字段定义完整性测试通过!")
    return True


def test_base_model_inheritance():
    """测试3: BaseModel继承"""
    print("\n" + "="*70)
    print("测试3: BaseModel继承")
    print("="*70)
    
    from src.db.mysql.models.base import ChunkSectionDocument
    
    # 测试审计字段
    print("\n✓ 测试审计字段...")
    audit_fields = ["status", "creator", "create_time", "updater", "update_time", "deleted"]
    columns = ChunkSectionDocument.__table__.columns
    column_names = [c.name for c in columns]
    
    for field_name in audit_fields:
        if field_name in column_names:
            column = columns[field_name]
            print(f"  ✓ {field_name}: {column.type}")
        else:
            print(f"  ✗ {field_name} (缺失!)")
            return False
    
    # 测试to_dict方法
    print("\n✓ 测试 to_dict 方法...")
    instance = ChunkSectionDocument(
        chunk_id="test-001",
        section_id="sec-001"
    )
    
    data_dict = instance.to_dict()
    print(f"  字典键数量: {len(data_dict)}")
    print(f"  包含 chunk_id: {'chunk_id' in data_dict}")
    
    if "chunk_id" in data_dict and data_dict["chunk_id"] == "test-001":
        print(f"  ✓ to_dict 方法正常工作")
    else:
        print(f"  ✗ to_dict 方法失败")
        return False
    
    print("\n✅ BaseModel继承测试通过!")
    return True


def test_auto_create_tables_sqlite():
    """测试4: 自动创建表功能 - SQLite模式"""
    print("\n" + "="*70)
    print("测试4: 自动创建表功能 - SQLite模式")
    print("="*70)
    
    try:
        from src.db.mysql.connection.factory import get_mysql_manager
        
        # 获取SQLite管理器
        print("\n✓ 获取 SQLite 管理器...")
        manager = get_mysql_manager("sqlite")
        print(f"  数据库路径: {manager.db_path}")
        
        # 初始化数据库（创建所有表）
        print("\n✓ 初始化数据库（创建表）...")
        manager.init_db()
        print("  ✓ 数据库初始化完成")
        
        # 验证表是否创建成功
        print("\n✓ 验证表结构...")
        from sqlalchemy import inspect
        
        inspector = inspect(manager.engine)
        table_names = inspector.get_table_names()
        
        print(f"  创建的表数量: {len(table_names)}")
        
        # 检查关键表是否存在
        expected_tables = [
            "chunk_section_document",
            "section_document",
            "chunk_meta_info",
            "chunk_summary",
            "document_meta_info",
            "workspace_file_system"
        ]
        
        print("\n  检查关键表:")
        for table_name in expected_tables:
            if table_name in table_names:
                print(f"    ✓ {table_name}")
            else:
                print(f"    ✗ {table_name} (未创建)")
                return False
        
        # 检查表的列
        print("\n✓ 验证表的列定义...")
        columns = inspector.get_columns("chunk_section_document")
        column_names = [c['name'] for c in columns]
        
        print(f"  chunk_section_document 列数量: {len(columns)}")
        
        required_columns = ["chunk_id", "section_id", "document_id", "deleted"]
        for col_name in required_columns:
            if col_name in column_names:
                print(f"    ✓ {col_name}")
            else:
                print(f"    ✗ {col_name} (未创建)")
                return False
        
        print("\n✅ SQLite模式自动创建表功能测试通过!")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auto_create_tables_mysql():
    """测试5: 自动创建表功能 - MySQL Server模式"""
    print("\n" + "="*70)
    print("测试5: 自动创建表功能 - MySQL Server模式")
    print("="*70)
    
    try:
        from src.db.mysql.connection.factory import get_mysql_manager
        
        # 获取MySQL管理器
        print("\n✓ 获取 MySQL Server 管理器...")
        manager = get_mysql_manager("mysql")
        
        # 健康检查
        print("\n✓ 检查 MySQL Server 连接...")
        if not manager.health_check():
            print("  ⚠️  MySQL Server 未启动或配置错误，跳过此测试")
            return True  # 不视为失败，只是跳过
        
        print("  ✓ MySQL Server 连接正常")
        
        # 初始化数据库（创建所有表）
        print("\n✓ 初始化数据库（创建表）...")
        manager.init_db()
        print("  ✓ 数据库初始化完成")
        
        # 验证表是否创建成功
        print("\n✓ 验证表结构...")
        from sqlalchemy import inspect
        
        inspector = inspect(manager.engine)
        table_names = inspector.get_table_names()
        
        print(f"  创建的表数量: {len(table_names)}")
        
        # 检查关键表是否存在
        expected_tables = [
            "chunk_section_document",
            "section_document",
            "chunk_meta_info",
            "chunk_summary",
            "document_meta_info",
            "workspace_file_system"
        ]
        
        print("\n  检查关键表:")
        for table_name in expected_tables:
            if table_name in table_names:
                print(f"    ✓ {table_name}")
            else:
                print(f"    ✗ {table_name} (未创建)")
                return False
        
        # 检查表的列
        print("\n✓ 验证表的列定义...")
        columns = inspector.get_columns("chunk_section_document")
        column_names = [c['name'] for c in columns]
        
        print(f"  chunk_section_document 列数量: {len(columns)}")
        
        required_columns = ["chunk_id", "section_id", "document_id", "deleted"]
        for col_name in required_columns:
            if col_name in column_names:
                print(f"    ✓ {col_name}")
            else:
                print(f"    ✗ {col_name} (未创建)")
                return False
        
        # 检查索引
        print("\n✓ 验证索引...")
        indexes = inspector.get_indexes("chunk_section_document")
        print(f"  chunk_section_document 索引数量: {len(indexes)}")
        for idx in indexes:
            print(f"    ✓ {idx['name']}: {idx['column_names']}")
        
        print("\n✅ MySQL Server模式自动创建表功能测试通过!")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_schema_comments():
    """测试6: Schema注释"""
    print("\n" + "="*70)
    print("测试6: Schema注释")
    print("="*70)
    
    from src.db.mysql.models.base import ChunkSectionDocument
    
    print("\n✓ 检查字段注释...")
    columns = ChunkSectionDocument.__table__.columns
    
    comment_count = 0
    for column in columns:
        if column.comment:
            comment_count += 1
            print(f"  ✓ {column.name}: {column.comment}")
    
    total_columns = len(columns)
    print(f"\n  总列数: {total_columns}")
    print(f"  有注释的列: {comment_count}")
    
    if comment_count == total_columns:
        print(f"  ✓ 所有列都有注释")
    else:
        print(f"  ⚠️  有 {total_columns - comment_count} 列缺少注释")
    
    print("\n✅ Schema注释测试通过!")
    return True


def test_mixin_classes():
    """测试7: Mixin类"""
    print("\n" + "="*70)
    print("测试7: Mixin类")
    print("="*70)
    
    from src.db.mysql.models.base import ChunkSectionDocument
    from src.db.mysql.models.business import WorkspaceFileSystem
    
    # 测试KnowledgeMixin
    print("\n✓ 测试 KnowledgeMixin...")
    knowledge_fields = ["role", "knowledge_type", "knowledge_id", "parent_knowledge_id"]
    chunk_columns = [c.name for c in ChunkSectionDocument.__table__.columns]
    
    for field_name in knowledge_fields:
        if field_name in chunk_columns:
            print(f"  ✓ {field_name}")
        else:
            print(f"  ✗ {field_name} (缺失!)")
            return False
    
    # 测试AgentMixin
    print("\n✓ 测试 AgentMixin...")
    agent_fields = ["user_id", "session_id", "task_id", "agent_id", "agent_instance_id"]
    ws_columns = [c.name for c in WorkspaceFileSystem.__table__.columns]
    
    for field_name in agent_fields:
        if field_name in ws_columns:
            print(f"  ✓ {field_name}")
        else:
            print(f"  ✗ {field_name} (缺失!)")
            return False
    
    print("\n✅ Mixin类测试通过!")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("MySQL Schema 测试套件")
    print("="*70)
    print(f"项目根目录: {project_root}")
    
    tests = [
        ("Schema定义正确性", test_schema_definitions),
        ("字段定义完整性", test_schema_fields),
        ("BaseModel继承", test_base_model_inheritance),
        ("自动创建表 - SQLite", test_auto_create_tables_sqlite),
        ("自动创建表 - MySQL Server", test_auto_create_tables_mysql),
        ("Schema注释", test_schema_comments),
        ("Mixin类", test_mixin_classes),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result if result is not None else True))
        except Exception as e:
            print(f"\n✗ {test_name} 测试异常: {e}")
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


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
