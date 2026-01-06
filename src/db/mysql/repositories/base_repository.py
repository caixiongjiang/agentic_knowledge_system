#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : base_repository.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    基础 Repository 类，提供通用 CRUD 操作
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.db.mysql.models.base_model import BaseModel

# 泛型类型
ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """
    基础 Repository 类
    
    提供通用的 CRUD 操作：
    - create: 创建单条记录
    - bulk_create: 批量创建记录
    - get_by_id: 根据主键查询
    - get_all: 查询所有记录（未删除）
    - update: 更新记录
    - delete: 软删除记录
    - bulk_delete_by_ids: 批量软删除
    - upsert: 插入或更新
    """
    
    def __init__(self, model: Type[ModelType]):
        """
        初始化 Repository
        
        Args:
            model: SQLAlchemy 模型类
        """
        self.model = model
        self.model_name = model.__name__
    
    def create(
        self, 
        session: Session, 
        **kwargs
    ) -> Optional[ModelType]:
        """
        创建单条记录
        
        Args:
            session: 数据库会话
            **kwargs: 模型字段及其值
        
        Returns:
            创建的模型实例，失败返回 None
        
        Examples:
            >>> repo = BaseRepository(ChunkSectionDocument)
            >>> obj = repo.create(
            ...     session,
            ...     chunk_id="uuid-123",
            ...     section_id="uuid-456"
            ... )
        """
        try:
            obj = self.model(**kwargs)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            logger.debug(f"成功创建{self.model_name}记录")
            return obj
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"创建{self.model_name}记录失败: {e}")
            return None
    
    def bulk_create(
        self, 
        session: Session, 
        batch_data: List[Dict[str, Any]]
    ) -> List[ModelType]:
        """
        批量创建记录
        
        Args:
            session: 数据库会话
            batch_data: 批量数据列表，每个元素是字典
        
        Returns:
            创建的模型实例列表
        
        Examples:
            >>> repo = BaseRepository(ChunkSectionDocument)
            >>> objs = repo.bulk_create(session, [
            ...     {"chunk_id": "uuid-1", "section_id": "sec-1"},
            ...     {"chunk_id": "uuid-2", "section_id": "sec-2"}
            ... ])
        """
        try:
            objects = []
            for data in batch_data:
                obj = self.model(**data)
                objects.append(obj)
            
            session.add_all(objects)
            session.commit()
            
            # 刷新所有对象以获取数据库生成的字段
            for obj in objects:
                session.refresh(obj)
            
            logger.debug(f"成功批量创建{len(objects)}个{self.model_name}记录")
            return objects
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"批量创建{self.model_name}记录失败: {e}")
            return []
    
    def get_by_id(
        self, 
        session: Session, 
        id_value: Any
    ) -> Optional[ModelType]:
        """
        根据主键查询单条记录
        
        Args:
            session: 数据库会话
            id_value: 主键值
        
        Returns:
            模型实例，未找到返回 None
        """
        try:
            # 获取主键列名
            pk_columns = [c for c in self.model.__table__.columns if c.primary_key]
            if not pk_columns:
                logger.error(f"{self.model_name} 没有定义主键")
                return None
            
            pk_column = pk_columns[0]
            
            result = session.query(self.model).filter(
                pk_column == id_value,
                self.model.deleted == 0
            ).first()
            
            if not result:
                logger.debug(f"未找到{self.model_name}记录: {id_value}")
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"查询{self.model_name}记录失败: {e}")
            return None
    
    def get_all(
        self, 
        session: Session,
        limit: int = 100,
        offset: int = 0
    ) -> List[ModelType]:
        """
        查询所有记录（未删除）
        
        Args:
            session: 数据库会话
            limit: 限制数量
            offset: 偏移量
        
        Returns:
            模型实例列表
        """
        try:
            results = session.query(self.model).filter(
                self.model.deleted == 0
            ).limit(limit).offset(offset).all()
            
            logger.debug(f"查询到{len(results)}个{self.model_name}记录")
            return results
        except SQLAlchemyError as e:
            logger.error(f"查询{self.model_name}记录失败: {e}")
            return []
    
    def update(
        self, 
        session: Session,
        id_value: Any,
        updater: str = "",
        **kwargs
    ) -> Optional[ModelType]:
        """
        更新记录
        
        Args:
            session: 数据库会话
            id_value: 主键值
            updater: 更新者
            **kwargs: 要更新的字段
        
        Returns:
            更新后的模型实例，失败返回 None
        """
        try:
            obj = self.get_by_id(session, id_value)
            if not obj:
                return None
            
            # 更新字段
            for key, value in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            
            # 更新审计字段
            obj.updater = updater
            obj.update_time = datetime.now()
            
            session.commit()
            session.refresh(obj)
            
            logger.debug(f"成功更新{self.model_name}记录: {id_value}")
            return obj
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新{self.model_name}记录失败: {e}")
            return None
    
    def delete(
        self, 
        session: Session,
        id_value: Any,
        updater: str = ""
    ) -> bool:
        """
        软删除记录
        
        Args:
            session: 数据库会话
            id_value: 主键值
            updater: 更新者
        
        Returns:
            删除成功返回 True，否则返回 False
        """
        try:
            obj = self.get_by_id(session, id_value)
            if obj:
                obj.deleted = 1
                obj.updater = updater
                obj.update_time = datetime.now()
                session.commit()
                logger.debug(f"成功删除{self.model_name}记录: {id_value}")
                return True
            
            logger.debug(f"未找到要删除的{self.model_name}记录: {id_value}")
            return False
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"删除{self.model_name}记录失败: {e}")
            return False
    
    def bulk_delete_by_ids(
        self, 
        session: Session,
        id_values: List[Any],
        updater: str = ""
    ) -> bool:
        """
        批量软删除记录
        
        Args:
            session: 数据库会话
            id_values: 主键值列表
            updater: 更新者
        
        Returns:
            删除成功返回 True，否则返回 False
        """
        try:
            if not id_values:
                return True
            
            # 获取主键列
            pk_columns = [c for c in self.model.__table__.columns if c.primary_key]
            if not pk_columns:
                logger.error(f"{self.model_name} 没有定义主键")
                return False
            
            pk_column = pk_columns[0]
            
            updated_count = session.query(self.model).filter(
                pk_column.in_(id_values),
                self.model.deleted == 0
            ).update({
                'deleted': 1,
                'updater': updater,
                'update_time': datetime.now()
            }, synchronize_session=False)
            
            session.commit()
            logger.debug(f"批量删除{self.model_name}记录: {updated_count}条")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"批量删除{self.model_name}记录失败: {e}")
            return False
    
    def upsert(
        self, 
        session: Session,
        id_value: Any,
        creator: str = "",
        updater: str = "",
        **kwargs
    ) -> Optional[ModelType]:
        """
        插入或更新（如果记录存在则更新，不存在则创建）
        
        Args:
            session: 数据库会话
            id_value: 主键值
            creator: 创建者
            updater: 更新者
            **kwargs: 字段值
        
        Returns:
            模型实例，失败返回 None
        """
        try:
            existing_obj = self.get_by_id(session, id_value)
            
            if existing_obj:
                # 记录已存在，更新
                logger.debug(f"{self.model_name} {id_value} 已存在，更新记录")
                
                for key, value in kwargs.items():
                    if value is not None and hasattr(existing_obj, key):
                        setattr(existing_obj, key, value)
                
                existing_obj.updater = updater
                existing_obj.update_time = datetime.now()
                
                session.commit()
                session.refresh(existing_obj)
                
                logger.debug(f"成功更新{self.model_name}记录: {id_value}")
                return existing_obj
            else:
                # 记录不存在，创建
                logger.debug(f"{self.model_name} {id_value} 不存在，创建新记录")
                
                # 获取主键列名
                pk_columns = [c.name for c in self.model.__table__.columns if c.primary_key]
                if pk_columns:
                    kwargs[pk_columns[0]] = id_value
                
                kwargs['creator'] = creator
                
                return self.create(session, **kwargs)
        
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"{self.model_name} upsert操作失败: {e}")
            return None
