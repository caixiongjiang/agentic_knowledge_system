#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
MongoWriter

监听: db_write:mongo:start
功能: 批量写入文档数据到 MongoDB，按 collection_name 路由到具体 Repository
"""

from typing import List, Dict, Optional
from loguru import logger

from src.db.kafka.writers.base_writer import BaseWriter
from src.db.kafka.topics import KafkaTopics
from src.db.mongodb.repositories.base_repository import BaseRepository as MongoBaseRepository
from src.types.messages.db_write import MongoWriteMessage, MongoCollection, WriteOperation


class MongoWriter(BaseWriter):
    """
    MongoWriter

    职责:
    - 消费 db_write:mongo:start Topic
    - 按 collection_name 路由消息到具体的 MongoDB Repository
    - 按 operation 分组执行批量操作
    - 使用 bulk_write 批量优化

    路由映射:
    - collection_name → MongoDB Repository 实例
    - 通过 register_repository() 注册路由

    配置参数:
    - Batch Size: 100条
    - Flush Interval: 500ms

    优化策略:
    - 批量 INSERT (batch_size=100)
    - 按 collection 分组 → 按 operation 分组
    - 使用 bulk_write 批量操作

    配置要求:
    - 资源: 2 CPU, 4GB RAM
    - 扩容触发: Kafka lag > 300
    """

    def __init__(self, *args, **kwargs):
        """初始化 MongoWriter"""
        super().__init__(*args, **kwargs)
        self._repo_registry: Dict[MongoCollection, MongoBaseRepository] = {}

    def register_repository(
        self,
        collection_name: MongoCollection,
        repository: MongoBaseRepository
    ) -> None:
        """
        注册 Collection 到 Repository 的映射

        Args:
            collection_name: MongoDB Collection 枚举
            repository: 对应的 Repository 实例
        """
        self._repo_registry[collection_name] = repository
        logger.info(
            f"已注册 MongoDB Repository: {collection_name} → {type(repository).__name__}"
        )

    def register_repositories(
        self,
        repos: Dict[MongoCollection, MongoBaseRepository]
    ) -> None:
        """
        批量注册 Collection 到 Repository 的映射

        Args:
            repos: collection_name → Repository 字典
        """
        for collection_name, repo in repos.items():
            self.register_repository(collection_name, repo)

    def _get_repository(
        self, collection_name: MongoCollection
    ) -> Optional[MongoBaseRepository]:
        """
        根据 Collection 名称获取对应的 Repository

        Args:
            collection_name: Collection 名称

        Returns:
            Repository 实例，未注册返回 None
        """
        repo = self._repo_registry.get(collection_name)
        if not repo:
            logger.error(f"未注册的 MongoDB Repository: {collection_name}")
        return repo

    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.DB_WRITE_MONGO

    async def process_batch_impl(
        self, messages: List[MongoWriteMessage]
    ) -> List[bool]:
        """
        批量处理文档写入

        处理流程:
        1. 按 collection_name 分组
        2. 每个 Collection 内按 operation 分组
        3. 路由到具体 Repository 执行批量操作

        所有子方法返回与输入等长、同序的 List[bool]，
        单条失败精准标记，不连累同批其他消息（P0 #3 / P1 #4）。

        Args:
            messages: MongoWriteMessage 列表

        Returns:
            List[bool]: 每条消息的处理结果
        """
        logger.info(f"开始批量写入文档: {len(messages)} 条消息")

        results_map: Dict[str, bool] = {}

        try:
            # 1. 按 collection_name 分组
            grouped_by_collection = self._group_by_collection(messages)

            # 2. 每个 Collection 分别处理
            for collection_name, coll_messages in grouped_by_collection.items():
                logger.debug(
                    f"处理 Collection {collection_name}: "
                    f"{len(coll_messages)} 条消息"
                )

                repo = self._get_repository(collection_name)
                if not repo:
                    for msg in coll_messages:
                        results_map[msg.metadata.event_id] = False
                    continue

                # 按 operation 分组
                grouped_by_op = self._group_by_operation(coll_messages)

                for operation, op_messages in grouped_by_op.items():
                    op_results = await self._execute_operation(
                        repo, operation, op_messages
                    )
                    for msg, ok in zip(op_messages, op_results):
                        results_map[msg.metadata.event_id] = ok

            # 3. 返回结果（按原始顺序）
            results = [
                results_map.get(msg.metadata.event_id, False)
                for msg in messages
            ]

            success_count = sum(results)
            logger.info(
                f"批量写入文档完成: success={success_count}/{len(messages)}"
            )
            return results

        except Exception as e:
            logger.error(f"批量写入文档失败: {e}", exc_info=True)
            return [
                results_map.get(msg.metadata.event_id, False)
                for msg in messages
            ]

    def _group_by_collection(
        self,
        messages: List[MongoWriteMessage]
    ) -> Dict[MongoCollection, List[MongoWriteMessage]]:
        """
        按 collection_name 分组

        Args:
            messages: 消息列表

        Returns:
            collection_name → 消息列表
        """
        grouped: Dict[MongoCollection, List[MongoWriteMessage]] = {}
        for msg in messages:
            grouped.setdefault(msg.collection_name, []).append(msg)
        return grouped

    def _group_by_operation(
        self,
        messages: List[MongoWriteMessage]
    ) -> Dict[WriteOperation, List[MongoWriteMessage]]:
        """
        按操作类型分组

        Args:
            messages: 消息列表

        Returns:
            operation → 消息列表
        """
        grouped: Dict[WriteOperation, List[MongoWriteMessage]] = {}
        for msg in messages:
            grouped.setdefault(msg.operation, []).append(msg)
        return grouped

    async def _execute_operation(
        self,
        repo: MongoBaseRepository,
        operation: WriteOperation,
        messages: List[MongoWriteMessage]
    ) -> List[bool]:
        """
        执行具体的数据库操作

        所有子方法返回与 messages 等长、同序的 List[bool]（P1 #4）。

        Args:
            repo: MongoDB Repository 实例
            operation: 操作类型
            messages: 消息列表

        Returns:
            每条消息的成功标志
        """
        try:
            if operation == WriteOperation.INSERT:
                return await self._batch_insert(repo, messages)
            elif operation == WriteOperation.UPDATE:
                return await self._batch_update(repo, messages)
            elif operation == WriteOperation.UPSERT:
                return await self._batch_upsert(repo, messages)
            elif operation == WriteOperation.REPLACE:
                return await self._batch_upsert(repo, messages)
            else:
                logger.error(f"不支持的操作类型: {operation}")
                return [False] * len(messages)
        except Exception as e:
            logger.error(
                f"执行 {operation} 操作失败 ({type(repo).__name__}): {e}",
                exc_info=True
            )
            return [False] * len(messages)

    async def _batch_insert(
        self,
        repo: MongoBaseRepository,
        messages: List[MongoWriteMessage]
    ) -> List[bool]:
        """
        批量 INSERT，失败时降级为逐条 INSERT（P0 #3 / P1 #4）

        create_batch 内部 insert_many 整批失败会抛异常，不会半写，
        因此降级重试是安全的（无重复写入风险）。

        Args:
            repo: Repository 实例
            messages: 消息列表

        Returns:
            每条消息的成功标志
        """
        data_list = [msg.document_data for msg in messages]
        creator = messages[0].updater if messages else "system"

        try:
            await repo.create_batch(data_list, creator=creator)
            logger.debug(
                f"批量 INSERT ({type(repo).__name__}): 成功 {len(messages)} 条"
            )
            return [True] * len(messages)
        except Exception as e:
            logger.warning(
                f"批量 INSERT 失败 ({type(repo).__name__}, {len(messages)}条)，"
                f"降级为逐条: {e}"
            )
            results: List[bool] = []
            for msg in messages:
                try:
                    await repo.create_batch([msg.document_data], creator=creator)
                    results.append(True)
                except Exception as e2:
                    logger.error(
                        f"单条 INSERT 失败 event_id={msg.metadata.event_id} "
                        f"collection={msg.collection_name}: {e2}"
                    )
                    results.append(False)
            return results

    async def _batch_update(
        self,
        repo: MongoBaseRepository,
        messages: List[MongoWriteMessage]
    ) -> List[bool]:
        """
        批量 UPDATE（MongoDB 暂走逐条 update，因每条字段可能不同）

        Args:
            repo: Repository 实例
            messages: 消息列表

        Returns:
            每条消息的成功标志
        """
        results: List[bool] = []
        for msg in messages:
            if not msg.document_id:
                logger.error(
                    f"UPDATE 操作缺少 document_id: event_id={msg.metadata.event_id}"
                )
                results.append(False)
                continue
            result = await repo.update(
                doc_id=msg.document_id,
                updater=msg.updater,
                **msg.document_data
            )
            results.append(result is not None)
        logger.debug(
            f"批量 UPDATE ({type(repo).__name__}): {sum(results)}/{len(messages)} 条成功"
        )
        return results

    async def _batch_upsert(
        self,
        repo: MongoBaseRepository,
        messages: List[MongoWriteMessage]
    ) -> List[bool]:
        """
        批量 UPSERT（使用 bulk_write ordered=False，P1 #4 精确捕获部分失败）

        bulk_write(ordered=False) 部分条目失败时抛 BulkWriteError，
        其中 writeErrors 携带失败条目的 index；据此精确标记每条消息成败，
        失败条目由 base_writer 送 retry/DLQ，成功条目不被连累。

        Args:
            repo: Repository 实例
            messages: 消息列表

        Returns:
            每条消息的成功标志
        """
        data_list = []
        for msg in messages:
            doc_data = msg.document_data.copy()
            if msg.document_id:
                doc_data["_id"] = msg.document_id
            data_list.append(doc_data)

        updater = messages[0].updater if messages else "system"
        creator = updater

        try:
            await repo.upsert_batch_optimized(
                data_list=data_list,
                id_field="_id",
                creator=creator,
                updater=updater
            )
            logger.debug(
                f"批量 UPSERT ({type(repo).__name__}): 成功 {len(messages)} 条"
            )
            return [True] * len(messages)
        except Exception as e:
            # 解析 BulkWriteError 的 writeErrors，定位失败 index
            failed_indices = self._extract_failed_indices(e)
            if failed_indices is not None:
                results = [True] * len(messages)
                for idx in failed_indices:
                    if 0 <= idx < len(messages):
                        results[idx] = False
                        logger.error(
                            f"UPSERT 单条失败 event_id={messages[idx].metadata.event_id} "
                            f"collection={messages[idx].collection_name}: {e}"
                        )
                logger.warning(
                    f"批量 UPSERT 部分失败 ({type(repo).__name__}): "
                    f"{len(failed_indices)}/{len(messages)} 条失败"
                )
                return results
            # 无法定位失败 index → 整批降级为逐条
            logger.warning(
                f"批量 UPSERT 失败且无法定位条目 ({type(repo).__name__}, "
                f"{len(messages)}条)，降级为逐条: {e}"
            )
            results: List[bool] = []
            for msg in messages:
                doc_data = msg.document_data.copy()
                if msg.document_id:
                    doc_data["_id"] = msg.document_id
                try:
                    await repo.upsert_batch_optimized(
                        data_list=[doc_data],
                        id_field="_id",
                        creator=creator,
                        updater=updater,
                    )
                    results.append(True)
                except Exception as e2:
                    logger.error(
                        f"单条 UPSERT 失败 event_id={msg.metadata.event_id}: {e2}"
                    )
                    results.append(False)
            return results

    @staticmethod
    def _extract_failed_indices(exc: Exception) -> Optional[List[int]]:
        """从 BulkWriteError 异常中提取失败条目的 index 列表。

        Motor/PyMongo 的 BulkWriteError.details['writeErrors'] 形如：
            [{"index": 0, "code": 11000, "errmsg": "..."}, ...]
        若不是 BulkWriteError 结构则返回 None。
        """
        details = getattr(exc, "details", None)
        if not isinstance(details, dict):
            return None
        write_errors = details.get("writeErrors")
        if not isinstance(write_errors, list) or not write_errors:
            return None
        indices: List[int] = []
        for we in write_errors:
            if isinstance(we, dict) and isinstance(we.get("index"), int):
                indices.append(we["index"])
        return indices if indices else None

    def get_stats(self) -> dict:
        """获取统计信息（包含路由注册状态）"""
        stats = super().get_stats()
        stats["registered_collections"] = [
            coll.value for coll in self._repo_registry.keys()
        ]
        stats["registered_collection_count"] = len(self._repo_registry)
        return stats
