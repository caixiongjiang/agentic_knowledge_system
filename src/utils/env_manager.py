#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : env_manager.py
@Author  : caixiongjiang
@Date    : 2025/12/30 17:30
@Function: 
    环境变量管理器，负责加载和管理所有敏感信息配置
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from loguru import logger


class EnvManager:
    """环境变量管理器"""
    
    # 默认环境变量文件路径（相对于项目根目录）
    DEFAULT_ENV_PATH = Path(__file__).parent.parent.parent / ".env"
    
    # 必需的环境变量列表（根据实际使用情况动态判断）
    _critical_vars = {
        "APP_SECRET_KEY",
        "APP_ENV",
    }
    
    def __init__(self, env_file: Optional[str] = None):
        """
        初始化环境变量管理器
        
        Args:
            env_file: .env 文件路径，如果为None则使用默认路径
        """
        self._env_file = env_file
        self._env_vars: Dict[str, str] = {}
        self._load_env()
    
    def _load_env(self) -> None:
        """加载环境变量"""
        # 确定环境变量文件路径
        if self._env_file:
            env_path = Path(self._env_file)
        else:
            env_path = self.DEFAULT_ENV_PATH
        
        # 检查文件是否存在
        if not env_path.exists():
            logger.warning(f"环境变量文件不存在: {env_path}，将仅使用系统环境变量")
            return
        
        # 加载.env文件
        load_dotenv(env_path, override=True)
        logger.info(f"已加载环境变量文件: {env_path}")
        
        # 缓存环境变量
        self._cache_env_vars()
    
    def _cache_env_vars(self) -> None:
        """缓存环境变量到内存"""
        self._env_vars = dict(os.environ)
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        获取环境变量
        
        Args:
            key: 环境变量名
            default: 默认值
            
        Returns:
            环境变量值
        """
        return os.getenv(key, default)
    
    def get_required(self, key: str) -> str:
        """
        获取必需的环境变量，如果不存在则抛出异常
        
        Args:
            key: 环境变量名
            
        Returns:
            环境变量值
            
        Raises:
            ValueError: 如果环境变量不存在
        """
        value = self.get(key)
        if value is None:
            raise ValueError(f"必需的环境变量未设置: {key}")
        return value
    
    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """
        获取整数类型的环境变量
        
        Args:
            key: 环境变量名
            default: 默认值
            
        Returns:
            整数值
        """
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning(f"环境变量 {key} 无法转换为整数: {value}，使用默认值 {default}")
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        获取布尔类型的环境变量
        
        Args:
            key: 环境变量名
            default: 默认值
            
        Returns:
            布尔值
        """
        value = self.get(key)
        if value is None:
            return default
        
        # 支持多种布尔值表示
        true_values = {"true", "1", "yes", "on", "t", "y"}
        false_values = {"false", "0", "no", "off", "f", "n"}
        
        value_lower = value.lower().strip()
        if value_lower in true_values:
            return True
        elif value_lower in false_values:
            return False
        else:
            logger.warning(f"环境变量 {key} 的值 '{value}' 无法识别为布尔值，使用默认值 {default}")
            return default
    
    def get_list(self, key: str, separator: str = ",", default: Optional[List[str]] = None) -> List[str]:
        """
        获取列表类型的环境变量
        
        Args:
            key: 环境变量名
            separator: 分隔符
            default: 默认值
            
        Returns:
            列表
        """
        value = self.get(key)
        if value is None:
            return default or []
        
        return [item.strip() for item in value.split(separator) if item.strip()]
    
    def validate_required_vars(self, required_vars: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        验证必需的环境变量是否都已设置
        
        Args:
            required_vars: 必需的环境变量列表，如果为None则使用默认列表
            
        Returns:
            验证结果字典，key为变量名，value为是否存在
        """
        if required_vars is None:
            required_vars = list(self._critical_vars)
        
        results = {}
        for var in required_vars:
            results[var] = self.get(var) is not None
        
        return results
    
    def check_health(self) -> bool:
        """
        检查环境变量健康状态
        
        Returns:
            是否健康
        """
        validation_results = self.validate_required_vars()
        missing_vars = [var for var, exists in validation_results.items() if not exists]
        
        if missing_vars:
            logger.error(f"缺少必需的环境变量: {', '.join(missing_vars)}")
            return False
        
        logger.info("环境变量健康检查通过")
        return True
    
    # ==================== 数据库认证信息获取 ====================
    
    def get_milvus_auth(self) -> Dict[str, str]:
        """获取Milvus认证信息"""
        return {
            "user": self.get("MILVUS_USER", "root"),
            "password": self.get("MILVUS_PASSWORD", ""),
            "token": self.get("MILVUS_TOKEN", ""),
        }
    
    def get_mongodb_auth(self) -> Dict[str, str]:
        """获取MongoDB认证信息"""
        uri = self.get("MONGODB_URI")
        if uri:
            return {"uri": uri}
        
        return {
            "user": self.get("MONGODB_USER", ""),
            "password": self.get("MONGODB_PASSWORD", ""),
            "auth_source": self.get("MONGODB_AUTH_SOURCE", "admin"),
        }
    
    def get_mysql_auth(self) -> Dict[str, str]:
        """获取MySQL认证信息"""
        return {
            "user": self.get("MYSQL_USER", "root"),
            "password": self.get("MYSQL_PASSWORD", ""),
        }
    
    def get_neo4j_auth(self) -> Dict[str, str]:
        """获取Neo4j认证信息"""
        return {
            "user": self.get("NEO4J_USER", "neo4j"),
            "password": self.get("NEO4J_PASSWORD", ""),
        }
    
    def get_redis_auth(self) -> Dict[str, str]:
        """获取Redis认证信息"""
        return {
            "username": self.get("REDIS_USERNAME", ""),
            "password": self.get("REDIS_PASSWORD", ""),
        }
    
    def get_minio_auth(self) -> Dict[str, str]:
        """获取MinIO认证信息"""
        return {
            "access_key": self.get("MINIO_ACCESS_KEY", "minioadmin"),
            "secret_key": self.get("MINIO_SECRET_KEY", ""),
        }
    
    # ==================== AI 模型 API Keys ====================
    
    def get_embedding_api_key(self) -> Optional[str]:
        """获取本地Embedding服务API Key"""
        return self.get("EMBEDDING_API_KEY")
    
    def get_openai_api_key(self) -> Optional[str]:
        """获取OpenAI API Key"""
        return self.get("OPENAI_API_KEY")
    
    def get_zhipu_api_key(self) -> Optional[str]:
        """获取智谱AI API Key"""
        return self.get("ZHIPU_API_KEY")
    
    def get_qwen_api_key(self) -> Optional[str]:
        """获取通义千问API Key"""
        return self.get("QWEN_API_KEY")
    
    def get_baidu_api_keys(self) -> Dict[str, str]:
        """获取百度千帆API Keys"""
        return {
            "api_key": self.get("BAIDU_API_KEY", ""),
            "secret_key": self.get("BAIDU_SECRET_KEY", ""),
        }
    
    def get_deepseek_api_key(self) -> Optional[str]:
        """获取DeepSeek API Key"""
        return self.get("DEEPSEEK_API_KEY")
    
    def get_anthropic_api_key(self) -> Optional[str]:
        """获取Anthropic API Key"""
        return self.get("ANTHROPIC_API_KEY")
    
    def get_cohere_api_key(self) -> Optional[str]:
        """获取Cohere API Key"""
        return self.get("COHERE_API_KEY")
    
    def get_jina_api_key(self) -> Optional[str]:
        """获取Jina AI API Key"""
        return self.get("JINA_API_KEY")
    
    # ==================== 第三方服务 ====================
    
    def get_mineru_api_key(self) -> Optional[str]:
        """获取MinerU API Key"""
        return self.get("MINERU_API_KEY")
    
    # ==================== 系统配置 ====================
    
    def get_app_env(self) -> str:
        """获取应用环境"""
        return self.get("APP_ENV", "development")
    
    def is_debug(self) -> bool:
        """是否为调试模式"""
        return self.get_bool("DEBUG", True)
    
    def get_app_secret_key(self) -> str:
        """获取应用密钥"""
        return self.get_required("APP_SECRET_KEY")
    
    def get_jwt_secret_key(self) -> Optional[str]:
        """获取JWT密钥"""
        return self.get("JWT_SECRET_KEY")


# 创建全局单例
_env_manager_instance: Optional[EnvManager] = None


def get_env_manager(env_file: Optional[str] = None) -> EnvManager:
    """
    获取环境变量管理器单例
    
    Args:
        env_file: .env文件路径
        
    Returns:
        EnvManager实例
    """
    global _env_manager_instance
    
    if _env_manager_instance is None:
        _env_manager_instance = EnvManager(env_file)
    
    return _env_manager_instance


# 便捷函数
def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """获取环境变量的便捷函数"""
    return get_env_manager().get(key, default)


def get_required_env(key: str) -> str:
    """获取必需环境变量的便捷函数"""
    return get_env_manager().get_required(key)
