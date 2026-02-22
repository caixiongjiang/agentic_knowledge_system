#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : cleanup_deleted_records.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    清理所有软删除的记录（deleted = 1）
    执行 cleanup_deleted_records.sql 脚本
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def preview_deleted_records() -> Dict[str, int]:
    """预览即将删除的记录数"""
    from src.db.mysql.connection.factory import get_mysql_manager
    from sqlalchemy import text
    
    manager = get_mysql_manager("mysql")
    
    tables = [
        "chunk_section_document",
        "section_document",
        "chunk_meta_info",
        "section_meta_info",
        "chunk_summary",
        "chunk_atomic_qa",
        "document_summary",
        "workspace_file_system",
    ]
    
    stats = {}
    
    with manager.get_session() as session:
        for table in tables:
            sql = text(f"SELECT COUNT(*) FROM {table} WHERE deleted = 1")
            result = session.execute(sql)
            count = result.scalar()
            stats[table] = count
    
    return stats


def cleanup_deleted_records(confirm: bool = False) -> Dict[str, Any]:
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
    
    from src.db.mysql.connection.factory import get_mysql_manager
    from sqlalchemy import text
    
    manager = get_mysql_manager("mysql")
    
    # 表定义
    tables = [
        # Base Layer
        "chunk_section_document",
        "section_document",
        "chunk_meta_info",
        "section_meta_info",
        # Extract Layer
        "chunk_summary",
        "chunk_atomic_qa",
        "document_summary",
        # Business Layer
        "workspace_file_system",
    ]
    
    print("\n" + "="*70)
    print("开始清理软删除记录")
    print("="*70)
    
    deleted_stats = {}
    total_deleted = 0
    
    with manager.get_session() as session:
        for table in tables:
            # 统计要删除的记录数
            count_sql = text(f"SELECT COUNT(*) FROM {table} WHERE deleted = 1")
            count = session.execute(count_sql).scalar()
            
            if count > 0:
                # 执行删除
                delete_sql = text(f"DELETE FROM {table} WHERE deleted = 1")
                result = session.execute(delete_sql)
                session.commit()
                
                deleted_count = result.rowcount
                deleted_stats[table] = deleted_count
                total_deleted += deleted_count
                
                print(f"✓ {table}: 删除 {deleted_count} 条记录")
            else:
                print(f"  {table}: 无需清理")
    
    print("\n" + "="*70)
    print(f"清理完成，共删除 {total_deleted} 条记录")
    print("="*70)
    
    return {
        "total_deleted": total_deleted,
        "details": deleted_stats
    }


def interactive_cleanup():
    """交互式清理流程"""
    print("\n" + "="*70)
    print("MySQL 软删除记录清理工具")
    print("="*70)
    
    # 步骤1：预览
    print("\n📊 步骤1: 预览即将删除的记录...")
    stats = preview_deleted_records()
    
    total = sum(stats.values())
    
    if total == 0:
        print("\n✓ 数据库中没有需要清理的记录（deleted=1）")
        return
    
    print(f"\n即将删除的记录统计：")
    print("-" * 50)
    for table, count in stats.items():
        if count > 0:
            print(f"  {table:<30} {count:>5} 条")
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
    result = cleanup_deleted_records(confirm=True)
    
    if "error" not in result:
        print(f"\n🎉 清理成功！共删除 {result['total_deleted']} 条记录")
    else:
        print(f"\n✗ 清理失败: {result['error']}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="清理MySQL数据库中所有软删除的记录（deleted=1）"
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
        stats = preview_deleted_records()
        
        total = sum(stats.values())
        
        if total == 0:
            print("\n✓ 数据库中没有需要清理的记录（deleted=1）")
            return
        
        print(f"\n软删除记录统计：")
        print("-" * 50)
        for table, count in stats.items():
            if count > 0:
                print(f"  {table:<30} {count:>5} 条")
        print("-" * 50)
        print(f"  总计：{total:>36} 条")
        
        print("\n提示：使用 --confirm 参数可直接执行清理")
        
    elif args.confirm:
        # 直接执行
        print("\n⚠️  确认模式：将直接执行清理")
        result = cleanup_deleted_records(confirm=True)
        
        if "error" not in result:
            print(f"\n🎉 清理完成！")
        
    else:
        # 交互式模式
        interactive_cleanup()


if __name__ == "__main__":
    main()
