#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Milvus Models (Schema层) - 统一导出
定义所有知识库表的结构
"""

# ========== 基础类和枚举 ==========
from src.db.milvus.models.base_schema import (
    BaseSchema,
    FieldDefinition,
    FieldType,
    MetricType,
    IndexType,
)

# ========== Base层 Schema ==========
from src.db.milvus.models.base.chunk_schema import ChunkSchema
from src.db.milvus.models.base.section_schema import SectionSchema

# ========== Enhanced层 Schema ==========
from src.db.milvus.models.enhanced.enhanced_chunk_schema import EnhancedChunkSchema

# ========== Extract层 Schema ==========
from src.db.milvus.models.extract.atomic_qa_schema import AtomicQASchema
from src.db.milvus.models.extract.summary_schema import SummarySchema

# ========== KG层 Schema ==========
from src.db.milvus.models.kg.spo_schema import SPOSchema
from src.db.milvus.models.kg.tag_schema import TagSchema

# ========== Schema集合 ==========
# 所有Schema类
ALL_SCHEMAS = [
    # Base层
    ChunkSchema,
    SectionSchema,
    # Enhanced层
    EnhancedChunkSchema,
    # Extract层
    AtomicQASchema,
    SummarySchema,
    # KG层
    SPOSchema,
    TagSchema,
]

# 按层次分组
SCHEMAS_BY_LAYER = {
    "base": [
        ChunkSchema,
        SectionSchema,
    ],
    "enhanced": [
        EnhancedChunkSchema,
    ],
    "extract": [
        AtomicQASchema,
        SummarySchema,
    ],
    "kg": [
        SPOSchema,
        TagSchema,
    ],
}


__all__ = [
    # ========== 基础类 ==========
    "BaseSchema",
    "FieldDefinition",
    "FieldType",
    "MetricType",
    "IndexType",
    
    # ========== Base层 ==========
    "ChunkSchema",
    "SectionSchema",
    
    # ========== Enhanced层 ==========
    "EnhancedChunkSchema",
    
    # ========== Extract层 ==========
    "AtomicQASchema",
    "SummarySchema",
    
    # ========== KG层 ==========
    "SPOSchema",
    "TagSchema",
    
    # ========== Schema集合 ==========
    "ALL_SCHEMAS",
    "SCHEMAS_BY_LAYER",
]
