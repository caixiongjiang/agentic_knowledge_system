#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Milvus Repositories (数据访问层)
封装所有表的CRUD操作
"""

# 基类
from src.db.milvus.repositories.base_repository import BaseRepository

# Base层 Repositories
from src.db.milvus.repositories.base import ChunkRepository, SectionRepository

# Enhanced层 Repositories
from src.db.milvus.repositories.enhanced import EnhancedChunkRepository

# Extract层 Repositories
from src.db.milvus.repositories.extract import AtomicQARepository, SummaryRepository

# KG层 Repositories
from src.db.milvus.repositories.kg import SPORepository, TagRepository


__all__ = [
    # Base
    "BaseRepository",
    
    # Base layer
    "ChunkRepository",
    "SectionRepository",
    
    # Enhanced layer
    "EnhancedChunkRepository",
    
    # Extract layer
    "AtomicQARepository",
    "SummaryRepository",
    
    # KG layer
    "SPORepository",
    "TagRepository",
]
