#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : anthropic.py
@Author  : caixiongjiang
@Date    : 2026/1/5 10:52
@Function: 
    Anthropic Adapter 实现
    处理 Claude 的特殊格式要求
@Modify History:
    2026/1/5 - 初始实现，支持 Claude 系列模型
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Dict, Any, List
import httpx

from src.client.llm.adapters.base import BaseAdapter
from src.client.llm.types import LLMResponse, TokenUsage


class AnthropicAdapter(BaseAdapter):
    """
    Anthropic Adapter
    
    支持的模型：
    - claude-3-5-sonnet-20241022
    - claude-3-opus-20240229
    - claude-3-sonnet-20240229
    - claude-3-haiku-20240307
    
    特性：
    - System message 单独字段处理
    - max_tokens 必填参数
    - 消息必须交替（user/assistant）
    - 特殊的 API 版本头
    """
    
    def build_request(self, messages: List[Dict[str, Any]], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建 Claude 请求
        
        Claude 格式特点：
        1. system message 单独作为 "system" 字段
        2. max_tokens 是必填参数
        3. 消息必须是 user/assistant 交替
        
        Args:
            messages: 标准消息列表
            params: 生成参数
        
        Returns:
            Claude API 请求体
        """
        # 1. 提取 system message
        system_messages = [m for m in messages if m["role"] == "system"]
        other_messages = [m for m in messages if m["role"] != "system"]
        
        # 2. 构建基础请求
        request = {
            "model": params["model_name"],
            "messages": other_messages,
            "max_tokens": params.get("max_tokens", 4096),  # Claude 必填，默认 4096
        }
        
        # 3. System message（单独字段）
        if system_messages:
            # 如果有多个 system message，合并它们
            system_content = "\n\n".join(
                msg["content"] for msg in system_messages
            )
            request["system"] = system_content
        
        # 4. 添加可选参数
        if "temperature" in params:
            request["temperature"] = params["temperature"]
        
        if "top_p" in params:
            request["top_p"] = params["top_p"]
        
        if "top_k" in params:
            request["top_k"] = params["top_k"]
        
        if "stop_sequences" in params:
            request["stop_sequences"] = params["stop_sequences"]
        
        if "stream" in params:
            request["stream"] = params["stream"]
        
        return request
    
    def parse_response(self, raw_response: Dict[str, Any]) -> LLMResponse:
        """
        解析 Claude 响应
        
        Claude 响应格式：
        {
            "id": "msg_xxx",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "回答内容"
                }
            ],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20
            }
        }
        
        Args:
            raw_response: Claude 原始响应
        
        Returns:
            统一的 LLMResponse
        """
        # 提取内容（content 是数组）
        content_blocks = raw_response["content"]
        # 合并所有文本块
        text_parts = [
            block["text"] for block in content_blocks 
            if block["type"] == "text"
        ]
        content = "\n".join(text_parts)
        
        # 提取 stop_reason，映射到统一格式
        stop_reason_map = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
        }
        stop_reason = stop_reason_map.get(
            raw_response.get("stop_reason", "end_turn"),
            "stop"
        )
        
        # 构建 Token 使用统计
        usage_data = raw_response["usage"]
        usage = TokenUsage(
            prompt_tokens=usage_data["input_tokens"],
            completion_tokens=usage_data["output_tokens"],
            thinking_tokens=None,  # Claude 不单独统计 thinking
            total_tokens=usage_data["input_tokens"] + usage_data["output_tokens"]
        )
        
        # 返回统一响应
        return LLMResponse(
            content=content,
            thinking=None,  # Claude 暂不支持 thinking
            usage=usage,
            model=raw_response["model"],
            finish_reason=stop_reason,
            raw_response=raw_response
        )
    
    def get_endpoint(self) -> str:
        """
        Claude API 端点
        
        Returns:
            "/messages"
        """
        return "/messages"
    
    def validate_params(self, params: Dict[str, Any]) -> None:
        """
        参数校验（Claude 特殊要求）
        
        Args:
            params: 生成参数
        
        Raises:
            ValueError: 参数不合法
        """
        # Claude 要求 max_tokens 必填
        if "max_tokens" not in params or params["max_tokens"] is None:
            raise ValueError("Claude 要求 max_tokens 参数必填")
        
        max_tokens = params["max_tokens"]
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError(f"max_tokens 必须为正整数，当前值: {max_tokens}")
        
        # temperature 范围校验
        if "temperature" in params:
            temp = params["temperature"]
            if not (0 <= temp <= 1):
                raise ValueError(f"Claude 的 temperature 必须在 [0, 1] 范围内，当前值: {temp}")
        
        # top_p 范围校验
        if "top_p" in params:
            top_p = params["top_p"]
            if not (0 <= top_p <= 1):
                raise ValueError(f"top_p 必须在 [0, 1] 范围内，当前值: {top_p}")
    
    def build_headers(self, api_key: str) -> Dict[str, str]:
        """
        构建 Claude 请求头
        
        Claude 使用特殊的 API 版本头和认证方式
        
        Args:
            api_key: API 密钥
        
        Returns:
            请求头字典
        """
        return {
            "Content-Type": "application/json",
            "x-api-key": api_key,  # Claude 使用 x-api-key 而不是 Bearer
            "anthropic-version": "2023-06-01",  # API 版本
        }
    
    def handle_error(self, response: httpx.Response) -> Exception:
        """
        Claude 错误处理
        
        Args:
            response: HTTP 响应对象
        
        Returns:
            异常对象
        """
        try:
            error_data = response.json()
            error_type = error_data.get("error", {}).get("type", "unknown")
            error_msg = error_data.get("error", {}).get("message", "未知错误")
            
            return ValueError(f"Claude API 错误 [{error_type}]: {error_msg}")
        except:
            return httpx.HTTPStatusError(
                f"Claude API 请求失败 ({response.status_code}): {response.text}",
                request=response.request,
                response=response
            )
