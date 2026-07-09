#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : route_registry.py
@Author  : caixiongjiang
@Date    : 2026/04/03
@Function: 
    路由注册表 — route_name → Capability 实例的映射管理
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Dict, List, Optional, Type

from loguru import logger

from src.retrieve.capabilities.base import BaseCapability, CapabilityDescriptor


# route_name → (Capability 类, 描述) 的静态注册表
_ROUTE_DEFINITIONS: Dict[str, Type[BaseCapability]] = {}


def _register_defaults() -> Dict[str, Type[BaseCapability]]:
    """延迟加载所有内置路由的 Capability 类"""
    from src.retrieve.capabilities.semantic import (
        ChunkVectorSearch,
        EnhancedChunkVectorSearch,
        QAVectorSearch,
        SectionVectorSearch,
        SectionSummaryVectorSearch,
        FileSummaryVectorSearch,
    )
    from src.retrieve.capabilities.lexical import (
        BM25Search,
        BooleanSearch,
        ExactMatch,
    )

    return {
        "chunk_dense": ChunkVectorSearch,
        "enhanced_chunk_dense": EnhancedChunkVectorSearch,
        "section_dense": SectionVectorSearch,
        "qa_dense": QAVectorSearch,
        "section_summary_dense": SectionSummaryVectorSearch,
        "file_summary_dense": FileSummaryVectorSearch,
        "bm25_sparse": BM25Search,
        "exact_match": ExactMatch,
        "boolean_search": BooleanSearch,
    }


class RouteRegistry:
    """路由注册表

    管理 route_name → Capability 实例的映射。
    Capability 实例延迟初始化，首次使用时创建。
    """

    def __init__(self) -> None:
        self._definitions: Dict[str, Type[BaseCapability]] = {}
        self._instances: Dict[str, BaseCapability] = {}
        self._initialized = False

    def _ensure_defaults(self) -> None:
        if not self._initialized:
            self._definitions = _register_defaults()
            self._initialized = True

    def register(
        self, route_name: str, capability_cls: Type[BaseCapability],
    ) -> None:
        """注册（或覆盖）一条路由"""
        self._ensure_defaults()
        self._definitions[route_name] = capability_cls
        self._instances.pop(route_name, None)
        logger.debug(f"注册路由: {route_name} -> {capability_cls.__name__}")

    def unregister(self, route_name: str) -> None:
        """注销一条路由"""
        self._definitions.pop(route_name, None)
        self._instances.pop(route_name, None)

    def get(self, route_name: str) -> BaseCapability:
        """获取 Capability 实例（延迟初始化）"""
        self._ensure_defaults()

        if route_name in self._instances:
            return self._instances[route_name]

        cls = self._definitions.get(route_name)
        if cls is None:
            raise KeyError(f"未注册的路由: {route_name}")

        instance = cls()
        self._instances[route_name] = instance
        return instance

    def has(self, route_name: str) -> bool:
        self._ensure_defaults()
        return route_name in self._definitions

    def list_routes(self) -> List[str]:
        """返回所有已注册的路由名"""
        self._ensure_defaults()
        return list(self._definitions.keys())

    def list_descriptors(self) -> List[CapabilityDescriptor]:
        """返回所有路由的 CapabilityDescriptor（用于生成 LLM₁ prompt）"""
        self._ensure_defaults()
        descriptors: List[CapabilityDescriptor] = []
        for route_name in self._definitions:
            capability = self.get(route_name)
            desc = capability.describe()
            descriptors.append(desc)
        return descriptors

    def get_descriptor(self, route_name: str) -> Optional[CapabilityDescriptor]:
        if not self.has(route_name):
            return None
        return self.get(route_name).describe()
