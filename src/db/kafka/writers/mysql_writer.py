#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
MySQLWriter

监听: db_write:meta:start
功能: 批量写入元数据到 MySQL，按 table_name 路由到具体 Repository
"""

from typing import List, Dict, Optional, Any
from loguru import logger
from sqlalchemy.orm import Session

from src.db.kafka.writers.base_writer import BaseWriter
from src.db.kafka.topics import KafkaTopics
from src.db.mysql.repositories.base_repository import BaseRepository as MySQLBaseRepository
from src.types.messages.db_write import MetaWriteMessage, MySQLTable, WriteOperation


class MySQLWriter(BaseWriter):
    """
    MySQLWriter

    职责:
    - 消费 db_write:meta:start Topic
    - 按 table_name 路由消息到具体的 MySQL Repository
    - 按 operation 分组执行批量 INSERT/UPDATE/UPSERT
    - 支持所有 MySQL 表的写入

    路由映射:
    - table_name → MySQL Repository 实例
    - 通过 register_repository() 注册路由

    配置参数:
    - Batch Size: 200条
    - Flush Interval: 1000ms

    优化策略:
    - 批量 INSERT/UPDATE (batch_size=200)
    - 使用 executemany 批量操作
    - 按表分组 → 按操作分组处理

    配置要求:
    - 资源: 2 CPU, 4GB RAM
    - 扩容触发: Kafka lag > 500
    """

    def __init__(
        self,
        *args,
        session_factory=None,
        **kwargs
    ):
        """
        初始化 MySQLWriter

        Args:
            session_factory: SQLAlchemy Session 工厂函数（返回 Session 实例）
        """
        super().__init__(*args, **kwargs)
        self._session_factory = session_factory
        self._repo_registry: Dict[MySQLTable, MySQLBaseRepository] = {}

    def register_repository(
        self,
        table_name: MySQLTable,
        repository: MySQLBaseRepository
    ) -> None:
        """
        注册表名到 Repository 的映射

        Args:
            table_name: MySQL 表名枚举
            repository: 对应的 Repository 实例
        """
        self._repo_registry[table_name] = repository
        logger.info(f"已注册 MySQL Repository: {table_name} → {type(repository).__name__}")

    def register_repositories(
        self,
        repos: Dict[MySQLTable, MySQLBaseRepository]
    ) -> None:
        """
        批量注册表名到 Repository 的映射

        Args:
            repos: 表名 → Repository 字典
        """
        for table_name, repo in repos.items():
            self.register_repository(table_name, repo)

    def _get_repository(self, table_name: MySQLTable) -> Optional[MySQLBaseRepository]:
        """
        根据表名获取对应的 Repository

        Args:
            table_name: MySQL 表名

        Returns:
            Repository 实例，未注册返回 None
        """
        repo = self._repo_registry.get(table_name)
        if not repo:
            logger.error(f"未注册的 MySQL Repository: {table_name}")
        return repo

    def _get_session(self) -> Optional[Session]:
        """
        获取数据库 Session

        Returns:
            Session 实例，工厂未配置返回 None
        """
        if not self._session_factory:
            logger.error("MySQL Session 工厂未配置")
            return None
        return self._session_factory()

    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.DB_WRITE_META

    async def process_batch_impl(self, messages: List[MetaWriteMessage]) -> List[bool]:
        """
        批量处理元数据写入

        处理流程:
        1. 按 table_name 分组
        2. 每个表内按 operation 分组
        3. 路由到具体 Repository 执行批量操作

        单 batch 使用单个 Session，按 table × op 在同一事务内多次 flush，
        最后统一提交；任意子组失败仅影响该子组对应的消息（降级为逐条）。

        Args:
            messages: MetaWriteMessage 列表

        Returns:
            List[bool]: 每条消息的处理结果（与输入等长、同序）
        """
        logger.info(f"开始批量写入元数据: {len(messages)} 条消息")

        results_map: Dict[str, bool] = {}

        # 单 batch 单 session（P1 #8）：避免按 table/op 反复开关连接
        session = self._get_session()
        if not session:
            return [False] * len(messages)

        try:
            # 1. 按 table_name 分组
            grouped_by_table = self._group_by_table(messages)

            # 2. 每个表分别处理
            for table_name, table_messages in grouped_by_table.items():
                logger.debug(
                    f"处理表 {table_name}: {len(table_messages)} 条消息"
                )

                repo = self._get_repository(table_name)
                if not repo:
                    for msg in table_messages:
                        results_map[msg.metadata.event_id] = False
                    continue

                # 按 operation 分组
                grouped_by_op = self._group_by_operation(table_messages)

                for operation, op_messages in grouped_by_op.items():
                    op_results = self._execute_operation(
                        session, repo, operation, op_messages
                    )
                    # op_results 与 op_messages 等长、同序
                    for msg, ok in zip(op_messages, op_results):
                        results_map[msg.metadata.event_id] = ok

            # 3. 返回结果（按原始顺序）
            results = [
                results_map.get(msg.metadata.event_id, False)
                for msg in messages
            ]

            success_count = sum(results)
            logger.info(
                f"批量写入元数据完成: success={success_count}/{len(messages)}"
            )
            return results

        except Exception as e:
            session.rollback()
            logger.error(f"批量写入元数据失败: {e}", exc_info=True)
            # 未被 _execute_operation 精确标记的，视为失败
            return [
                results_map.get(msg.metadata.event_id, False)
                for msg in messages
            ]
        finally:
            session.close()

    def _group_by_table(
        self,
        messages: List[MetaWriteMessage]
    ) -> Dict[MySQLTable, List[MetaWriteMessage]]:
        """
        按 table_name 分组

        Args:
            messages: 消息列表

        Returns:
            table_name → 消息列表
        """
        grouped: Dict[MySQLTable, List[MetaWriteMessage]] = {}
        for msg in messages:
            grouped.setdefault(msg.table_name, []).append(msg)
        return grouped

    def _group_by_operation(
        self,
        messages: List[MetaWriteMessage]
    ) -> Dict[WriteOperation, List[MetaWriteMessage]]:
        """
        按操作类型分组

        Args:
            messages: 消息列表

        Returns:
            operation → 消息列表
        """
        grouped: Dict[WriteOperation, List[MetaWriteMessage]] = {}
        for msg in messages:
            grouped.setdefault(msg.operation, []).append(msg)
        return grouped

    def _execute_operation(
        self,
        session: Session,
        repo: MySQLBaseRepository,
        operation: WriteOperation,
        messages: List[MetaWriteMessage]
    ) -> List[bool]:
        """
        执行具体的数据库操作

        所有子方法都返回与 messages 等长、同序的 List[bool]，
        单条失败不会连累同批其他消息（P0 #3 / P1 #4）。

        Args:
            session: 共享的数据库 Session（由调用方统一管理生命周期）
            repo: MySQL Repository 实例
            operation: 操作类型
            messages: 消息列表

        Returns:
            每条消息的成功标志
        """
        try:
            if operation == WriteOperation.INSERT:
                return self._batch_insert(session, repo, messages)
            elif operation == WriteOperation.UPDATE:
                return self._batch_update(session, repo, messages)
            elif operation == WriteOperation.UPSERT:
                return self._batch_upsert(session, repo, messages)
            else:
                logger.error(f"不支持的操作类型: {operation}")
                return [False] * len(messages)
        except Exception as e:
            session.rollback()
            logger.error(
                f"执行 {operation} 操作失败 ({type(repo).__name__}): {e}",
                exc_info=True
            )
            return [False] * len(messages)

    def _batch_insert(
        self,
        session: Session,
        repo: MySQLBaseRepository,
        messages: List[MetaWriteMessage]
    ) -> List[bool]:
        """
        批量 INSERT，失败时降级为逐条 INSERT（P0 #3 / P1 #4）

        bulk_create 内部是单事务 add_all+commit，整批失败会 rollback，
        因此降级重试是安全的（不会产生重复写入）。

        Args:
            session: 数据库 Session
            repo: Repository 实例
            messages: 消息列表

        Returns:
            每条消息的成功标志
        """
        batch_data = [msg.record_data for msg in messages]
        result = repo.bulk_create(session, batch_data)

        # bulk_create 成功返回等长列表；失败返回 []（已 rollback）
        if len(result) == len(messages):
            logger.debug(
                f"批量 INSERT ({type(repo).__name__}): 成功 {len(messages)} 条"
            )
            return [True] * len(messages)

        # 整批失败 → 降级逐条，精准定位坏数据
        logger.warning(
            f"批量 INSERT 失败 ({type(repo).__name__}, {len(messages)}条)，降级为逐条"
        )
        results: List[bool] = []
        for msg in messages:
            single = repo.bulk_create(session, [msg.record_data])
            results.append(len(single) == 1)
            if len(single) != 1:
                logger.error(
                    f"单条 INSERT 失败 event_id={msg.metadata.event_id} "
                    f"table={msg.table_name}"
                )
        return results

    def _batch_update(
        self,
        session: Session,
        repo: MySQLBaseRepository,
        messages: List[MetaWriteMessage]
    ) -> List[bool]:
        """
        批量 UPDATE（P1 #2：真正批量，单次 round-trip）

        Args:
            session: 数据库 Session
            repo: Repository 实例
            messages: 消息列表

        Returns:
            每条消息的成功标志
        """
        # 校验 record_id 并构造 rows
        rows: List[Dict[str, Any]] = []
        idx_missing: List[int] = []
        for i, msg in enumerate(messages):
            if not msg.record_id:
                logger.error(f"UPDATE 操作缺少 record_id: event_id={msg.metadata.event_id}")
                idx_missing.append(i)
                continue
            row = dict(msg.record_data)
            # 写入主键值，bulk_update 要求 mappings 包含主键
            pk_name = repo._primary_key_name()
            if pk_name:
                row[pk_name] = msg.record_id
            rows.append(row)

        if not rows:
            return [False] * len(messages)

        ok_flags = repo.bulk_update(session, rows, updater=messages[0].updater if messages else "")

        # 把 missing record_id 的位置置 False，其余按 ok_flags 顺序对齐
        results: List[bool] = []
        ok_iter = iter(ok_flags)
        for i in range(len(messages)):
            if i in idx_missing:
                results.append(False)
            else:
                results.append(next(ok_iter, False))
        logger.debug(
            f"批量 UPDATE ({type(repo).__name__}): {sum(results)}/{len(messages)} 条成功"
        )
        return results

    def _batch_upsert(
        self,
        session: Session,
        repo: MySQLBaseRepository,
        messages: List[MetaWriteMessage]
    ) -> List[bool]:
        """
        批量 UPSERT（P1 #2：MySQL INSERT ... ON DUPLICATE KEY UPDATE，单次 round-trip）

        Args:
            session: 数据库 Session
            repo: Repository 实例
            messages: 消息列表

        Returns:
            每条消息的成功标志
        """
        rows: List[Dict[str, Any]] = []
        idx_missing: List[int] = []
        for i, msg in enumerate(messages):
            if not msg.record_id:
                logger.error(f"UPSERT 操作缺少 record_id: event_id={msg.metadata.event_id}")
                idx_missing.append(i)
                continue
            row = dict(msg.record_data)
            pk_name = repo._primary_key_name()
            if pk_name:
                row[pk_name] = msg.record_id
            rows.append(row)

        if not rows:
            return [False] * len(messages)

        updater = messages[0].updater if messages else ""
        ok_flags = repo.bulk_upsert(
            session, rows,
            creator=updater,
            updater=updater,
        )

        results: List[bool] = []
        ok_iter = iter(ok_flags)
        for i in range(len(messages)):
            if i in idx_missing:
                results.append(False)
            else:
                results.append(next(ok_iter, False))
        logger.debug(
            f"批量 UPSERT ({type(repo).__name__}): {sum(results)}/{len(messages)} 条成功"
        )
        return results

    def get_stats(self) -> dict:
        """获取统计信息（包含路由注册状态）"""
        stats = super().get_stats()
        stats["registered_tables"] = [
            table.value for table in self._repo_registry.keys()
        ]
        stats["registered_table_count"] = len(self._repo_registry)
        return stats
