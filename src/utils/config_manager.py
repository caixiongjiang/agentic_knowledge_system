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

from src.utils.env_manager import EnvManager, get_env_manager


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
        # 主机/端点统一来自环境变量（.env / .env.production），config.toml 不再承载 IP
        self._env_manager = get_env_manager()
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
    # 主机/端点统一从环境变量注入；config.toml 仅提供业务参数（端口/连接池/维度等）。
    
    def _milvus_section(self, env: EnvManager) -> Dict[str, Any]:
        config = self.get_section("milvus")
        config["host"] = env.get_milvus_host()
        config["database"] = env.get_milvus_database()
        return config

    def get_milvus_config(self) -> Dict[str, Any]:
        """获取Milvus配置"""
        return self._milvus_section(self._env_manager)
    
    def _mongodb_section(self, env: EnvManager) -> Dict[str, Any]:
        config = self.get_section("mongodb")
        config["host"] = env.get_mongodb_host()
        config["database"] = env.get_mongodb_database()
        return config

    def get_mongodb_config(self) -> Dict[str, Any]:
        """获取MongoDB配置"""
        return self._mongodb_section(self._env_manager)
    
    def _mysql_section(self, env: EnvManager) -> Dict[str, Any]:
        config = self.get_section("mysql")
        config["host"] = env.get_mysql_host()
        config["database"] = env.get_mysql_database()
        return config

    def get_mysql_config(self) -> Dict[str, Any]:
        """获取MySQL配置"""
        return self._mysql_section(self._env_manager)
    
    def _neo4j_section(self, env: EnvManager) -> Dict[str, Any]:
        config = self.get_section("neo4j")
        config["uri"] = env.get_neo4j_uri()
        return config

    def get_neo4j_config(self) -> Dict[str, Any]:
        """获取Neo4j配置"""
        return self._neo4j_section(self._env_manager)
    
    def _redis_section(self, env: EnvManager) -> Dict[str, Any]:
        config = self.get_section("redis")
        config["host"] = env.get_redis_host()
        config["db"] = env.get_redis_db()
        return config

    def get_redis_config(self) -> Dict[str, Any]:
        """获取Redis配置"""
        return self._redis_section(self._env_manager)
    
    def get_storage_config(self) -> Dict[str, Any]:
        """获取Storage配置"""
        return self.get_section("storage")
    
    def _minio_section(self, env: EnvManager) -> Dict[str, Any]:
        config = self.get_section("minio")
        config["endpoint"] = env.get_minio_endpoint()
        config["default_bucket"] = env.get_minio_bucket()
        return config

    def _get_minio_config(self) -> Dict[str, Any]:
        """获取MinIO配置（内部方法）"""
        return self._minio_section(self._env_manager)
    
    def _kafka_section(self, env: EnvManager) -> Dict[str, Any]:
        config = self.get_section("kafka")
        config["bootstrap_servers"] = env.get_kafka_bootstrap_servers()
        config.setdefault("consumer", {})["group_id_prefix"] = env.get_kafka_group_id_prefix()
        return config

    def get_kafka_config(self) -> Dict[str, Any]:
        """获取Kafka配置"""
        return self._kafka_section(self._env_manager)
    
    # ==================== 模型网关（LiteLLM Proxy） ====================
    # 同时被 LLM / Embedding / Reranker 复用

    def get_proxy_config(self) -> Dict[str, Any]:
        """获取 [proxy] 配置节（不含敏感字段）"""
        return self.get_section("proxy")

    def get_proxy_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """
        获取完整模型网关配置（合并 [proxy] + .env 中的 LITELLM_PROXY_*）

        优先级：环境变量 > config.toml；空字符串视为未设置。

        Returns:
            ``{api_base, api_key, default_timeout, default_max_retries}``，
            缺失字段为 None / 默认值。
        """
        proxy_cfg = self.get_proxy_config()

        env_url = env_manager.get_litellm_proxy_url()
        env_key = env_manager.get_litellm_proxy_key()

        api_base = env_url or proxy_cfg.get("api_base") or None
        if api_base == "":
            api_base = None
        api_key = env_key or None  # api_key 仅来自 .env（敏感）

        return {
            "api_base": api_base,
            "api_key": api_key,
            "default_timeout": proxy_cfg.get("default_timeout", 60),
            "default_max_retries": proxy_cfg.get("default_max_retries", 2),
        }

    # ==================== LLM 配置获取（LiteLLM 统一接入） ====================

    def get_llm_config(self) -> Dict[str, Any]:
        """获取整个 [llm] 配置节"""
        return self.get_section("llm")

    def get_llm_presets(self) -> Dict[str, Dict[str, Any]]:
        """获取所有 LLM 预设（[llm.presets]）"""
        return deepcopy(self._config.get("llm", {}).get("presets", {}) or {})

    def get_llm_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取单个 LLM preset

        Args:
            name: preset 名称（如 fast / quality / reasoning / multimodal / test）

        Returns:
            preset 字典；未配置返回 None
        """
        presets = self._config.get("llm", {}).get("presets", {}) or {}
        preset = presets.get(name)
        return deepcopy(preset) if preset else None

    # ==================== Embedding / Reranker presets ====================

    def get_embedding_config(self) -> Dict[str, Any]:
        """获取 [embedding] 配置节（业务约束 + default_preset）"""
        return self.get_section("embedding")

    def get_embedding_presets(self) -> Dict[str, Dict[str, Any]]:
        """获取所有 Embedding 预设（[embedding.presets]）"""
        return deepcopy(self._config.get("embedding", {}).get("presets", {}) or {})

    def get_embedding_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """获取单个 Embedding preset"""
        presets = self._config.get("embedding", {}).get("presets", {}) or {}
        preset = presets.get(name)
        return deepcopy(preset) if preset else None

    def _sparse_embedding_section(self, env: EnvManager) -> Dict[str, Any]:
        config = self.get_section("sparse_embedding")
        config["api_base"] = env.get_sparse_embedding_api_base()
        return config

    def get_sparse_embedding_config(self) -> Dict[str, Any]:
        """获取稀疏向量 Embedding 配置（BGE-M3，独立实现）"""
        return self._sparse_embedding_section(self._env_manager)

    def get_reranker_config(self) -> Dict[str, Any]:
        """获取 [reranker] 配置节（业务约束 + default_preset）"""
        return self.get_section("reranker")

    def get_reranker_presets(self) -> Dict[str, Dict[str, Any]]:
        """获取所有 Reranker 预设（[reranker.presets]）"""
        return deepcopy(self._config.get("reranker", {}).get("presets", {}) or {})

    def get_reranker_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """获取单个 Reranker preset"""
        presets = self._config.get("reranker", {}).get("presets", {}) or {}
        preset = presets.get(name)
        return deepcopy(preset) if preset else None
    
    # ==================== 第三方服务配置获取 ====================
    
    def _mineru_section(self, env: EnvManager) -> Dict[str, Any]:
        config = self.get_section("mineru")
        config["api_url"] = env.get_mineru_api_url()
        return config

    def get_mineru_config(self) -> Dict[str, Any]:
        """获取MinerU服务配置"""
        return self._mineru_section(self._env_manager)

    def get_libreoffice_config(self) -> Dict[str, Any]:
        """
        获取 LibreOffice 配置（用于 PPT/Word/图片 转 PDF）

        全部来自环境变量（与 MINERU_API_URL / MINIO_ENDPOINT 等主机/路径类配置一致）：
        - LIBREOFFICE_SOFFICE_PATH：soffice 可执行文件路径
            - macOS: /Applications/LibreOffice.app/Contents/MacOS/soffice
            - Linux/Docker: soffice（PATH 中）或 /usr/bin/soffice
            - 未设置时默认 "soffice"（Linux 生产装 libreoffice 后即可用）
        - LIBREOFFICE_CONVERT_TIMEOUT：转换超时（秒），未设置默认 600

        Returns:
            {soffice_path, convert_timeout}
        """
        env = self._env_manager
        soffice_path = env.get("LIBREOFFICE_SOFFICE_PATH") or "soffice"
        convert_timeout_raw = env.get("LIBREOFFICE_CONVERT_TIMEOUT")
        try:
            convert_timeout = int(convert_timeout_raw) if convert_timeout_raw else 600
        except (TypeError, ValueError):
            convert_timeout = 600
        return {
            "soffice_path": soffice_path,
            "convert_timeout": convert_timeout,
        }
    
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
        
        # 定义必需的配置节和字段（仅业务参数；主机/端点由环境变量提供，不在此校验）
        required_configs = {
            "milvus": ["port", "vector_dim"],
            "mongodb": ["port"],
            "mysql": ["port"],
            "neo4j": ["database"],
            "redis": ["port"],
            "storage": ["type"],
            "minio": [],
            "kafka": [],  # 业务参数均在子节，bootstrap_servers / group_id_prefix 由 env 提供
            "proxy": ["default_timeout"],
            "llm": ["presets"],
            "embedding": ["default_preset", "dimension", "presets"],
            "sparse_embedding": ["model_name"],  # api_base 由 env 提供
            "reranker": ["default_preset", "presets"],
            "mineru": [],  # api_url 由 env 提供
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
        config = self._milvus_section(env_manager)
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
        config = self._mongodb_section(env_manager)
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
        config = self._mysql_section(env_manager)
        auth = env_manager.get_mysql_auth()
        config.update(auth)
        return config
    
    def get_neo4j_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的Neo4j配置"""
        config = self._neo4j_section(env_manager)
        auth = env_manager.get_neo4j_auth()
        config.update(auth)
        return config
    
    def get_redis_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的Redis配置"""
        config = self._redis_section(env_manager)
        auth = env_manager.get_redis_auth()
        config.update(auth)
        return config
    
    def get_storage_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """
        获取完整的存储配置（根据 storage.type 自动获取对应配置）
        
        Args:
            env_manager: 环境变量管理器实例
            
        Returns:
            完整配置，包含存储类型和对应的认证信息
        """
        storage_config = self.get_storage_config()
        storage_type = storage_config.get("type", "minio")
        
        # 根据存储类型获取对应的完整配置
        if storage_type == "minio":
            minio_config = self._minio_section(env_manager)
            auth = env_manager.get_minio_auth()
            storage_specific_config = {**minio_config, **auth}
        elif storage_type == "oss":
            # 未来实现 OSS 配置
            storage_specific_config = {}
        elif storage_type == "gcs":
            # 未来实现 GCS 配置
            storage_specific_config = {}
        elif storage_type == "s3":
            # 未来实现 S3 配置
            storage_specific_config = {}
        else:
            storage_specific_config = {}
        
        # 合并存储配置
        result = {"type": storage_type}
        result.update(storage_specific_config)
        
        return result
    
    def get_embedding_full_config(
        self,
        env_manager: EnvManager,
        preset_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        组装完整 Embedding 配置：``[embedding]`` 业务约束 + 选定 preset + ``[proxy]`` 兜底

        Args:
            env_manager: 用于读取 ``LITELLM_PROXY_*``
            preset_name: 指定 preset；缺省时使用 ``[embedding].default_preset``

        Returns:
            合并后的 dict，包含 ``model / api_base / api_key / dimension /
            batch_size / max_concurrent / timeout`` 等键
        """
        section = self.get_embedding_config()
        chosen = preset_name or section.get("default_preset")
        if not chosen:
            raise ValueError("[embedding] 未设置 default_preset 且未传入 preset_name")
        preset = self.get_embedding_preset(chosen)
        if not preset:
            available = ", ".join(sorted(self.get_embedding_presets().keys())) or "(empty)"
            raise ValueError(f"未知 embedding preset '{chosen}'，可用: {available}")

        merged: Dict[str, Any] = {
            "dimension": section.get("dimension"),
            "batch_size": section.get("batch_size", 32),
            "max_concurrent": section.get("max_concurrent", 5),
            "timeout": section.get("timeout", 60.0),
        }
        merged.update(preset)

        proxy = self.get_proxy_full_config(env_manager)
        if not merged.get("api_base"):
            merged["api_base"] = proxy.get("api_base")
        if not merged.get("api_key"):
            merged["api_key"] = proxy.get("api_key")
        if "timeout" not in merged or merged["timeout"] is None:
            merged["timeout"] = proxy.get("default_timeout", 60.0)

        return merged

    def get_sparse_embedding_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的稀疏向量 Embedding 配置（BGE-M3，独立实现，未走 LiteLLM）"""
        config = self._sparse_embedding_section(env_manager)

        api_key = env_manager.get_sparse_embedding_api_key()
        if api_key:
            config["api_key"] = api_key

        return config

    def get_reranker_full_config(
        self,
        env_manager: EnvManager,
        preset_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        组装完整 Reranker 配置：``[reranker]`` 业务约束 + 选定 preset + ``[proxy]`` 兜底
        """
        section = self.get_reranker_config()
        chosen = preset_name or section.get("default_preset")
        if not chosen:
            raise ValueError("[reranker] 未设置 default_preset 且未传入 preset_name")
        preset = self.get_reranker_preset(chosen)
        if not preset:
            available = ", ".join(sorted(self.get_reranker_presets().keys())) or "(empty)"
            raise ValueError(f"未知 reranker preset '{chosen}'，可用: {available}")

        merged: Dict[str, Any] = {
            "batch_size": section.get("batch_size", 16),
            "top_k": section.get("top_k", 10),
            "timeout": section.get("timeout", 30.0),
        }
        merged.update(preset)

        proxy = self.get_proxy_full_config(env_manager)
        if not merged.get("api_base"):
            merged["api_base"] = proxy.get("api_base")
        if not merged.get("api_key"):
            merged["api_key"] = proxy.get("api_key")
        if "timeout" not in merged or merged["timeout"] is None:
            merged["timeout"] = proxy.get("default_timeout", 30.0)

        return merged
    
    def get_mineru_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """获取完整的MinerU配置"""
        config = self._mineru_section(env_manager)
        api_key = env_manager.get_mineru_api_key()
        
        if api_key:
            config["api_key"] = api_key
        
        return config
    
    def get_kafka_full_config(self, env_manager: EnvManager) -> Dict[str, Any]:
        """
        获取完整的Kafka配置（配置文件 + 环境变量）
        
        Args:
            env_manager: 环境变量管理器实例
            
        Returns:
            完整配置，包含认证信息
        """
        config = self._kafka_section(env_manager)
        auth = env_manager.get_kafka_auth()
        
        # 将认证信息添加到配置中
        # 注意：这里不直接合并，因为 kafka_manager 需要从环境变量中单独获取
        # 这个方法主要用于统一的配置获取接口
        config["auth"] = auth
        
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
