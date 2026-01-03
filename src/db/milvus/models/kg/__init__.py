#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
KG Layer Models
知识图谱层Schema - 知识图谱实体和关系
"""

from src.db.milvus.models.kg.spo_schema import SPOSchema, SPOSchemaZh, SPOSchemaEn
from src.db.milvus.models.kg.tag_schema import TagSchema, TagSchemaZh, TagSchemaEn

__all__ = [
    "SPOSchema",
    "SPOSchemaZh",
    "SPOSchemaEn",
    "TagSchema",
    "TagSchemaZh",
    "TagSchemaEn",
]
