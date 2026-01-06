#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : factory.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    MySQL 连接管理器工厂，根据配置自动创建对应的连接管理器
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Literal, Optional, Dict, Any
from loguru import logger
from src.db.mysql.connection.base import BaseMySQLManager
from src.db.mysql.connection.sqlite_manager import SQLiteManager
from src.db.mysql.connection.mysql_manager import MySQLServerManager
from src.utils.config_manager import get_config_manager

config_manager = get_config_manager()

DatabaseType = Literal["sqlite", "mysql"]


class MySQLManagerFactory:
    """MySQL 连接管理器工厂"""
    
    _managers: Dict[str, BaseMySQLManager] = {}
    
    @classmethod
    def get_manager(
        cls, 
        db_type: Optional[DatabaseType] = None,
        **kwargs
    ) -> BaseMySQLManager:
        """
        获取数据库连接管理器
        
        Args:
            db_type: 数据库类型（"sqlite" 或 "mysql"），
                    如果不指定则从配置文件的 mysql.mode 读取
            **kwargs: 传递给管理器的额外参数，会覆盖配置文件的值
        
        Returns:
            BaseMySQLManager: 数据库连接管理器实例
        
        配置文件示例 (config.toml):
            [mysql]
            mode = "mysql"  # 或 "sqlite"
            
            # MySQL Server配置
            host = "192.168.201.14"
            port = 3306
            database = "default"
            
            # SQLite配置
            sqlite_db_path = "data/sqlite.db"
            sqlite_echo = false
        
        Examples:
            # 使用 SQLite
            manager = MySQLManagerFactory.get_manager("sqlite")
            
            # 使用 MySQL Server
            manager = MySQLManagerFactory.get_manager("mysql")
            
            # 从配置文件读取（读取 mysql.mode）
            manager = MySQLManagerFactory.get_manager()
            
            # 使用自定义参数覆盖配置
            manager = MySQLManagerFactory.get_manager("sqlite", db_path="data/test.db")
        """
        # 如果未指定类型，从配置文件读取
        if db_type is None:
            db_type = config_manager.get("mysql.mode", "mysql")
            if db_type not in ["sqlite", "mysql"]:
                logger.warning(
                    f"配置中的数据库类型 '{db_type}' 不支持，"
                    f"使用默认值 'mysql'"
                )
                db_type = "mysql"
        
        # 检查是否已创建该类型的管理器
        if db_type in cls._managers:
            return cls._managers[db_type]
        
        # 创建新的管理器
        if db_type == "sqlite":
            # 从配置文件读取 SQLite 配置
            db_path = kwargs.get("db_path", config_manager.get("mysql.sqlite_db_path", "data/sqlite.db"))
            echo = kwargs.get("echo", config_manager.get("mysql.sqlite_echo", False))
            manager = SQLiteManager(
                db_path=db_path,
                echo=echo
            )
        elif db_type == "mysql":
            # 从配置文件读取 MySQL Server 配置
            mysql_config = config_manager.get("mysql", {})
            manager = MySQLServerManager(
                host=kwargs.get("host") if "host" in kwargs else mysql_config.get("host"),
                port=kwargs.get("port") if "port" in kwargs else mysql_config.get("port"),
                user=kwargs.get("user") if "user" in kwargs else mysql_config.get("user"),
                password=kwargs.get("password") if "password" in kwargs else None,
                database=kwargs.get("database") if "database" in kwargs else mysql_config.get("database"),
                pool_size=kwargs.get("pool_size") if "pool_size" in kwargs else mysql_config.get("pool_size", 5),
                max_overflow=kwargs.get("max_overflow") if "max_overflow" in kwargs else mysql_config.get("max_overflow", 10),
                pool_timeout=kwargs.get("pool_timeout") if "pool_timeout" in kwargs else mysql_config.get("pool_timeout", 30),
                pool_recycle=kwargs.get("pool_recycle") if "pool_recycle" in kwargs else mysql_config.get("pool_recycle", 3600),
                echo=kwargs.get("echo") if "echo" in kwargs else mysql_config.get("echo", False)
            )
        else:
            raise ValueError(
                f"不支持的数据库类型: {db_type}，"
                f"支持的类型: sqlite, mysql"
            )
        
        # 缓存管理器实例
        cls._managers[db_type] = manager
        logger.info(f"创建 {db_type} 连接管理器")
        
        return manager
    
    @classmethod
    def close_all(cls) -> None:
        """关闭所有连接管理器"""
        for db_type, manager in cls._managers.items():
            manager.close()
            logger.info(f"关闭 {db_type} 连接管理器")
        cls._managers.clear()


# 便捷函数
def get_mysql_manager(db_type: Optional[DatabaseType] = None, **kwargs) -> BaseMySQLManager:
    """
    获取数据库连接管理器（便捷函数）
    
    Args:
        db_type: 数据库类型（"sqlite" 或 "mysql"）
        **kwargs: 传递给管理器的额外参数
    
    Returns:
        BaseMySQLManager: 数据库连接管理器实例
    
    Examples:
        # 使用 SQLite
        manager = get_mysql_manager("sqlite")
        
        # 使用 MySQL Server
        manager = get_mysql_manager("mysql")
        
        # 从配置文件读取
        manager = get_mysql_manager()
    """
    return MySQLManagerFactory.get_manager(db_type, **kwargs)
