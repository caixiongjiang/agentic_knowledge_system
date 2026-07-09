#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_data.py
@Author  : caixiongjiang
@Date    : 2026/1/7 16:44
@Function:
    ChunkData Schema - Chunk数据表
    存储各种类型的chunk数据，包括文本、图片等
@Modify History:
    2026/06/08 - 重构字段结构：
        - text → text_meta (JSON，存储结构化元数据)
        - 移除扁平字段：summary, image_caption, image_footnote,
          table_body, table_caption, table_footnote
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional, List, Dict, Any
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING

from src.db.mongodb.models.base_model import BaseDocument


class ChunkData(BaseDocument):
    """
    Chunk数据表

    存储文档分块后的核心内容数据，字段与 Milvus 一一对应：

    - ``search_text``    ↔ Milvus ``chunk_store``           （向量化 / 检索源，无包装）
    - ``text_meta``      结构化内容元数据（JSON），按 chunk_type 存储不同字段
    - ``enhanced_text``  ↔ Milvus ``enhanced_chunk_store`` 展示增强文本（可空）
    - ``translation``    多语言翻译
    - ``atomic_qa``      原子问答对（后续填充）
    - ``language``       chunk 语言（split 阶段按 vector_text 实测，与 Milvus 一致）
    - ``vlm_description`` VLM 图片描述历史快照（可选，高级阶段写入）

    text_meta 结构（按 chunk_type）：
    - text / code_block: {"text": "原始文本内容"}
    - image: {"image_caption": "...", "image_footnote": "...", "section_title": "...", "page_index": 0}
    - table: {"table_caption": "...", "table_body": "原始HTML/MD", "table_footnote": "..."}

    设计原则：
    - **`search_text` 是向量化与检索源**；展示文本从 text_meta 拼接。
    - **召回**：Rerank / exact_match / BM25 / dense 使用 ``search_text``。
    - **展示**：read_chunks / 预览从 ``text_meta`` 拼接。
    """

    # ========== 主键字段 ==========
    id: str = Field(
        ...,
        alias="_id",
        description="chunk唯一标识（格式：chunk_<uuid>）"
    )

    # ========== 核心字段 ==========
    chunk_type: Optional[str] = Field(
        None,
        alias="type",
        description="chunk类型：text=文本，image=图片，table=表格，code_block=代码块"
    )

    search_text: Optional[str] = Field(
        None,
        description=(
            "检索文本：Milvus chunk_store 向量化源；"
            "Rerank / exact_match / BM25 / dense 使用。"
        ),
    )

    text_meta: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "结构化内容元数据（JSON），按 chunk_type 存储不同字段。"
            "展示文本从 text_meta 拼接，不再存储扁平包装文本。"
        )
    )

    enhanced_text: Optional[str] = Field(
        None,
        description=(
            "增强文本（Section标题 + search_text），对应 Milvus enhanced_chunk_store 的向量化源；"
            "无 section 关联时可为空。"
        )
    )

    translation: List[Any] = Field(
        default_factory=list,
        description="chunk翻译内容列表（支持多语言）"
    )

    atomic_qa: List[Any] = Field(
        default_factory=list,
        description="chunk原子问答对列表"
    )

    language: Optional[str] = Field(
        None,
        description=(
            "chunk 语言（zh / en / ja / ko / ru / ar / hi / th / unknown），"
            "由 split 阶段对 vector_text 跑 detect_language 得到，按 chunk 级实测；"
            "供 MongoDB 元数据层按语言过滤，与 Milvus chunk_store.language 一致。"
        )
    )

    vlm_description: Optional[str] = Field(
        None,
        description=(
            "VLM 图片描述（高级 image_understand 阶段写入，仅作 audit 快照；"
            "实际向量化与展示统一走 text_meta 字段。)"
        )
    )

    # ========== Pydantic 配置 ==========
    class Config:
        """Pydantic 配置"""
        populate_by_name = True  # 允许使用字段名和别名

    # ========== Beanie 配置 ==========
    class Settings:
        name = "chunk_data"  # MongoDB 集合名称
        use_state_management = True  # 启用状态管理
        validate_on_save = True  # 保存时验证数据

        # 索引定义
        indexes = [
            # 软删除 + 创建时间复合索引（常用查询）
            IndexModel(
                [("deleted", ASCENDING), ("create_time", DESCENDING)],
                name="idx_deleted_create_time"
            ),

            # type 字段索引（按类型筛选）
            IndexModel(
                [("type", ASCENDING)],
                name="idx_type"
            ),
        ]

    # ========== 自定义方法 ==========

    def has_text(self) -> bool:
        """检查是否包含文本内容"""
        if not self.text_meta:
            return False
        return bool(self.text_meta.get("text"))
