#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/1/5 10:07
@Function: 
    LLM Client 统一导出接口
@Modify History:
    2026/1/5 - 初始实现，导出核心类和工厂函数
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.client.llm.llm import (
    LLMClient,
    create_llm_client
)

from src.client.llm.types import (
    Message,
    ContentPart,
    LLMResponse,
    TokenUsage,
    ThinkingContent,
    MessageList,
    GenerateParams,
    StreamChunk,
)

__all__ = [
    # 核心类
    "LLMClient",
    
    # 工厂函数
    "create_llm_client",
    
    # 数据类型
    "Message",
    "ContentPart",
    "LLMResponse",
    "TokenUsage",
    "ThinkingContent",
    "MessageList",
    "GenerateParams",
    "StreamChunk",  # 流式响应块
]
