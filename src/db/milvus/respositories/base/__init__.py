#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Base Layer Repositories
基础层数据访问
"""

from src.db.milvus.respositories.base.chunk_repository import ChunkRepository
from src.db.milvus.respositories.base.section_repository import SectionRepository

__all__ = [
    "ChunkRepository",
    "SectionRepository",
]
