#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : cleanup_deleted_records.py
@Author  : caixiongjiang
@Date    : 2026/01/07
@Function: 
    清理所有软删除的记录（deleted = 1）
    异步清理 MongoDB 中的软删除数据
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import asyncio
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


async def preview_deleted_records() -> Dict[str, int]:
    """预览即将删除的记录数"""
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    
    manager = await get_mongodb_manager()
    database = await manager.get_database()
    
    # MongoDB 集合列表
    collections = [
        "chunk_data",
        "section_data",
        "document_data",
    ]
    
    stats = {}
    
    for collection_name in collections:
        collection = database[collection_name]
        count = await collection.count_documents({"deleted": 1})
        stats[collection_name] = count
    
    return stats


async def cleanup_deleted_records(confirm: bool = False) -> Dict[str, Any]:
    """清理所有软删除的记录
    
    Args:
        confirm: 是否确认删除，必须显式设置为 True
    
    Returns:
        清理统计信息
    """
    if not confirm:
        print("⚠️  此操作将物理删除所有标记为 deleted=1 的记录")
        print("   请使用 confirm=True 参数确认执行")
        return {"error": "需要确认"}
    
    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    
    manager = await get_mongodb_manager()
    database = await manager.get_database()
    
    # MongoDB 集合列表
    collections = [
        "chunk_data",       # Chunk 数据
        "section_data",     # Section 数据
        "document_data",    # Document 数据
    ]
    
    print("\n" + "="*70)
    print("开始清理软删除记录")
    print("="*70)
    
    deleted_stats = {}
    total_deleted = 0
    
    for collection_name in collections:
        collection = database[collection_name]
        
        # 统计要删除的记录数
        count = await collection.count_documents({"deleted": 1})
        
        if count > 0:
            # 执行删除
            result = await collection.delete_many({"deleted": 1})
            
            deleted_count = result.deleted_count
            deleted_stats[collection_name] = deleted_count
            total_deleted += deleted_count
            
            print(f"✓ {collection_name}: 删除 {deleted_count} 条记录")
        else:
            print(f"  {collection_name}: 无需清理")
    
    print("\n" + "="*70)
    print(f"清理完成，共删除 {total_deleted} 条记录")
    print("="*70)
    
    return {
        "total_deleted": total_deleted,
        "details": deleted_stats
    }


async def interactive_cleanup():
    """交互式清理流程"""
    print("\n" + "="*70)
    print("MongoDB 软删除记录清理工具")
    print("="*70)
    
    # 步骤1：预览
    print("\n📊 步骤1: 预览即将删除的记录...")
    stats = await preview_deleted_records()
    
    total = sum(stats.values())
    
    if total == 0:
        print("\n✓ 数据库中没有需要清理的记录（deleted=1）")
        return
    
    print(f"\n即将删除的记录统计：")
    print("-" * 50)
    for collection, count in stats.items():
        if count > 0:
            print(f"  {collection:<30} {count:>5} 条")
    print("-" * 50)
    print(f"  总计：{total:>36} 条")
    
    # 步骤2：确认
    print("\n⚠️  警告：此操作将物理删除上述记录，不可恢复！")
    print("   建议在生产环境执行前先备份数据库")
    
    response = input("\n是否继续？(yes/no): ").strip().lower()
    
    if response not in ["yes", "y"]:
        print("\n✗ 操作已取消")
        return
    
    # 步骤3：执行清理
    print("\n🧹 步骤2: 执行清理...")
    result = await cleanup_deleted_records(confirm=True)
    
    if "error" not in result:
        print(f"\n🎉 清理成功！共删除 {result['total_deleted']} 条记录")
    else:
        print(f"\n✗ 清理失败: {result['error']}")


async def main_async():
    """异步主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="清理MongoDB数据库中所有软删除的记录（deleted=1）"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="仅预览要删除的记录数，不执行删除"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="直接执行清理，跳过交互式确认"
    )
    
    args = parser.parse_args()
    
    if args.preview:
        # 仅预览
        print("\n📊 预览模式：查看要删除的记录数")
        print("="*70)
        stats = await preview_deleted_records()
        
        total = sum(stats.values())
        
        if total == 0:
            print("\n✓ 数据库中没有需要清理的记录（deleted=1）")
            return
        
        print(f"\n软删除记录统计：")
        print("-" * 50)
        for collection, count in stats.items():
            if count > 0:
                print(f"  {collection:<30} {count:>5} 条")
        print("-" * 50)
        print(f"  总计：{total:>36} 条")
        
        print("\n提示：使用 --confirm 参数可直接执行清理")
        
    elif args.confirm:
        # 直接执行
        print("\n⚠️  确认模式：将直接执行清理")
        result = await cleanup_deleted_records(confirm=True)
        
        if "error" not in result:
            print(f"\n🎉 清理完成！")
        
    else:
        # 交互式模式
        await interactive_cleanup()


def main():
    """主函数入口"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\n⚠️  操作被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
