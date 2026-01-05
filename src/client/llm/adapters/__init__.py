#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/1/5 10:51
@Function: 
    Adapter 注册表
    所有 Adapter 实现都在此注册，供 LLMClient 使用
@Modify History:
    2026/1/5 - 初始实现，定义 ADAPTER_REGISTRY
    2026/1/5 - 注册所有具体 Adapter 实现
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.client.llm.adapters.base import BaseAdapter
from src.client.llm.adapters.openai import OpenAIAdapter
from src.client.llm.adapters.deepseek import DeepSeekAdapter
from src.client.llm.adapters.gemini import GeminiAdapter
from src.client.llm.adapters.anthropic import AnthropicAdapter


# Adapter 注册表
# key: provider名称（小写）
# value: Adapter类
ADAPTER_REGISTRY = {
    "openai": OpenAIAdapter,
    "deepseek": DeepSeekAdapter,
    "gemini": GeminiAdapter,
    "anthropic": AnthropicAdapter,
}


__all__ = [
    "BaseAdapter",
    "OpenAIAdapter",
    "DeepSeekAdapter",
    "GeminiAdapter",
    "AnthropicAdapter",
    "ADAPTER_REGISTRY",
]
