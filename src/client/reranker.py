#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : reranker.py
@Author  : caixiongjiang
@Date    : 2025/12/21 15:54
@Function: 
    Reranker 模型请求客户端（本地部署 / API 服务）
    支持同步/异步调用，超时控制，可选重试机制
@Modify History:
    2026/04/03 - 完整实现，参照 EmbeddingClient 设计模式
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import logging
from typing import List, Optional, Dict, Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from src.utils.config_manager import ConfigManager, get_config_manager
from src.utils.env_manager import EnvManager, get_env_manager
from src.utils.retry_decorator import retry_async, retry_sync


class RerankResult(BaseModel):
    """单条重排序结果"""
    index: int = Field(..., description="原始文档列表中的索引")
    score: float = Field(..., description="相关性分数")
    text: str = Field(default="", description="原始文档文本")


class RerankerClient:
    """
    Reranker 模型客户端

    支持本地部署的 Cross-Encoder 服务（如 bge-reranker-v2-m3）
    以及 Cohere / Jina 等 API 服务。

    资源管理与 EmbeddingClient 完全一致，支持上下文管理器和临时使用两种模式。

    推荐用法:
    ```python
    # 方式1: 临时使用
    client = create_reranker_client()
    results = client.rerank("查询文本", ["文档1", "文档2"])

    # 方式2: 上下文管理器（推荐）
    with create_reranker_client() as client:
        results = client.rerank("查询", docs)

    # 方式3: 异步
    async with create_reranker_client() as client:
        results = await client.arerank("查询", docs)
    ```
    """

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        env_manager: Optional[EnvManager] = None,
        custom_config: Optional[Dict[str, Any]] = None,
    ):
        self._sync_client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
        self._context_mode = False

        self._config_manager = config_manager or get_config_manager()
        self._env_manager = env_manager or get_env_manager()

        self._config = self._config_manager.get_reranker_full_config(self._env_manager)

        if custom_config:
            self._config.update(custom_config)

        self._validate_config()

        self.provider = self._config.get("provider", "local").lower()
        self.model_name = self._config.get("model_name", "")
        self.api_base = self._config.get("api_base", "").rstrip("/")
        self.batch_size = self._config.get("batch_size", 16)
        self.default_top_k = self._config.get("top_k", 10)
        self.timeout = self._config.get("timeout", 30)

        self.enable_retry = self._config.get("enable_retry", False)
        self.max_retries = self._config.get("max_retries", 3)
        self.retry_delay = self._config.get("retry_delay", 0.5)
        self.retry_strategy = self._config.get("retry_strategy", "exponential")
        self.max_retry_delay = self._config.get("max_retry_delay", 10.0)

        self.api_key = self._config.get("api_key")

        self._headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"

        logger.info(
            f"Reranker客户端初始化完成 - "
            f"Provider: {self.provider}, "
            f"Model: {self.model_name}, "
            f"API: {self.api_base}, "
            f"超时: {self.timeout}s"
        )

    def _validate_config(self) -> None:
        required_fields = ["provider", "model_name", "timeout"]
        missing = [f for f in required_fields if not self._config.get(f)]
        if missing:
            raise ValueError(f"Reranker配置缺少必需字段: {', '.join(missing)}")

    # ==================== 上下文管理器 ====================

    def __enter__(self) -> "RerankerClient":
        self._context_mode = True
        self._sync_client = httpx.Client(timeout=self.timeout)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._context_mode = False
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None
        return False

    async def __aenter__(self) -> "RerankerClient":
        self._context_mode = True
        self._async_client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._context_mode = False
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None
        return False

    def close(self) -> None:
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    async def aclose(self) -> None:
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def __del__(self):
        if self._sync_client is not None:
            try:
                self._sync_client.close()
            except Exception:
                pass

    # ==================== 同步方法 ====================

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
    ) -> List[RerankResult]:
        """
        同步重排序

        Args:
            query: 查询文本
            documents: 待排序的文档列表
            top_k: 返回 top-K 结果，None 时使用配置默认值

        Returns:
            按相关性降序排列的 RerankResult 列表
        """
        if not query or not query.strip():
            raise ValueError("查询文本不能为空")
        if not documents:
            raise ValueError("文档列表不能为空")

        top_k = top_k or self.default_top_k

        if self.enable_retry:
            return self._rerank_with_retry_sync(query, documents, top_k)
        return self._rerank_sync(query, documents, top_k)

    def _rerank_sync(
        self, query: str, documents: List[str], top_k: int,
    ) -> List[RerankResult]:
        if self._context_mode and self._sync_client is not None:
            client = self._sync_client
            should_close = False
        else:
            client = httpx.Client(timeout=self.timeout)
            should_close = True

        try:
            all_results: List[RerankResult] = []

            rerank_url = self._get_rerank_url()

            for i in range(0, len(documents), self.batch_size):
                batch_docs = documents[i : i + self.batch_size]
                batch_offset = i

                # 每批请求全部结果，全局排序后再截断
                batch_top_n = len(batch_docs)
                payload = self._build_request_payload(query, batch_docs, batch_top_n)

                try:
                    response = client.post(
                        rerank_url, json=payload, headers=self._headers,
                    )
                    response.raise_for_status()
                except httpx.TimeoutException as e:
                    raise TimeoutError(
                        f"Reranker请求超时 ({self.timeout}s)"
                    ) from e
                except httpx.HTTPError:
                    raise

                result = response.json()
                batch_results = self._parse_response(result, batch_docs, batch_offset)
                all_results.extend(batch_results)

            all_results.sort(key=lambda r: r.score, reverse=True)
            return all_results[:top_k]

        finally:
            if should_close:
                client.close()

    def _rerank_with_retry_sync(
        self, query: str, documents: List[str], top_k: int,
    ) -> List[RerankResult]:
        decorator = retry_sync(
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            retry_strategy=self.retry_strategy,
            max_delay=self.max_retry_delay,
            exceptions=(httpx.HTTPError, TimeoutError),
            logger=logging.getLogger(__name__),
            raise_on_failure=True,
        )
        wrapped = decorator(self._rerank_sync)
        return wrapped(query, documents, top_k)

    # ==================== 异步方法 ====================

    async def arerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
    ) -> List[RerankResult]:
        """
        异步重排序

        Args:
            query: 查询文本
            documents: 待排序的文档列表
            top_k: 返回 top-K 结果

        Returns:
            按相关性降序排列的 RerankResult 列表
        """
        if not query or not query.strip():
            raise ValueError("查询文本不能为空")
        if not documents:
            raise ValueError("文档列表不能为空")

        top_k = top_k or self.default_top_k

        if self.enable_retry:
            return await self._arerank_with_retry(query, documents, top_k)
        return await self._arerank(query, documents, top_k)

    async def _arerank(
        self, query: str, documents: List[str], top_k: int,
    ) -> List[RerankResult]:
        if self._context_mode and self._async_client is not None:
            client = self._async_client
            should_close = False
        else:
            client = httpx.AsyncClient(timeout=self.timeout)
            should_close = True

        try:
            all_results: List[RerankResult] = []

            rerank_url = self._get_rerank_url()

            for i in range(0, len(documents), self.batch_size):
                batch_docs = documents[i : i + self.batch_size]
                batch_offset = i

                batch_top_n = len(batch_docs)
                payload = self._build_request_payload(query, batch_docs, batch_top_n)

                try:
                    response = await client.post(
                        rerank_url, json=payload, headers=self._headers,
                    )
                    response.raise_for_status()
                except httpx.TimeoutException as e:
                    raise TimeoutError(
                        f"Reranker请求超时 ({self.timeout}s)"
                    ) from e
                except httpx.HTTPError:
                    raise

                result = response.json()
                batch_results = self._parse_response(result, batch_docs, batch_offset)
                all_results.extend(batch_results)

            all_results.sort(key=lambda r: r.score, reverse=True)
            return all_results[:top_k]

        finally:
            if should_close:
                await client.aclose()

    async def _arerank_with_retry(
        self, query: str, documents: List[str], top_k: int,
    ) -> List[RerankResult]:
        decorator = retry_async(
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            retry_strategy=self.retry_strategy,
            max_delay=self.max_retry_delay,
            exceptions=(httpx.HTTPError, TimeoutError),
            logger=logging.getLogger(__name__),
            raise_on_failure=True,
            timeout=None,
        )
        wrapped = decorator(self._arerank)
        return await wrapped(query, documents, top_k)

    # ==================== 请求构建 ====================

    def _get_rerank_url(self) -> str:
        if self.provider == "cohere":
            return f"{self.api_base}/rerank"
        elif self.provider == "jina":
            return f"{self.api_base}/rerank"
        return f"{self.api_base}/rerank"

    def _build_request_payload(
        self, query: str, documents: List[str], top_k: int,
    ) -> Dict[str, Any]:
        if self.provider == "cohere":
            return {
                "model": self.model_name,
                "query": query,
                "documents": documents,
                "top_n": top_k,
                "return_documents": False,
            }
        elif self.provider == "jina":
            return {
                "model": self.model_name,
                "query": query,
                "documents": documents,
                "top_n": top_k,
            }
        # local / default: OpenAI-compatible or custom reranker API
        return {
            "model": self.model_name,
            "query": query,
            "documents": documents,
            "top_n": top_k,
        }

    # ==================== 响应解析 ====================

    def _parse_response(
        self,
        response: Dict[str, Any],
        original_docs: List[str],
        batch_offset: int,
    ) -> List[RerankResult]:
        """
        解析 reranker 响应。

        支持两种常见格式:
        1. {"results": [{"index": 0, "relevance_score": 0.95}, ...]}  (Cohere/Jina)
        2. {"results": [{"index": 0, "score": 0.95}, ...]}  (通用)
        """
        try:
            results_raw = response.get("results", [])
            parsed: List[RerankResult] = []

            for item in results_raw:
                idx = item.get("index", 0)
                score = item.get("relevance_score", item.get("score", 0.0))
                text = ""
                if idx < len(original_docs):
                    text = original_docs[idx]
                parsed.append(RerankResult(
                    index=idx + batch_offset,
                    score=float(score),
                    text=text,
                ))

            return parsed

        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"解析Reranker响应失败: {e}, 响应: {response}")
            raise ValueError(f"解析Reranker响应失败: {e}") from e

    # ==================== 辅助方法 ====================

    def get_config(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "api_base": self.api_base,
            "batch_size": self.batch_size,
            "default_top_k": self.default_top_k,
            "timeout": self.timeout,
            "enable_retry": self.enable_retry,
        }

    def health_check(self) -> bool:
        try:
            results = self.rerank("测试查询", ["测试文档"], top_k=1)
            if results:
                logger.info("Reranker客户端健康检查通过")
                return True
            logger.error("Reranker健康检查失败：无结果")
            return False
        except Exception as e:
            logger.error(f"Reranker客户端健康检查失败: {e}")
            return False

    async def ahealth_check(self) -> bool:
        try:
            results = await self.arerank("测试查询", ["测试文档"], top_k=1)
            if results:
                logger.info("Reranker客户端健康检查通过")
                return True
            logger.error("Reranker健康检查失败：无结果")
            return False
        except Exception as e:
            logger.error(f"Reranker客户端健康检查失败: {e}")
            return False


# ==================== 工厂函数 ====================

def create_reranker_client(
    config_manager: Optional[ConfigManager] = None,
    env_manager: Optional[EnvManager] = None,
    custom_config: Optional[Dict[str, Any]] = None,
) -> RerankerClient:
    """
    创建 Reranker 客户端实例（工厂函数）

    Args:
        config_manager: 配置管理器
        env_manager: 环境变量管理器
        custom_config: 自定义配置

    Returns:
        新的 RerankerClient 实例
    """
    return RerankerClient(
        config_manager=config_manager,
        env_manager=env_manager,
        custom_config=custom_config,
    )
