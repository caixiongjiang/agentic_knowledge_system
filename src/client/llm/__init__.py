#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/04/21
@Function:
    LLM Client 统一导出接口（LiteLLM 重写版）

    - ``LLMClient``：LiteLLM 薄封装；同时支持多模态、思考链
      （DeepSeek-Reasoner / Anthropic / Gemini Thinking）与 OpenAI 风格 tool calling。
    - ``create_llm_client``：关键字入参 ``model="provider/model"``。
    - ``create_llm_client_from_preset``：从 ``config/config.toml``
      → ``[llm.presets.<name>]`` 读取配置；``api_base`` / ``api_key`` 默认
      回落到 ``[proxy]`` + ``LITELLM_PROXY_URL`` / ``LITELLM_PROXY_KEY``。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from src.client.llm.client import (
    LLMClient,
    LLMClientConfig,
    create_llm_client,
    create_llm_client_from_preset,
)
from src.client.llm.types import (
    LLMResponse,
    MessageDict,
    MessageList,
    StreamChunk,
    ThinkingContent,
    TokenUsage,
    ToolCall,
    ToolCallDelta,
    ToolSchema,
)

__all__ = [
    "LLMClient",
    "LLMClientConfig",
    "create_llm_client",
    "create_llm_client_from_preset",
    "LLMResponse",
    "TokenUsage",
    "ThinkingContent",
    "ToolCall",
    "ToolCallDelta",
    "StreamChunk",
    "MessageDict",
    "MessageList",
    "ToolSchema",
]
