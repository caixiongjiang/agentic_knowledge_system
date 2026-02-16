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
    - FileSummary（文件摘要）
    - KGExtractor（知识图谱提取）
    - ImageUnderstand（图片理解）
    - TextAnalyzer（文本分析器）
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
    
    def get_kg_extractor_config(self) -> Dict[str, Any]:
        """获取 KGExtractor 组件配置"""
        return self.get_component_config("kg_extractor")
    
    def get_image_understand_config(self) -> Dict[str, Any]:
        """获取 ImageUnderstand 组件配置"""
        return self.get_component_config("image_understand")
    
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
