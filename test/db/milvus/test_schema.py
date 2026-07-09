#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_schema.py
@Author  : caixiongjiang
@Date    : 2026/1/6 11:21
@Function: 
    测试Milvus Schema定义和自动创建表的能力
    - 测试Schema定义正确性
    - 测试字段定义完整性
    - 测试索引配置
    - 测试自动创建集合功能（Lite和Server两种模式）
    - 不依赖外部配置文件，手动设置测试配置
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import os
from pathlib import Path

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


def test_schema_definitions():
    """测试1: Schema定义正确性"""
    print("\n" + "="*70)
    print("测试1: Schema定义正确性")
    print("="*70)
    
    from src.db.milvus.models import (
        ChunkSchema,
        SectionSchema,
        EnhancedChunkSchema,
        AtomicQASchema,
        FileSummarySchema,
        SectionSummarySchema,
        SPOSchema,
        TagSchema,
        ALL_SCHEMAS,
        SCHEMAS_BY_LAYER
    )
    
    # 测试所有Schema都能正常实例化
    print("\n✓ 测试Schema实例化...")
    schemas = {
        "ChunkSchema": ChunkSchema(),
        "SectionSchema": SectionSchema(),
        "EnhancedChunkSchema": EnhancedChunkSchema(),
        "AtomicQASchema": AtomicQASchema(),
        "FileSummarySchema": FileSummarySchema(),
        "SectionSummarySchema": SectionSummarySchema(),
        "SPOSchema": SPOSchema(),
        "TagSchema": TagSchema(),
    }
    
    for name, schema in schemas.items():
        print(f"  ✓ {name}: {schema.get_collection_name()}")
    
    # 验证集合名称唯一性
    print("\n✓ 验证集合名称唯一性...")
    collection_names = [s.get_collection_name() for s in schemas.values()]
    if len(collection_names) == len(set(collection_names)):
        print(f"  ✓ 所有集合名称唯一 (共{len(collection_names)}个)")
    else:
        print(f"  ✗ 发现重复的集合名称!")
        return False
    
    # 验证ALL_SCHEMAS列表
    print(f"\n✓ ALL_SCHEMAS包含 {len(ALL_SCHEMAS)} 个Schema")
    
    # 验证分层结构
    print("\n✓ 验证Schema分层结构:")
    for layer, layer_schemas in SCHEMAS_BY_LAYER.items():
        print(f"  - {layer}: {len(layer_schemas)} 个Schema")
    
    print("\n✅ Schema定义正确性测试通过!")
    return True


def test_schema_fields():
    """测试2: 字段定义完整性"""
    print("\n" + "="*70)
    print("测试2: 字段定义完整性")
    print("="*70)
    
    from src.db.milvus.models import ChunkSchema, SPOSchema
    
    # 测试ChunkSchema的字段
    print("\n✓ 测试 ChunkSchema 字段定义...")
    chunk_schema = ChunkSchema()
    fields = chunk_schema.get_fields()
    
    print(f"  字段数量: {len(fields)}")
    print(f"  集合名称: {chunk_schema.get_collection_name()}")
    print(f"  向量维度: {chunk_schema.VECTOR_DIM}")
    print(f"  启用动态字段: {chunk_schema.ENABLE_DYNAMIC_FIELD}")
    
    # 检查必需字段
    required_fields = ["id", "vector", "user_id", "knowledge_base_id", "agent_ids"]
    field_names = [f.name for f in fields]
    
    print(f"\n  检查必需字段:")
    for field_name in required_fields:
        if field_name in field_names:
            print(f"    ✓ {field_name}")
        else:
            print(f"    ✗ {field_name} (缺失!)")
            return False
    
    # 测试SPOSchema的字段（使用自增ID）
    print("\n✓ 测试 SPOSchema 字段定义 (自增ID)...")
    spo_schema = SPOSchema()
    spo_fields = spo_schema.get_fields()
    
    # 找到主键字段
    primary_field = None
    for field in spo_fields:
        if field.is_primary:
            primary_field = field
            break
    
    if primary_field:
        print(f"  主键字段: {primary_field.name}")
        print(f"  主键类型: {primary_field.dtype.value}")
        print(f"  自动生成ID: {primary_field.auto_id}")
        
        if primary_field.auto_id:
            print(f"  ✓ SPO表正确使用自增ID")
        else:
            print(f"  ✗ SPO表应该使用自增ID")
            return False
    
    print("\n✅ 字段定义完整性测试通过!")
    return True


def test_index_configuration():
    """测试3: 索引配置"""
    print("\n" + "="*70)
    print("测试3: 索引配置")
    print("="*70)
    
    from src.db.milvus.models import ChunkSchema, EnhancedChunkSchema
    
    # 测试ChunkSchema的索引配置
    print("\n✓ 测试 ChunkSchema 索引配置...")
    chunk_schema = ChunkSchema()
    index_params = chunk_schema.get_index_params()
    
    print(f"  索引类型: {index_params.get('index_type')}")
    print(f"  距离度量: {index_params.get('metric_type')}")
    print(f"  索引参数: {index_params.get('params')}")
    
    # 验证索引配置完整性
    required_keys = ['index_type', 'metric_type', 'params']
    for key in required_keys:
        if key in index_params:
            print(f"    ✓ {key}")
        else:
            print(f"    ✗ {key} (缺失!)")
            return False
    
    print("\n✅ 索引配置测试通过!")
    return True


def test_auto_create_collection_lite():
    """测试4: 自动创建集合功能 - Lite模式"""
    print("\n" + "="*70)
    print("测试4: 自动创建集合功能 - Lite模式")
    print("="*70)
    
    temp_dir = None
    try:
        # 设置Lite模式配置
        temp_dir = TestConfig.setup_lite_config()
        print(f"\n✓ 使用Lite数据库: {TestConfig.LITE_CONFIG['lite_db_path']}")
        
        from src.db.milvus import get_milvus_manager, reset_manager
        from src.db.milvus.repositories import ChunkRepository
        from src.db.milvus.models import ChunkSchema
        
        # 重置管理器
        reset_manager()
        
        # 强制使用Lite模式
        manager = get_milvus_manager(mode="lite")
        print(f"\n✓ 使用管理器: {type(manager).__name__}")
        
        # 检查连接
        is_connected = manager.check_connection()
        print(f"  连接状态: {'已连接' if is_connected else '未连接'}")
        
        if not is_connected:
            print("\n⚠️  Lite模式连接失败")
            return False
        
        # 获取Schema信息
        schema = ChunkSchema()
        collection_name = schema.get_collection_name()
        
        print(f"\n✓ 目标集合: {collection_name}")
        
        # 创建Repository（会自动创建集合）
        print(f"\n✓ 创建 ChunkRepository (自动创建集合)...")
        repo = ChunkRepository(manager=manager)
        print(f"  ✓ Repository 创建成功")
        print(f"  ✓ 集合名称: {repo.collection_name}")
        
        # 验证集合已创建
        collections = manager.list_collections()
        if collection_name in collections:
            print(f"  ✓ 集合 '{collection_name}' 已成功创建")
            
            # 获取集合记录数
            count = repo.count()
            print(f"  ✓ 集合记录数: {count}")
        else:
            print(f"  ✗ 集合 '{collection_name}' 创建失败")
            return False
        
        print("\n✅ Lite模式自动创建集合功能测试通过!")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理
        try:
            from src.db.milvus import reset_manager
            reset_manager()
        except:
            pass
        
        TestConfig.cleanup_config()
        
        # 注意：数据库文件保留在 data/milvus.db 供后续查看
        # 如需清理，可手动删除 data/milvus.db 文件


def test_auto_create_collection_server():
    """测试5: 自动创建集合功能 - Server模式"""
    print("\n" + "="*70)
    print("测试5: 自动创建集合功能 - Server模式")
    print("="*70)
    
    try:
        # 设置Server模式配置
        TestConfig.setup_server_config()
        print(f"\n✓ 使用Server配置: {TestConfig.SERVER_CONFIG['host']}:{TestConfig.SERVER_CONFIG['port']}")
        
        from src.db.milvus import get_milvus_manager, reset_manager
        from src.db.milvus.repositories import ChunkRepository
        from src.db.milvus.models import ChunkSchema
        
        # 重置管理器
        reset_manager()
        
        # 强制使用Server模式
        manager = get_milvus_manager(mode="server")
        print(f"\n✓ 使用管理器: {type(manager).__name__}")
        
        # 检查连接
        is_connected = manager.check_connection()
        print(f"  连接状态: {'已连接' if is_connected else '未连接'}")
        
        if not is_connected:
            print("\n⚠️  无法连接到Milvus Server，跳过Server模式测试")
            print("   提示: 确保Milvus服务正在运行并可访问")
            return True  # 返回True以不影响整体测试结果
        
        # 获取Schema信息
        schema = ChunkSchema()
        collection_name = schema.get_collection_name()
        
        print(f"\n✓ 目标集合: {collection_name}")
        
        # 检查集合是否已存在
        existing_collections = manager.list_collections()
        print(f"  现有集合数量: {len(existing_collections)}")
        
        # 创建Repository（会自动创建集合）
        print(f"\n✓ 创建 ChunkRepository (自动创建集合)...")
        repo = ChunkRepository(manager=manager)
        print(f"  ✓ Repository 创建成功")
        print(f"  ✓ 集合名称: {repo.collection_name}")
        
        # 验证集合已创建
        updated_collections = manager.list_collections()
        if collection_name in updated_collections:
            print(f"  ✓ 集合 '{collection_name}' 已成功创建/加载")
            
            # 获取集合记录数
            count = repo.count()
            print(f"  ✓ 集合记录数: {count}")
        else:
            print(f"  ✗ 集合 '{collection_name}' 创建失败")
            return False
        
        print("\n✅ Server模式自动创建集合功能测试通过!")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理
        try:
            from src.db.milvus import reset_manager
            reset_manager()
        except:
            pass
        
        TestConfig.cleanup_config()


def test_schema_export():
    """测试6: Schema导出功能"""
    print("\n" + "="*70)
    print("测试6: Schema导出功能")
    print("="*70)
    
    from src.db.milvus.models import ChunkSchema
    
    print("\n✓ 测试Schema导出为字典...")
    schema = ChunkSchema()
    schema_dict = schema.get_schema_dict()
    
    # 验证导出的字典结构
    required_keys = ['collection_name', 'description', 'fields', 'index_params', 'enable_dynamic_field']
    
    print(f"  导出的字典包含以下键:")
    for key in required_keys:
        if key in schema_dict:
            print(f"    ✓ {key}")
        else:
            print(f"    ✗ {key} (缺失!)")
            return False
    
    # 显示部分信息
    print(f"\n  集合名称: {schema_dict['collection_name']}")
    print(f"  字段数量: {len(schema_dict['fields'])}")
    print(f"  启用动态字段: {schema_dict['enable_dynamic_field']}")
    
    print("\n✅ Schema导出功能测试通过!")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("Milvus Schema 测试套件")
    print("="*70)
    print(f"项目根目录: {project_root}")
    print(f"测试模式: 独立配置（不依赖外部配置文件）")
    
    tests = [
        ("Schema定义正确性", test_schema_definitions),
        ("字段定义完整性", test_schema_fields),
        ("索引配置", test_index_configuration),
        ("Schema导出功能", test_schema_export),
        ("自动创建集合 - Lite模式", test_auto_create_collection_lite),
        ("自动创建集合 - Server模式", test_auto_create_collection_server),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
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
