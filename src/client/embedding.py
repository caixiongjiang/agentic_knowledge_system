#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : embedding.py
@Author  : caixiongjiang
@Date    : 2025/12/21 15:53
@Function: 
    Embedding模型请求客户端（本地部署）
    支持同步/异步调用，超时控制，可选重试机制
@Modify History:
    2026/01/04 - 完整实现同步/异步embedding客户端
    2026/01/04 - 移除闭包改用静态方法；移除单例模式，采用工厂函数+上下文管理器
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import asyncio
import logging
from typing import List, Optional, Dict, Any, Union
from pathlib import Path

import httpx
from loguru import logger

from src.utils.config_manager import ConfigManager, get_config_manager
from src.utils.env_manager import EnvManager, get_env_manager
from src.utils.retry_decorator import retry_async, retry_sync


class EmbeddingClient:
    """
    本地部署Embedding模型客户端
    
    特性:
    - 支持同步和异步调用
    - 必须的超时控制
    - 可选的重试机制
    - 批量处理优化
    - 支持上下文管理器，自动管理连接池资源
    
    资源管理说明:
    
    两种使用模式，资源管理机制完全不同：
    
    1. **临时使用模式**（不使用上下文管理器）：
       - 每次调用 embed() 时，在方法内部创建临时 httpx.Client
       - 请求完成后，在 finally 块中自动关闭临时 httpx.Client
       - EmbeddingClient 对象本身由垃圾回收器管理
       - 适合：偶尔调用，单次请求
    
    2. **上下文管理器模式**（推荐）：
       - __enter__ 时创建持久化 httpx.Client（self._sync_client）
       - 多次调用 embed() 复用同一个连接池，性能更优
       - __exit__ 时自动关闭持久化 httpx.Client
       - 适合：批量处理，频繁调用
    
    推荐用法:
    ```python
    # 方式1: 临时使用（偶尔调用，单次请求）
    client = create_embedding_client()
    embedding = client.embed("text")
    # embed()方法内部的临时httpx.Client已自动关闭
    # EmbeddingClient对象由GC管理，无需手动close()
    
    # 方式2: 上下文管理器（推荐，批量处理）
    with create_embedding_client() as client:
        embedding1 = client.embed("text1")  # 复用连接池
        embedding2 = client.embed("text2")  # 复用连接池
    # __exit__自动关闭持久化连接池
    
    # 方式3: 异步上下文管理器（异步场景）
    async with create_embedding_client() as client:
        embedding = await client.aembed("text")
    # __aexit__自动关闭持久化连接池
    ```
    
    ⚠️ 注意：不要手动调用 __enter__() 而不调用 __exit__()，会导致资源泄漏！
    """
    
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        env_manager: Optional[EnvManager] = None,
        custom_config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化Embedding客户端
        
        注意: 每次调用都会创建新的独立实例，无单例模式。
        
        Args:
            config_manager: 配置管理器实例，如果为None则使用默认配置管理器
            env_manager: 环境变量管理器实例，如果为None则使用默认环境管理器
            custom_config: 自定义配置，会覆盖配置文件中的设置
        """
        # 获取配置管理器
        self._config_manager = config_manager or get_config_manager()
        self._env_manager = env_manager or get_env_manager()
        
        # 加载配置
        self._config = self._config_manager.get_embedding_full_config(self._env_manager)
        
        # 应用自定义配置
        if custom_config:
            self._config.update(custom_config)
        
        # 验证必需配置
        self._validate_config()
        
        # 提取配置项
        self.api_base = self._config["api_base"].rstrip("/")
        self.model_name = self._config["model_name"]
        self.dimension = self._config["dimension"]
        self.batch_size = self._config.get("batch_size", 32)
        self.timeout = self._config["timeout"]
        
        # 构建embeddings端点URL（本地部署固定使用 /v1/embeddings）
        self.embeddings_url = f"{self.api_base}/v1/embeddings"
        
        # 重试配置
        self.enable_retry = self._config.get("enable_retry", False)
        self.max_retries = self._config.get("max_retries", 3)
        self.retry_delay = self._config.get("retry_delay", 0.5)
        self.retry_strategy = self._config.get("retry_strategy", "exponential")
        self.max_retry_delay = self._config.get("max_retry_delay", 10.0)
        
        # 认证信息
        self.api_key = self._config.get("api_key")
        
        # 构建请求头
        self._headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"
        
        # 连接池管理（用于上下文管理器模式）
        self._sync_client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
        self._context_mode = False  # 标记是否在上下文管理器中
        
        # 日志
        logger.info(
            f"Embedding客户端初始化完成 - "
            f"API: {self.embeddings_url}, "
            f"模型: {self.model_name}, 维度: {self.dimension}, "
            f"超时: {self.timeout}s, 重试: {self.enable_retry}"
        )
    
    def _validate_config(self) -> None:
        """验证配置完整性"""
        required_fields = ["api_base", "model_name", "dimension", "timeout"]
        missing_fields = [field for field in required_fields if field not in self._config]
        
        if missing_fields:
            raise ValueError(f"Embedding配置缺少必需字段: {', '.join(missing_fields)}")
        
        # 验证超时时间
        if not isinstance(self._config["timeout"], (int, float)) or self._config["timeout"] <= 0:
            raise ValueError(f"timeout必须是正数，当前值: {self._config['timeout']}")
        
        # 验证维度
        if not isinstance(self._config["dimension"], int) or self._config["dimension"] <= 0:
            raise ValueError(f"dimension必须是正整数，当前值: {self._config['dimension']}")
    
    # ==================== 上下文管理器（资源管理） ====================
    
    def __enter__(self) -> 'EmbeddingClient':
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
    
    async def __aenter__(self) -> 'EmbeddingClient':
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
        如果只是临时调用embed()，无需调用此方法（临时客户端已自动关闭）。
        
        使用场景:
        - 提前退出上下文管理器（不推荐，应该用with语句）
        - 某些特殊场景需要手动管理上下文
        
        Example:
            >>> # 不推荐（应该用with语句）
            >>> client = create_embedding_client()
            >>> client.__enter__()  # 手动进入上下文
            >>> embedding = client.embed("text")
            >>> client.close()  # 手动关闭
        """
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None
            logger.debug("手动关闭同步HTTP客户端")
    
    async def aclose(self) -> None:
        """
        显式关闭异步客户端，释放连接池资源
        
        注意: 只有在使用了异步上下文管理器（async with）后，才会有持久化客户端需要关闭。
        如果只是临时调用aembed()，无需调用此方法（临时客户端已自动关闭）。
        
        使用场景:
        - 提前退出异步上下文管理器（不推荐，应该用async with语句）
        - 某些特殊场景需要手动管理上下文
        
        Example:
            >>> # 不推荐（应该用async with语句）
            >>> client = create_embedding_client()
            >>> await client.__aenter__()  # 手动进入上下文
            >>> embedding = await client.aembed("text")
            >>> await client.aclose()  # 手动关闭
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
    
    def embed(self, text: str) -> List[float]:
        """
        同步单条文本embedding
        
        Args:
            text: 输入文本
            
        Returns:
            向量列表
            
        Raises:
            ValueError: 文本为空
            httpx.HTTPError: HTTP请求错误
            TimeoutError: 请求超时
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        
        return self.embed_batch([text])[0]
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        同步批量文本embedding
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表的列表
            
        Raises:
            ValueError: 文本列表为空或包含空文本
            httpx.HTTPError: HTTP请求错误
            TimeoutError: 请求超时
        """
        if not texts:
            raise ValueError("文本列表不能为空")
        
        # 过滤空文本
        non_empty_texts = [t for t in texts if t and t.strip()]
        if len(non_empty_texts) != len(texts):
            logger.warning(f"过滤了 {len(texts) - len(non_empty_texts)} 个空文本")
        
        if not non_empty_texts:
            raise ValueError("没有有效的非空文本")
        
        # 如果启用重试，使用装饰器包装的方法
        if self.enable_retry:
            return self._embed_batch_with_retry_sync(non_empty_texts)
        else:
            return self._embed_batch_sync(non_empty_texts)
    
    def _embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """
        同步批量embedding的核心实现（无重试）
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        # 分批处理
        all_embeddings = []
        
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
            for i in range(0, len(texts), self.batch_size):
                batch_texts = texts[i:i + self.batch_size]
                
                logger.debug(
                    f"处理批次 {i // self.batch_size + 1}/{(len(texts) - 1) // self.batch_size + 1} "
                    f"({len(batch_texts)} 条文本)"
                )
                
                # 构建请求
                payload = {
                    "model": self.model_name,
                    "input": batch_texts,
                }
                
                # 发送请求
                try:
                    response = client.post(
                        self.embeddings_url,
                        json=payload,
                        headers=self._headers
                    )
                    response.raise_for_status()
                    
                except httpx.TimeoutException as e:
                    logger.error(f"Embedding请求超时 ({self.timeout}s): {e}")
                    raise TimeoutError(f"Embedding请求超时 ({self.timeout}s)") from e
                
                except httpx.HTTPError as e:
                    logger.error(f"Embedding请求失败: {e}")
                    raise
                
                # 解析响应
                result = response.json()
                embeddings = self._parse_response(result)
                all_embeddings.extend(embeddings)
        
        finally:
            # 如果是临时客户端，确保关闭释放资源
            if should_close:
                client.close()
        
        logger.info(f"成功获取 {len(all_embeddings)} 个文本的embedding")
        return all_embeddings
    
    def _embed_batch_with_retry_sync(self, texts: List[str]) -> List[List[float]]:
        """
        带重试的同步批量embedding
        
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
        
        wrapped_func = retry_decorator(self._embed_batch_sync)
        return wrapped_func(texts)
    
    # ==================== 异步方法 ====================
    
    async def aembed(self, text: str) -> List[float]:
        """
        异步单条文本embedding
        
        Args:
            text: 输入文本
            
        Returns:
            向量列表
            
        Raises:
            ValueError: 文本为空
            httpx.HTTPError: HTTP请求错误
            TimeoutError: 请求超时
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        
        embeddings = await self.aembed_batch([text])
        return embeddings[0]
    
    async def aembed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        异步批量文本embedding
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表的列表
            
        Raises:
            ValueError: 文本列表为空或包含空文本
            httpx.HTTPError: HTTP请求错误
            TimeoutError: 请求超时
        """
        if not texts:
            raise ValueError("文本列表不能为空")
        
        # 过滤空文本
        non_empty_texts = [t for t in texts if t and t.strip()]
        if len(non_empty_texts) != len(texts):
            logger.warning(f"过滤了 {len(texts) - len(non_empty_texts)} 个空文本")
        
        if not non_empty_texts:
            raise ValueError("没有有效的非空文本")
        
        # 如果启用重试，使用装饰器包装的方法
        if self.enable_retry:
            return await self._aembed_batch_with_retry_async(non_empty_texts)
        else:
            return await self._aembed_batch(non_empty_texts)
    
    async def _aembed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        异步批量embedding的核心实现（无重试）
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        # 分批处理
        all_embeddings = []
        
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
            for i in range(0, len(texts), self.batch_size):
                batch_texts = texts[i:i + self.batch_size]
                
                logger.debug(
                    f"处理批次 {i // self.batch_size + 1}/{(len(texts) - 1) // self.batch_size + 1} "
                    f"({len(batch_texts)} 条文本)"
                )
                
                # 构建请求
                payload = {
                    "model": self.model_name,
                    "input": batch_texts,
                }
                
                # 发送请求
                try:
                    response = await client.post(
                        self.embeddings_url,
                        json=payload,
                        headers=self._headers
                    )
                    response.raise_for_status()
                    
                except httpx.TimeoutException as e:
                    logger.error(f"Embedding请求超时 ({self.timeout}s): {e}")
                    raise TimeoutError(f"Embedding请求超时 ({self.timeout}s)") from e
                
                except httpx.HTTPError as e:
                    logger.error(f"Embedding请求失败: {e}")
                    raise
                
                # 解析响应
                result = response.json()
                embeddings = self._parse_response(result)
                all_embeddings.extend(embeddings)
        
        finally:
            # 如果是临时客户端，确保关闭释放资源
            if should_close:
                await client.aclose()
        
        logger.info(f"成功获取 {len(all_embeddings)} 个文本的embedding")
        return all_embeddings
    
    async def _aembed_batch_with_retry_async(self, texts: List[str]) -> List[List[float]]:
        """
        带重试的异步批量embedding
        
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
        
        wrapped_func = retry_decorator(self._aembed_batch)
        return await wrapped_func(texts)
    
    # ==================== 高级异步方法 ====================
    
    async def aembed_concurrent(
        self,
        texts: List[str],
        max_concurrent: int = 5
    ) -> List[List[float]]:
        """
        并发异步批量embedding（适用于大量文本）
        
        Args:
            texts: 文本列表
            max_concurrent: 最大并发请求数
            
        Returns:
            向量列表的列表
        """
        if not texts:
            raise ValueError("文本列表不能为空")
        
        # 过滤空文本
        non_empty_texts = [t for t in texts if t and t.strip()]
        if not non_empty_texts:
            raise ValueError("没有有效的非空文本")
        
        # 分组
        batches = [
            non_empty_texts[i:i + self.batch_size]
            for i in range(0, len(non_empty_texts), self.batch_size)
        ]
        
        logger.info(f"开始并发处理 {len(batches)} 个批次（最大并发: {max_concurrent}）")
        
        # 创建信号量限制并发数
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # 并发执行 - 使用静态方法代替闭包
        tasks = [
            self._process_single_batch_with_semaphore(batch, semaphore)
            for batch in batches
        ]
        results = await asyncio.gather(*tasks)
        
        # 合并结果
        all_embeddings = []
        for batch_embeddings in results:
            all_embeddings.extend(batch_embeddings)
        
        logger.info(f"并发处理完成，共获取 {len(all_embeddings)} 个embedding")
        return all_embeddings
    
    async def _process_single_batch_with_semaphore(
        self,
        batch_texts: List[str],
        semaphore: asyncio.Semaphore
    ) -> List[List[float]]:
        """
        使用信号量控制的单批次处理（替代闭包）
        
        Args:
            batch_texts: 批次文本列表
            semaphore: 并发控制信号量
            
        Returns:
            该批次的embedding列表
        """
        async with semaphore:
            if self.enable_retry:
                return await self._aembed_batch_with_retry_async(batch_texts)
            else:
                return await self._aembed_batch(batch_texts)
    
    # ==================== 辅助方法 ====================
    
    def _parse_response(self, response: Dict[str, Any]) -> List[List[float]]:
        """
        解析API响应
        
        Args:
            response: API响应JSON
            
        Returns:
            向量列表
            
        Raises:
            ValueError: 响应格式错误
        """
        try:
            # OpenAI兼容格式
            if "data" in response:
                embeddings = [item["embedding"] for item in response["data"]]
                
                # 验证维度
                for i, emb in enumerate(embeddings):
                    if len(emb) != self.dimension:
                        raise ValueError(
                            f"第 {i} 个embedding维度不匹配: "
                            f"期望 {self.dimension}, 实际 {len(emb)}"
                        )
                
                return embeddings
            
            # 其他格式
            elif "embeddings" in response:
                embeddings = response["embeddings"]
                
                # 验证维度
                for i, emb in enumerate(embeddings):
                    if len(emb) != self.dimension:
                        raise ValueError(
                            f"第 {i} 个embedding维度不匹配: "
                            f"期望 {self.dimension}, 实际 {len(emb)}"
                        )
                
                return embeddings
            
            else:
                raise ValueError(f"无法解析响应格式: {list(response.keys())}")
        
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"解析embedding响应失败: {e}, 响应: {response}")
            raise ValueError(f"解析embedding响应失败: {e}") from e
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "api_base": self.api_base,
            "model_name": self.model_name,
            "dimension": self.dimension,
            "batch_size": self.batch_size,
            "timeout": self.timeout,
            "enable_retry": self.enable_retry,
            "max_retries": self.max_retries if self.enable_retry else None,
            "retry_strategy": self.retry_strategy if self.enable_retry else None,
        }
    
    def health_check(self) -> bool:
        """
        健康检查（同步）
        
        Returns:
            是否健康
        """
        try:
            test_text = "健康检查测试文本"
            embedding = self.embed(test_text)
            
            if len(embedding) == self.dimension:
                logger.info("Embedding客户端健康检查通过")
                return True
            else:
                logger.error(f"Embedding维度不匹配: 期望 {self.dimension}, 实际 {len(embedding)}")
                return False
        
        except Exception as e:
            logger.error(f"Embedding客户端健康检查失败: {e}")
            return False
    
    async def ahealth_check(self) -> bool:
        """
        健康检查（异步）
        
        Returns:
            是否健康
        """
        try:
            test_text = "健康检查测试文本"
            embedding = await self.aembed(test_text)
            
            if len(embedding) == self.dimension:
                logger.info("Embedding客户端健康检查通过")
                return True
            else:
                logger.error(f"Embedding维度不匹配: 期望 {self.dimension}, 实际 {len(embedding)}")
                return False
        
        except Exception as e:
            logger.error(f"Embedding客户端健康检查失败: {e}")
            return False


# ==================== 工厂函数 ====================

def create_embedding_client(
    config_manager: Optional[ConfigManager] = None,
    env_manager: Optional[EnvManager] = None,
    custom_config: Optional[Dict[str, Any]] = None
) -> EmbeddingClient:
    """
    创建Embedding客户端实例（工厂函数）
    
    每次调用都会创建新的独立实例，无单例模式。
    建议使用上下文管理器来自动管理资源。
    
    Args:
        config_manager: 配置管理器，如果为None则使用默认
        env_manager: 环境变量管理器，如果为None则使用默认
        custom_config: 自定义配置，会覆盖配置文件中的设置
        
    Returns:
        新的EmbeddingClient实例
        
    Examples:
        # 方式1: 临时使用（适合偶尔调用、单次请求）
        >>> client = create_embedding_client()
        >>> embedding = client.embed("text")
        # 资源管理：embed()内部创建临时httpx.Client，完成后自动关闭
        # EmbeddingClient对象由GC管理，无需手动close()
        # 缺点：每次调用都创建新连接，性能略低
        
        # 方式2: 上下文管理器（推荐，批量处理、频繁调用）
        >>> with create_embedding_client() as client:
        ...     embedding1 = client.embed("text1")
        ...     embedding2 = client.embed("text2")
        ...     embeddings = client.embed_batch(["text3", "text4", "text5"])
        # 资源管理：__enter__创建持久化httpx.Client，多次调用复用连接池
        #          __exit__自动关闭持久化httpx.Client
        # 优点：复用连接池，性能优异
        
        # 方式3: 异步上下文管理器（异步场景推荐）
        >>> async with create_embedding_client() as client:
        ...     embedding = await client.aembed("text")
        ...     embeddings = await client.aembed_concurrent(texts, max_concurrent=10)
        # 资源管理：__aenter__创建持久化httpx.AsyncClient
        #          __aexit__自动关闭
        
        # 方式4: 多个不同配置的客户端
        >>> client_fast = create_embedding_client(custom_config={"timeout": 10})
        >>> client_slow = create_embedding_client(custom_config={"timeout": 60})
        >>> fast_result = client_fast.embed("short text")  # 临时httpx.Client自动管理
        >>> slow_result = client_slow.embed("long text")   # 临时httpx.Client自动管理
    """
    return EmbeddingClient(
        config_manager=config_manager,
        env_manager=env_manager,
        custom_config=custom_config
    )
