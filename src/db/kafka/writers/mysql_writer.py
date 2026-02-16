#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
MySQLWriter

监听: db_write:meta:start
功能: 批量写入元数据到 MySQL，按 table_name 路由到具体 Repository
"""

from typing import List, Dict, Optional
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

        Args:
            messages: MetaWriteMessage 列表

        Returns:
            List[bool]: 每条消息的处理结果
        """
        logger.info(f"开始批量写入元数据: {len(messages)} 条消息")

        results_map: Dict[str, bool] = {}

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
                    success = await self._execute_operation(
                        repo, operation, op_messages
                    )
                    for msg in op_messages:
                        results_map[msg.metadata.event_id] = success

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
            logger.error(f"批量写入元数据失败: {e}", exc_info=True)
            return [False] * len(messages)

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

    async def _execute_operation(
        self,
        repo: MySQLBaseRepository,
        operation: WriteOperation,
        messages: List[MetaWriteMessage]
    ) -> bool:
        """
        执行具体的数据库操作

        Args:
            repo: MySQL Repository 实例
            operation: 操作类型
            messages: 消息列表

        Returns:
            是否成功
        """
        session = self._get_session()
        if not session:
            return False

        try:
            if operation == WriteOperation.INSERT:
                return self._batch_insert(session, repo, messages)
            elif operation == WriteOperation.UPDATE:
                return self._batch_update(session, repo, messages)
            elif operation == WriteOperation.UPSERT:
                return self._batch_upsert(session, repo, messages)
            else:
                logger.error(f"不支持的操作类型: {operation}")
                return False
        except Exception as e:
            logger.error(
                f"执行 {operation} 操作失败 ({type(repo).__name__}): {e}",
                exc_info=True
            )
            return False
        finally:
            session.close()

    def _batch_insert(
        self,
        session: Session,
        repo: MySQLBaseRepository,
        messages: List[MetaWriteMessage]
    ) -> bool:
        """
        批量 INSERT

        Args:
            session: 数据库 Session
            repo: Repository 实例
            messages: 消息列表

        Returns:
            是否成功
        """
        batch_data = [msg.record_data for msg in messages]
        result = repo.bulk_create(session, batch_data)

        success = len(result) == len(messages)
        logger.debug(
            f"批量 INSERT ({type(repo).__name__}): "
            f"请求 {len(messages)} 条, 成功 {len(result)} 条"
        )
        return success

    def _batch_update(
        self,
        session: Session,
        repo: MySQLBaseRepository,
        messages: List[MetaWriteMessage]
    ) -> bool:
        """
        批量 UPDATE

        Args:
            session: 数据库 Session
            repo: Repository 实例
            messages: 消息列表

        Returns:
            是否成功
        """
        all_success = True
        for msg in messages:
            if not msg.record_id:
                logger.error(f"UPDATE 操作缺少 record_id: event_id={msg.metadata.event_id}")
                all_success = False
                continue

            result = repo.update(
                session,
                id_value=msg.record_id,
                updater=msg.updater,
                **msg.record_data
            )
            if result is None:
                all_success = False

        logger.debug(
            f"批量 UPDATE ({type(repo).__name__}): {len(messages)} 条记录"
        )
        return all_success

    def _batch_upsert(
        self,
        session: Session,
        repo: MySQLBaseRepository,
        messages: List[MetaWriteMessage]
    ) -> bool:
        """
        批量 UPSERT

        Args:
            session: 数据库 Session
            repo: Repository 实例
            messages: 消息列表

        Returns:
            是否成功
        """
        all_success = True
        for msg in messages:
            if not msg.record_id:
                logger.error(f"UPSERT 操作缺少 record_id: event_id={msg.metadata.event_id}")
                all_success = False
                continue

            result = repo.upsert(
                session,
                id_value=msg.record_id,
                updater=msg.updater,
                **msg.record_data
            )
            if result is None:
                all_success = False

        logger.debug(
            f"批量 UPSERT ({type(repo).__name__}): {len(messages)} 条记录"
        )
        return all_success

    def get_stats(self) -> dict:
        """获取统计信息（包含路由注册状态）"""
        stats = super().get_stats()
        stats["registered_tables"] = [
            table.value for table in self._repo_registry.keys()
        ]
        stats["registered_table_count"] = len(self._repo_registry)
        return stats
