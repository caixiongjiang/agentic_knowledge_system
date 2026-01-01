#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : config_manager.py
@Author  : caixiongjiang
@Date    : 2025/12/30 17:30
@Function: 
    配置文件管理器，负责加载和管理config.toml中的公共配置
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import toml
from pathlib import Path
from typing import Any, Dict, Optional, List
from copy import deepcopy
from loguru import logger

from src.utils.env_manager import EnvManager


class ConfigManager:
    """配置文件管理器"""
    
    # 默认配置文件路径（相对于项目根目录）
    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "config.toml"
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_file: config.toml 文件路径，如果为None则使用默认路径
        """
        self._config_file = config_file
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """加载配置文件"""
        # 确定配置文件路径
        if self._config_file:
            config_path = Path(self._config_file)
        else:
            config_path = self.DEFAULT_CONFIG_PATH
        
        # 检查文件是否存在
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        # 加载TOML配置
        try:
            self._config = toml.load(config_path)
            logger.info(f"已加载配置文件: {config_path}")
        except Exception as e:
            raise ValueError(f"配置文件加载失败: {e}")
    
    def reload(self) -> None:
        """重新加载配置文件"""
        self._load_config()
        logger.info("配置文件已重新加载")
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        获取配置项（支持点号路径）
        
        Args:
            path: 配置路径，如 "milvus.host" 或 "embedding.model_name"
            default: 默认值
            
        Returns:
            配置值
            
        Examples:
            >>> config.get("milvus.host")
            'localhost'
            >>> config.get("milvus.port")
            19530
        """
        keys = path.split(".")
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        获取整个配置节
        
        Args:
            section: 配置节名称
            
        Returns:
            配置节字典的深拷贝
        """
        return deepcopy(self._config.get(section, {}))
    
    def has(self, path: str) -> bool:
        """
        检查配置项是否存在
        
        Args:
            path: 配置路径
            
        Returns:
            是否存在
        """
        keys = path.split(".")
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return False
        
        return True
    
    def get_all(self) -> Dict[str, Any]:
        """
        获取所有配置
        
        Returns:
            配置字典的深拷贝
        """
        return deepcopy(self._config)
    
    # ==================== 数据库配置获取 ====================
    
    def get_milvus_config(self) -> Dict[str, Any]:
        """获取Milvus配置"""
        return self.get_section("milvus")
    
    def get_mongodb_config(self) -> Dict[str, Any]:
        """获取MongoDB配置"""
        return self.get_section("mongodb")
    
    def get_mysql_config(self) -> Dict[str, Any]:
        """获取MySQL配置"""
        return self.get_section("mysql")
    
    def get_neo4j_config(self) -> Dict[str, Any]:
        """获取Neo4j配置"""
        return self.get_section("neo4j")
    
    def get_redis_config(self) -> Dict[str, Any]:
        """获取Redis配置"""
        return self.get_section("redis")
    
    def get_minio_config(self) -> Dict[str, Any]:
        """获取MinIO配置"""
        return self.get_section("minio")
    
    # ==================== 模型配置获取 ====================
    
    def get_embedding_config(self) -> Dict[str, Any]:
        """获取Embedding模型配置"""
        return self.get_section("embedding")
    
    def get_reranker_config(self) -> Dict[str, Any]:
        """获取Reranker模型配置"""
        return self.get_section("reranker")
    
    # ==================== 第三方服务配置获取 ====================
    
    def get_mineru_config(self) -> Dict[str, Any]:
        """获取MinerU服务配置"""
        return self.get_section("mineru")
    
    # ==================== 系统配置获取 ====================
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.get_section("logging")
    
    def get_file_upload_config(self) -> Dict[str, Any]:
        """获取文件处理配置"""
        return self.get_section("file_upload")
    
    # ==================== 配置验证 ====================
    
    def validate(self) -> Dict[str, List[str]]:
        """
        验证配置完整性
        
        Returns:
            验证结果，key为配置节名称，value为缺失的必需字段列表
        """
        validation_results = {}
        
        # 定义必需的配置节和字段
        required_configs = {
            "milvus": ["host", "port", "vector_dim"],
            "mongodb": ["host", "port", "database"],
            "mysql": ["host", "port", "database"],
            "neo4j": ["uri", "database"],
            "redis": ["host", "port"],
            "minio": ["endpoint", "default_bucket"],
            "embedding": ["provider", "model_name", "dimension"],
            "reranker": ["provider", "model_name"],
            "mineru": ["api_url"],
            "logging": ["level", "log_dir", "log_file"],
            "file_upload": ["supported_formats", "max_file_size", "temp_dir"],
        }
        
        for section, required_fields in required_configs.items():
            missing_fields = []
            section_config = self.get_section(section)
            
            for field in required_fields:
                if field not in section_config:
                    missing_fields.append(field)
            
            if missing_fields:
                validation_results[section] = missing_fields
        
        return validation_results
    
    def check_health(self) -> bool:
        """
        检查配置健康状态
        
        Returns:
            是否健康
        """
        validation_results = self.validate()
        
        if validation_results:
            for section, missing_fields in validation_results.items():
                logger.error(f"配置节 [{section}] 缺少必需字段: {', '.join(missing_fields)}")
            return False
        
        logger.info("配置健康检查通过")
        return True
    
    # ==================== 配置组装（结合环境变量） ====================
    
    def get_milvus_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """
        获取完整的Milvus配置（配置文件 + 环境变量）
        
        Args:
            env_manager: 环境变量管理器实例
            
        Returns:
            完整配置
        """
        config = self.get_milvus_config()
        auth = env_manager.get_milvus_auth()
        
        # 如果有token，优先使用token
        if auth.get("token"):
            config["token"] = auth["token"]
        else:
            config["user"] = auth["user"]
            config["password"] = auth["password"]
        
        return config
    
    def get_mongodb_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的MongoDB配置"""
        config = self.get_mongodb_config()
        auth = env_manager.get_mongodb_auth()
        
        # 如果提供了URI，直接使用
        if "uri" in auth and auth["uri"]:
            config["uri"] = auth["uri"]
        else:
            config.update({
                "username": auth["user"],
                "password": auth["password"],
                "authSource": auth["auth_source"],
            })
        
        return config
    
    def get_mysql_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的MySQL配置"""
        config = self.get_mysql_config()
        auth = env_manager.get_mysql_auth()
        config.update(auth)
        return config
    
    def get_neo4j_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的Neo4j配置"""
        config = self.get_neo4j_config()
        auth = env_manager.get_neo4j_auth()
        config.update(auth)
        return config
    
    def get_redis_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的Redis配置"""
        config = self.get_redis_config()
        auth = env_manager.get_redis_auth()
        config.update(auth)
        return config
    
    def get_minio_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的MinIO配置"""
        config = self.get_minio_config()
        auth = env_manager.get_minio_auth()
        config.update(auth)
        return config
    
    def get_embedding_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的Embedding配置"""
        config = self.get_embedding_config()
        provider = config.get("provider", "").lower()
        
        # 根据provider获取对应的API Key
        if provider == "openai":
            config["api_key"] = env_manager.get_openai_api_key()
        elif provider == "zhipu":
            config["api_key"] = env_manager.get_zhipu_api_key()
        elif provider == "qwen":
            config["api_key"] = env_manager.get_qwen_api_key()
        
        return config
    
    def get_reranker_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的Reranker配置"""
        config = self.get_reranker_config()
        provider = config.get("provider", "").lower()
        
        # 根据provider获取对应的API Key
        if provider == "cohere":
            config["api_key"] = env_manager.get_cohere_api_key()
        elif provider == "jina":
            config["api_key"] = env_manager.get_jina_api_key()
        
        return config
    
    def get_mineru_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的MinerU配置"""
        config = self.get_mineru_config()
        api_key = env_manager.get_mineru_api_key()
        
        if api_key:
            config["api_key"] = api_key
        
        return config


# 创建全局单例
_config_manager_instance: Optional[ConfigManager] = None


def get_config_manager(config_file: Optional[str] = None) -> ConfigManager:
    """
    获取配置管理器单例
    
    Args:
        config_file: 配置文件路径
        
    Returns:
        ConfigManager实例
    """
    global _config_manager_instance
    
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager(config_file)
    
    return _config_manager_instance


# 便捷函数
def get_config(path: str, default: Any = None) -> Any:
    """获取配置项的便捷函数"""
    return get_config_manager().get(path, default)


def get_config_section(section: str) -> Dict[str, Any]:
    """获取配置节的便捷函数"""
    return get_config_manager().get_section(section)
