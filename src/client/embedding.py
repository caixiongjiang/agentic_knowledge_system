#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : embedding.py
@Author  : caixiongjiang
@Date    : 2025/12/21 15:53
@Function:
    Embedding 客户端

    1. **EmbeddingClient（稠密向量）** — LiteLLM 薄封装
       - 通过 ``litellm.embedding`` / ``litellm.aembedding`` 走自托管 LiteLLM Proxy
       - 业务侧只暴露：``embed`` / ``embed_batch`` / ``aembed`` / ``aembed_batch`` /
         ``aembed_concurrent`` 与 ``health_check``
       - 客户端侧只做：批分（``batch_size``）+ 并发限流（``max_concurrent``）+ 维度校验
       - 重试 / 超时由 LiteLLM 内部 + Proxy 层统一处理
       - 上下文管理器接口保留（无状态 no-op），便于上层 ``with``/``async with`` 写法不变
    2. **SparseEmbeddingClient（BGE-M3 稀疏向量）** — 维持原 httpx 实现
       - LiteLLM 暂不支持 sparse_embedding 输出，因此该客户端不走 Proxy

@Modify History:
    2026/04/21 - 改造为 LiteLLM 薄封装，移除自实现的 httpx + retry 重型逻辑
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from src.utils.config_manager import ConfigManager, get_config_manager
from src.utils.env_manager import EnvManager, get_env_manager
from src.utils.retry_decorator import retry_async, retry_sync


# ==================== 稠密向量：LiteLLM 薄封装 ====================


class EmbeddingClient:
    """稠密向量 Embedding 客户端（LiteLLM 薄封装）

    设计要点
    --------
    - 模型字符串从 ``[embedding.presets.<name>]`` 取，形如 ``"openai/qwen3-embedding-0.6b"``，
      由 LiteLLM 路由到自托管 Proxy（``api_base`` / ``api_key`` 走 ``[proxy]`` + ``.env``）。
    - 客户端只做批分 + 并发限流 + 维度校验；HTTP 重试 / 连接池由 LiteLLM 接管。
    - ``with`` / ``async with`` 接口保留为 no-op（LiteLLM 内部维护连接池），
      调用方代码无需感知。

    选择 preset
    -----------
    - 默认使用 ``[embedding].default_preset``。
    - 通过 ``preset_name="..."`` 指定其它 preset。
    - ``custom_config`` 可以临时覆盖任意字段（``model`` / ``dimension`` /
      ``api_base`` / ``api_key`` / ``batch_size`` / ``timeout`` / ``extra_params``）。
    """

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        env_manager: Optional[EnvManager] = None,
        custom_config: Optional[Dict[str, Any]] = None,
        preset_name: Optional[str] = None,
    ) -> None:
        # 复用 LLMClient 的 LiteLLM 初始化（telemetry off / drop_params 等）
        from src.client.llm.client import _ensure_litellm_initialized

        _ensure_litellm_initialized()

        self._config_manager = config_manager or get_config_manager()
        self._env_manager = env_manager or get_env_manager()

        merged = self._config_manager.get_embedding_full_config(
            self._env_manager, preset_name=preset_name
        )
        if custom_config:
            merged.update(custom_config)

        if not merged.get("model"):
            raise ValueError(
                "EmbeddingClient 配置缺少 'model'，请在 [embedding.presets.*] 中声明"
            )

        self.model_name: str = merged["model"]
        self.api_base: Optional[str] = merged.get("api_base")
        self.api_key: Optional[str] = merged.get("api_key")
        self.dimension: Optional[int] = (
            int(merged["dimension"]) if merged.get("dimension") else None
        )
        self.batch_size: int = int(merged.get("batch_size", 32))
        self.max_concurrent: int = int(merged.get("max_concurrent", 5))
        self.timeout: float = float(merged.get("timeout", 60.0))
        self.extra_params: Dict[str, Any] = dict(merged.get("extra_params") or {})

        logger.info(
            f"EmbeddingClient 初始化完成 - model={self.model_name} "
            f"api_base={self.api_base or '(env/default)'} dim={self.dimension} "
            f"batch={self.batch_size} max_concurrent={self.max_concurrent} "
            f"timeout={self.timeout}s"
        )

    # ---------- 上下文管理器（保留兼容，LiteLLM 内部维护连接池） ----------
    def __enter__(self) -> "EmbeddingClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False

    async def __aenter__(self) -> "EmbeddingClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False

    def close(self) -> None:
        return None

    async def aclose(self) -> None:
        return None

    # ---------- 同步 ----------
    def embed(self, text: str) -> List[float]:
        """同步单条文本编码"""
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """同步批量编码（按 ``batch_size`` 切批，依次调用 LiteLLM）"""
        import litellm

        cleaned = self._sanitize(texts)
        all_emb: List[List[float]] = []
        total_batches = (len(cleaned) + self.batch_size - 1) // self.batch_size
        for batch_idx, start in enumerate(range(0, len(cleaned), self.batch_size), 1):
            batch = cleaned[start : start + self.batch_size]
            logger.debug(f"Embedding 批次 {batch_idx}/{total_batches} size={len(batch)}")
            resp = litellm.embedding(
                model=self.model_name,
                input=batch,
                api_base=self.api_base,
                api_key=self.api_key,
                timeout=self.timeout,
                **self.extra_params,
            )
            all_emb.extend(self._parse(resp))
        logger.info(f"成功获取 {len(all_emb)} 个文本的稠密向量")
        return all_emb

    # ---------- 异步 ----------
    async def aembed(self, text: str) -> List[float]:
        """异步单条文本编码"""
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        results = await self.aembed_batch([text])
        return results[0]

    async def aembed_batch(self, texts: List[str]) -> List[List[float]]:
        """异步批量编码（按 ``batch_size`` 切批，串行 await）"""
        import litellm

        cleaned = self._sanitize(texts)
        all_emb: List[List[float]] = []
        total_batches = (len(cleaned) + self.batch_size - 1) // self.batch_size
        for batch_idx, start in enumerate(range(0, len(cleaned), self.batch_size), 1):
            batch = cleaned[start : start + self.batch_size]
            logger.debug(
                f"Embedding[async] 批次 {batch_idx}/{total_batches} size={len(batch)}"
            )
            resp = await litellm.aembedding(
                model=self.model_name,
                input=batch,
                api_base=self.api_base,
                api_key=self.api_key,
                timeout=self.timeout,
                **self.extra_params,
            )
            all_emb.extend(self._parse(resp))
        logger.info(f"成功获取 {len(all_emb)} 个文本的稠密向量")
        return all_emb

    async def aembed_concurrent(
        self,
        texts: List[str],
        max_concurrent: Optional[int] = None,
    ) -> List[List[float]]:
        """异步并发批量编码，受 ``max_concurrent`` 信号量限流"""
        import litellm

        cleaned = self._sanitize(texts)
        limit = max_concurrent or self.max_concurrent
        batches = [
            cleaned[i : i + self.batch_size]
            for i in range(0, len(cleaned), self.batch_size)
        ]
        logger.info(f"Embedding[concurrent] {len(batches)} 批 / 最大并发 {limit}")
        sem = asyncio.Semaphore(limit)

        async def _run(batch: List[str]) -> List[List[float]]:
            async with sem:
                resp = await litellm.aembedding(
                    model=self.model_name,
                    input=batch,
                    api_base=self.api_base,
                    api_key=self.api_key,
                    timeout=self.timeout,
                    **self.extra_params,
                )
                return self._parse(resp)

        results = await asyncio.gather(*[_run(b) for b in batches])
        flat = [v for batch in results for v in batch]
        logger.info(f"Embedding[concurrent] 完成，共 {len(flat)} 个向量")
        return flat

    # ---------- 工具方法 ----------
    @staticmethod
    def _sanitize(texts: List[str]) -> List[str]:
        if not texts:
            raise ValueError("文本列表不能为空")
        cleaned = [t for t in texts if t and t.strip()]
        if len(cleaned) != len(texts):
            logger.warning(f"过滤了 {len(texts) - len(cleaned)} 个空文本")
        if not cleaned:
            raise ValueError("没有有效的非空文本")
        return cleaned

    def _parse(self, resp: Any) -> List[List[float]]:
        """统一解析 LiteLLM EmbeddingResponse 为 ``List[List[float]]`` 并校验维度"""
        try:
            data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
        except Exception:
            data = resp  # type: ignore[assignment]
        items = data.get("data") if isinstance(data, dict) else None
        if not items:
            raise ValueError(f"LiteLLM 返回无 data 字段: {data!r}")
        embeddings: List[List[float]] = []
        for idx, item in enumerate(items):
            emb = item.get("embedding") if isinstance(item, dict) else None
            if emb is None:
                raise ValueError(f"data[{idx}] 缺少 'embedding' 字段")
            if self.dimension and len(emb) != self.dimension:
                raise ValueError(
                    f"第 {idx} 个 embedding 维度不匹配: 期望 {self.dimension}, 实际 {len(emb)}"
                )
            embeddings.append(list(emb))
        return embeddings

    # ---------- 健康检查 ----------
    def health_check(self) -> bool:
        try:
            v = self.embed("健康检查")
            ok = bool(v) and (self.dimension is None or len(v) == self.dimension)
            if ok:
                logger.info(f"Embedding 健康检查通过 (model={self.model_name})")
            return ok
        except Exception as e:
            logger.error(f"Embedding 健康检查失败: {e}")
            return False

    async def ahealth_check(self) -> bool:
        try:
            v = await self.aembed("健康检查")
            ok = bool(v) and (self.dimension is None or len(v) == self.dimension)
            if ok:
                logger.info(f"Embedding 健康检查通过 (model={self.model_name})")
            return ok
        except Exception as e:
            logger.error(f"Embedding 健康检查失败: {e}")
            return False

    # ---------- 辅助 ----------
    def get_config(self) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "api_base": self.api_base,
            "dimension": self.dimension,
            "batch_size": self.batch_size,
            "max_concurrent": self.max_concurrent,
            "timeout": self.timeout,
        }


# ==================== 稀疏向量：BGE-M3（独立实现，未走 LiteLLM） ====================


class SparseEmbeddingClient:
    """BGE-M3 稀疏向量客户端

    LiteLLM 暂不支持 ``sparse_embedding`` 字段输出，因此 BGE-M3 仍走自实现的
    ``httpx`` 客户端，保留同步/异步、上下文管理器、显式重试机制。

    返回格式：``Dict[int, float]``（``{token_id: weight}``）。
    """

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        env_manager: Optional[EnvManager] = None,
        custom_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._config_manager = config_manager or get_config_manager()
        self._env_manager = env_manager or get_env_manager()

        self._config = self._config_manager.get_sparse_embedding_full_config(self._env_manager)
        if custom_config:
            self._config.update(custom_config)

        self._validate_config()

        self.api_base: str = self._config["api_base"].rstrip("/")
        self.model_name: str = self._config["model_name"]
        self.batch_size: int = int(self._config.get("batch_size", 32))
        self.timeout: float = float(self._config["timeout"])

        self.embeddings_url = f"{self.api_base}/embeddings"

        self.enable_retry: bool = bool(self._config.get("enable_retry", False))
        self.max_retries: int = int(self._config.get("max_retries", 3))
        self.retry_delay: float = float(self._config.get("retry_delay", 0.5))
        self.retry_strategy: str = str(self._config.get("retry_strategy", "exponential"))
        self.max_retry_delay: float = float(self._config.get("max_retry_delay", 10.0))

        self.api_key: Optional[str] = self._config.get("api_key")

        self._headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"

        self._sync_client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
        self._context_mode: bool = False

        logger.info(
            f"SparseEmbeddingClient 初始化完成 - api={self.embeddings_url} "
            f"model={self.model_name} timeout={self.timeout}s retry={self.enable_retry}"
        )

    def _validate_config(self) -> None:
        required_fields = ["api_base", "model_name", "timeout"]
        missing = [f for f in required_fields if f not in self._config]
        if missing:
            raise ValueError(f"SparseEmbedding 配置缺少必需字段: {', '.join(missing)}")
        if not isinstance(self._config["timeout"], (int, float)) or self._config["timeout"] <= 0:
            raise ValueError(f"timeout 必须是正数，当前值: {self._config['timeout']}")

    # ---------- 上下文管理器（保留持久化连接池） ----------
    def __enter__(self) -> "SparseEmbeddingClient":
        self._context_mode = True
        self._sync_client = httpx.Client(timeout=self.timeout)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._context_mode = False
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None
        return False

    async def __aenter__(self) -> "SparseEmbeddingClient":
        self._context_mode = True
        self._async_client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
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
        try:
            if self._sync_client is not None:
                self._sync_client.close()
        except Exception:
            pass
        if self._async_client is not None:
            logger.warning(
                "检测到未关闭的异步 SparseEmbeddingClient，请使用 'async with' 或 await client.aclose()"
            )

    # ---------- 同步 ----------
    def embed_sparse(self, text: str) -> Dict[int, float]:
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        return self.embed_sparse_batch([text])[0]

    def embed_sparse_batch(self, texts: List[str]) -> List[Dict[int, float]]:
        cleaned = self._sanitize(texts)
        if self.enable_retry:
            return self._embed_sparse_batch_with_retry_sync(cleaned)
        return self._embed_sparse_batch_sync(cleaned)

    def _embed_sparse_batch_sync(self, texts: List[str]) -> List[Dict[int, float]]:
        all_sparse: List[Dict[int, float]] = []
        if self._context_mode and self._sync_client is not None:
            client = self._sync_client
            should_close = False
        else:
            client = httpx.Client(timeout=self.timeout)
            should_close = True
        try:
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start : start + self.batch_size]
                payload = {
                    "model": self.model_name,
                    "input": batch,
                    "return_dense": False,
                    "return_sparse": True,
                }
                try:
                    response = client.post(
                        self.embeddings_url, json=payload, headers=self._headers
                    )
                    response.raise_for_status()
                except httpx.TimeoutException as e:
                    raise TimeoutError(f"SparseEmbedding 请求超时 ({self.timeout}s)") from e
                all_sparse.extend(self._parse_sparse_response(response.json()))
        finally:
            if should_close:
                client.close()
        return all_sparse

    def _embed_sparse_batch_with_retry_sync(
        self, texts: List[str]
    ) -> List[Dict[int, float]]:
        retry_decorator = retry_sync(
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            retry_strategy=self.retry_strategy,
            max_delay=self.max_retry_delay,
            exceptions=(httpx.HTTPError, TimeoutError),
            logger=logging.getLogger(__name__),
            raise_on_failure=True,
        )
        wrapped = retry_decorator(self._embed_sparse_batch_sync)
        return wrapped(texts)

    # ---------- 异步 ----------
    async def aembed_sparse(self, text: str) -> Dict[int, float]:
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        results = await self.aembed_sparse_batch([text])
        return results[0]

    async def aembed_sparse_batch(self, texts: List[str]) -> List[Dict[int, float]]:
        cleaned = self._sanitize(texts)
        if self.enable_retry:
            return await self._aembed_sparse_batch_with_retry(cleaned)
        return await self._aembed_sparse_batch(cleaned)

    async def _aembed_sparse_batch(self, texts: List[str]) -> List[Dict[int, float]]:
        all_sparse: List[Dict[int, float]] = []
        if self._context_mode and self._async_client is not None:
            client = self._async_client
            should_close = False
        else:
            client = httpx.AsyncClient(timeout=self.timeout)
            should_close = True
        try:
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start : start + self.batch_size]
                payload = {
                    "model": self.model_name,
                    "input": batch,
                    "return_dense": False,
                    "return_sparse": True,
                }
                try:
                    response = await client.post(
                        self.embeddings_url, json=payload, headers=self._headers
                    )
                    response.raise_for_status()
                except httpx.TimeoutException as e:
                    raise TimeoutError(f"SparseEmbedding 请求超时 ({self.timeout}s)") from e
                all_sparse.extend(self._parse_sparse_response(response.json()))
        finally:
            if should_close:
                await client.aclose()
        return all_sparse

    async def _aembed_sparse_batch_with_retry(
        self, texts: List[str]
    ) -> List[Dict[int, float]]:
        retry_decorator = retry_async(
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            retry_strategy=self.retry_strategy,
            max_delay=self.max_retry_delay,
            exceptions=(httpx.HTTPError, TimeoutError),
            logger=logging.getLogger(__name__),
            raise_on_failure=True,
            timeout=None,
        )
        wrapped = retry_decorator(self._aembed_sparse_batch)
        return await wrapped(texts)

    async def aembed_sparse_concurrent(
        self,
        texts: List[str],
        max_concurrent: int = 5,
    ) -> List[Dict[int, float]]:
        cleaned = self._sanitize(texts)
        batches = [
            cleaned[i : i + self.batch_size]
            for i in range(0, len(cleaned), self.batch_size)
        ]
        sem = asyncio.Semaphore(max_concurrent)

        async def _run(batch: List[str]) -> List[Dict[int, float]]:
            async with sem:
                if self.enable_retry:
                    return await self._aembed_sparse_batch_with_retry(batch)
                return await self._aembed_sparse_batch(batch)

        results = await asyncio.gather(*[_run(b) for b in batches])
        return [v for batch in results for v in batch]

    # ---------- 解析 ----------
    def _parse_sparse_response(
        self, response: Dict[str, Any]
    ) -> List[Dict[int, float]]:
        if "data" not in response:
            raise ValueError(f"响应中缺少 'data' 字段: {list(response.keys())}")
        sparse_vectors: List[Dict[int, float]] = []
        for item in response["data"]:
            sparse_raw = item.get("sparse_embedding")
            if sparse_raw is None:
                raise ValueError(
                    f"响应 data[{item.get('index', '?')}] 中缺少 'sparse_embedding' 字段"
                )
            sparse_vectors.append(self._convert_sparse_format(sparse_raw))
        return sparse_vectors

    @staticmethod
    def _convert_sparse_format(sparse_raw: Any) -> Dict[int, float]:
        if isinstance(sparse_raw, dict):
            if "indices" in sparse_raw and "values" in sparse_raw:
                indices = sparse_raw["indices"]
                values = sparse_raw["values"]
                if len(indices) != len(values):
                    raise ValueError(
                        f"indices 和 values 长度不匹配: {len(indices)} vs {len(values)}"
                    )
                return {int(idx): float(val) for idx, val in zip(indices, values)}
            return {int(k): float(v) for k, v in sparse_raw.items()}
        raise ValueError(f"不支持的稀疏向量格式: {type(sparse_raw)}")

    @staticmethod
    def _sanitize(texts: List[str]) -> List[str]:
        if not texts:
            raise ValueError("文本列表不能为空")
        cleaned = [t for t in texts if t and t.strip()]
        if len(cleaned) != len(texts):
            logger.warning(f"过滤了 {len(texts) - len(cleaned)} 个空文本")
        if not cleaned:
            raise ValueError("没有有效的非空文本")
        return cleaned

    # ---------- 健康检查 ----------
    def health_check(self) -> bool:
        try:
            v = self.embed_sparse("健康检查测试文本")
            return isinstance(v, dict) and len(v) > 0
        except Exception as e:
            logger.error(f"SparseEmbedding 健康检查失败: {e}")
            return False

    async def ahealth_check(self) -> bool:
        try:
            v = await self.aembed_sparse("健康检查测试文本")
            return isinstance(v, dict) and len(v) > 0
        except Exception as e:
            logger.error(f"SparseEmbedding 健康检查失败: {e}")
            return False

    def get_config(self) -> Dict[str, Any]:
        return {
            "api_base": self.api_base,
            "model_name": self.model_name,
            "batch_size": self.batch_size,
            "timeout": self.timeout,
            "enable_retry": self.enable_retry,
            "max_retries": self.max_retries if self.enable_retry else None,
            "retry_strategy": self.retry_strategy if self.enable_retry else None,
        }


# ==================== 工厂函数 ====================


def create_embedding_client(
    config_manager: Optional[ConfigManager] = None,
    env_manager: Optional[EnvManager] = None,
    custom_config: Optional[Dict[str, Any]] = None,
    preset_name: Optional[str] = None,
) -> EmbeddingClient:
    """创建稠密 ``EmbeddingClient`` 实例

    Args:
        config_manager: 配置管理器，缺省使用全局单例
        env_manager: 环境变量管理器，缺省使用全局单例
        custom_config: 临时覆盖（``model`` / ``api_base`` / ``api_key`` /
            ``dimension`` / ``batch_size`` / ``timeout`` / ``extra_params``）
        preset_name: 指定 ``[embedding.presets.<name>]``，缺省走 ``default_preset``
    """
    return EmbeddingClient(
        config_manager=config_manager,
        env_manager=env_manager,
        custom_config=custom_config,
        preset_name=preset_name,
    )


def create_sparse_embedding_client(
    config_manager: Optional[ConfigManager] = None,
    env_manager: Optional[EnvManager] = None,
    custom_config: Optional[Dict[str, Any]] = None,
) -> SparseEmbeddingClient:
    """创建 ``SparseEmbeddingClient`` 实例（BGE-M3，未走 LiteLLM）"""
    return SparseEmbeddingClient(
        config_manager=config_manager,
        env_manager=env_manager,
        custom_config=custom_config,
    )
