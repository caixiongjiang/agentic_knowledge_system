#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
EmbeddingMilvusWriter

监听: db_write:embedding:start
功能: 核心组件 - 按 collection_type 路由，统一处理 Embedding + Milvus 写入
    1. 接收原始文本 (不是向量)
    2. 按 collection_type 分组路由
    3. 批量调用 Embedding API
    4. 路由到具体 Milvus Repository 批量写入
"""

from typing import List, Dict, Optional, Any, Set

from loguru import logger

from src.db.kafka.writers.base_writer import BaseWriter
from src.db.kafka.topics import KafkaTopics
from src.db.milvus.repositories.base_repository import BaseRepository as MilvusBaseRepository
from src.types.messages.db_write import EmbeddingWriteMessage, MilvusCollection
from src.client.embedding import EmbeddingClient, SparseEmbeddingClient


class EmbeddingMilvusWriter(BaseWriter):
    """
    EmbeddingMilvusWriter

    核心设计: 这是整个架构的关键组件
    - 消费 db_write:embedding:start Topic
    - 按 collection_type 路由到具体 Milvus Repository
    - 接收**原始文本** (不是向量,节省 Kafka 带宽)
    - 统一处理 Embedding + Milvus 写入
    - 批量优化: 批量 Embedding + 批量插入

    路由映射:
    - collection_type → Milvus Repository 实例
    - 通过 register_repository() 注册路由

    数据来源:
    - TextSplitter: 原始文本 chunk → MilvusCollection.CHUNK
    - TextSplitter: Section标题+Chunk文本 → MilvusCollection.ENHANCED_CHUNK
    - Summary: 摘要 → MilvusCollection.SUMMARY
    - AtomicQA: 原子QA → MilvusCollection.ATOMIC_QA
    - KG Extract: SPO/Tag → MilvusCollection.SPO / MilvusCollection.TAG

    配置参数:
    - Batch Size: 100条
    - Flush Interval: 500ms
    - Embedding Batch Size: 64条/请求
    - Milvus Insert Batch Size: 100条/次

    配置要求:
    - 资源: 4 CPU, 8GB RAM
    - 扩容触发: Kafka lag > 500
    """

    def __init__(
        self,
        *args,
        embedding_client: Optional[EmbeddingClient] = None,
        sparse_embedding_client: Optional[SparseEmbeddingClient] = None,
        embedding_batch_size: int = 64,
        **kwargs
    ):
        """
        初始化 EmbeddingMilvusWriter

        Args:
            embedding_client: 稠密向量 Embedding 客户端实例
            sparse_embedding_client: 稀疏向量 Embedding 客户端实例（BGE-M3）
            embedding_batch_size: Embedding API 批处理大小
        """
        super().__init__(*args, **kwargs)
        self._embedding_client = embedding_client
        self._sparse_embedding_client = sparse_embedding_client
        self._embedding_batch_size = embedding_batch_size
        self._repo_registry: Dict[MilvusCollection, MilvusBaseRepository] = {}

    _SPARSE_VECTOR_COLLECTIONS: Set[MilvusCollection] = {
        MilvusCollection.CHUNK,
        MilvusCollection.ENHANCED_CHUNK,
    }

    def register_repository(
        self,
        collection_type: MilvusCollection,
        repository: MilvusBaseRepository
    ) -> None:
        """
        注册 Collection 类型到 Repository 的映射

        Args:
            collection_type: Milvus Collection 类型枚举
            repository: 对应的 Repository 实例
        """
        self._repo_registry[collection_type] = repository
        logger.info(
            f"已注册 Milvus Repository: "
            f"{collection_type} → {type(repository).__name__}"
        )

    def register_repositories(
        self,
        repos: Dict[MilvusCollection, MilvusBaseRepository]
    ) -> None:
        """
        批量注册 Collection 类型到 Repository 的映射

        Args:
            repos: collection_type → Repository 字典
        """
        for collection_type, repo in repos.items():
            self.register_repository(collection_type, repo)

    def _get_repository(
        self, collection_type: MilvusCollection
    ) -> Optional[MilvusBaseRepository]:
        """
        根据 Collection 类型获取对应的 Repository

        Args:
            collection_type: Collection 类型

        Returns:
            Repository 实例，未注册返回 None
        """
        repo = self._repo_registry.get(collection_type)
        if not repo:
            logger.error(f"未注册的 Milvus Repository: {collection_type}")
        return repo

    def get_original_topic(self) -> str:
        """返回监听的 Topic"""
        return KafkaTopics.DB_WRITE_EMBEDDING

    async def process_batch_impl(
        self, messages: List[EmbeddingWriteMessage]
    ) -> List[bool]:
        """
        批量处理向量化和写入

        处理流程:
        1. 按 collection_type 分组路由
        2. 每个 Collection 内提取文本
        3. 批量调用 Embedding API
        4. 路由到具体 Milvus Repository 批量写入

        Args:
            messages: EmbeddingWriteMessage 列表

        Returns:
            List[bool]: 每条消息的处理结果
        """
        logger.info(f"开始批量向量化和写入: {len(messages)} 条消息")

        results_map: Dict[str, bool] = {}

        try:
            # 1. 按 collection_type 分组
            grouped = self._group_by_collection(messages)

            # 2. 每个 Collection 分别处理
            for collection_type, group_messages in grouped.items():
                logger.debug(
                    f"处理 Collection {collection_type}: "
                    f"{len(group_messages)} 条消息"
                )

                repo = self._get_repository(collection_type)
                if not repo:
                    for msg in group_messages:
                        results_map[msg.metadata.event_id] = False
                    continue

                # 处理该 Collection 的消息
                success = await self._process_collection_batch(
                    repo, collection_type, group_messages
                )
                for msg in group_messages:
                    results_map[msg.metadata.event_id] = success

            # 3. 返回结果（按原始顺序）
            results = [
                results_map.get(msg.metadata.event_id, False)
                for msg in messages
            ]

            success_count = sum(results)
            logger.info(
                f"批量向量化完成: success={success_count}/{len(messages)}"
            )
            return results

        except Exception as e:
            logger.error(f"批量向量化失败: {e}", exc_info=True)
            return [False] * len(messages)

    async def _process_collection_batch(
        self,
        repo: MilvusBaseRepository,
        collection_type: MilvusCollection,
        messages: List[EmbeddingWriteMessage]
    ) -> bool:
        """
        处理单个 Collection 的消息批次

        Args:
            repo: Milvus Repository 实例
            collection_type: Collection 类型
            messages: 该 Collection 的消息列表

        Returns:
            是否成功
        """
        try:
            # 1. 提取所有文本和元数据
            texts, item_metadata = self._extract_texts_and_metadata(messages)

            if not texts:
                logger.warning(f"Collection {collection_type} 没有待处理的文本")
                return True

            # 2. 批量调用稠密向量 Embedding API
            embeddings = await self._batch_embed(texts)

            if len(embeddings) != len(texts):
                logger.error(
                    f"Embedding 结果数量不匹配: "
                    f"期望 {len(texts)}, 实际 {len(embeddings)}"
                )
                return False

            # 3. 需要稀疏向量的 Collection，批量调用稀疏编码
            need_sparse = collection_type in self._SPARSE_VECTOR_COLLECTIONS
            sparse_vectors: Optional[List[Dict[int, float]]] = None
            
            if need_sparse:
                sparse_vectors = await self._batch_embed_sparse(texts)
                if sparse_vectors is None or len(sparse_vectors) != len(texts):
                    logger.error(
                        f"稀疏向量结果数量不匹配: "
                        f"期望 {len(texts)}, 实际 {len(sparse_vectors) if sparse_vectors else 0}"
                    )
                    return False

            # 4. 构建 Milvus 插入数据
            insert_data = self._build_insert_data(
                item_metadata, embeddings, sparse_vectors
            )

            # 5. 批量写入到具体 Repository
            result_ids = repo.insert(insert_data)

            success = len(result_ids) == len(insert_data)
            logger.debug(
                f"写入 Milvus ({type(repo).__name__}): "
                f"请求 {len(insert_data)} 条, 成功 {len(result_ids)} 条"
            )
            return success

        except Exception as e:
            logger.error(
                f"处理 Collection {collection_type} 失败: {e}",
                exc_info=True
            )
            return False

    def _group_by_collection(
        self,
        messages: List[EmbeddingWriteMessage]
    ) -> Dict[MilvusCollection, List[EmbeddingWriteMessage]]:
        """
        按 collection_type 分组

        Args:
            messages: 消息列表

        Returns:
            collection_type → 消息列表
        """
        grouped: Dict[MilvusCollection, List[EmbeddingWriteMessage]] = {}
        for msg in messages:
            grouped.setdefault(msg.collection_type, []).append(msg)
        return grouped

    def _extract_texts_and_metadata(
        self,
        messages: List[EmbeddingWriteMessage]
    ) -> tuple[List[str], List[Dict[str, Any]]]:
        """
        提取所有文本和对应的元数据

        Args:
            messages: 消息列表

        Returns:
            (文本列表, 元数据列表)
            元数据列表与文本列表一一对应，包含用于构建 Milvus 记录的信息
        """
        texts: List[str] = []
        item_metadata: List[Dict[str, Any]] = []

        for msg in messages:
            for data_item in msg.items:
                text = data_item.get("text", "")
                if not text:
                    logger.warning(
                        f"数据项缺少 text 字段: file_id={msg.file_id}"
                    )
                    continue

                item_id = (
                    data_item.get("id")
                    or data_item.get("chunk_id")
                    or ""
                )

                texts.append(text)
                item_metadata.append({
                    "id": item_id,
                    "user_id": msg.user_id,
                    "file_id": msg.file_id,
                    "document_id": msg.document_id,
                    "knowledge_base_id": msg.knowledge_base_id,
                    "knowledge_base_name": msg.knowledge_base_name,
                    "text": text,
                    "item_metadata": data_item.get("metadata", {}),
                })

        return texts, item_metadata

    async def _batch_embed(self, texts: List[str]) -> List[List[float]]:
        """
        批量调用稠密向量 Embedding API（分批处理）

        Args:
            texts: 文本列表

        Returns:
            稠密向量列表
        """
        if not self._embedding_client:
            logger.error("稠密向量 Embedding 客户端未配置")
            return []

        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), self._embedding_batch_size):
            batch = texts[i:i + self._embedding_batch_size]
            batch_embeddings = await self._embedding_client.aembed_batch(batch)
            all_embeddings.extend(batch_embeddings)

        logger.debug(f"批量稠密 Embedding 完成: {len(texts)} 文本 → {len(all_embeddings)} 向量")
        return all_embeddings

    async def _batch_embed_sparse(self, texts: List[str]) -> Optional[List[Dict[int, float]]]:
        """
        批量调用稀疏向量 Embedding API（BGE-M3，分批处理）

        Args:
            texts: 文本列表

        Returns:
            稀疏向量列表，客户端未配置时返回 None
        """
        if not self._sparse_embedding_client:
            logger.error("稀疏向量 Embedding 客户端未配置")
            return None

        all_sparse: List[Dict[int, float]] = []

        for i in range(0, len(texts), self._embedding_batch_size):
            batch = texts[i:i + self._embedding_batch_size]
            batch_sparse = await self._sparse_embedding_client.aembed_sparse_batch(batch)
            all_sparse.extend(batch_sparse)

        logger.debug(f"批量稀疏 Embedding 完成: {len(texts)} 文本 → {len(all_sparse)} 稀疏向量")
        return all_sparse

    def _build_insert_data(
        self,
        item_metadata: List[Dict[str, Any]],
        embeddings: List[List[float]],
        sparse_vectors: Optional[List[Dict[int, float]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        构建 Milvus 插入数据

        Args:
            item_metadata: 元数据列表
            embeddings: 稠密向量列表
            sparse_vectors: 稀疏向量列表（仅 CHUNK / ENHANCED_CHUNK 需要）

        Returns:
            Milvus 插入数据列表
        """
        import time
        now_ts = int(time.time())
        insert_data = []

        for idx, (meta, embedding) in enumerate(zip(item_metadata, embeddings)):
            chunk_meta = meta.get("item_metadata", {})
            record: Dict[str, Any] = {
                "id": meta["id"],
                "vector": embedding,
                "user_id": meta["user_id"],
                "document_id": meta["document_id"],
                "type": chunk_meta.get("chunk_type"),
                "knowledge_base_id": meta.get("knowledge_base_id"),
                "knowledge_base_name": meta.get("knowledge_base_name"),
                "create_time": now_ts,
                "update_time": now_ts,
            }

            if sparse_vectors is not None:
                record["sparse_vector"] = sparse_vectors[idx]

            insert_data.append(record)

        return insert_data

    def get_stats(self) -> dict:
        """获取统计信息（包含路由注册状态）"""
        stats = super().get_stats()
        stats["registered_collections"] = [
            coll.value for coll in self._repo_registry.keys()
        ]
        stats["registered_collection_count"] = len(self._repo_registry)
        stats["embedding_batch_size"] = self._embedding_batch_size
        stats["embedding_client_configured"] = self._embedding_client is not None
        stats["sparse_embedding_client_configured"] = self._sparse_embedding_client is not None
        return stats
