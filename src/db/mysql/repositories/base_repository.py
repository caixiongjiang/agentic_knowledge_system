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
from sqlalchemy.dialects.mysql import insert as mysql_insert
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
            
            # 更新审计字段（update_time 由数据库 onupdate 自动处理）
            obj.updater = updater
            
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
                # update_time 由数据库 onupdate 自动处理
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
                'updater': updater
                # update_time 由数据库 onupdate 自动处理
            }, synchronize_session='fetch')
            
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
                # update_time 由数据库 onupdate 自动处理
                
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

    # ========== 真正的批量 UPDATE / UPSERT ==========

    def _primary_key_name(self) -> Optional[str]:
        """返回单列主键的列名；复合主键或无主键返回 None。"""
        pk_cols = [c for c in self.model.__table__.columns if c.primary_key]
        if len(pk_cols) != 1:
            return None
        return pk_cols[0].name

    def bulk_update(
        self,
        session: Session,
        rows: List[Dict[str, Any]],
        updater: str = "",
        extra_set: Optional[Dict[str, Any]] = None
    ) -> List[bool]:
        """批量 UPDATE，单次 round-trip（SQLAlchemy bulk_update_mappings）。

        Args:
            session: 数据库会话
            rows: 每行必须包含主键字段 + 需要更新的字段
            updater: 写入 updater 审计字段的值
            extra_set: 额外要统一 set 的字段（如 status）

        Returns:
            每行对应的成功标志（True/False）。批量整体失败时回退到逐条 update。
        """
        if not rows:
            return []

        pk_name = self._primary_key_name()
        if not pk_name:
            logger.error(f"{self.model_name} 无单列主键，无法 bulk_update")
            return [False] * len(rows)

        # 准备 mappings：包含主键 + 待更新字段 + 审计字段
        mappings: List[Dict[str, Any]] = []
        for row in rows:
            if pk_name not in row:
                logger.error(f"{self.model_name} bulk_update 行缺少主键 {pk_name}: {row}")
                return [False] * len(rows)
            mapping = {k: v for k, v in row.items()}
            mapping["updater"] = updater
            if extra_set:
                mapping.update(extra_set)
            mappings.append(mapping)

        try:
            session.bulk_update_mappings(self.model, mappings)
            session.commit()
            logger.debug(f"成功 bulk_update {len(mappings)} 条 {self.model_name}")
            return [True] * len(rows)
        except SQLAlchemyError as e:
            session.rollback()
            logger.warning(
                f"{self.model_name} bulk_update 整批失败({len(rows)}条)，降级逐条: {e}"
            )
            # 降级：逐条 update，精准定位坏数据
            results: List[bool] = []
            for row in rows:
                pk_val = row.get(pk_name)
                update_fields = {k: v for k, v in row.items() if k != pk_name}
                ok = self.update(session, pk_val, updater=updater, **update_fields) is not None
                results.append(ok)
            return results

    def bulk_upsert(
        self,
        session: Session,
        rows: List[Dict[str, Any]],
        creator: str = "",
        updater: str = "",
    ) -> List[bool]:
        """批量 UPSERT（INSERT ... ON DUPLICATE KEY UPDATE）。

        MySQL 走原生 ON DUPLICATE KEY UPDATE（单次 round-trip）；
        非 MySQL 方言（如 SQLite）自动降级为逐条 upsert。

        Args:
            session: 数据库会话
            rows: 每行必须包含主键字段 + 全部字段值
            creator / updater: 审计字段

        Returns:
            每行对应的成功标志。
        """
        if not rows:
            return []

        pk_name = self._primary_key_name()
        if not pk_name:
            logger.error(f"{self.model_name} 无单列主键，无法 bulk_upsert")
            return [False] * len(rows)

        # 统一补齐审计字段
        prepared: List[Dict[str, Any]] = []
        for row in rows:
            r = dict(row)
            r.setdefault("creator", creator)
            r.setdefault("updater", updater)
            prepared.append(r)

        bind = session.bind
        # SQLAlchemy 2.0 移除了 Inspector.get_dialect()；Engine 直接暴露 .dialect
        dialect_name = bind.dialect.name if bind is not None else "mysql"

        if dialect_name == "mysql":
            try:
                # 收集需要在冲突时更新的列（除主键、creator 外的所有列）
                update_cols = {
                    col: prepared[0][col]
                    for col in prepared[0]
                    if col != pk_name and col != "creator"
                }
                stmt = mysql_insert(self.model.__table__).values(prepared)
                # ON DUPLICATE KEY UPDATE：用 INSERTED 引用待插入的值
                stmt = stmt.on_duplicate_key_update(
                    **{col: getattr(stmt.inserted, col) for col in update_cols}
                )
                session.execute(stmt)
                session.commit()
                logger.debug(f"成功 bulk_upsert(MySQL) {len(prepared)} 条 {self.model_name}")
                return [True] * len(rows)
            except SQLAlchemyError as e:
                session.rollback()
                logger.warning(
                    f"{self.model_name} bulk_upsert(MySQL) 整批失败({len(rows)}条)，降级逐条: {e}"
                )
                return self._upsert_row_by_row(session, prepared, pk_name, creator, updater)
        else:
            # SQLite 等不支持 ON DUPLICATE KEY UPDATE 的方言，直接逐条
            return self._upsert_row_by_row(session, prepared, pk_name, creator, updater)

    def _upsert_row_by_row(
        self,
        session: Session,
        rows: List[Dict[str, Any]],
        pk_name: str,
        creator: str,
        updater: str,
    ) -> List[bool]:
        """逐条 upsert 兜底，用于非 MySQL 方言或整批失败降级。"""
        results: List[bool] = []
        for row in rows:
            pk_val = row.get(pk_name)
            fields = {k: v for k, v in row.items() if k != pk_name}
            ok = self.upsert(
                session,
                id_value=pk_val,
                creator=creator,
                updater=updater,
                **fields,
            ) is not None
            results.append(ok)
        return results
