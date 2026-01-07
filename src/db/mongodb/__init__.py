#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2025/12/31 14:44
@Function: 
    MongoDB 数据库层统一导出
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

# 连接层
from src.db.mongodb.mongodb_manager import MongoDBManager, get_mongodb_manager

# Schema层
from src.db.mongodb.models import (
    BaseDocument,
    ChunkData,
    SectionData,
    DocumentData,
)

# Repository层
from src.db.mongodb.repositories import (
    BaseRepository,
    ChunkDataRepository,
    chunk_data_repository,
    SectionDataRepository,
    section_data_repository,
    DocumentDataRepository,
    document_data_repository,
)

__all__ = [
    # 连接层
    "MongoDBManager",
    "get_mongodb_manager",
    
    # Schema层
    "BaseDocument",
    "ChunkData",
    "SectionData",
    "DocumentData",
    
    # Repository层
    "BaseRepository",
    "ChunkDataRepository",
    "chunk_data_repository",
    "SectionDataRepository",
    "section_data_repository",
    "DocumentDataRepository",
    "document_data_repository",
]
