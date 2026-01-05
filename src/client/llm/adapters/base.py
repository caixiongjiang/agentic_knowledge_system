#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : base.py
@Author  : caixiongjiang
@Date    : 2026/1/5 10:51
@Function: 
    BaseAdapter 抽象基类
    定义 Adapter 的标准接口，所有具体 Adapter 必须继承此类
@Modify History:
    2026/1/5 - 初始实现，定义 Adapter 接口
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import httpx

from src.client.llm.types import LLMResponse


class BaseAdapter(ABC):
    """
    Adapter 抽象基类
    
    职责：
    - 定义 Adapter 的标准接口
    - 提供默认的通用实现
    - 统一处理不同 LLM 提供商的格式差异
    
    所有具体 Adapter 必须实现：
    - build_request(): 构建 provider 特定的请求格式
    - parse_response(): 解析 provider 响应为统一格式
    - get_endpoint(): 返回 API 端点路径
    
    可选实现（有默认实现）：
    - validate_params(): 参数校验
    - build_headers(): 构建请求头
    - handle_error(): 错误处理
    """
    
    @abstractmethod
    def build_request(self, messages: List[Dict[str, Any]], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建请求体（必须实现）
        
        将标准消息格式转换为 provider 特定格式
        
        Args:
            messages: 标准消息列表
                [
                    {"role": "system", "content": "..."},
                    {"role": "user", "content": "..."}
                ]
            params: 生成参数
                {
                    "model_name": "...",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    ...
                }
        
        Returns:
            Provider 特定的请求体字典
            
        Example:
            >>> adapter = OpenAIAdapter()
            >>> request = adapter.build_request(messages, params)
            >>> # 返回: {"model": "gpt-4", "messages": [...], ...}
        """
        pass
    
    @abstractmethod
    def parse_response(self, raw_response: Dict[str, Any]) -> LLMResponse:
        """
        解析响应（必须实现）
        
        将 provider 特定的响应转换为统一的 LLMResponse
        
        Args:
            raw_response: Provider 的原始响应字典
        
        Returns:
            统一的 LLMResponse 对象
            
        Example:
            >>> adapter = OpenAIAdapter()
            >>> response = adapter.parse_response(raw_response)
            >>> # 返回: LLMResponse(content="...", usage=..., ...)
        """
        pass
    
    @abstractmethod
    def get_endpoint(self) -> str:
        """
        获取 API 端点路径（必须实现）
        
        Returns:
            API 端点路径（相对于 api_base）
            
        Example:
            >>> adapter = OpenAIAdapter()
            >>> endpoint = adapter.get_endpoint()
            >>> # 返回: "/chat/completions"
        
        Note:
            - 路径必须以 "/" 开头
            - 某些 provider 可能需要占位符，如 Gemini 的 "/models/{model}:generateContent"
            - 占位符会在 LLMClient 中被替换
        """
        pass
    
    # ==================== 可选方法（有默认实现） ====================
    
    def validate_params(self, params: Dict[str, Any]) -> None:
        """
        参数校验（可选实现）
        
        默认实现：不做任何校验
        
        Args:
            params: 生成参数
        
        Raises:
            ValueError: 参数不合法
            
        Example:
            >>> def validate_params(self, params: dict) -> None:
            ...     if "max_tokens" not in params:
            ...         raise ValueError("max_tokens 是必需参数")
        """
        pass
    
    def build_headers(self, api_key: str) -> Dict[str, str]:
        """
        构建请求头（可选实现）
        
        默认实现：标准的 Bearer Token 认证
        
        Args:
            api_key: API 密钥
        
        Returns:
            请求头字典
            
        Example:
            >>> adapter = OpenAIAdapter()
            >>> headers = adapter.build_headers("sk-xxx")
            >>> # 返回: {"Content-Type": "application/json", "Authorization": "Bearer sk-xxx"}
        """
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def handle_error(self, response: httpx.Response) -> Exception:
        """
        错误处理（可选实现）
        
        默认实现：返回通用的 HTTPError
        
        Args:
            response: HTTP 响应对象
        
        Returns:
            异常对象
            
        Example:
            >>> def handle_error(self, response: httpx.Response) -> Exception:
            ...     error_data = response.json()
            ...     error_msg = error_data.get("error", {}).get("message", "未知错误")
            ...     return ValueError(f"API 错误: {error_msg}")
        """
        try:
            error_data = response.json()
            error_msg = str(error_data)
        except:
            error_msg = response.text or f"HTTP {response.status_code}"
        
        return httpx.HTTPStatusError(
            f"API 请求失败 ({response.status_code}): {error_msg}",
            request=response.request,
            response=response
        )
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"{self.__class__.__name__}()"
