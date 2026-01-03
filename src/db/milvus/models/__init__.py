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
from src.db.milvus.models.base.chunk_schema import (
    ChunkSchema,
    ChunkSchemaZh,
    ChunkSchemaEn,
)
from src.db.milvus.models.base.section_schema import (
    SectionSchema,
    SectionSchemaZh,
    SectionSchemaEn,
)

# ========== Enhanced层 Schema ==========
from src.db.milvus.models.enhanced.enhanced_chunk_schema import (
    EnhancedChunkSchema,
    EnhancedChunkSchemaZh,
    EnhancedChunkSchemaEn,
)

# ========== Extract层 Schema ==========
from src.db.milvus.models.extract.atomic_qa_schema import (
    AtomicQASchema,
    AtomicQASchemaZh,
    AtomicQASchemaEn,
)
from src.db.milvus.models.extract.summary_schema import (
    SummarySchema,
    SummarySchemaZh,
    SummarySchemaEn,
)

# ========== KG层 Schema ==========
from src.db.milvus.models.kg.spo_schema import (
    SPOSchema,
    SPOSchemaZh,
    SPOSchemaEn,
)
from src.db.milvus.models.kg.tag_schema import (
    TagSchema,
    TagSchemaZh,
    TagSchemaEn,
)

# ========== Schema集合 ==========
# 所有基础Schema类（不包含语言变体）
ALL_BASE_SCHEMAS = [
    ChunkSchema,
    SectionSchema,
    EnhancedChunkSchema,
    AtomicQASchema,
    SummarySchema,
    SPOSchema,
    TagSchema,
]

# 所有Schema类（包含语言变体）
ALL_SCHEMAS = [
    # Base层
    ChunkSchema, ChunkSchemaZh, ChunkSchemaEn,
    SectionSchema, SectionSchemaZh, SectionSchemaEn,
    # Enhanced层
    EnhancedChunkSchema, EnhancedChunkSchemaZh, EnhancedChunkSchemaEn,
    # Extract层
    AtomicQASchema, AtomicQASchemaZh, AtomicQASchemaEn,
    SummarySchema, SummarySchemaZh, SummarySchemaEn,
    # KG层
    SPOSchema, SPOSchemaZh, SPOSchemaEn,
    TagSchema, TagSchemaZh, TagSchemaEn,
]

# 按层次分组
SCHEMAS_BY_LAYER = {
    "base": [
        ChunkSchema, ChunkSchemaZh, ChunkSchemaEn,
        SectionSchema, SectionSchemaZh, SectionSchemaEn,
    ],
    "enhanced": [
        EnhancedChunkSchema, EnhancedChunkSchemaZh, EnhancedChunkSchemaEn,
    ],
    "extract": [
        AtomicQASchema, AtomicQASchemaZh, AtomicQASchemaEn,
        SummarySchema, SummarySchemaZh, SummarySchemaEn,
    ],
    "kg": [
        SPOSchema, SPOSchemaZh, SPOSchemaEn,
        TagSchema, TagSchemaZh, TagSchemaEn,
    ],
}

# 按语言分组
SCHEMAS_BY_LANGUAGE = {
    "zh": [
        ChunkSchemaZh,
        SectionSchemaZh,
        EnhancedChunkSchemaZh,
        AtomicQASchemaZh,
        SummarySchemaZh,
        SPOSchemaZh,
        TagSchemaZh,
    ],
    "en": [
        ChunkSchemaEn,
        SectionSchemaEn,
        EnhancedChunkSchemaEn,
        AtomicQASchemaEn,
        SummarySchemaEn,
        SPOSchemaEn,
        TagSchemaEn,
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
    "ChunkSchemaZh",
    "ChunkSchemaEn",
    "SectionSchema",
    "SectionSchemaZh",
    "SectionSchemaEn",
    
    # ========== Enhanced层 ==========
    "EnhancedChunkSchema",
    "EnhancedChunkSchemaZh",
    "EnhancedChunkSchemaEn",
    
    # ========== Extract层 ==========
    "AtomicQASchema",
    "AtomicQASchemaZh",
    "AtomicQASchemaEn",
    "SummarySchema",
    "SummarySchemaZh",
    "SummarySchemaEn",
    
    # ========== KG层 ==========
    "SPOSchema",
    "SPOSchemaZh",
    "SPOSchemaEn",
    "TagSchema",
    "TagSchemaZh",
    "TagSchemaEn",
    
    # ========== Schema集合 ==========
    "ALL_BASE_SCHEMAS",
    "ALL_SCHEMAS",
    "SCHEMAS_BY_LAYER",
    "SCHEMAS_BY_LANGUAGE",
]
