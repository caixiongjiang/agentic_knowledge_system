#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : v0_8_0_add_chat_session_folder_scope.py
@Author  : caixiongjiang
@Date    : 2026/05/22
@Function:
    v0.8.0 升级脚本：为 ``chat_session`` 表新增两列以支持文件夹问答（folder scope）。

    - ``folder_id VARCHAR(64) NULL``           : session 绑定的文件夹 ID
    - ``include_subfolders TINYINT(1) DEFAULT 1``: folder 模式是否含子文件夹

    幂等：检测列存在再决定是否 ALTER；可重复执行。

    使用：
        python scripts/mysql/migrations/v0_8_0_add_chat_session_folder_scope.py

    回滚（可选，需手动确认）：
        python scripts/mysql/migrations/v0_8_0_add_chat_session_folder_scope.py --rollback
@Modify History:
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import argparse
import sys
from pathlib import Path
from typing import List

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from sqlalchemy import text

_TARGET_TABLE = "chat_session"

# 每条 (column_name, ALTER 子句, 回滚 ALTER 子句)
_COLUMNS: List[tuple] = [
    (
        "folder_id",
        (
            "ALTER TABLE chat_session "
            "ADD COLUMN folder_id VARCHAR(64) NULL "
            "COMMENT '会话绑定的文件夹 ID（NULL=KB scope；非 NULL=folder scope）'"
        ),
        "ALTER TABLE chat_session DROP COLUMN folder_id",
    ),
    (
        "include_subfolders",
        (
            "ALTER TABLE chat_session "
            "ADD COLUMN include_subfolders TINYINT(1) NOT NULL DEFAULT 1 "
            "COMMENT 'folder scope 下是否含子文件夹，默认 1'"
        ),
        "ALTER TABLE chat_session DROP COLUMN include_subfolders",
    ),
]


def _column_exists(session, column: str) -> bool:
    """检查 chat_session 表是否已存在指定列（兼容 MySQL information_schema）。"""
    sql = text(
        "SELECT COUNT(*) "
        "FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() "
        "  AND TABLE_NAME = :tbl "
        "  AND COLUMN_NAME = :col"
    )
    return bool(
        session.execute(sql, {"tbl": _TARGET_TABLE, "col": column}).scalar()
    )


def upgrade() -> None:
    """正向升级：缺哪列加哪列。"""
    from src.db.mysql.connection.factory import get_mysql_manager

    manager = get_mysql_manager("mysql")
    added: List[str] = []
    skipped: List[str] = []

    with manager.get_session() as session:
        for column, alter_sql, _rollback_sql in _COLUMNS:
            if _column_exists(session, column):
                skipped.append(column)
                logger.info(f"列 {column} 已存在，跳过")
                continue
            session.execute(text(alter_sql))
            session.commit()
            added.append(column)
            logger.info(f"列 {column} 已添加")

    logger.info(
        f"upgrade 完成：新增 {len(added)} 列={added}；"
        f"已存在 {len(skipped)} 列={skipped}"
    )


def rollback() -> None:
    """回滚：把两列删掉。仅人工确认后使用，不在生产链路自动调用。"""
    from src.db.mysql.connection.factory import get_mysql_manager

    manager = get_mysql_manager("mysql")
    dropped: List[str] = []
    skipped: List[str] = []

    with manager.get_session() as session:
        for column, _alter_sql, rollback_sql in _COLUMNS:
            if not _column_exists(session, column):
                skipped.append(column)
                logger.info(f"列 {column} 不存在，跳过回滚")
                continue
            session.execute(text(rollback_sql))
            session.commit()
            dropped.append(column)
            logger.info(f"列 {column} 已删除")

    logger.info(
        f"rollback 完成：删除 {len(dropped)} 列={dropped}；"
        f"未存在 {len(skipped)} 列={skipped}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="v0.8.0 chat_session folder scope 升级"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="执行回滚（删除已添加的列）",
    )
    args = parser.parse_args()

    try:
        if args.rollback:
            rollback()
        else:
            upgrade()
        return 0
    except Exception as e:  # noqa: BLE001
        logger.exception(f"执行失败：{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
