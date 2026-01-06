#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Milvus Schema 导出工具

用途：
    将Schema定义导出为可执行的Python脚本，供DBA审核和手动执行

功能：
    1. 导出单个集合的创建脚本
    2. 导出所有集合的创建脚本
    3. 生成包含注释的可读脚本
    4. 支持JSON格式导出（便于文档和审核）

使用示例：
    # 导出单个集合
    python scripts/export_milvus_schema.py --collection chunk_store
    
    # 导出所有集合
    python scripts/export_milvus_schema.py --all
    
    # 导出为JSON格式
    python scripts/export_milvus_schema.py --collection chunk_store --format json
    
    # 导出到文件
    python scripts/export_milvus_schema.py --all --output schemas/
"""

import sys
import os
import argparse
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.milvus.models import (
    ALL_SCHEMAS,
    SCHEMAS_BY_LAYER,
)


class MilvusSchemaExporter:
    """Milvus Schema 导出器"""
    
    def __init__(self):
        """初始化导出器"""
        self.schema_map = self._build_schema_map()
    
    def _build_schema_map(self) -> Dict[str, Any]:
        """构建Schema映射表"""
        schema_map = {}
        for schema_class in ALL_SCHEMAS:
            schema = schema_class()
            collection_name = schema.get_collection_name()
            schema_map[collection_name] = schema
        return schema_map
    
    def export_to_python(self, schema: Any) -> str:
        """导出为Python脚本
        
        Args:
            schema: Schema实例
            
        Returns:
            Python脚本字符串
        """
        collection_name = schema.get_collection_name()
        description = schema.get_description()
        fields = schema.get_fields()
        index_params = schema.get_index_params()
        
        # 生成脚本头部
        script = f'''#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Milvus Collection 创建脚本

集合名称: {collection_name}
描述: {description}
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

⚠️  执行前请注意：
1. 确认目标环境和数据库
2. 确认集合不存在（避免覆盖）
3. 确认有足够的权限
4. 建议在测试环境先验证

执行方式：
    python this_script.py --host localhost --port 19530
"""

from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType
import argparse


def create_collection_{collection_name.replace("-", "_")}(alias: str = "default"):
    """创建集合: {collection_name}
    
    {description}
    """
    print(f"开始创建集合: {collection_name}")
    
    # 定义字段
    fields = [
'''
        
        # 生成字段定义
        for field in fields:
            field_params = [
                f'name="{field.name}"',
                f'dtype=DataType.{field.dtype.value}',
            ]
            
            if field.is_primary:
                field_params.append('is_primary=True')
            if field.auto_id:
                field_params.append('auto_id=True')
            if field.max_length:
                field_params.append(f'max_length={field.max_length}')
            if field.dim:
                field_params.append(f'dim={field.dim}')
            
            field_line = f'        FieldSchema({", ".join(field_params)})'
            
            # 添加注释
            if field.description:
                comment = f'  # {field.description}'
            else:
                comment = ''
            
            script += f'{field_line},{comment}\n'
        
        script += '    ]\n\n'
        
        # 生成Schema定义
        script += f'''    # 创建Schema
    schema = CollectionSchema(
        fields=fields,
        description="{description}",
        enable_dynamic_field={schema.ENABLE_DYNAMIC_FIELD}
    )
    
    # 创建集合
    collection = Collection(
        name="{collection_name}",
        schema=schema,
        using=alias
    )
    
    print(f"✓ 集合创建成功: {collection_name}")
    
    # 创建索引
    print("开始创建索引...")
    
'''
        
        # 生成索引创建代码
        vector_fields = [f for f in fields if f.dtype.value in ["FLOAT_VECTOR", "BINARY_VECTOR"]]
        
        if vector_fields:
            script += f'''    index_params = {{
        "metric_type": "{index_params['metric_type']}",
        "index_type": "{index_params['index_type']}",
        "params": {index_params['params']}
    }}
    
'''
            for field in vector_fields:
                script += f'''    collection.create_index(
        field_name="{field.name}",
        index_params=index_params
    )
    print(f"✓ 已为字段 '{field.name}' 创建索引")
    
'''
        
        script += f'''    # 加载集合
    collection.load()
    print(f"✓ 集合已加载: {collection_name}")
    
    return collection


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="创建 Milvus 集合")
    parser.add_argument("--host", default="localhost", help="Milvus 主机地址")
    parser.add_argument("--port", type=int, default=19530, help="Milvus 端口")
    parser.add_argument("--alias", default="default", help="连接别名")
    
    args = parser.parse_args()
    
    # 连接到 Milvus
    print(f"连接到 Milvus: {{args.host}}:{{args.port}}")
    connections.connect(
        alias=args.alias,
        host=args.host,
        port=args.port
    )
    
    # 创建集合
    try:
        collection = create_collection_{collection_name.replace("-", "_")}(args.alias)
        print("\\n✅ 所有操作完成！")
        
        # 显示集合信息
        print(f"\\n集合信息:")
        print(f"  名称: {{collection.name}}")
        print(f"  描述: {{collection.description}}")
        print(f"  字段数: {{len(collection.schema.fields)}}")
        print(f"  记录数: {{collection.num_entities}}")
        
    except Exception as e:
        print(f"\\n❌ 创建失败: {{e}}")
        raise
    finally:
        connections.disconnect(args.alias)


if __name__ == "__main__":
    main()
'''
        
        return script
    
    def export_to_json(self, schema: Any) -> str:
        """导出为JSON格式
        
        Args:
            schema: Schema实例
            
        Returns:
            JSON字符串
        """
        schema_dict = schema.get_schema_dict()
        
        # 添加元数据
        schema_dict["export_time"] = datetime.now().isoformat()
        schema_dict["export_tool"] = "export_milvus_schema.py"
        
        return json.dumps(schema_dict, ensure_ascii=False, indent=2)
    
    def export_collection(
        self, 
        collection_name: str,
        output_dir: str = None,
        format: str = "python"
    ) -> str:
        """导出单个集合
        
        Args:
            collection_name: 集合名称
            output_dir: 输出目录（None表示输出到stdout）
            format: 输出格式 ("python" 或 "json")
            
        Returns:
            导出的脚本内容
        """
        if collection_name not in self.schema_map:
            raise ValueError(
                f"集合 '{collection_name}' 不存在。\n"
                f"可用的集合: {', '.join(self.schema_map.keys())}"
            )
        
        schema = self.schema_map[collection_name]
        
        # 根据格式导出
        if format == "python":
            content = self.export_to_python(schema)
            ext = ".py"
        elif format == "json":
            content = self.export_to_json(schema)
            ext = ".json"
        else:
            raise ValueError(f"不支持的格式: {format}")
        
        # 输出到文件或stdout
        if output_dir:
            output_path = Path(output_dir) / f"{collection_name}{ext}"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            print(f"✓ 已导出: {output_path}")
        else:
            print(content)
        
        return content
    
    def export_all(
        self,
        output_dir: str = None,
        format: str = "python"
    ):
        """导出所有集合
        
        Args:
            output_dir: 输出目录
            format: 输出格式
        """
        print(f"开始导出所有集合 (格式: {format})...")
        print(f"总共 {len(self.schema_map)} 个集合\n")
        
        for i, collection_name in enumerate(self.schema_map.keys(), 1):
            print(f"[{i}/{len(self.schema_map)}] 导出: {collection_name}")
            self.export_collection(collection_name, output_dir, format)
        
        print(f"\n✅ 所有集合导出完成！")
    
    def list_collections(self):
        """列出所有可用的集合"""
        print("可用的集合：\n")
        
        for layer, schemas in SCHEMAS_BY_LAYER.items():
            print(f"【{layer.upper()} 层】")
            for schema_class in schemas:
                schema = schema_class()
                print(f"  - {schema.get_collection_name()}")
                print(f"    {schema.get_description()}")
            print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Milvus Schema 导出工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  # 列出所有集合
  python scripts/export_milvus_schema.py --list
  
  # 导出单个集合（输出到stdout）
  python scripts/export_milvus_schema.py --collection chunk_store
  
  # 导出单个集合到文件
  python scripts/export_milvus_schema.py --collection chunk_store --output schemas/
  
  # 导出所有集合
  python scripts/export_milvus_schema.py --all --output schemas/
  
  # 导出为JSON格式
  python scripts/export_milvus_schema.py --collection chunk_store --format json
        """
    )
    
    parser.add_argument(
        "--collection",
        help="要导出的集合名称"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="导出所有集合"
    )
    parser.add_argument(
        "--output",
        help="输出目录（不指定则输出到stdout）"
    )
    parser.add_argument(
        "--format",
        choices=["python", "json"],
        default="python",
        help="导出格式 (默认: python)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用的集合"
    )
    
    args = parser.parse_args()
    
    # 创建导出器
    exporter = MilvusSchemaExporter()
    
    # 执行操作
    try:
        if args.list:
            exporter.list_collections()
        elif args.all:
            exporter.export_all(args.output, args.format)
        elif args.collection:
            exporter.export_collection(args.collection, args.output, args.format)
        else:
            parser.print_help()
            print("\n❌ 错误：必须指定 --collection、--all 或 --list")
            sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
