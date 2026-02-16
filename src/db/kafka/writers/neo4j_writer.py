#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Neo4jWriter

监听: db_write:graph:start
功能: 批量写入知识图谱到 Neo4j，按实体类型分组优化写入
"""

from typing import List, Dict, Optional, Any, Protocol
from loguru import logger

from src.db.kafka.writers.base_writer import BaseWriter
from src.db.kafka.topics import KafkaTopics
from src.types.messages.db_write import GraphWriteMessage


class Neo4jClient(Protocol):
    """Neo4j 客户端协议"""
    async def execute(self, cypher: str, **params: Any) -> Any:
        """执行 Cypher 查询"""
        ...


class Neo4jWriter(BaseWriter):
    """
    Neo4jWriter

    职责:
    - 消费 db_write:graph:start Topic
    - 按实体类型（entity_type）分组批量 MERGE 节点
    - 按关系类型（relation_type）分组批量 CREATE 关系
    - 使用大事务批量处理
    - 先处理节点，再处理关系（确保节点存在）

    内部路由:
    - 实体按 entity_type 分组 → 每组使用 UNWIND + MERGE
    - 关系按 relation_type 分组 → 每组使用 UNWIND + MERGE

    配置参数:
    - Batch Size: 500条
    - Flush Interval: 2000ms

    优化策略:
    - 大事务批量处理 (batch_size=500)
    - 按类型分组使用 UNWIND 批量 MERGE
    - 先处理节点，再处理关系
    - 避免死锁的单线程写入

    配置要求:
    - 资源: 2 CPU, 4GB RAM
    - 扩容触发: Kafka lag > 200
    """

    def __init__(
        self,
        *args,
        neo4j_client: Optional[Neo4jClient] = None,
        node_batch_size: int = 500,
        relation_batch_size: int = 200,
        **kwargs
    ):
        """
        初始化 Neo4jWriter

        Args:
            neo4j_client: Neo4j 客户端实例
            node_batch_size: 节点批量写入大小
            relation_batch_size: 关系批量写入大小
        """
        super().__init__(*args, **kwargs)
        self._neo4j_client = neo4j_client
        self._node_batch_size = node_batch_size
        self._relation_batch_size = relation_batch_size

    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.DB_WRITE_GRAPH

    async def process_batch_impl(
        self, messages: List[GraphWriteMessage]
    ) -> List[bool]:
        """
        批量处理图谱写入

        处理流程:
        1. 聚合所有实体和关系
        2. 按 entity_type 分组批量 MERGE 节点
        3. 按 relation_type 分组批量 MERGE 关系

        Args:
            messages: GraphWriteMessage 列表

        Returns:
            List[bool]: 每条消息的处理结果
        """
        logger.info(f"开始批量写入图谱: {len(messages)} 条消息")

        if not self._neo4j_client:
            logger.error("Neo4j 客户端未配置")
            return [False] * len(messages)

        try:
            # 1. 聚合所有实体和关系
            all_entities: List[Dict[str, Any]] = []
            all_relations: List[Dict[str, Any]] = []

            for msg in messages:
                all_entities.extend(msg.entities)
                all_relations.extend(msg.relations)

            logger.debug(
                f"聚合完成: entities={len(all_entities)}, "
                f"relations={len(all_relations)}"
            )

            # 2. 按 entity_type 分组批量 MERGE 节点
            if all_entities:
                entity_success = await self._batch_merge_nodes_by_type(
                    all_entities
                )
                if not entity_success:
                    logger.error("批量 MERGE 节点失败")
                    return [False] * len(messages)

            # 3. 按 relation_type 分组批量 MERGE 关系
            if all_relations:
                relation_success = await self._batch_merge_relations_by_type(
                    all_relations
                )
                if not relation_success:
                    logger.error("批量 MERGE 关系失败")
                    return [False] * len(messages)

            logger.info(f"批量写入图谱完成: {len(messages)} 条消息")
            return [True] * len(messages)

        except Exception as e:
            logger.error(f"批量写入图谱失败: {e}", exc_info=True)
            return [False] * len(messages)

    async def _batch_merge_nodes_by_type(
        self,
        entities: List[Dict[str, Any]]
    ) -> bool:
        """
        按 entity_type 分组批量 MERGE 节点

        Args:
            entities: 实体列表

        Returns:
            是否成功
        """
        grouped = self._group_entities_by_type(entities)

        for entity_type, type_entities in grouped.items():
            logger.debug(
                f"MERGE 节点类型 {entity_type}: {len(type_entities)} 个"
            )

            # 分批处理
            for i in range(0, len(type_entities), self._node_batch_size):
                batch = type_entities[i:i + self._node_batch_size]
                success = await self._merge_nodes_batch(entity_type, batch)
                if not success:
                    return False

        return True

    async def _batch_merge_relations_by_type(
        self,
        relations: List[Dict[str, Any]]
    ) -> bool:
        """
        按 relation_type 分组批量 MERGE 关系

        Args:
            relations: 关系列表

        Returns:
            是否成功
        """
        grouped = self._group_relations_by_type(relations)

        for relation_type, type_relations in grouped.items():
            logger.debug(
                f"MERGE 关系类型 {relation_type}: {len(type_relations)} 条"
            )

            # 分批处理
            for i in range(0, len(type_relations), self._relation_batch_size):
                batch = type_relations[i:i + self._relation_batch_size]
                success = await self._merge_relations_batch(
                    relation_type, batch
                )
                if not success:
                    return False

        return True

    def _group_entities_by_type(
        self,
        entities: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        按实体类型分组

        Args:
            entities: 实体列表

        Returns:
            entity_type → 实体列表
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for entity in entities:
            entity_type = entity.get("type", "Entity")
            grouped.setdefault(entity_type, []).append(entity)
        return grouped

    def _group_relations_by_type(
        self,
        relations: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        按关系类型分组

        Args:
            relations: 关系列表

        Returns:
            relation_type → 关系列表
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for relation in relations:
            relation_type = relation.get("relation", "RELATED_TO")
            grouped.setdefault(relation_type, []).append(relation)
        return grouped

    async def _merge_nodes_batch(
        self,
        entity_type: str,
        entities: List[Dict[str, Any]]
    ) -> bool:
        """
        批量 MERGE 同类型节点

        使用 UNWIND + MERGE 优化，单条 Cypher 处理一批同类型节点。

        Args:
            entity_type: 节点标签（实体类型）
            entities: 实体列表

        Returns:
            是否成功
        """
        cypher = (
            f"UNWIND $entities AS entity "
            f"MERGE (n:`{entity_type}` {{name: entity.name}}) "
            f"SET n += entity.properties"
        )

        try:
            await self._neo4j_client.execute(cypher, entities=entities)
            logger.debug(
                f"MERGE 节点成功: type={entity_type}, count={len(entities)}"
            )
            return True
        except Exception as e:
            logger.error(
                f"MERGE 节点失败: type={entity_type}, error={e}",
                exc_info=True
            )
            return False

    async def _merge_relations_batch(
        self,
        relation_type: str,
        relations: List[Dict[str, Any]]
    ) -> bool:
        """
        批量 MERGE 同类型关系

        使用 UNWIND + MATCH + MERGE 优化，单条 Cypher 处理一批同类型关系。

        Args:
            relation_type: 关系类型
            relations: 关系列表

        Returns:
            是否成功
        """
        cypher = (
            f"UNWIND $relations AS rel "
            f"MATCH (h {{name: rel.head}}) "
            f"MATCH (t {{name: rel.tail}}) "
            f"MERGE (h)-[r:`{relation_type}`]->(t) "
            f"SET r += rel.properties"
        )

        try:
            await self._neo4j_client.execute(cypher, relations=relations)
            logger.debug(
                f"MERGE 关系成功: type={relation_type}, count={len(relations)}"
            )
            return True
        except Exception as e:
            logger.error(
                f"MERGE 关系失败: type={relation_type}, error={e}",
                exc_info=True
            )
            return False

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = super().get_stats()
        stats["neo4j_client_configured"] = self._neo4j_client is not None
        stats["node_batch_size"] = self._node_batch_size
        stats["relation_batch_size"] = self._relation_batch_size
        return stats
