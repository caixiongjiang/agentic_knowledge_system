#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Extract Layer Models
提取层Schema - 从文本中提取的结构化知识
"""

from src.db.milvus.models.extract.atomic_qa_schema import AtomicQASchema
from src.db.milvus.models.extract.summary_schema import SummarySchema

__all__ = [
    "AtomicQASchema",
    "SummarySchema",
]
