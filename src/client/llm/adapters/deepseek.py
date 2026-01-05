#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : deepseek.py
@Author  : caixiongjiang
@Date    : 2026/1/5 10:51
@Function: 
    DeepSeek Adapter 实现
    继承 OpenAI Adapter，扩展 thinking 支持
@Modify History:
    2026/1/5 - 初始实现，支持 DeepSeek 推理模式
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Dict, Any, List, Optional, Union

from src.client.llm.adapters.openai import OpenAIAdapter
from src.client.llm.types import LLMResponse, TokenUsage, ThinkingContent


class DeepSeekAdapter(OpenAIAdapter):
    """
    DeepSeek Adapter
    
    继承自 OpenAIAdapter（OpenAI 兼容格式）
    
    支持的模型（DeepSeek-V3.2）：
    - deepseek-chat：非思考模式，快速响应
    - deepseek-reasoner：思考模式，适合复杂推理任务
    
    特性：
    - 兼容 OpenAI 格式
    - 扩展 enable_thinking 参数（deepseek-chat 使用）
    - deepseek-reasoner 自动启用思考模式
    - 解析 reasoning_content 字段
    - 单独统计 thinking tokens
    
    注意：
    - deepseek-chat + enable_thinking=True 等价于 deepseek-reasoner
    - 推荐直接使用 deepseek-reasoner 进行复杂推理
    """
    
    def build_request(self, messages: List[Dict[str, Any]], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建 DeepSeek 请求
        
        在 OpenAI 标准格式基础上，添加 thinking 相关参数
        
        Args:
            messages: 标准消息列表
            params: 生成参数
        
        Returns:
            DeepSeek API 请求体
        """
        # 使用父类方法构建基础请求
        request = super().build_request(messages, params)
        
        # 添加 DeepSeek 特有参数
        if params.get("enable_thinking"):
            request["enable_thinking"] = True
        
        if "thinking_budget" in params:
            request["thinking_budget"] = params["thinking_budget"]
        
        return request
    
    def parse_response(self, raw_response: Dict[str, Any]) -> LLMResponse:
        """
        解析 DeepSeek 响应
        
        DeepSeek V3.2 在 OpenAI 格式基础上，添加了 reasoning_content 字段：
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "正式回答",
                        "reasoning_content": "推理过程"  # DeepSeek 扩展字段
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 308,
                "completion_tokens_details": {
                    "reasoning_tokens": 278  # V3.2: 移到这里
                }
            }
        }
        
        Args:
            raw_response: DeepSeek 原始响应
        
        Returns:
            统一的 LLMResponse（包含 thinking）
        """
        # 提取第一个选择
        choice = raw_response["choices"][0]
        message = choice["message"]
        
        # 提取内容
        content = message["content"]
        
        # 提取 thinking（如果有）
        thinking: Optional[ThinkingContent] = None
        if "reasoning_content" in message and message["reasoning_content"]:
            # DeepSeek V3.2: reasoning_tokens 在 completion_tokens_details 中
            reasoning_tokens = raw_response["usage"].get("completion_tokens_details", {}).get("reasoning_tokens")
            
            thinking = ThinkingContent(
                reasoning=message["reasoning_content"],
                tokens_used=reasoning_tokens
            )
        
        # 提取 finish_reason
        finish_reason_map = {
            "stop": "stop",
            "length": "length",
            "content_filter": "content_filter",
        }
        finish_reason = finish_reason_map.get(
            choice["finish_reason"], 
            "stop"
        )
        
        # 构建 Token 使用统计（包含 thinking tokens）
        # DeepSeek V3.2: reasoning_tokens 在 completion_tokens_details 中
        reasoning_tokens = raw_response["usage"].get("completion_tokens_details", {}).get("reasoning_tokens")
        
        usage = TokenUsage(
            prompt_tokens=raw_response["usage"]["prompt_tokens"],
            completion_tokens=raw_response["usage"]["completion_tokens"],
            thinking_tokens=reasoning_tokens,
            total_tokens=raw_response["usage"]["total_tokens"]
        )
        
        # 返回统一响应
        return LLMResponse(
            content=content,
            thinking=thinking,  # DeepSeek 扩展字段
            usage=usage,
            model=raw_response["model"],
            finish_reason=finish_reason,
            raw_response=raw_response
        )
    
    def parse_stream_chunk(self, chunk_data: Dict[str, Any]) -> Union[Dict[str, Any], None]:
        """
        解析 DeepSeek 流式响应块
        
        DeepSeek 流式响应格式（与 OpenAI 相似，但支持 reasoning_content）：
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": "回答内容",
                        "reasoning_content": "推理内容"  # DeepSeek 扩展字段
                    },
                    "finish_reason": null
                }
            ]
        }
        
        Args:
            chunk_data: 解析后的 JSON 数据
        
        Returns:
            包含内容和是否为思考的字典 {"content": str, "is_thought": bool}
            如果没有内容则返回 None
        
        注意：
            - reasoning_content 和 content 会在不同的块中返回
            - reasoning_content 在前，标记为 is_thought=True
            - content 在后，标记为 is_thought=False
        """
        if "choices" not in chunk_data or not chunk_data["choices"]:
            return None
        
        choice = chunk_data["choices"][0]
        
        # 提取 delta
        if "delta" not in choice:
            return None
        
        delta = choice["delta"]
        
        # 检查是否有 reasoning_content（思考内容）
        if "reasoning_content" in delta and delta["reasoning_content"]:
            return {
                "content": delta["reasoning_content"],
                "is_thought": True
            }
        
        # 检查是否有普通 content（回答内容）
        if "content" in delta and delta["content"]:
            return {
                "content": delta["content"],
                "is_thought": False
            }
        
        return None
    
    def validate_params(self, params: Dict[str, Any]) -> None:
        """
        参数校验（扩展 thinking 相关参数）
        
        Args:
            params: 生成参数
        
        Raises:
            ValueError: 参数不合法
        """
        # 先调用父类校验
        super().validate_params(params)
        
        # DeepSeek 特有参数校验
        if "thinking_budget" in params:
            budget = params["thinking_budget"]
            if not isinstance(budget, int) or budget <= 0:
                raise ValueError(f"thinking_budget 必须为正整数，当前值: {budget}")
