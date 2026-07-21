#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : qa_vector_search.py
@Author  : caixiongjiang
@Date    : 2026/02/28
@Function:
    原子 QA 对向量语义检索原子能力（v1.1：Milvus 命中 → Mongo 下钻取正文）

    流程：
    1. query_text → EmbeddingClient 向量化
    2. Milvus atomic_qa_store ANN 检索（按 question 向量）→ 拿到 qa_id / score
       + 标量（document_id / knowledge_base_id / section_id）
    3. **Mongo 下钻**：按 qa_id 批量查 section_data.atomic_qa，回填
       question / answer / source_chunk_ids（chunk 级溯源）
    4. 返回 RetrieveResult[QAItem]

    设计原则（对齐「Milvus 返回 id → Mongo 取数」）：
    - Milvus 只存 question 向量 + 标量，不存 answer/source_chunk_ids（数组型
      不适合 Milvus），故正文必须下钻 Mongo。
    - Mongo 下钻失败不阻断召回：保留 Milvus 命中的 qa_id/score，仅缺正文
      （下游短路判断会因 answer 缺失而降级走正常融合路径）。
@Modify History:
    2026/07/14 - v1.1：接入 Mongo 下钻（section_data.atomic_qa），回填
        question/answer/source_chunk_ids，支撑直答短路 + chunk 注入融合

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Any, Dict, List, Optional

from loguru import logger

from src.client.embedding import EmbeddingClient
from src.db.milvus import BaseMilvusManager
from src.db.milvus.repositories.extract.atomic_qa_repository import AtomicQARepository
from src.retrieve.capabilities.base import CapabilityDescriptor
from src.retrieve.capabilities.semantic.base_vector_search import BaseVectorSearch
from src.retrieve.types.query import SemanticQuery
from src.retrieve.types.result import QAItem, RetrieveResult


class QAVectorSearch(BaseVectorSearch):
    """原子 QA 对向量语义检索（v1.1 Milvus + Mongo 下钻）

    对 Milvus atomic_qa_store Collection 执行 ANN 向量检索（向量化源=question），
    再按 qa_id 下钻 Mongo section_data.atomic_qa 回填 question/answer/source_chunk_ids。

    对应 Collection: atomic_qa_store
    对应 Repository: AtomicQARepository
    """

    def __init__(
        self,
        embedding_client: Optional[EmbeddingClient] = None,
        milvus_manager: Optional[BaseMilvusManager] = None,
    ) -> None:
        repository = AtomicQARepository(manager=milvus_manager)
        super().__init__(repository=repository, embedding_client=embedding_client)

    async def _do_execute(self, **kwargs: Any) -> RetrieveResult:
        """
        重写统一流程：Milvus 召回后追加 Mongo 下钻回填。

        走父类 _do_execute 完成 embed → search → _build_result_items（含 score 阈值过滤），
        再对结果做异步 Mongo 下钻。
        """
        result: RetrieveResult = await super()._do_execute(**kwargs)
        items: List[QAItem] = result.items
        if not items:
            return result

        await self._enrich_from_mongo(items)
        return result

    async def _enrich_from_mongo(self, items: List[QAItem]) -> None:
        """按 qa_id 批量下钻 Mongo section_data.atomic_qa，回填正文与溯源。"""
        qa_ids = [it.qa_id for it in items if it.qa_id]
        if not qa_ids:
            return
        try:
            from src.db.mongodb.repositories import section_data_repository
            qa_map = await section_data_repository.get_atomic_qa_by_qa_ids(qa_ids)
        except Exception as e:
            logger.warning(
                f"QAVectorSearch: Mongo 下钻失败，保留 Milvus 命中（缺正文）: "
                f"{len(qa_ids)} qa, error={e}"
            )
            return

        if not qa_map:
            logger.debug(
                f"QAVectorSearch: Mongo 未命中任何 qa 正文（可能未落库）: "
                f"{len(qa_ids)} qa"
            )
            return

        for it in items:
            entry = qa_map.get(it.qa_id)
            if not entry:
                continue
            it.question = entry.get("question") or it.question
            it.answer = entry.get("answer") or it.answer
            source_chunk_ids = entry.get("source_chunk_ids") or []
            section_id = entry.get("section_id") or it.metadata.get("section_id")
            # 溯源字段放 metadata，供 GranularityAligner 展开 + 直答短路判断
            it.metadata["source_chunk_ids"] = list(source_chunk_ids)
            if section_id:
                it.metadata["section_id"] = section_id
            it.metadata["qa_type"] = entry.get("qa_type")
            it.metadata["relevance"] = entry.get("relevance")

    def _build_result_items(self, hits: List[Dict[str, Any]]) -> List[QAItem]:
        items: List[QAItem] = []
        for hit in hits:
            entity = hit.get("entity", {})
            items.append(QAItem(
                qa_id=str(hit.get("id", "")),
                score=hit.get("score", 0.0),
                document_id=entity.get("document_id"),
                knowledge_base_id=entity.get("knowledge_base_id"),
                metadata={
                    k: v for k, v in entity.items()
                    if k not in ("document_id", "knowledge_base_id", "vector")
                },
            ))
        return items

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="qa_vector_search",
            display_name="QA 对向量语义检索",
            description=(
                "在 atomic_qa_store 中执行向量 ANN 检索，"
                "通过匹配已抽取的问题来召回最相关的问答对，"
                "并下钻 Mongo 回填 question/answer/source_chunk_ids。"
                "适用于用户提问与原文表述差异较大的场景；"
                "高置信命中可触发直答短路。"
            ),
            input_schema={
                "query_text": "str - 自然语言查询（与 query_vector 二选一）",
                "query_vector": "List[float] - 预计算向量（与 query_text 二选一）",
                "top_k": "int - 返回数量上限，默认 10",
                "filters": "MetadataFilter - 元数据过滤条件（可选）",
            },
            output_type="RetrieveResult[QAItem]",
        )
