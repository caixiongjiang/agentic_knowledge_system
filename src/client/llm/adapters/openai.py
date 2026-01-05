#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : openai.py
@Author  : caixiongjiang
@Date    : 2026/1/5 10:51
@Function: 
    OpenAI Adapter 实现
    处理标准 OpenAI 格式的请求和响应
@Modify History:
    2026/1/5 - 初始实现，支持 GPT-4、GPT-3.5 等模型
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Dict, Any, List

from src.client.llm.adapters.base import BaseAdapter
from src.client.llm.types import LLMResponse, TokenUsage


class OpenAIAdapter(BaseAdapter):
    """
    OpenAI Adapter
    
    支持的模型：
    - gpt-4o
    - gpt-4-turbo
    - gpt-4
    - gpt-3.5-turbo
    
    特性：
    - 标准 OpenAI 格式
    - 直接透传大部分参数
    - 无特殊处理需求
    """
    
    def build_request(self, messages: List[Dict[str, Any]], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建 OpenAI 格式请求
        
        OpenAI 格式特点：
        - 标准的 messages 数组
        - 扁平的参数结构
        - 直接透传
        
        Args:
            messages: 标准消息列表
            params: 生成参数
        
        Returns:
            OpenAI API 请求体
        """
        request = {
            "model": params["model_name"],
            "messages": messages,
        }
        
        # 添加可选参数
        if "temperature" in params:
            request["temperature"] = params["temperature"]
        
        if "max_tokens" in params:
            request["max_tokens"] = params["max_tokens"]
        
        if "top_p" in params:
            request["top_p"] = params["top_p"]
        
        if "stream" in params:
            request["stream"] = params["stream"]
        
        if "frequency_penalty" in params:
            request["frequency_penalty"] = params["frequency_penalty"]
        
        if "presence_penalty" in params:
            request["presence_penalty"] = params["presence_penalty"]
        
        if "stop" in params:
            request["stop"] = params["stop"]
        
        if "n" in params:
            request["n"] = params["n"]
        
        if "logit_bias" in params:
            request["logit_bias"] = params["logit_bias"]
        
        if "user" in params:
            request["user"] = params["user"]
        
        return request
    
    def parse_response(self, raw_response: Dict[str, Any]) -> LLMResponse:
        """
        解析 OpenAI 响应
        
        OpenAI 响应格式：
        {
            "id": "chatcmpl-xxx",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "回答内容"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
        
        Args:
            raw_response: OpenAI 原始响应
        
        Returns:
            统一的 LLMResponse
        """
        # 提取第一个选择（通常只有一个）
        choice = raw_response["choices"][0]
        
        # 提取内容
        content = choice["message"]["content"]
        
        # 提取 finish_reason，映射到统一格式
        finish_reason_map = {
            "stop": "stop",
            "length": "length",
            "content_filter": "content_filter",
            "function_call": "stop",  # 函数调用也算正常停止
            "tool_calls": "stop",
        }
        finish_reason = finish_reason_map.get(
            choice["finish_reason"], 
            "stop"
        )
        
        # 构建 Token 使用统计
        usage = TokenUsage(
            prompt_tokens=raw_response["usage"]["prompt_tokens"],
            completion_tokens=raw_response["usage"]["completion_tokens"],
            thinking_tokens=None,  # OpenAI 标准格式无 thinking
            total_tokens=raw_response["usage"]["total_tokens"]
        )
        
        # 返回统一响应
        return LLMResponse(
            content=content,
            thinking=None,  # OpenAI 标准格式无 thinking
            usage=usage,
            model=raw_response["model"],
            finish_reason=finish_reason,
            raw_response=raw_response
        )
    
    def get_endpoint(self) -> str:
        """
        OpenAI API 端点
        
        Returns:
            "/chat/completions"
        """
        return "/chat/completions"
    
    def validate_params(self, params: Dict[str, Any]) -> None:
        """
        参数校验（OpenAI 无特殊要求）
        
        Args:
            params: 生成参数
        
        Raises:
            ValueError: 参数不合法
        """
        # OpenAI 对参数比较宽容，只做基础校验
        
        # temperature 范围校验
        if "temperature" in params:
            temp = params["temperature"]
            if not (0 <= temp <= 2):
                raise ValueError(f"temperature 必须在 [0, 2] 范围内，当前值: {temp}")
        
        # top_p 范围校验
        if "top_p" in params:
            top_p = params["top_p"]
            if not (0 <= top_p <= 1):
                raise ValueError(f"top_p 必须在 [0, 1] 范围内，当前值: {top_p}")
        
        # max_tokens 校验
        if "max_tokens" in params:
            max_tokens = params["max_tokens"]
            if max_tokens <= 0:
                raise ValueError(f"max_tokens 必须为正整数，当前值: {max_tokens}")
