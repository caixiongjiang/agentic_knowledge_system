#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : llm.py
@Author  : caixiongjiang
@Date    : 2026/1/5 10:50
@Function: 
    LLM Client 核心实现
    统一接口，支持多种 LLM 提供商（OpenAI、DeepSeek、Gemini、Anthropic）
@Modify History:
    2026/1/5 - 初始实现，参考 EmbeddingClient 设计模式
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import logging
import json
from typing import List, Optional, Dict, Any, Union, Iterator, AsyncIterator
from pathlib import Path

import httpx
from loguru import logger

from src.utils.config_manager import ConfigManager, get_config_manager
from src.utils.env_manager import EnvManager, get_env_manager
from src.utils.retry_decorator import retry_async, retry_sync

from src.client.llm.types import Message, LLMResponse, MessageList, GenerateParams, StreamChunk


class LLMClient:
    """
    统一的 LLM 客户端
    
    特性:
    - 支持多种 LLM 提供商（OpenAI、DeepSeek、Gemini、Anthropic）
    - 统一的接口，屏蔽底层差异
    - 支持同步和异步调用
    - 必须的超时控制
    - 可选的重试机制
    - 支持上下文管理器，自动管理连接池资源
    
    资源管理说明:
    
    两种使用模式，资源管理机制完全不同：
    
    1. **临时使用模式**（不使用上下文管理器）：
       - 每次调用 generate() 时，在方法内部创建临时 httpx.Client
       - 请求完成后，在 finally 块中自动关闭临时 httpx.Client
       - LLMClient 对象本身由垃圾回收器管理
       - 适合：偶尔调用，单次请求
    
    2. **上下文管理器模式**（推荐）：
       - __enter__ 时创建持久化 httpx.Client（self._sync_client）
       - 多次调用 generate() 复用同一个连接池，性能更优
       - __exit__ 时自动关闭持久化 httpx.Client
       - 适合：批量处理，频繁调用
    
    推荐用法:
    ```python
    # 方式1: 直接指定配置（最灵活）
    client = create_llm_client(
        provider="deepseek",
        model_name="deepseek-chat",
        temperature=0.0,
        max_tokens=4096
    )
    response = client.generate(messages=[...])
    
    # 方式2: 使用预设配置（推荐）
    client = create_llm_client_from_preset("reasoning")
    response = client.generate(messages=[...])
    
    # 方式3: 上下文管理器（批量处理）
    with create_llm_client("deepseek", "deepseek-chat") as client:
        response1 = client.generate(messages=[...])
        response2 = client.generate(messages=[...])
    # __exit__自动关闭持久化连接池
    
    # 方式4: 异步上下文管理器（异步场景）
    async with create_llm_client("deepseek", "deepseek-chat") as client:
        response = await client.agenerate(messages=[...])
    # __aexit__自动关闭持久化连接池
    ```
    """
    
    def __init__(
        self,
        provider: str,
        model_name: str,
        config_manager: Optional[ConfigManager] = None,
        env_manager: Optional[EnvManager] = None,
        **kwargs
    ):
        """
        初始化 LLM 客户端
        
        Args:
            provider: LLM 提供商（openai, deepseek, gemini, anthropic）
            model_name: 模型名称
            config_manager: 配置管理器实例，如果为None则使用默认配置管理器
            env_manager: 环境变量管理器实例，如果为None则使用默认环境管理器
            **kwargs: 其他参数（temperature, max_tokens, timeout等）
        """
        # 配置管理器
        self._config_manager = config_manager or get_config_manager()
        self._env_manager = env_manager or get_env_manager()
        
        # 提供商和模型
        self.provider = provider.lower()
        self.model_name = model_name
        
        # 加载配置
        self._load_config(**kwargs)
        
        # 加载 Adapter
        self._load_adapter()
        
        # 连接池管理（用于上下文管理器模式）
        self._sync_client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
        self._context_mode = False  # 标记是否在上下文管理器中
        
        # 日志
        logger.info(
            f"LLM客户端初始化完成 - "
            f"Provider: {self.provider}, "
            f"Model: {self.model_name}, "
            f"API: {self.api_base}, "
            f"超时: {self.timeout}s, 重试: {self.enable_retry}"
        )
    
    def _load_config(self, **kwargs) -> None:
        """
        加载配置
        
        优先级：运行时参数 > config.json > 默认值
        """
        # 尝试从 config.json 加载 LLM 配置
        config_path = Path(self._config_manager.DEFAULT_CONFIG_PATH).parent / "config.json"
        
        llm_config = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    full_config = json.load(f)
                    llm_config = full_config.get("llm", {})
            except Exception as e:
                logger.warning(f"加载 config.json 失败: {e}")
        
        # 获取 provider 配置
        provider_config = llm_config.get("providers", {}).get(self.provider, {})
        
        # API Base
        self.api_base = kwargs.get(
            "api_base",
            provider_config.get("api_base", self._get_default_api_base())
        ).rstrip("/")
        
        # 超时时间
        self.timeout = kwargs.get(
            "timeout",
            provider_config.get("default_timeout", 60)
        )
        
        # API Key
        self.api_key = kwargs.get("api_key") or self._get_api_key()
        if not self.api_key:
            raise ValueError(f"未找到 {self.provider} 的 API Key，请在环境变量中设置")
        
        # 生成参数
        self.temperature = kwargs.get("temperature")
        self.max_tokens = kwargs.get("max_tokens")
        self.top_p = kwargs.get("top_p")
        self.stream = kwargs.get("stream", False)
        
        # Provider 特有参数
        self.extra_params = {
            k: v for k, v in kwargs.items()
            if k not in ["api_base", "timeout", "api_key", "temperature", 
                        "max_tokens", "top_p", "stream"]
        }
        
        # 重试配置
        self.enable_retry = kwargs.get("enable_retry", False)
        self.max_retries = kwargs.get("max_retries", 3)
        self.retry_delay = kwargs.get("retry_delay", 0.5)
        self.retry_strategy = kwargs.get("retry_strategy", "exponential")
        self.max_retry_delay = kwargs.get("max_retry_delay", 10.0)
    
    def _get_default_api_base(self) -> str:
        """获取默认的 API Base"""
        defaults = {
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com",
            "gemini": "https://generativelanguage.googleapis.com/v1beta",
            "anthropic": "https://api.anthropic.com/v1"
        }
        return defaults.get(self.provider, "")
    
    def _get_api_key(self) -> Optional[str]:
        """从环境变量获取 API Key"""
        key_methods = {
            "openai": self._env_manager.get_openai_api_key,
            "deepseek": self._env_manager.get_deepseek_api_key,
            "gemini": self._env_manager.get_gemini_api_key,
            "anthropic": self._env_manager.get_anthropic_api_key
        }
        
        method = key_methods.get(self.provider)
        if method:
            return method()
        return None
    
    def _load_adapter(self) -> None:
        """加载对应的 Adapter"""
        from src.client.llm.adapters import ADAPTER_REGISTRY
        
        adapter_class = ADAPTER_REGISTRY.get(self.provider)
        if not adapter_class:
            raise ValueError(
                f"不支持的 provider: {self.provider}。"
                f"支持的 provider: {list(ADAPTER_REGISTRY.keys())}"
            )
        
        self.adapter = adapter_class()
        logger.debug(f"加载 Adapter: {adapter_class.__name__}")
    
    # ==================== 上下文管理器（资源管理） ====================
    
    def __enter__(self) -> 'LLMClient':
        """
        同步上下文管理器入口
        
        创建持久化的httpx.Client，用于复用连接池，提高性能
        """
        self._context_mode = True
        self._sync_client = httpx.Client(timeout=self.timeout)
        logger.debug("创建持久化同步HTTP客户端")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        同步上下文管理器退出
        
        确保httpx.Client被正确关闭，释放连接资源
        """
        self._context_mode = False
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None
            logger.debug("关闭同步HTTP客户端，释放资源")
        return False
    
    async def __aenter__(self) -> 'LLMClient':
        """
        异步上下文管理器入口
        
        创建持久化的httpx.AsyncClient，用于复用连接池，提高性能
        """
        self._context_mode = True
        self._async_client = httpx.AsyncClient(timeout=self.timeout)
        logger.debug("创建持久化异步HTTP客户端")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器退出
        
        确保httpx.AsyncClient被正确关闭，释放连接资源
        """
        self._context_mode = False
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None
            logger.debug("关闭异步HTTP客户端，释放资源")
        return False
    
    def close(self) -> None:
        """
        显式关闭同步客户端，释放连接池资源
        
        注意: 只有在使用了上下文管理器（with）后，才会有持久化客户端需要关闭。
        如果只是临时调用generate()，无需调用此方法（临时客户端已自动关闭）。
        """
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None
            logger.debug("手动关闭同步HTTP客户端")
    
    async def aclose(self) -> None:
        """
        显式关闭异步客户端，释放连接池资源
        
        注意: 只有在使用了异步上下文管理器（async with）后，才会有持久化客户端需要关闭。
        如果只是临时调用agenerate()，无需调用此方法（临时客户端已自动关闭）。
        """
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None
            logger.debug("手动关闭异步HTTP客户端")
    
    def __del__(self):
        """
        析构函数，确保资源被释放
        
        作为最后的保障，防止忘记关闭客户端导致的资源泄漏
        """
        if self._sync_client is not None:
            try:
                self._sync_client.close()
                logger.warning("在析构函数中关闭同步客户端（应该使用上下文管理器或手动close）")
            except Exception as e:
                logger.error(f"析构函数关闭客户端失败: {e}")
        
        # 注意：异步客户端无法在同步的__del__中关闭
        if self._async_client is not None:
            logger.warning(
                "检测到未关闭的异步客户端，无法在析构函数中关闭。"
                "请使用 'async with' 或手动调用 await client.aclose()"
            )
    
    # ==================== 同步方法 ====================
    
    def generate(
        self,
        messages: Union[MessageList, List[Dict[str, Any]]],
        **kwargs
    ) -> LLMResponse:
        """
        同步生成回答
        
        Args:
            messages: 消息列表
            **kwargs: 覆盖默认参数（temperature, max_tokens等）
            
        Returns:
            LLMResponse: 统一的响应对象
            
        Raises:
            ValueError: 参数错误
            httpx.HTTPError: HTTP请求错误
            TimeoutError: 请求超时
        """
        # 验证和转换消息
        validated_messages = self._validate_messages(messages)
        
        # 如果启用重试，使用装饰器包装的方法
        if self.enable_retry:
            return self._generate_with_retry_sync(validated_messages, **kwargs)
        else:
            return self._generate_sync(validated_messages, **kwargs)
    
    def _generate_sync(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """
        同步生成的核心实现（无重试）
        
        Args:
            messages: 已验证的消息列表
            **kwargs: 生成参数
            
        Returns:
            LLMResponse
        """
        # 构建参数
        params = self._build_params(**kwargs)
        
        # 委托 Adapter 验证参数
        self.adapter.validate_params(params)
        
        # 委托 Adapter 构建请求
        request_body = self.adapter.build_request(messages, params)
        
        # 构建请求头
        headers = self.adapter.build_headers(self.api_key)
        
        # 构建完整 URL
        endpoint = self.adapter.get_endpoint()
        # 替换占位符（如 Gemini 的 {model}）
        endpoint = endpoint.format(model=self.model_name)
        url = f"{self.api_base}{endpoint}"
        
        # Gemini 特殊处理：API key 通过 URL 参数传递
        if self.provider == "gemini":
            url = f"{url}?key={self.api_key}"
        
        # 根据是否在上下文管理器中决定使用持久化客户端还是临时客户端
        if self._context_mode and self._sync_client is not None:
            # 使用持久化客户端（复用连接池）
            client = self._sync_client
            should_close = False
        else:
            # 创建临时客户端（自动管理）
            client = httpx.Client(timeout=self.timeout)
            should_close = True
        
        try:
            # 发送请求
            logger.debug(f"发送请求到: {url}")
            sanitized_body = self._sanitize_request_body_for_log(request_body)
            logger.debug(f"请求体: {json.dumps(sanitized_body, ensure_ascii=False)}")
            
            try:
                response = client.post(
                    url,
                    json=request_body,
                    headers=headers
                )
                
                # 检查状态码
                if response.status_code != 200:
                    error = self.adapter.handle_error(response)
                    logger.error(f"API 请求失败: {error}")
                    raise error
                
                response.raise_for_status()
                
            except httpx.TimeoutException as e:
                logger.error(f"LLM 请求超时 ({self.timeout}s): {e}")
                raise TimeoutError(f"LLM 请求超时 ({self.timeout}s)") from e
            
            except httpx.HTTPError as e:
                logger.error(f"LLM 请求失败: {e}")
                raise
            
            # 解析响应
            raw_response = response.json()
            logger.debug(f"原始响应: {json.dumps(raw_response, ensure_ascii=False)}")
            
            # 委托 Adapter 解析响应
            llm_response = self.adapter.parse_response(raw_response)
            
            logger.info(
                f"成功生成回答 - "
                f"Model: {llm_response.model}, "
                f"Tokens: {llm_response.usage.total_tokens}, "
                f"Finish: {llm_response.finish_reason}"
            )
            
            return llm_response
        
        finally:
            # 如果是临时客户端，确保关闭释放资源
            if should_close:
                client.close()
    
    def _generate_with_retry_sync(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """
        带重试的同步生成
        
        手动应用重试装饰器，使用实例配置的重试参数
        """
        # 手动应用重试逻辑
        retry_decorator = retry_sync(
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            retry_strategy=self.retry_strategy,
            max_delay=self.max_retry_delay,
            exceptions=(httpx.HTTPError, TimeoutError),
            logger=logging.getLogger(__name__),
            raise_on_failure=True
        )
        
        wrapped_func = retry_decorator(self._generate_sync)
        return wrapped_func(messages, **kwargs)
    
    # ==================== 流式生成方法 ====================
    
    def generate_stream(
        self,
        messages: Union[MessageList, List[Dict[str, Any]]],
        **kwargs
    ) -> Iterator[StreamChunk]:
        """
        同步流式生成回答
        
        Args:
            messages: 消息列表
            **kwargs: 覆盖默认参数（temperature, max_tokens等）
            
        Yields:
            StreamChunk: 流式响应块
            
        Raises:
            ValueError: 参数错误
            httpx.HTTPError: HTTP请求错误
            TimeoutError: 请求超时
            
        Example:
            >>> client = create_llm_client("openai", "gpt-4o-mini")
            >>> for chunk in client.generate_stream(messages=[{"role": "user", "content": "你好"}]):
            >>>     print(chunk.delta, end='', flush=True)
        """
        # 验证和转换消息
        validated_messages = self._validate_messages(messages)
        
        # 流式不使用重试（流式响应难以重试）
        yield from self._generate_stream_sync(validated_messages, **kwargs)
    
    def _generate_stream_sync(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> Iterator[StreamChunk]:
        """
        同步流式生成的核心实现
        
        Args:
            messages: 已验证的消息列表
            **kwargs: 生成参数
            
        Yields:
            StreamChunk: 流式响应块
        """
        # 构建参数（强制启用流式）
        params = self._build_params(**kwargs)
        params["stream"] = True  # 强制启用流式
        
        # 委托 Adapter 验证参数
        self.adapter.validate_params(params)
        
        # 委托 Adapter 构建请求
        request_body = self.adapter.build_request(messages, params)
        
        # 构建请求头
        headers = self.adapter.build_headers(self.api_key)
        
        # 构建完整 URL
        # 检查 adapter 是否支持流式端点（Gemini 特有）
        if hasattr(self.adapter, 'get_stream_endpoint'):
            endpoint = self.adapter.get_stream_endpoint()
        else:
            endpoint = self.adapter.get_endpoint()
        
        endpoint = endpoint.format(model=self.model_name)
        url = f"{self.api_base}{endpoint}"
        
        # Gemini 特殊处理：旧版本通过 URL 参数传递 API key
        # 新版本已经使用 x-goog-api-key header，不需要这个
        if self.provider == "gemini" and "x-goog-api-key" not in headers:
            url = f"{url}?key={self.api_key}"
        
        # 根据是否在上下文管理器中决定使用持久化客户端还是临时客户端
        if self._context_mode and self._sync_client is not None:
            client = self._sync_client
            should_close = False
        else:
            client = httpx.Client(timeout=self.timeout)
            should_close = True
        
        try:
            logger.debug(f"发送流式请求到: {url}")
            
            # 发送流式请求
            with client.stream(
                "POST",
                url,
                json=request_body,
                headers=headers
            ) as response:
                # 检查状态码
                if response.status_code != 200:
                    error = self.adapter.handle_error(response)
                    logger.error(f"API 请求失败: {error}")
                    raise error
                
                # 解析流式响应
                for line in response.iter_lines():
                    if not line or line.startswith(":"):
                        continue
                    
                    # 移除 "data: " 前缀
                    if line.startswith("data: "):
                        line = line[6:]
                    
                    # 结束标记
                    if line == "[DONE]":
                        break
                    
                    try:
                        # 解析 JSON
                        chunk_data = json.loads(line)
                        
                        # 使用 Adapter 解析流式块（如果支持）
                        if hasattr(self.adapter, 'parse_stream_chunk'):
                            result = self.adapter.parse_stream_chunk(chunk_data)
                            if result:
                                # 检查返回值类型：字符串（旧格式）或字典（新格式）
                                if isinstance(result, str):
                                    # 旧格式：直接是字符串
                                    yield StreamChunk(
                                        delta=result,
                                        is_thought=False,
                                        finish_reason=None,
                                        model=chunk_data.get("modelVersion") or chunk_data.get("model")
                                    )
                                elif isinstance(result, dict):
                                    # 新格式：包含 content 和 is_thought
                                    yield StreamChunk(
                                        delta=result.get("content", ""),
                                        is_thought=result.get("is_thought", False),
                                        finish_reason=None,
                                        model=chunk_data.get("modelVersion") or chunk_data.get("model")
                                    )
                        else:
                            # 提取增量内容（OpenAI/DeepSeek 格式）
                            choices = chunk_data.get("choices", [])
                            if choices and len(choices) > 0:
                                choice = choices[0]
                                
                                # 获取增量内容
                                delta = choice.get("delta", {})
                                content = delta.get("content", "")
                                
                                if content:
                                    # 返回流式块
                                    yield StreamChunk(
                                        delta=content,
                                        is_thought=False,
                                        finish_reason=choice.get("finish_reason"),
                                        model=chunk_data.get("model")
                                    )
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析流式响应失败: {line}, 错误: {e}")
                        continue
        
        finally:
            if should_close:
                client.close()
    
    # ==================== 异步方法 ====================
    
    async def agenerate(
        self,
        messages: Union[MessageList, List[Dict[str, Any]]],
        **kwargs
    ) -> LLMResponse:
        """
        异步生成回答
        
        Args:
            messages: 消息列表
            **kwargs: 覆盖默认参数（temperature, max_tokens等）
            
        Returns:
            LLMResponse: 统一的响应对象
            
        Raises:
            ValueError: 参数错误
            httpx.HTTPError: HTTP请求错误
            TimeoutError: 请求超时
        """
        # 验证和转换消息
        validated_messages = self._validate_messages(messages)
        
        # 如果启用重试，使用装饰器包装的方法
        if self.enable_retry:
            return await self._agenerate_with_retry_async(validated_messages, **kwargs)
        else:
            return await self._agenerate_async(validated_messages, **kwargs)
    
    async def _agenerate_async(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """
        异步生成的核心实现（无重试）
        
        Args:
            messages: 已验证的消息列表
            **kwargs: 生成参数
            
        Returns:
            LLMResponse
        """
        # 构建参数
        params = self._build_params(**kwargs)
        
        # 委托 Adapter 验证参数
        self.adapter.validate_params(params)
        
        # 委托 Adapter 构建请求
        request_body = self.adapter.build_request(messages, params)
        
        # 构建请求头
        headers = self.adapter.build_headers(self.api_key)
        
        # 构建完整 URL
        endpoint = self.adapter.get_endpoint()
        # 替换占位符（如 Gemini 的 {model}）
        endpoint = endpoint.format(model=self.model_name)
        url = f"{self.api_base}{endpoint}"
        
        # Gemini 特殊处理：API key 通过 URL 参数传递
        if self.provider == "gemini":
            url = f"{url}?key={self.api_key}"
        
        # 根据是否在上下文管理器中决定使用持久化客户端还是临时客户端
        if self._context_mode and self._async_client is not None:
            # 使用持久化客户端（复用连接池）
            client = self._async_client
            should_close = False
        else:
            # 创建临时客户端（自动管理）
            client = httpx.AsyncClient(timeout=self.timeout)
            should_close = True
        
        try:
            # 发送请求
            logger.debug(f"发送异步请求到: {url}")
            sanitized_body = self._sanitize_request_body_for_log(request_body)
            logger.debug(f"请求体: {json.dumps(sanitized_body, ensure_ascii=False)}")
            
            try:
                response = await client.post(
                    url,
                    json=request_body,
                    headers=headers
                )
                
                # 检查状态码
                if response.status_code != 200:
                    error = self.adapter.handle_error(response)
                    logger.error(f"API 请求失败: {error}")
                    raise error
                
                response.raise_for_status()
                
            except httpx.TimeoutException as e:
                logger.error(f"LLM 请求超时 ({self.timeout}s): {e}")
                raise TimeoutError(f"LLM 请求超时 ({self.timeout}s)") from e
            
            except httpx.HTTPError as e:
                logger.error(f"LLM 请求失败: {e}")
                raise
            
            # 解析响应
            raw_response = response.json()
            logger.debug(f"原始响应: {json.dumps(raw_response, ensure_ascii=False)}")
            
            # 委托 Adapter 解析响应
            llm_response = self.adapter.parse_response(raw_response)
            
            logger.info(
                f"成功生成回答 - "
                f"Model: {llm_response.model}, "
                f"Tokens: {llm_response.usage.total_tokens}, "
                f"Finish: {llm_response.finish_reason}"
            )
            
            return llm_response
        
        finally:
            # 如果是临时客户端，确保关闭释放资源
            if should_close:
                await client.aclose()
    
    async def _agenerate_with_retry_async(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """
        带重试的异步生成
        
        手动应用重试装饰器，使用实例配置的重试参数
        """
        # 手动应用重试逻辑
        retry_decorator = retry_async(
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            retry_strategy=self.retry_strategy,
            max_delay=self.max_retry_delay,
            exceptions=(httpx.HTTPError, TimeoutError),
            logger=logging.getLogger(__name__),
            raise_on_failure=True,
            timeout=None  # 不在重试装饰器层面设置timeout，使用httpx的timeout
        )
        
        wrapped_func = retry_decorator(self._agenerate_async)
        return await wrapped_func(messages, **kwargs)
    
    # ==================== 异步流式生成方法 ====================
    
    async def agenerate_stream(
        self,
        messages: Union[MessageList, List[Dict[str, Any]]],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        异步流式生成回答
        
        Args:
            messages: 消息列表
            **kwargs: 覆盖默认参数（temperature, max_tokens等）
            
        Yields:
            StreamChunk: 流式响应块
            
        Raises:
            ValueError: 参数错误
            httpx.HTTPError: HTTP请求错误
            TimeoutError: 请求超时
            
        Example:
            >>> client = create_llm_client("openai", "gpt-4o-mini")
            >>> async for chunk in client.agenerate_stream(messages=[{"role": "user", "content": "你好"}]):
            >>>     print(chunk.delta, end='', flush=True)
        """
        # 验证和转换消息
        validated_messages = self._validate_messages(messages)
        
        # 流式不使用重试（流式响应难以重试）
        async for chunk in self._agenerate_stream_async(validated_messages, **kwargs):
            yield chunk
    
    async def _agenerate_stream_async(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        异步流式生成的核心实现
        
        Args:
            messages: 已验证的消息列表
            **kwargs: 生成参数
            
        Yields:
            StreamChunk: 流式响应块
        """
        # 构建参数（强制启用流式）
        params = self._build_params(**kwargs)
        params["stream"] = True  # 强制启用流式
        
        # 委托 Adapter 验证参数
        self.adapter.validate_params(params)
        
        # 委托 Adapter 构建请求
        request_body = self.adapter.build_request(messages, params)
        
        # 构建请求头
        headers = self.adapter.build_headers(self.api_key)
        
        # 构建完整 URL
        # 检查 adapter 是否支持流式端点（Gemini 特有）
        if hasattr(self.adapter, 'get_stream_endpoint'):
            endpoint = self.adapter.get_stream_endpoint()
        else:
            endpoint = self.adapter.get_endpoint()
        
        endpoint = endpoint.format(model=self.model_name)
        url = f"{self.api_base}{endpoint}"
        
        # Gemini 特殊处理：旧版本通过 URL 参数传递 API key
        # 新版本已经使用 x-goog-api-key header，不需要这个
        if self.provider == "gemini" and "x-goog-api-key" not in headers:
            url = f"{url}?key={self.api_key}"
        
        # 根据是否在上下文管理器中决定使用持久化客户端还是临时客户端
        if self._context_mode and self._async_client is not None:
            client = self._async_client
            should_close = False
        else:
            client = httpx.AsyncClient(timeout=self.timeout)
            should_close = True
        
        try:
            logger.debug(f"发送异步流式请求到: {url}")
            
            # 发送异步流式请求
            async with client.stream(
                "POST",
                url,
                json=request_body,
                headers=headers
            ) as response:
                # 检查状态码
                if response.status_code != 200:
                    error = self.adapter.handle_error(response)
                    logger.error(f"API 请求失败: {error}")
                    raise error
                
                # 解析流式响应
                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue
                    
                    # 移除 "data: " 前缀
                    if line.startswith("data: "):
                        line = line[6:]
                    
                    # 结束标记
                    if line == "[DONE]":
                        break
                    
                    try:
                        # 解析 JSON
                        chunk_data = json.loads(line)
                        
                        # 使用 Adapter 解析流式块（如果支持）
                        if hasattr(self.adapter, 'parse_stream_chunk'):
                            result = self.adapter.parse_stream_chunk(chunk_data)
                            if result:
                                # 检查返回值类型：字符串（旧格式）或字典（新格式）
                                if isinstance(result, str):
                                    # 旧格式：直接是字符串
                                    yield StreamChunk(
                                        delta=result,
                                        is_thought=False,
                                        finish_reason=None,
                                        model=chunk_data.get("modelVersion") or chunk_data.get("model")
                                    )
                                elif isinstance(result, dict):
                                    # 新格式：包含 content 和 is_thought
                                    yield StreamChunk(
                                        delta=result.get("content", ""),
                                        is_thought=result.get("is_thought", False),
                                        finish_reason=None,
                                        model=chunk_data.get("modelVersion") or chunk_data.get("model")
                                    )
                        else:
                            # 提取增量内容（OpenAI/DeepSeek 格式）
                            choices = chunk_data.get("choices", [])
                            if choices and len(choices) > 0:
                                choice = choices[0]
                                
                                # 获取增量内容
                                delta = choice.get("delta", {})
                                content = delta.get("content", "")
                                
                                if content:
                                    # 返回流式块
                                    yield StreamChunk(
                                        delta=content,
                                        is_thought=False,
                                        finish_reason=choice.get("finish_reason"),
                                        model=chunk_data.get("model")
                                    )
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析流式响应失败: {line}, 错误: {e}")
                        continue
        
        finally:
            if should_close:
                await client.aclose()
    
    # ==================== 辅助方法 ====================
    
    def _sanitize_request_body_for_log(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理请求体中的敏感/冗长数据，用于日志输出
        
        主要清理：
        - base64 编码的图片数据（Gemini inlineData）
        - 其他大型二进制数据
        
        Args:
            request_body: 原始请求体
        
        Returns:
            清理后的请求体（用于日志）
        """
        import copy
        
        # 深拷贝避免修改原始数据
        sanitized = copy.deepcopy(request_body)
        
        # 处理 Gemini 格式的请求体
        if "contents" in sanitized:
            for content in sanitized.get("contents", []):
                for part in content.get("parts", []):
                    # 清理 inlineData 中的 base64 数据
                    if "inlineData" in part and "data" in part["inlineData"]:
                        data_len = len(part["inlineData"]["data"])
                        part["inlineData"]["data"] = f"<base64_data_{data_len}_bytes>"
        
        # 处理 OpenAI 格式的多模态内容
        if "messages" in sanitized:
            for message in sanitized.get("messages", []):
                content = message.get("content")
                if isinstance(content, list):
                    for item in content:
                        # 清理 image_url 中的 base64 数据
                        if isinstance(item, dict):
                            if item.get("type") == "image_url":
                                image_url = item.get("image_url", {})
                                if isinstance(image_url, dict) and "url" in image_url:
                                    url = image_url["url"]
                                    if url.startswith("data:image"):
                                        data_len = len(url)
                                        image_url["url"] = f"<base64_image_url_{data_len}_bytes>"
        
        return sanitized
    
    def _validate_messages(
        self,
        messages: Union[MessageList, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        验证和转换消息列表
        
        Args:
            messages: 消息列表（可以是 Message 对象或字典）
            
        Returns:
            验证后的字典列表
            
        Raises:
            ValueError: 消息格式错误
        """
        if not messages:
            raise ValueError("消息列表不能为空")
        
        validated = []
        for i, msg in enumerate(messages):
            try:
                # 如果是 Pydantic 模型，转换为字典
                if isinstance(msg, Message):
                    msg_dict = msg.model_dump()
                # 如果是字典，验证格式
                elif isinstance(msg, dict):
                    # 使用 Pydantic 验证
                    validated_msg = Message(**msg)
                    msg_dict = validated_msg.model_dump()
                else:
                    raise ValueError(f"不支持的消息类型: {type(msg)}")
                
                validated.append(msg_dict)
                
            except Exception as e:
                raise ValueError(f"消息 {i} 验证失败: {e}") from e
        
        return validated
    
    def _build_params(self, **kwargs) -> Dict[str, Any]:
        """
        构建生成参数
        
        Args:
            **kwargs: 覆盖参数
            
        Returns:
            完整的参数字典
        """
        params = {
            "model_name": self.model_name,
        }
        
        # 添加可选参数（使用实例配置或覆盖）
        if self.temperature is not None or "temperature" in kwargs:
            params["temperature"] = kwargs.get("temperature", self.temperature)
        
        if self.max_tokens is not None or "max_tokens" in kwargs:
            params["max_tokens"] = kwargs.get("max_tokens", self.max_tokens)
        
        if self.top_p is not None or "top_p" in kwargs:
            params["top_p"] = kwargs.get("top_p", self.top_p)
        
        if self.stream is not None or "stream" in kwargs:
            params["stream"] = kwargs.get("stream", self.stream)
        
        # 添加 provider 特有参数
        params.update(self.extra_params)
        
        # 覆盖参数（kwargs 中的其他参数）
        for key, value in kwargs.items():
            if key not in ["temperature", "max_tokens", "top_p", "stream"]:
                params[key] = value
        
        return params
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "api_base": self.api_base,
            "timeout": self.timeout,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "stream": self.stream,
            "enable_retry": self.enable_retry,
            "max_retries": self.max_retries if self.enable_retry else None,
            "retry_strategy": self.retry_strategy if self.enable_retry else None,
            "extra_params": self.extra_params,
        }
    
    def health_check(self) -> bool:
        """
        健康检查（同步）
        
        Returns:
            是否健康
        """
        try:
            test_messages = [{"role": "user", "content": "健康检查测试"}]
            response = self.generate(messages=test_messages, max_tokens=10)
            
            if response.content and response.usage.total_tokens > 0:
                logger.info("LLM客户端健康检查通过")
                return True
            else:
                logger.error("LLM客户端健康检查失败：响应内容为空")
                return False
        
        except Exception as e:
            logger.error(f"LLM客户端健康检查失败: {e}")
            return False
    
    async def ahealth_check(self) -> bool:
        """
        健康检查（异步）
        
        Returns:
            是否健康
        """
        try:
            test_messages = [{"role": "user", "content": "健康检查测试"}]
            response = await self.agenerate(messages=test_messages, max_tokens=10)
            
            if response.content and response.usage.total_tokens > 0:
                logger.info("LLM客户端健康检查通过")
                return True
            else:
                logger.error("LLM客户端健康检查失败：响应内容为空")
                return False
        
        except Exception as e:
            logger.error(f"LLM客户端健康检查失败: {e}")
            return False


# ==================== 工厂函数 ====================

def create_llm_client(
    provider: str,
    model_name: str,
    config_manager: Optional[ConfigManager] = None,
    env_manager: Optional[EnvManager] = None,
    **kwargs
) -> LLMClient:
    """
    创建 LLM 客户端实例（工厂函数）
    
    每次调用都会创建新的独立实例。
    建议使用上下文管理器来自动管理资源。
    
    Args:
        provider: LLM 提供商（openai, deepseek, gemini, anthropic）
        model_name: 模型名称
        config_manager: 配置管理器，如果为None则使用默认
        env_manager: 环境变量管理器，如果为None则使用默认
        **kwargs: 其他参数（temperature, max_tokens, timeout等）
        
    Returns:
        新的 LLMClient 实例
        
    Examples:
        # 方式1: 直接指定配置（最灵活）
        >>> client = create_llm_client(
        ...     provider="deepseek",
        ...     model_name="deepseek-chat",
        ...     temperature=0.0,
        ...     max_tokens=4096,
        ...     enable_thinking=True
        ... )
        >>> response = client.generate(messages=[...])
        
        # 方式2: 上下文管理器（推荐，批量处理）
        >>> with create_llm_client("deepseek", "deepseek-chat") as client:
        ...     response1 = client.generate(messages=[...])
        ...     response2 = client.generate(messages=[...])
        
        # 方式3: 异步上下文管理器（异步场景）
        >>> async with create_llm_client("deepseek", "deepseek-chat") as client:
        ...     response = await client.agenerate(messages=[...])
    """
    return LLMClient(
        provider=provider,
        model_name=model_name,
        config_manager=config_manager,
        env_manager=env_manager,
        **kwargs
    )