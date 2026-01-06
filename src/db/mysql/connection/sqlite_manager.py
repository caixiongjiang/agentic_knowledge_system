#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : sqlite_manager.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    SQLite 连接管理器
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from pathlib import Path
from typing import Optional
from loguru import logger
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from src.db.mysql.connection.base import BaseMySQLManager


class SQLiteManager(BaseMySQLManager):
    """SQLite 连接管理器"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(
        self, 
        db_path: Optional[str] = None,
        echo: bool = False
    ):
        """
        初始化 SQLite 连接管理器
        
        Args:
            db_path: 数据库文件路径，默认为 data/sqlite.db
            echo: 是否打印 SQL 语句，默认 False
        """
        if self._initialized:
            return
        
        super().__init__()
        
        self.echo = echo
        self.db_path = db_path or "data/sqlite.db"
        
        # 确保数据目录存在
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=self.engine
        )
        
        self._initialized = True
        logger.info(f"SQLite 连接管理器初始化成功: {self.db_path}")
    
    def get_db_url(self) -> str:
        """获取数据库连接 URL"""
        return f"sqlite:///{self.db_path}"
    
    def _create_engine(self) -> Engine:
        """创建数据库引擎"""
        db_url = self.get_db_url()
        
        engine = create_engine(
            db_url,
            echo=self.echo,
            connect_args={"check_same_thread": False},  # SQLite 特有配置
        )
        
        # 启用 SQLite 外键约束
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        return engine
    
    def create_database(self) -> None:
        """SQLite 不需要显式创建数据库"""
        pass
