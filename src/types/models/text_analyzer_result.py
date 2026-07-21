#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
TextAnalyzerResult 数据模型

section 级 atomic_qa 抽取结果的统一数据模型，由 TextAnalyzerService 产出，
供 TextAnalyzerWorker 分发到 db_write.* Topics 落地 + 发送 analyze.end。

存储映射（v1.1）：
- MySQL section_atomic_qa: 关联表（qa_id ↔ section_id ↔ document_id）
- MongoDB section_data.atomic_qa: QA 正文数组（question/answer/source_chunk_ids/...）
  按 section_id 局部 $set（一个 section 一条 MongoWriteMessage，atomic_qa 整组替换）
- Milvus atomic_qa_store: QA 向量（id=qa_id, 向量化源=question, 标量含 section_id）

设计原则：
- 与 SectionSummaryResult / FileSummaryResult 的转换方法风格保持一致。
- 一个文档对应多个 AtomicQAItem（每个 QA 一条），跨 section。
- chunk 级溯源由 source_chunk_ids 承担（LLM 用 [Cn] 占位符 → 后处理替换为真实 chunk_id）。
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid


class AtomicQAItem(BaseModel):
    """
    单条原子问答（Atomic QA）产出

    抽取粒度：section 级（一次 LLM 调用覆盖一个 section 的 N 个 chunk）；
    溯源粒度：chunk 级（source_chunk_ids 可含多个 chunk，QA 可横跨 chunk）。
    """

    # ========== 主键 / 溯源 ==========
    qa_id: str = Field(
        default_factory=lambda: f"atomic-qa-{uuid.uuid4()}",
        description="AtomicQA 唯一 ID（Milvus atomic_qa_store 主键、MySQL section_atomic_qa.qa_id）"
    )
    section_id: str = Field(
        ...,
        description="所属 Section ID（QA 在该 section 级抽取；Mongo section_data.atomic_qa 按 section_id 落库）"
    )
    document_id: str = Field(
        ...,
        description="所属 Document ID（document-{uuid}）"
    )

    # ========== QA 正文 ==========
    question: str = Field(
        ...,
        min_length=1,
        description="问题文本（同时作为 Milvus 向量化源；检索侧 qa_dense 按问题向量召回）"
    )
    answer: str = Field(
        ...,
        min_length=1,
        description="答案文本（基于 section 正文凝练，忠实不臆造）"
    )

    # ========== chunk 级溯源 ==========
    source_chunk_ids: List[str] = Field(
        default_factory=list,
        description=(
            "该 QA 答案所依据的 chunk_id 列表（LLM 用 [Cn] 占位符标注 → "
            "后处理替换为真实 chunk_id）。可含多个 chunk，体现 QA 横跨 chunk。"
        )
    )

    # ========== LLM 抽取的元信息 ==========
    qa_type: str = Field(
        default="factual",
        description=(
            "QA 类型（factual=事实型 / procedural=流程型 / conceptual=概念型 / "
            "comparative=对比型）。供检索侧按类型过滤。"
        )
    )
    relevance: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="QA 与文档主题相关度（0-1，file_summary 锚点约束下评估）"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="创建时间（ISO 8601）"
    )

    # ========== 知识库归属（写入 MySQL 关联表需要）==========
    knowledge_base_id: Optional[str] = Field(default=None, description="知识库 ID")
    knowledge_base_name: Optional[str] = Field(default=None, description="知识库名称")

    # ========== 转换方法 ==========

    def to_mysql_dict(self) -> Dict[str, Any]:
        """转换为 MySQL section_atomic_qa 表的字典格式。"""
        return {
            "qa_id": self.qa_id,
            "section_id": self.section_id,
            "document_id": self.document_id,
            "knowledge_base_id": self.knowledge_base_id or "",
            "knowledge_base_name": self.knowledge_base_name or "",
        }

    def to_mongodb_qa_dict(self) -> Dict[str, Any]:
        """转换为 MongoDB section_data.atomic_qa[] 单条条目格式（不含 _id，_id 由外层 section 提供）。"""
        return {
            "qa_id": self.qa_id,
            "question": self.question,
            "answer": self.answer,
            "source_chunk_ids": self.source_chunk_ids,
            "qa_type": self.qa_type,
            "relevance": self.relevance,
            "created_at": self.created_at,
        }

    def to_embedding_message_dict(self) -> Dict[str, Any]:
        """转换为 db_write.embedding.start 的 item 格式（Milvus atomic_qa_store，向量化源=question）。"""
        return {
            "id": self.qa_id,
            "text": self.question,
            "metadata": {
                "role": "atomic_qa",
                "section_id": self.section_id,
                "document_id": self.document_id,
                "type": self.qa_type,
                "relevance": self.relevance,
                "timestamp": int(__import__("time").time()),
            },
        }


class TextAnalyzerResult(BaseModel):
    """
    文本分析（atomic_qa 抽取）结果聚合

    由 TextAnalyzerService.analyze_document() 返回，
    TextAnalyzerWorker 据此分发到 db_write.* Topics + 发送 analyze.end。
    """

    document_id: str = Field(..., description="所属 Document ID")

    items: List[AtomicQAItem] = Field(
        default_factory=list,
        description="各 atomic_qa 产出列表（跨 section）"
    )

    llm_model: str = Field(..., description="使用的 LLM 模型名称")

    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token 使用统计（input, output, total）"
    )

    # 知识库归属（透传到 MySQL 关联表）
    knowledge_base_id: Optional[str] = Field(default=None)
    knowledge_base_name: Optional[str] = Field(default=None)

    # 统计
    section_count: int = Field(
        default=0,
        ge=0,
        description="参与抽取的 section 数"
    )
    llm_call_count: int = Field(
        default=0,
        ge=0,
        description="实际发起的 LLM 调用次数（含分批）"
    )

    # ========== 状态 / 统计 ==========

    def is_success(self) -> bool:
        """至少产出一条 QA 视为成功。"""
        return len(self.items) > 0

    @property
    def total_qa(self) -> int:
        return len(self.items)

    # ========== 数据转换方法（与 SectionSummaryResult / FileSummaryResult 风格一致）==========

    def get_mysql_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取用于 MySQL 的所有数据。

        Returns:
            {"section_atomic_qa": [item.to_mysql_dict() ...]} 或空列表
        """
        return {
            "section_atomic_qa": [item.to_mysql_dict() for item in self.items]
        }

    def get_mongodb_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取用于 MongoDB 的所有数据。

        按 section_id 聚合：一个 section 一条 MongoWriteMessage，
        atomic_qa 为该 section 下全部 QA 的数组（UPSERT $set 整组替换，幂等）。

        Returns:
            {"section_data": [{"_id": section_id, "atomic_qa": [...]}, ...]}
        """
        section_qa_map: Dict[str, List[Dict[str, Any]]] = {}
        for item in self.items:
            section_qa_map.setdefault(item.section_id, []).append(
                item.to_mongodb_qa_dict()
            )
        return {
            "section_data": [
                {"_id": section_id, "atomic_qa": qa_list}
                for section_id, qa_list in section_qa_map.items()
            ]
        }

    def get_embedding_messages(self) -> List[Dict[str, Any]]:
        """获取 Milvus atomic_qa_store 的 Embedding 消息列表（向量化源=question）。"""
        return [item.to_embedding_message_dict() for item in self.items]

    def get_analyze_end_stats(self) -> Dict[str, Any]:
        """
        供 AnalyzeEndMessage 携带的轻量统计（决策 a：轻量，不含正文）。

        Returns:
            {total_sections, total_qa, llm_call_count}
        """
        return {
            "total_sections": self.section_count,
            "total_qa": self.total_qa,
            "llm_call_count": self.llm_call_count,
        }
