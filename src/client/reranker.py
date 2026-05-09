#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : reranker.py
@Author  : caixiongjiang
@Date    : 2025/12/21 15:54
@Function:
    Reranker 客户端（LiteLLM 薄封装）

    1. 通过 ``litellm.rerank`` / ``litellm.arerank`` 走自托管 LiteLLM Proxy
    2. 自动适配 cohere /rerank 协议（vLLM 部署的 Qwen3-reranker 完全兼容该格式）
    3. 业务侧只暴露：``rerank`` / ``arerank`` / ``health_check`` / ``ahealth_check``
    4. 客户端侧只做：批分（``batch_size``）+ 跨批次合并 + Top-K 截断
    5. 上下文管理器接口保留为 no-op，便于上层代码无感知迁移

@Modify History:
    2026/04/03 - 初版（自实现 httpx + provider 分支）
    2026/04/21 - 改造为 LiteLLM 薄封装，统一走模型网关
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field

from src.utils.config_manager import ConfigManager, get_config_manager
from src.utils.env_manager import EnvManager, get_env_manager


class RerankResult(BaseModel):
    """单条重排序结果"""

    index: int = Field(..., description="原始文档列表中的索引")
    score: float = Field(..., description="相关性分数")
    text: str = Field(default="", description="原始文档文本")


class RerankerClient:
    """Reranker 客户端（LiteLLM 薄封装）

    设计要点
    --------
    - 模型字符串从 ``[reranker.presets.<name>]`` 取，形如
      ``"cohere/qwen3-reranker-0.6b"``，由 LiteLLM 路由到自托管 Proxy
      （``api_base`` / ``api_key`` 走 ``[proxy]`` + ``.env``）。
    - 大输入按 ``batch_size`` 切批，跨批次合并后再做 Top-K 截断。
    - 重试 / 超时 / 连接池由 LiteLLM + Proxy 接管，本端无 httpx 依赖。

    选择 preset
    -----------
    - 默认使用 ``[reranker].default_preset``。
    - 通过 ``preset_name="..."`` 指定其它 preset。
    - ``custom_config`` 可临时覆盖任意字段（``model`` / ``batch_size`` /
      ``top_k`` / ``timeout`` / ``api_base`` / ``api_key`` / ``extra_params``）。
    """

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        env_manager: Optional[EnvManager] = None,
        custom_config: Optional[Dict[str, Any]] = None,
        preset_name: Optional[str] = None,
    ) -> None:
        from src.client.llm.client import _ensure_litellm_initialized

        _ensure_litellm_initialized()

        self._config_manager = config_manager or get_config_manager()
        self._env_manager = env_manager or get_env_manager()

        merged = self._config_manager.get_reranker_full_config(
            self._env_manager, preset_name=preset_name
        )
        if custom_config:
            merged.update(custom_config)

        if not merged.get("model"):
            raise ValueError(
                "RerankerClient 配置缺少 'model'，请在 [reranker.presets.*] 中声明"
            )

        self.model_name: str = merged["model"]
        self.api_base: Optional[str] = merged.get("api_base")
        self.api_key: Optional[str] = merged.get("api_key")
        self.batch_size: int = int(merged.get("batch_size", 16))
        self.default_top_k: int = int(merged.get("top_k", 10))
        self.timeout: float = float(merged.get("timeout", 30.0))
        self.extra_params: Dict[str, Any] = dict(merged.get("extra_params") or {})

        logger.info(
            f"RerankerClient 初始化完成 - model={self.model_name} "
            f"api_base={self.api_base or '(env/default)'} batch={self.batch_size} "
            f"top_k={self.default_top_k} timeout={self.timeout}s"
        )

    # ---------- 上下文管理器（保留兼容，LiteLLM 内部维护连接池） ----------
    def __enter__(self) -> "RerankerClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False

    async def __aenter__(self) -> "RerankerClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False

    def close(self) -> None:
        return None

    async def aclose(self) -> None:
        return None

    # ---------- 同步 ----------
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
    ) -> List[RerankResult]:
        """同步重排序

        Args:
            query: 查询文本
            documents: 候选文档（按原始顺序）
            top_k: 返回前 K 条；缺省走 ``default_top_k``

        Returns:
            按 ``score`` 降序排列的 ``RerankResult`` 列表，``index`` 为原始全局下标
        """
        import litellm

        self._validate_inputs(query, documents)
        target_k = top_k or self.default_top_k

        all_results: List[RerankResult] = []
        for offset in range(0, len(documents), self.batch_size):
            batch = documents[offset : offset + self.batch_size]
            resp = litellm.rerank(
                model=self.model_name,
                query=query,
                documents=batch,
                top_n=len(batch),
                api_base=self.api_base,
                api_key=self.api_key,
                timeout=self.timeout,
                **self.extra_params,
            )
            all_results.extend(self._parse(resp, batch, offset))

        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:target_k]

    # ---------- 异步 ----------
    async def arerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
    ) -> List[RerankResult]:
        """异步重排序"""
        import litellm

        self._validate_inputs(query, documents)
        target_k = top_k or self.default_top_k

        all_results: List[RerankResult] = []
        for offset in range(0, len(documents), self.batch_size):
            batch = documents[offset : offset + self.batch_size]
            resp = await litellm.arerank(
                model=self.model_name,
                query=query,
                documents=batch,
                top_n=len(batch),
                api_base=self.api_base,
                api_key=self.api_key,
                timeout=self.timeout,
                **self.extra_params,
            )
            all_results.extend(self._parse(resp, batch, offset))

        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:target_k]

    # ---------- 解析 ----------
    @staticmethod
    def _validate_inputs(query: str, documents: List[str]) -> None:
        if not query or not query.strip():
            raise ValueError("查询文本不能为空")
        if not documents:
            raise ValueError("文档列表不能为空")

    @staticmethod
    def _parse(
        resp: Any,
        original_docs: List[str],
        batch_offset: int,
    ) -> List[RerankResult]:
        try:
            data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
        except Exception:
            data = resp  # type: ignore[assignment]

        results_raw = (
            data.get("results") if isinstance(data, dict) else None
        )
        if results_raw is None:
            raise ValueError(f"LiteLLM rerank 返回无 results 字段: {data!r}")

        parsed: List[RerankResult] = []
        for item in results_raw:
            if not isinstance(item, dict):
                continue
            local_idx = int(item.get("index", 0))
            # 部分 provider 返回 ``relevance_score``，部分返回 ``score``
            score = item.get("relevance_score", item.get("score", 0.0))
            text = (
                original_docs[local_idx]
                if 0 <= local_idx < len(original_docs)
                else ""
            )
            parsed.append(
                RerankResult(
                    index=local_idx + batch_offset,
                    score=float(score),
                    text=text,
                )
            )
        return parsed

    # ---------- 健康检查 ----------
    def health_check(self) -> bool:
        try:
            r = self.rerank("健康检查", ["测试文档"], top_k=1)
            ok = bool(r)
            if ok:
                logger.info(f"Reranker 健康检查通过 (model={self.model_name})")
            return ok
        except Exception as e:
            logger.error(f"Reranker 健康检查失败: {e}")
            return False

    async def ahealth_check(self) -> bool:
        try:
            r = await self.arerank("健康检查", ["测试文档"], top_k=1)
            ok = bool(r)
            if ok:
                logger.info(f"Reranker 健康检查通过 (model={self.model_name})")
            return ok
        except Exception as e:
            logger.error(f"Reranker 健康检查失败: {e}")
            return False

    # ---------- 辅助 ----------
    def get_config(self) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "api_base": self.api_base,
            "batch_size": self.batch_size,
            "top_k": self.default_top_k,
            "timeout": self.timeout,
        }


# ==================== 工厂函数 ====================


def create_reranker_client(
    config_manager: Optional[ConfigManager] = None,
    env_manager: Optional[EnvManager] = None,
    custom_config: Optional[Dict[str, Any]] = None,
    preset_name: Optional[str] = None,
) -> RerankerClient:
    """创建 ``RerankerClient`` 实例

    Args:
        config_manager: 配置管理器，缺省使用全局单例
        env_manager: 环境变量管理器，缺省使用全局单例
        custom_config: 临时覆盖（``model`` / ``api_base`` / ``api_key`` /
            ``batch_size`` / ``top_k`` / ``timeout`` / ``extra_params``）
        preset_name: 指定 ``[reranker.presets.<name>]``，缺省走 ``default_preset``
    """
    return RerankerClient(
        config_manager=config_manager,
        env_manager=env_manager,
        custom_config=custom_config,
        preset_name=preset_name,
    )
