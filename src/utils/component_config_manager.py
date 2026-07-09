#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : component_config_manager.py
@Author  : caixiongjiang
@Date    : 2025/12/30 17:30
@Function: 
    组件配置文件管理器，负责加载和管理config/components.json中的公共配置
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger


class ComponentConfigManager:
    """
    组件配置管理器
    
    负责加载和管理 config/components.json 中的所有组件配置，包括：
    - FileParser（文件解析器）
    - TextSplitter（文本切分器）
    - SectionSummary（Section 摘要）
    - FileSummary（文件摘要）
    - KGExtractor（知识图谱提取）
    - TextAnalyzer（文本分析器 / Atomic QA）
    - RoutePlanner（检索管线 LLM₁；支持 llm 内联或 llm_preset）
    - 各种 Writers（MySQL、MongoDB、Neo4j、Embedding+Milvus）
    """
    
    _instance = None
    _config: Optional[Dict[str, Any]] = None
    _config_path: Optional[Path] = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化配置管理器"""
        if self._config is None:
            self._load_config()
    
    def _find_config_file(self) -> Path:
        """
        查找配置文件路径
        
        Returns:
            配置文件路径
        """
        # 尝试多个可能的位置
        possible_paths = [
            # 1. 从当前工作目录
            Path.cwd() / "config" / "components.json",
            # 2. 从模块路径向上查找
            Path(__file__).parent.parent.parent / "config" / "components.json",
            # 3. 从环境变量
            Path(os.getenv("COMPONENTS_CONFIG_PATH", "")) if os.getenv("COMPONENTS_CONFIG_PATH") else None,
        ]
        
        for path in possible_paths:
            if path and path.exists():
                return path
        
        # 默认路径
        default_path = Path(__file__).parent.parent.parent / "config" / "components.json"
        logger.warning(f"配置文件未找到，使用默认路径: {default_path}")
        return default_path
    
    def _load_config(self):
        """加载配置文件"""
        try:
            self._config_path = self._find_config_file()
            
            if not self._config_path.exists():
                raise FileNotFoundError(f"配置文件不存在: {self._config_path}")
            
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            
            logger.info(f"成功加载组件配置: {self._config_path}")
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {}
    
    def reload(self):
        """重新加载配置文件"""
        self._config = None
        self._load_config()
    
    # ========== 获取组件配置 ==========
    
    def get_component_config(self, component_name: str) -> Dict[str, Any]:
        """
        获取指定组件的配置
        
        Args:
            component_name: 组件名称（如 text_splitter, file_parser 等）
        
        Returns:
            组件配置字典
        """
        if self._config is None:
            self._load_config()
        
        config = self._config.get(component_name, {})
        
        if not config:
            logger.warning(f"组件 {component_name} 的配置不存在，返回空配置")
        
        return config.copy()
    
    def get_text_splitter_config(self, document_type: Optional[str] = None) -> Dict[str, Any]:
        """
        获取 TextSplitter 组件配置
        
        Args:
            document_type: 文档类型（暂不支持，保留接口用于未来扩展）
        
        Returns:
            TextSplitter 配置字典
        """
        return self.get_component_config("text_splitter")
    
    def get_file_parser_config(self) -> Dict[str, Any]:
        """获取 FileParser 组件配置"""
        return self.get_component_config("file_parser")
    
    def get_file_summary_config(self) -> Dict[str, Any]:
        """获取 FileSummary 组件配置"""
        return self.get_component_config("file_summary")

    def get_section_summary_config(self) -> Dict[str, Any]:
        """获取 SectionSummary 组件配置"""
        return self.get_component_config("section_summary")
    
    def get_kg_extractor_config(self) -> Dict[str, Any]:
        """获取 KGExtractor 组件配置"""
        return self.get_component_config("kg_extractor")
    
    def get_text_analyzer_config(self) -> Dict[str, Any]:
        """获取 TextAnalyzer 组件配置"""
        return self.get_component_config("text_analyzer")
    
    def get_mysql_writer_config(self) -> Dict[str, Any]:
        """获取 MySQLWriter 组件配置"""
        return self.get_component_config("mysql_writer")
    
    def get_mongo_writer_config(self) -> Dict[str, Any]:
        """获取 MongoWriter 组件配置"""
        return self.get_component_config("mongo_writer")
    
    def get_neo4j_writer_config(self) -> Dict[str, Any]:
        """获取 Neo4jWriter 组件配置"""
        return self.get_component_config("neo4j_writer")
    
    def get_embedding_milvus_writer_config(self) -> Dict[str, Any]:
        """获取 EmbeddingMilvusWriter 组件配置"""
        return self.get_component_config("embedding_milvus_writer")
    
    def get_route_planner_config(self) -> Dict[str, Any]:
        """获取 RoutePlanner 组件配置"""
        return self.get_component_config("route_planner")

    # ========== LLM 客户端创建 ==========

    # ``llm`` 内联字段允许出现的键（其它键会被忽略并 warning，避免 TypeError）
    _ALLOWED_LLM_KEYS = frozenset({
        "model",
        "api_base",
        "api_key",
        "temperature",
        "max_tokens",
        "timeout",
        "max_retries",
        "thinking_budget",
        "extra_params",
    })

    def get_llm_client_for_component(self, component_name: str, **kwargs):
        """
        根据组件配置创建 LLM 客户端（LiteLLM）

        组件配置优先级：``llm`` 内联 > ``llm_preset`` 引用。

        ``llm`` 内联字段示例（仅 ``model`` 必填）::

            {
              "model": "deepseek/deepseek-chat",   # 必填，LiteLLM 'provider/model'
              "api_base": "...",                   # 选填，覆盖 [proxy] / .env
              "api_key": "...",                    # 选填，覆盖 [proxy] / .env
              "temperature": 0.3,
              "max_tokens": 2048,
              "timeout": 60,
              "max_retries": 2,
              "thinking_budget": 2048,
              "extra_params": { ... }              # 透传 litellm.acompletion
            }

        ``llm_preset`` 引用示例::

            { "llm_preset": "fast" }   # → config/config.toml [llm.presets.fast]

        全局唯一字段（模型网关的 ``api_base`` / ``api_key`` / ``default_timeout``
        / ``default_max_retries``）统一来自 ``ConfigManager.get_proxy_full_config``，
        组件无需重复声明，需要差异化时再在 ``llm`` / preset 中覆盖即可。

        Args:
            component_name: 组件名称
            **kwargs: 运行时覆盖参数（透传 ``create_llm_client``）

        Returns:
            ``LLMClient`` 实例

        Raises:
            ValueError: 组件未配置 ``llm`` / ``llm_preset``，或 ``llm`` 字段缺少 ``model``
        """
        from src.client.llm import create_llm_client, create_llm_client_from_preset

        config = self.get_component_config(component_name)

        # ── 1) 内联 llm（LiteLLM 风格） ──
        llm_config = config.get("llm")
        if isinstance(llm_config, dict):
            if "model" not in llm_config:
                raise ValueError(
                    f"组件 '{component_name}' 的 llm 内联配置缺少必填字段 'model'"
                )
            llm_params: Dict[str, Any] = {
                k: v for k, v in llm_config.items() if k in self._ALLOWED_LLM_KEYS
            }
            unknown = set(llm_config) - self._ALLOWED_LLM_KEYS
            if unknown:
                logger.warning(
                    f"组件 '{component_name}' 的 llm 配置包含未识别字段 {sorted(unknown)}，已忽略"
                )
            llm_params.update(kwargs)
            return create_llm_client(**llm_params)

        # ── 2) preset 引用 ──
        preset_name = config.get("llm_preset")
        if preset_name:
            client = create_llm_client_from_preset(preset_name)
            if kwargs:
                for k, v in kwargs.items():
                    if hasattr(client.config, k):
                        setattr(client.config, k, v)
            return client

        raise ValueError(
            f"组件 '{component_name}' 未配置 llm 或 llm_preset，"
            f"请在 components.json 中添加对应配置"
        )
    
    # ========== Embedding / Reranker 客户端创建 ==========

    _ALLOWED_EMBEDDING_KEYS = frozenset({
        "model",
        "api_base",
        "api_key",
        "dimension",
        "batch_size",
        "max_concurrent",
        "timeout",
        "extra_params",
    })

    _ALLOWED_RERANKER_KEYS = frozenset({
        "model",
        "api_base",
        "api_key",
        "batch_size",
        "top_k",
        "timeout",
        "extra_params",
    })

    def get_embedding_client_for_component(self, component_name: str, **kwargs):
        """根据组件配置创建 Embedding 客户端（LiteLLM）

        优先级：组件 ``embedding`` 内联 > 组件 ``embedding_preset`` 引用 >
        ``[embedding].default_preset``。

        组件可在 ``components.json`` 内声明：

        - ``"embedding_preset": "local_dense"``
        - ``"embedding": {"model": "openai/...", "dimension": 1024, ...}``

        Args:
            component_name: 组件名称
            **kwargs: 透传给 ``create_embedding_client.custom_config``

        Returns:
            ``EmbeddingClient`` 实例
        """
        from src.client.embedding import create_embedding_client

        config = self.get_component_config(component_name)

        custom: Dict[str, Any] = {}
        preset_name: Optional[str] = None

        emb = config.get("embedding")
        if isinstance(emb, dict):
            unknown = set(emb) - self._ALLOWED_EMBEDDING_KEYS
            if unknown:
                logger.warning(
                    f"组件 '{component_name}' 的 embedding 配置含未识别字段 {sorted(unknown)}，已忽略"
                )
            custom = {k: v for k, v in emb.items() if k in self._ALLOWED_EMBEDDING_KEYS}
        else:
            preset_name = config.get("embedding_preset")

        if kwargs:
            custom.update(kwargs)

        return create_embedding_client(
            custom_config=custom or None,
            preset_name=preset_name,
        )

    def get_reranker_client_for_component(self, component_name: str, **kwargs):
        """根据组件配置创建 Reranker 客户端（LiteLLM）

        优先级：组件 ``reranker`` 内联 > 组件 ``reranker_preset`` 引用 >
        ``[reranker].default_preset``。
        """
        from src.client.reranker import create_reranker_client

        config = self.get_component_config(component_name)

        custom: Dict[str, Any] = {}
        preset_name: Optional[str] = None

        rk = config.get("reranker")
        if isinstance(rk, dict):
            unknown = set(rk) - self._ALLOWED_RERANKER_KEYS
            if unknown:
                logger.warning(
                    f"组件 '{component_name}' 的 reranker 配置含未识别字段 {sorted(unknown)}，已忽略"
                )
            custom = {k: v for k, v in rk.items() if k in self._ALLOWED_RERANKER_KEYS}
        else:
            preset_name = config.get("reranker_preset")

        if kwargs:
            custom.update(kwargs)

        return create_reranker_client(
            custom_config=custom or None,
            preset_name=preset_name,
        )

    # ========== 工具方法 ==========

    def is_component_enabled(self, component_name: str) -> bool:
        """
        检查组件是否启用
        
        Args:
            component_name: 组件名称
        
        Returns:
            是否启用
        """
        config = self.get_component_config(component_name)
        return config.get("enabled", False)
    
    def get_all_components(self) -> Dict[str, Any]:
        """获取所有组件配置"""
        if self._config is None:
            self._load_config()
        
        return self._config.copy()


# ========== 全局单例实例 ==========

_config_manager_instance: Optional[ComponentConfigManager] = None


def get_component_config_manager() -> ComponentConfigManager:
    """
    获取组件配置管理器单例
    
    Returns:
        ComponentConfigManager 实例
    """
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ComponentConfigManager()
    return _config_manager_instance
