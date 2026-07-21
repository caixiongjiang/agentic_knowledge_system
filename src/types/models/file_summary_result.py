#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
FileSummaryResult 数据模型

文件级摘要抽取结果的统一数据模型，由 FileSummaryService 产出，
供 FileSummaryWorker 分发到 db_write.* Topics 落地。

设计原则：
- 与 SectionSummaryResult 的转换方法风格保持一致：
  - get_mysql_data()        → MySQL document_summary 表
  - get_mongodb_data()      → MongoDB document_data.summary 字段（结构化子文档，局部 $set 合并）
  - get_embedding_messages() → Milvus file_summary_store（role=document_summary）
- 一个文档对应一个 FileSummaryItem（与 SectionSummary 的多 item 不同）。
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import uuid


class FileSummaryItem(BaseModel):
    """
    单个文档的文件级摘要产出

    存储映射：
    - MySQL document_summary: 关联表（document_id ↔ summary_id）
    - MongoDB document_data.summary: 结构化子文档（summary_id / text / keywords / topics / ...）
    - Milvus file_summary_store: 摘要向量（id=summary_id, role=document_summary）
    """

    # ========== 主键 / 溯源 ==========
    document_id: str = Field(
        ...,
        description="所属 Document ID（document-{uuid}）"
    )

    # Milvus 主键 + MySQL 关联键；全局唯一
    summary_id: str = Field(
        default_factory=lambda: f"file-summary-{uuid.uuid4()}",
        description="文件摘要唯一 ID（Milvus 主键、MySQL document_summary.summary_id）"
    )

    # ========== 摘要内容 ==========
    summary_text: str = Field(
        ...,
        min_length=1,
        description="文件级摘要正文（LLM 产出，3-6 句）"
    )

    # ========== LLM 抽取的元信息 ==========
    keywords: List[str] = Field(
        default_factory=list,
        description="文档关键词列表（供前端展示、检索路由改写、知识库主题聚合）"
    )

    topics: List[str] = Field(
        default_factory=list,
        description="文档主题标签列表（供知识库主题分面导航、跨文档主题聚合）"
    )

    document_type: Optional[str] = Field(
        default=None,
        description=(
            "文档类型分类（如 technical / research_paper / tutorial / blog / manual）。"
            "供按类型过滤检索、差异化召回策略。"
        )
    )

    # ========== 统计 ==========
    section_count: int = Field(
        default=0,
        ge=0,
        description="参与汇总的 section 摘要数量"
    )

    chunk_count: int = Field(
        default=0,
        ge=0,
        description="全文档 chunk 总数（聚合各 section 的 chunk_count）"
    )

    language: str = Field(
        default="unknown",
        description="摘要语言（zh / en / mixed / unknown）"
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
        """转换为 MySQL document_summary 表的字典格式。"""
        return {
            "document_id": self.document_id,
            "summary_id": self.summary_id,
            "knowledge_base_id": self.knowledge_base_id or "",
            "knowledge_base_name": self.knowledge_base_name or "",
        }

    def to_mongodb_update_dict(self) -> Dict[str, Any]:
        """
        转换为 MongoDB document_data 的局部更新字典。

        MongoDB Writer 走 UPSERT（$set 局部合并），故只需携带 _id 与 summary 字段，
        不会破坏 document_data 已有的 metadata 等字段。

        结构化子文档与 section_data.summary 风格对齐。
        """
        return {
            "_id": self.document_id,
            "summary": {
                "summary_id": self.summary_id,
                "text": self.summary_text,
                "keywords": self.keywords,
                "topics": self.topics,
                "document_type": self.document_type,
                "section_count": self.section_count,
                "chunk_count": self.chunk_count,
                "language": self.language,
            },
        }

    def to_embedding_message_dict(self) -> Dict[str, Any]:
        """转换为 db_write.embedding.start 的 item 格式（Milvus file_summary_store）。"""
        return {
            "id": self.summary_id,
            "text": self.summary_text,
            "metadata": {
                "role": "document_summary",
                "document_id": self.document_id,
                "keywords": self.keywords,
                "topics": self.topics,
                "document_type": self.document_type,
                "section_count": self.section_count,
                "chunk_count": self.chunk_count,
                "language": self.language,
                "timestamp": int(__import__("time").time()),
            },
        }


class FileSummaryResult(BaseModel):
    """
    文件级摘要抽取结果聚合

    由 FileSummaryService.summarize_document() 返回，
    FileSummaryWorker 据此分发到 db_write.* Topics。
    """

    document_id: str = Field(..., description="所属 Document ID")

    item: Optional[FileSummaryItem] = Field(
        default=None,
        description="文件摘要产出（None 表示无 section 摘要可用，跳过）"
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
        """成功生成文件摘要视为成功。"""
        return self.item is not None

    # ========== 数据转换方法（与 SectionSummaryResult 风格一致）==========

    def get_mysql_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取用于 MySQL 的所有数据。

        Returns:
            {"document_summary": [item.to_mysql_dict()]} 或空列表
        """
        if self.item is None:
            return {"document_summary": []}
        return {"document_summary": [self.item.to_mysql_dict()]}

    def get_mongodb_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取用于 MongoDB 的所有数据。

        Returns:
            {"document_data": [item.to_mongodb_update_dict()]} 或空列表
        """
        if self.item is None:
            return {"document_data": []}
        return {"document_data": [self.item.to_mongodb_update_dict()]}

    def get_embedding_messages(self) -> List[Dict[str, Any]]:
        """获取 Milvus file_summary_store 的 Embedding 消息列表。"""
        if self.item is None:
            return []
        return [self.item.to_embedding_message_dict()]
