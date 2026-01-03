#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
KG Layer Repositories
知识图谱层数据访问
"""

from src.db.milvus.respositories.kg.spo_repository import SPORepository
from src.db.milvus.respositories.kg.tag_repository import TagRepository

__all__ = [
    "SPORepository",
    "TagRepository",
]
