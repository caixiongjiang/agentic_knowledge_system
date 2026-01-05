#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : types.py
@Author  : caixiongjiang
@Date    : 2026/1/5 10:50
@Function: 
    LLM Client 数据结构定义
    使用 Pydantic 进行数据验证和序列化
@Modify History:
    2026/1/5 - 初始实现，定义 Message、LLMResponse 等数据结构
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Literal, Union, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


# ==================== 输入结构 ====================

class ContentPart(BaseModel):
    """
    多模态内容单元
    
    支持文本、图片URL、Base64图片等多种类型
    """
    type: Literal["text", "image_url", "image_base64"] = Field(
        ...,
        description="内容类型"
    )
    text: Optional[str] = Field(
        None,
        description="文本内容（当 type='text' 时）"
    )
    image_url: Optional[str] = Field(
        None,
        description="图片URL（当 type='image_url' 时）"
    )
    image_data: Optional[str] = Field(
        None,
        description="Base64图片数据（当 type='image_base64' 时）"
    )
    
    @field_validator('text')
    @classmethod
    def validate_text(cls, v, info):
        """验证文本类型时必须有text字段"""
        if info.data.get('type') == 'text' and not v:
            raise ValueError("当 type='text' 时，text 字段不能为空")
        return v
    
    @field_validator('image_url')
    @classmethod
    def validate_image_url(cls, v, info):
        """验证图片URL类型时必须有image_url字段"""
        if info.data.get('type') == 'image_url' and not v:
            raise ValueError("当 type='image_url' 时，image_url 字段不能为空")
        return v
    
    @field_validator('image_data')
    @classmethod
    def validate_image_data(cls, v, info):
        """验证Base64图片类型时必须有image_data字段"""
        if info.data.get('type') == 'image_base64' and not v:
            raise ValueError("当 type='image_base64' 时，image_data 字段不能为空")
        return v
    
    class Config:
        extra = "forbid"  # 禁止额外字段
        json_schema_extra = {
            "examples": [
                {"type": "text", "text": "这是一段文本"},
                {"type": "image_url", "image_url": "https://example.com/image.jpg"},
                {"type": "image_base64", "image_data": "iVBORw0KGgoAAAANSUhEUgAAAAUA..."}
            ]
        }


class Message(BaseModel):
    """
    对话消息
    
    支持纯文本和多模态内容
    """
    role: Literal["system", "user", "assistant"] = Field(
        ...,
        description="消息角色"
    )
    content: Union[str, List[ContentPart]] = Field(
        ...,
        description="消息内容（字符串或多模态内容列表）"
    )
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """验证内容不能为空"""
        if isinstance(v, str) and not v.strip():
            raise ValueError("消息内容不能为空")
        if isinstance(v, list) and len(v) == 0:
            raise ValueError("多模态内容列表不能为空")
        return v
    
    class Config:
        extra = "forbid"
        json_schema_extra = {
            "examples": [
                {"role": "user", "content": "你好"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "这张图片里有什么？"},
                        {"type": "image_url", "image_url": "https://example.com/image.jpg"}
                    ]
                }
            ]
        }


# ==================== 输出结构 ====================

class ThinkingContent(BaseModel):
    """
    推理过程（DeepSeek, Gemini 等支持）
    
    某些模型会在生成答案前进行推理，这部分内容可以单独提取
    """
    reasoning: str = Field(
        ...,
        description="推理内容"
    )
    tokens_used: Optional[int] = Field(
        None,
        ge=0,
        description="思考消耗的 token 数"
    )
    
    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "reasoning": "首先分析问题的核心要素...",
                "tokens_used": 256
            }
        }


class TokenUsage(BaseModel):
    """
    Token 使用统计
    
    记录提示词、生成内容、思考过程的 token 消耗
    """
    prompt_tokens: int = Field(
        ...,
        ge=0,
        description="提示词 tokens"
    )
    completion_tokens: int = Field(
        ...,
        ge=0,
        description="生成内容 tokens"
    )
    thinking_tokens: Optional[int] = Field(
        None,
        ge=0,
        description="思考 tokens（特殊模型，如 DeepSeek）"
    )
    total_tokens: int = Field(
        ...,
        ge=0,
        description="总 tokens"
    )
    
    @field_validator('total_tokens')
    @classmethod
    def validate_total(cls, v, info):
        """验证总token数是否正确"""
        prompt = info.data.get('prompt_tokens', 0)
        completion = info.data.get('completion_tokens', 0)
        thinking = info.data.get('thinking_tokens', 0) or 0
        
        expected_total = prompt + completion + thinking
        
        # 允许一定的误差（某些API可能有舍入误差）
        if abs(v - expected_total) > 1:
            # 只是警告，不抛出异常
            pass
        
        return v
    
    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "prompt_tokens": 128,
                "completion_tokens": 512,
                "thinking_tokens": 256,
                "total_tokens": 896
            }
        }


class LLMResponse(BaseModel):
    """
    LLM 统一响应结构
    
    所有 provider 的响应都会被转换为这个统一格式
    """
    content: str = Field(
        ...,
        description="主要文本回答"
    )
    thinking: Optional[ThinkingContent] = Field(
        None,
        description="推理过程（可选，仅部分模型支持）"
    )
    usage: TokenUsage = Field(
        ...,
        description="Token 使用统计"
    )
    model: str = Field(
        ...,
        description="实际使用的模型名称"
    )
    finish_reason: Literal["stop", "length", "error", "content_filter"] = Field(
        ...,
        description="停止原因"
    )
    raw_response: Dict[str, Any] = Field(
        ...,
        description="原始响应（调试用）"
    )
    
    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "content": "这是模型的回答",
                "thinking": {
                    "reasoning": "首先分析问题...",
                    "tokens_used": 256
                },
                "usage": {
                    "prompt_tokens": 128,
                    "completion_tokens": 512,
                    "thinking_tokens": 256,
                    "total_tokens": 896
                },
                "model": "deepseek-chat",
                "finish_reason": "stop",
                "raw_response": {}
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()
    
    def to_json(self, **kwargs) -> str:
        """序列化为 JSON"""
        return self.model_dump_json(**kwargs)
    
    @classmethod
    def from_json(cls, json_data: str) -> "LLMResponse":
        """从 JSON 反序列化"""
        return cls.model_validate_json(json_data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMResponse":
        """从字典创建实例"""
        return cls.model_validate(data)
    
    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"LLMResponse(model={self.model}, "
            f"tokens={self.usage.total_tokens}, "
            f"finish_reason={self.finish_reason})"
        )
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return self.__str__()


# ==================== 流式输出结构 ====================

class StreamChunk(BaseModel):
    """
    流式输出的单个块
    
    每次流式返回一个增量内容块
    """
    delta: str = Field(
        ...,
        description="增量内容"
    )
    is_thought: bool = Field(
        False,
        description="是否为思考内容（Gemini/DeepSeek 等模型支持）"
    )
    finish_reason: Optional[Literal["stop", "length", "error", "content_filter"]] = Field(
        None,
        description="完成原因（仅在最后一个块中有值）"
    )
    model: Optional[str] = Field(
        None,
        description="模型名称"
    )
    
    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "delta": "这是",
                "is_thought": False,
                "finish_reason": None,
                "model": "deepseek-chat"
            }
        }


# ==================== 类型别名 ====================

# 消息列表类型
MessageList = List[Union[Message, Dict[str, Any]]]

# 生成参数类型
GenerateParams = Dict[str, Any]
