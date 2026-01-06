#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_atomic_qa_repo.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    ChunkAtomicQA Repository
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.extract.chunk_atomic_qa import ChunkAtomicQA
from src.db.mysql.repositories.base_repository import BaseRepository


class ChunkAtomicQARepository(BaseRepository[ChunkAtomicQA]):
    """ChunkAtomicQA Repository"""
    
    def __init__(self):
        super().__init__(ChunkAtomicQA)
    
    def get_by_atomic_qa_id(
        self, 
        session: Session,
        atomic_qa_id: str
    ) -> Optional[ChunkAtomicQA]:
        """
        根据 atomic_qa_id 查询 ChunkAtomicQA
        
        Args:
            session: 数据库会话
            atomic_qa_id: AtomicQA ID
        
        Returns:
            ChunkAtomicQA 实例，未找到返回 None
        """
        try:
            result = session.query(self.model).filter(
                self.model.atomic_qa_id == atomic_qa_id,
                self.model.deleted == 0
            ).first()
            
            if not result:
                logger.debug(f"未找到ChunkAtomicQA: atomic_qa_id={atomic_qa_id}")
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"根据atomic_qa_id查询失败: {e}")
            return None


# 全局实例
chunk_atomic_qa_repo = ChunkAtomicQARepository()
