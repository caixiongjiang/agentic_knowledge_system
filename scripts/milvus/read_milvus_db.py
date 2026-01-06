#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : read_milvus_db.py
@Author  : caixiongjiang
@Date    : 2026/1/6 18:58
@Function: 
    函数功能名称
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pymilvus import MilvusClient

# 连接到你的本地 milvus.db 文件
client = MilvusClient("./data/milvus.db")

# 1. 查看有哪些集合
print(client.list_collections())

# 2. 先查看集合信息
try:
    collection_info = client.describe_collection("chunk_store")
    print("\n集合信息:")
    print(collection_info)
except Exception as e:
    print(f"获取集合信息失败: {e}")

# 3. 查询数据 - 排除向量字段
# 注意：向量字段不支持直接查询，需要明确指定其他字段
try:
    res = client.query(
        collection_name="chunk_store",
        filter="",  # 空字符串表示无过滤条件
        output_fields=[
            "id", 
            "user_id", 
            "knowledge_base_id", 
            "knowledge_base_name",
            "type",
            "role",
            "document_id",
            "timestamp",
            "create_time",
            "update_time"
        ],
        limit=5
    )
    
    print(f"\n查询结果 (共 {len(res)} 条):")
    for idx, item in enumerate(res, 1):
        print(f"\n--- 记录 {idx} ---")
        for key, value in item.items():
            print(f"{key}: {value}")
except Exception as e:
    print(f"\n查询失败: {e}")
    print("\n尝试使用更简单的查询...")
    try:
        # 只获取主键
        res = client.query(
            collection_name="chunk_store",
            filter="",
            output_fields=["id"],
            limit=5
        )
        print(f"简单查询成功，找到 {len(res)} 条记录")
        for item in res:
            print(item)
    except Exception as e2:
        print(f"简单查询也失败: {e2}")
        print("\n数据库可能已损坏，建议删除 data/milvus.db 目录并重新创建")