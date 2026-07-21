#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
SectionSummaryResult 数据模型

Section 摘要抽取结果的统一数据模型，由 SectionSummaryService 产出，
供 SectionSummaryWorker 分发到 db_write.* Topics 落地。

设计原则：
- 与 SplitResult 的转换方法风格保持一致：
  - get_mysql_data()     → MySQL section_summary 表
  - get_mongodb_data()   → MongoDB section_data.summary 字段（局部 $set 合并）
  - get_embedding_messages() → Milvus summary collection（role=section_summary）
- 不携带 chunk 原文，仅携带摘要文本与溯源 id。
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import uuid


class SectionSummaryItem(BaseModel):
    """
    单个 Section 的摘要产出

    存储映射：
    - MySQL section_summary: 关联表（section_id ↔ summary_id）
    - MongoDB section_data.summary: 摘要正文（按 section_id 局部 $set）
    - Milvus summary collection: 摘要向量（id=summary_id, role=section_summary）
    """

    # ========== 主键 / 溯源 ==========
    section_id: str = Field(
        ...,
        description="所属 Section ID（与 split 阶段一致）"
    )

    document_id: str = Field(
        ...,
        description="所属 Document ID"
    )

    # Section 标题（供下游 FileSummary 的 LLM prompt 使用；不落 MySQL/Mongo summary 子文档）
    title: str = Field(
        default="",
        description="Section 标题（供 FileSummary prompt 使用，不落 summary 子文档）"
    )

    # Milvus 主键 + MySQL 关联键；全局唯一
    summary_id: str = Field(
        default_factory=lambda: f"section-summary-{uuid.uuid4()}",
        description="Section 摘要唯一 ID（Milvus 主键、MySQL section_summary.summary_id）"
    )

    # ========== 摘要内容 ==========
    summary_text: str = Field(
        ...,
        min_length=1,
        description="Section 级摘要正文（LLM 产出）"
    )

    # ========== 统计 ==========
    chunk_count: int = Field(
        default=0,
        ge=0,
        description="该 section 下的 chunk 数量（参与摘要的）"
    )

    chunk_id_list: List[str] = Field(
        default_factory=list,
        description=(
            "该 section 及其所有后代叶子的 chunk_id 列表（去重、保序）。"
            "叶子 section = 自身 chunk_id_list；"
            "父 section = 递归合并后代叶子的 chunk_id_list。"
            "用于「Milvus 命中 summary → 拿到 chunk_id 列表下钻」检索路径。"
        )
    )

    language: str = Field(
        default="unknown",
        description="摘要语言（zh / en / mixed / unknown）"
    )

    # ========== 结构层级（用于父子 section 拼树 / rollup；v1.1 写 MySQL section_document）==========
    parent_section_id: Optional[str] = Field(
        default=None,
        description=(
            "直接父 section ID（顶级 section 为 None）。"
            "由 SectionSummaryService 建 section 树时按标题编号推断得到，"
            "写入 MySQL section_document.parent_section_id，前端骨架接口据此递归组树。"
        )
    )

    is_leaf: bool = Field(
        default=True,
        description=(
            "是否叶子 section。True=叶子（挂有 chunk，走 LLM 生成摘要）；"
            "False=父节点（rollup，由子节点摘要合成）。写入 MySQL section_document.is_leaf，"
            "用于日志/统计区分及 TextAnalyzer 叶子过滤，两类 item 结构一致，下游存储路径无差异。"
        )
    )

    # ========== 知识库归属（写入 MySQL 关联表需要）==========
    knowledge_base_id: Optional[str] = Field(
        default=None,
        description="知识库 ID"
    )

    knowledge_base_name: Optional[str] = Field(
        default=None,
        description="知识库名称"
    )

    # ========== 转换方法 ==========

    def to_mysql_dict(self) -> Dict[str, Any]:
        """转换为 MySQL section_summary 表的字典格式。"""
        return {
            "section_id": self.section_id,
            "document_id": self.document_id,
            "summary_id": self.summary_id,
            "knowledge_base_id": self.knowledge_base_id or "",
            "knowledge_base_name": self.knowledge_base_name or "",
        }

    def to_section_document_update_dict(self) -> Dict[str, Any]:
        """
        转换为 MySQL section_document 表的局部更新字典（UPSERT）。

        v1.1（2026/07/17）：parent_section_id / is_leaf 由 MongoDB section_data 迁移到
        MySQL section_document，骨架树重建与叶子过滤都在 MySQL 完成。这里只回写拓扑
        两字段 + document_id（兜底，避免极端竞态下写出缺 document_id 的残行），
        不触碰 knowledge_base_* 等 mixin 字段（由 split 阶段负责）。

        UPSERT 走 ON DUPLICATE KEY UPDATE：列只出现在 INSERT 子句里才会被更新，
        故本字典未包含的列（kb mixin）不会被覆盖。
        """
        return {
            "section_id": self.section_id,
            "document_id": self.document_id,
            "parent_section_id": self.parent_section_id,
            "is_leaf": self.is_leaf,
        }

    def to_mongodb_update_dict(self) -> Dict[str, Any]:
        """
        转换为 MongoDB section_data 的局部更新字典。

        MongoDB Writer 走 UPSERT（$set 局部合并），故只需携带 _id 与 summary 字段，
        不会破坏 section_data 已有的 text / translation 等字段。

        v1.1（2026/07/17）：parent_section_id / is_leaf 已迁移到 MySQL section_document，
        不再写入 section_data。chunk_id_list 仍写 Mongo（检索侧「summary 命中 → chunk 下钻」
        需要它，且属内容型字段，留在 Mongo 与 text/summary 一致）。
        """
        return {
            "_id": self.section_id,
            "chunk_id_list": self.chunk_id_list,
            "summary": {
                "summary_id": self.summary_id,
                "text": self.summary_text,
                "chunk_count": self.chunk_count,
                "language": self.language,
            },
        }

    def to_embedding_message_dict(self) -> Dict[str, Any]:
        """转换为 db_write.embedding.start 的 item 格式（Milvus section_summary_store）。"""
        return {
            "id": self.summary_id,
            "text": self.summary_text,
            "metadata": {
                "role": "section_summary",
                "section_id": self.section_id,
                "document_id": self.document_id,
                "chunk_count": self.chunk_count,
                "language": self.language,
                "parent_section_id": self.parent_section_id,
                "is_leaf": self.is_leaf,
                "timestamp": int(__import__("time").time()),
            },
        }


class SectionSummaryResult(BaseModel):
    """
    Section 摘要抽取结果聚合

    由 SectionSummaryService.summarize_document_sections() 返回，
    SectionSummaryWorker 据此分发到 db_write.* Topics。
    """

    document_id: str = Field(..., description="所属 Document ID")

    items: List[SectionSummaryItem] = Field(
        default_factory=list,
        description="各 section 摘要产出列表"
    )

    llm_model: str = Field(..., description="使用的 LLM 模型名称")

    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token 使用统计（input, output, total）"
    )

    # 知识库归属（透传到 MySQL 关联表）
    knowledge_base_id: Optional[str] = Field(default=None)
    knowledge_base_name: Optional[str] = Field(default=None)

    # ========== 状态 / 统计 ==========

    def is_success(self) -> bool:
        """至少有一条 section 摘要产出视为成功。"""
        return len(self.items) > 0

    @property
    def total_sections(self) -> int:
        return len(self.items)

    @property
    def successful_sections(self) -> int:
        return len(self.items)

    # ========== 数据转换方法（与 SplitResult 风格一致）==========

    def get_mysql_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取用于 MySQL 的所有数据。

        Returns:
            {
                "section_summary": [item.to_mysql_dict() ...],
                "section_document": [item.to_section_document_update_dict() ...],
            }
        """
        return {
            "section_summary": [item.to_mysql_dict() for item in self.items],
            "section_document": [item.to_section_document_update_dict() for item in self.items],
        }

    def get_mongodb_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取用于 MongoDB 的所有数据。

        Returns:
            {"section_data": [item.to_mongodb_update_dict() ...]}
        """
        return {
            "section_data": [item.to_mongodb_update_dict() for item in self.items],
        }

    def get_embedding_messages(self) -> List[Dict[str, Any]]:
        """获取 Milvus summary collection 的 Embedding 消息列表。"""
        return [item.to_embedding_message_dict() for item in self.items]

    def get_section_summaries_stats(self) -> List[Dict[str, Any]]:
        """
        供 SectionSummaryEndMessage 携带的轻量统计（不含正文）。

        Returns:
            各 section 摘要的统计字段列表
        """
        return [
            {
                "section_id": item.section_id,
                "summary_id": item.summary_id,
                "chunk_count": item.chunk_count,
                "summary_length": len(item.summary_text),
            }
            for item in self.items
        ]

    def get_section_summaries_payload(self) -> List[Dict[str, Any]]:
        """
        供 SectionSummaryEndMessage.section_summaries_payload 携带的完整数据（含正文）。

        下游 FileSummaryWorker 据此自包含消费，不读数据库，消除写库竞态。

        Returns:
            各 section 摘要的完整字段列表：
            {section_id, summary_id, title, summary_text,
             is_leaf, parent_section_id, chunk_count, language}
        """
        return [
            {
                "section_id": item.section_id,
                "summary_id": item.summary_id,
                "title": item.title,
                "summary_text": item.summary_text,
                "is_leaf": item.is_leaf,
                "parent_section_id": item.parent_section_id or "",
                "chunk_count": item.chunk_count,
                "language": item.language,
            }
            for item in self.items
        ]
