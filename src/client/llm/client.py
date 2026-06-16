#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : client.py
@Author  : caixiongjiang
@Date    : 2026/04/21
@Function:
    LiteLLM 统一客户端封装

    设计要点
    --------
    1. **薄封装、零业务**：LiteLLM 已经处理了 provider 路由、重试、token 统计；
       这里只负责把 ``components.json`` 的配置 + 业务 messages → ``litellm.acompletion``
       的入参，并把响应解析成本项目内部的 ``LLMResponse``。
    2. **统一一个 model 字符串**：完全采用 LiteLLM 的 ``"<provider>/<model>"`` 形式，
       例如 ``"deepseek/deepseek-chat"``、``"openai/gpt-4o-mini"``、
       ``"openai/<proxy_virtual_name>"``（指向 LiteLLM Proxy）。
    3. **支持 LiteLLM Proxy**：用户自托管 proxy 时，统一通过 ``api_base`` /
       ``api_key`` 注入；这两个参数可由组件配置直接指定，也可由
       ``LITELLM_PROXY_URL`` / ``LITELLM_PROXY_KEY`` 环境变量兜底。
    4. **多模态原生支持**：``messages`` 里直接传 OpenAI 风格的 multi-content
       结构（``{"type":"text","text":...}`` / ``{"type":"image_url",...}``），
       LiteLLM 会负责按 provider 转换。
    5. **思考链（统一经 LiteLLM 翻译）**：应用只传 ``thinking_budget`` 三态语义，
       ``LLMClient`` 映射为 LiteLLM 统一的 ``reasoning_effort``（``none/low/medium/high``），
       由 LiteLLM / Proxy 按 provider 转成 ``enable_thinking``、``thinking`` 等原生参数。
       - **配置层 ``thinking_budget=0``**：默认不下发（上游自决）。
       - **调用层 ``thinking_budget=0``**：显式关 → ``reasoning_effort="none"``。
       - **调用层 ``thinking_budget>0``**：显式开 → 按 budget 映射 effort 档位。
       不在应用侧写 provider 分支；Proxy 建议开启 ``litellm_settings.drop_params: true``。
       响应里若有 ``reasoning_content`` 会自动归入 ``LLMResponse.thinking``。
    6. **观测**：用户运行的 LiteLLM Proxy 把日志写入 PostgreSQL，本地客户端
       仅用 loguru 输出关键 metrics（延迟 / token / model），无需 LangSmith。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from src.client.llm.types import (
    LLMResponse,
    MessageList,
    StreamChunk,
    TokenUsage,
    ToolCallDelta,
    ToolSchema,
    parse_litellm_response,
)

# 延迟 import litellm，避免启动期立即拉依赖
_LITELLM_INITIALIZED = False


def _ensure_litellm_initialized() -> None:
    """全局只跑一次：禁用 LiteLLM 的网络遥测、设默认日志级别。"""
    global _LITELLM_INITIALIZED
    if _LITELLM_INITIALIZED:
        return

    import litellm  # noqa: WPS433 (deferred import)

    litellm.suppress_debug_info = True
    litellm.set_verbose = False  # type: ignore[attr-defined]
    litellm.drop_params = True   # 自动丢掉 provider 不支持的参数
    litellm.telemetry = False    # 关闭 LiteLLM 的匿名遥测
    litellm.modify_params = True  # 容许 LiteLLM 微调入参（例如 anthropic system 拼接）

    _LITELLM_INITIALIZED = True
    logger.debug("LiteLLM 全局初始化完成（telemetry=False, drop_params=True）")


# ==================== 客户端配置 ====================


class LLMClientConfig(BaseModel):
    """单个 LLM 客户端的运行时配置（由 ComponentConfigManager 构造）"""

    model: str = Field(
        ...,
        description="LiteLLM 模型字符串，形如 'deepseek/deepseek-chat'、'openai/gpt-4o-mini'",
    )
    api_base: Optional[str] = Field(
        None,
        description="覆盖 provider 默认 endpoint，自托管 LiteLLM Proxy 时填写",
    )
    api_key: Optional[str] = Field(
        None,
        description="provider / proxy 的 API Key；为空则走环境变量",
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2048, ge=1)
    timeout: float = Field(60.0, gt=0.0)
    max_retries: int = Field(2, ge=0)
    thinking_budget: int = Field(
        0,
        ge=0,
        description=(
            "本客户端的默认思考策略：0=不主动声明（按上游默认），"
            ">0=默认开思考并设置预算（tokens）。单次调用可被 "
            "``astream(thinking_budget=...)`` 覆盖（None / 0 / >0 三态）。"
        ),
    )
    extra_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="透传给 litellm.acompletion 的额外参数（例如 top_p / response_format）",
    )

    model_config = ConfigDict(extra="ignore")


# ==================== 客户端实现 ====================


class LLMClient:
    """LiteLLM 统一客户端

    生命周期
    --------
    - 进程内可创建多个实例（每个组件持有自己的实例），互不影响。
    - 不持有长连接，无需显式 close（保留 ``aclose()`` 供 explicit 清理）。
    """

    def __init__(self, config: LLMClientConfig) -> None:
        _ensure_litellm_initialized()
        self.config = config

    # ---- 兼容字段（旧代码读取 client.provider / client.model_name 等） ----
    @property
    def model_name(self) -> str:
        return self.config.model

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def provider(self) -> str:
        if "/" in self.config.model:
            return self.config.model.split("/", 1)[0]
        return ""

    @property
    def api_base(self) -> Optional[str]:
        return self.config.api_base

    @property
    def api_key(self) -> Optional[str]:
        return self.config.api_key

    # ---- 同步入口（仅保留必要场景，主流统一用 agenerate） ----
    def generate(
        self,
        messages: MessageList,
        *,
        tools: Optional[List[ToolSchema]] = None,
        tool_choice: Optional[Any] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """同步请求，内部仍走 LiteLLM 的 ``completion``。"""
        import litellm

        params = self._build_params(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking_budget=thinking_budget,
            extra=kwargs,
        )
        t0 = time.perf_counter()
        try:
            resp = litellm.completion(**params)
        except Exception as e:
            logger.error(f"[LLM] {self.config.model} sync generate 失败: {e}")
            raise
        elapsed_ms = (time.perf_counter() - t0) * 1000
        parsed = parse_litellm_response(resp)
        self._log_metrics("sync", parsed, elapsed_ms)
        return parsed

    # ---- 异步入口（业务主流） ----
    async def agenerate(
        self,
        messages: MessageList,
        *,
        tools: Optional[List[ToolSchema]] = None,
        tool_choice: Optional[Any] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """异步请求。"""
        import litellm

        params = self._build_params(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking_budget=thinking_budget,
            extra=kwargs,
        )
        t0 = time.perf_counter()
        try:
            resp = await litellm.acompletion(**params)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[LLM] {self.config.model} async generate 失败: {e}")
            raise
        elapsed_ms = (time.perf_counter() - t0) * 1000
        parsed = parse_litellm_response(resp)
        self._log_metrics("async", parsed, elapsed_ms)
        return parsed

    # ---- 流式（同步） ----
    def stream(
        self,
        messages: MessageList,
        *,
        tools: Optional[List[ToolSchema]] = None,
        tool_choice: Optional[Any] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """同步流式生成。支持 ``tools / tool_choice`` 透传，便于 Agent 模式
        在流式过程中也能拿到 ``tool_calls`` 增量。
        """
        import litellm

        params = self._build_params(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking_budget=thinking_budget,
            extra=kwargs,
        )
        params["stream"] = True
        params["stream_options"] = {"include_usage": True}
        for chunk in litellm.completion(**params):
            yield from _yield_stream_chunks(chunk)

    # ---- 流式（异步） ----
    async def astream(
        self,
        messages: MessageList,
        *,
        tools: Optional[List[ToolSchema]] = None,
        tool_choice: Optional[Any] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """异步流式生成。支持 ``tools / tool_choice`` 透传。

        在 ChatService 的 Agent 模式中，每轮都通过本方法拉流：
        - 文本增量按 ``StreamChunk(delta=..., is_thought=False)`` 透出
        - 思考链按 ``StreamChunk(delta=..., is_thought=True)`` 透出
        - 工具调用按 ``StreamChunk(tool_call_delta=ToolCallDelta(...))`` 透出
        - 流结束按 ``StreamChunk(finish_reason=..., delta="")`` 透出
        """
        import litellm

        params = self._build_params(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking_budget=thinking_budget,
            extra=kwargs,
        )
        params["stream"] = True
        params["stream_options"] = {"include_usage": True}
        resp = await litellm.acompletion(**params)
        async for chunk in resp:  # type: ignore[union-attr]
            for sc in _yield_stream_chunks(chunk):
                yield sc

    # ---- 资源清理 ----
    async def aclose(self) -> None:
        """LiteLLM 自身无需 close；保留方法便于上层统一调用。"""
        return None

    def close(self) -> None:
        return None

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    # ---- 内部 ----
    def _build_params(
        self,
        messages: MessageList,
        *,
        tools: Optional[List[ToolSchema]] = None,
        tool_choice: Optional[Any] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        cfg = self.config
        params: Dict[str, Any] = {
            "model": cfg.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else cfg.temperature,
            "max_tokens": max_tokens if max_tokens is not None else cfg.max_tokens,
            "timeout": cfg.timeout,
            "num_retries": cfg.max_retries,
        }
        if cfg.api_base:
            params["api_base"] = cfg.api_base
        if cfg.api_key:
            params["api_key"] = cfg.api_key

        if tools:
            params["tools"] = tools
            if tool_choice is not None:
                params["tool_choice"] = tool_choice

        if cfg.extra_params:
            for k, v in cfg.extra_params.items():
                params.setdefault(k, v)
        if extra:
            for k, v in extra.items():
                if v is None:
                    continue
                params[k] = v

        # 与全局 litellm.drop_params 双保险；Proxy 侧也建议 drop_params: true
        params["drop_params"] = True
        self._apply_thinking_params(params, thinking_budget)

        return params

    def _apply_thinking_params(
        self,
        params: Dict[str, Any],
        call_budget: Optional[int],
    ) -> None:
        """把 ``thinking_budget`` 映射为 LiteLLM 统一参数 ``reasoning_effort``。

        ===========================  ====================================
        ``call_budget``               下发策略
        ===========================  ====================================
        ``None``                     沿用 ``cfg.thinking_budget``；cfg=0 则不下发
        ``0``                        ``reasoning_effort="none"``（显式关）
        ``>0``                       ``reasoning_effort=low|medium|high``
        ===========================  ====================================

        Provider 差异（Qwen ``enable_thinking``、GLM ``thinking`` 等）交给 LiteLLM
        翻译；不支持的参数由 ``drop_params`` 丢弃。
        """
        effective_budget = self._resolve_effective_thinking_budget(call_budget)
        if effective_budget is None:
            return
        if effective_budget <= 0:
            params["reasoning_effort"] = "none"
            return
        params["reasoning_effort"] = _budget_to_reasoning_effort(effective_budget)

    def _resolve_effective_thinking_budget(
        self,
        call_budget: Optional[int],
    ) -> Optional[int]:
        if call_budget is None:
            cfg_budget = int(self.config.thinking_budget or 0)
            return cfg_budget if cfg_budget > 0 else None
        return int(call_budget)

    def _log_metrics(self, mode: str, resp: LLMResponse, elapsed_ms: float) -> None:
        usage = resp.usage
        logger.info(
            "[LLM] {mode} {model} {elapsed:.0f}ms tokens={total} "
            "(prompt={p}, completion={c}, reasoning={r}) finish={fr} tools={n}",
            mode=mode,
            model=resp.model or self.config.model,
            elapsed=elapsed_ms,
            total=usage.total_tokens,
            p=usage.prompt_tokens,
            c=usage.completion_tokens,
            r=usage.thinking_tokens or 0,
            fr=resp.finish_reason,
            n=len(resp.tool_calls),
        )


def _budget_to_reasoning_effort(budget: int) -> str:
    """把 token 预算粗映射为 LiteLLM 统一的 ``reasoning_effort`` 档位。"""
    if budget < 1024:
        return "low"
    if budget < 4096:
        return "medium"
    return "high"


# ==================== 工厂函数 ====================


def _proxy_defaults() -> Dict[str, Any]:
    """从 ``ConfigManager`` + ``EnvManager`` 读取模型网关默认配置。

    优先级：
      1) 组件 / preset 显式 ``api_base`` / ``api_key``
      2) ``ConfigManager.get_proxy_full_config(env_manager)``：
         - ``api_base`` 取 ``.env: LITELLM_PROXY_URL`` 或 ``[proxy].api_base``
         - ``api_key``  取 ``.env: LITELLM_PROXY_KEY``
         - ``timeout`` / ``max_retries`` 取 ``[proxy]``
    单例失败时降级为返回空字典，避免阻断单元测试 / 离线场景。
    """
    try:
        from src.utils.config_manager import get_config_manager
        from src.utils.env_manager import get_env_manager

        return get_config_manager().get_proxy_full_config(get_env_manager())
    except Exception as e:  # pragma: no cover - 配置缺失时不阻断
        logger.debug(f"读取模型网关默认配置失败，使用空默认值: {e}")
        return {}


def create_llm_client(
    *,
    model: str,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    thinking_budget: int = 0,
    extra_params: Optional[Dict[str, Any]] = None,
) -> LLMClient:
    """显式参数构造；通常由 ``ComponentConfigManager`` 调用。

    ``api_base`` / ``api_key`` / ``timeout`` / ``max_retries`` 未显式提供时，
    自动回落到 ``[proxy]`` + ``.env`` 的模型网关默认值。
    """
    proxy = _proxy_defaults()
    routable_model = _ensure_proxy_routable(model)
    if routable_model != model:
        logger.debug(
            f"create_llm_client: '{model}' → '{routable_model}' "
            f"(自动补 litellm_proxy/ 前缀，避免裸名被 LiteLLM SDK 当成 provider 推断失败)"
        )
    cfg = LLMClientConfig(
        model=routable_model,
        api_base=api_base or proxy.get("api_base"),
        api_key=api_key or proxy.get("api_key"),
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout if timeout is not None else float(proxy.get("default_timeout", 60.0)),
        max_retries=max_retries if max_retries is not None else int(proxy.get("default_max_retries", 2)),
        thinking_budget=thinking_budget,
        extra_params=extra_params or {},
    )
    return LLMClient(cfg)


_LITELLM_PROXY_PREFIX = "litellm_proxy/"


def _ensure_proxy_routable(model: str) -> str:
    """对接 LiteLLM Proxy 的兜底归一化。

    现象：用户的 LiteLLM Proxy 给模型配置的 ``model_name`` 多数是裸 alias（如
    ``deepseek-v4-flash``），``/v1/models`` 直接返回这种裸字符串。前端把它当
    ``model`` 参数透传到后端，``litellm.acompletion(model="deepseek-v4-flash",
    api_base=<proxy>)`` 时 LiteLLM SDK 自己推不出 provider，抛
    ``BadRequestError: LLM Provider NOT provided``。

    解决方法：任何"看起来不像带 provider 的 id"（即不含 ``/``）都强制加上
    ``litellm_proxy/`` 前缀，告诉 SDK 走"透传到 api_base 指向的 LiteLLM Proxy"
    分支。已带 ``provider/`` 前缀的（``openai/gpt-4o`` 等）保持不动——它们走
    SDK 内置的 provider adapter，符合预期。

    这层归一化是**防御式的**：``LiteLLMRegistry`` 已经在生成模型清单时做了
    一遍前缀归一；这里再做一次主要是覆盖"会话已经把裸名落库"的旧数据，让
    它们也能正确路由。
    """
    if not model:
        return model
    if "/" in model:
        return model
    return _LITELLM_PROXY_PREFIX + model


def create_llm_client_from_model(
    *,
    model: str,
    chat_template_preset: str = "fast",
) -> LLMClient:
    """按"具体模型字符串 + 采样模板 preset"组装 LLMClient

    使用场景：用户在前端从 ``/api/chat/models`` 选了一个 LiteLLM 模型字符串
    （如 ``openai/gpt-4o-mini`` 或 ``litellm_proxy/deepseek-v4-flash``），后端
    不再走 preset 的 ``model`` 字段，但仍希望复用 preset 里调好的
    ``temperature / max_tokens / thinking_budget / extra_params`` 这些采样
    参数——这就是 ``chat_template_preset`` 的用途。

    优先级：
        - ``model`` ← 入参（覆盖 preset.model）；裸名会自动加 ``litellm_proxy/``
          前缀以确保 LiteLLM SDK 能正确路由
        - 其他字段 ← preset；preset 缺失 / 字段未设 → 走默认值

    ``api_base`` / ``api_key`` 始终走 ``[proxy]`` + ``.env``，与
    ``create_llm_client_from_preset`` 一致。
    """
    from src.utils.config_manager import get_config_manager

    cm = get_config_manager()
    p = cm.get_llm_preset(chat_template_preset) or {}
    # template preset 找不到也不阻塞：用纯默认值即可
    if not p:
        logger.warning(
            f"chat_template_preset '{chat_template_preset}' 未配置，"
            f"使用默认采样参数",
        )

    routable_model = _ensure_proxy_routable(model)
    if routable_model != model:
        logger.debug(
            f"create_llm_client_from_model: '{model}' → '{routable_model}' "
            f"(自动补 litellm_proxy/ 前缀)"
        )

    return create_llm_client(
        model=routable_model,
        api_base=p.get("api_base"),
        api_key=p.get("api_key"),
        temperature=p.get("temperature", 0.7),
        max_tokens=p.get("max_tokens", 2048),
        timeout=p.get("timeout"),
        max_retries=p.get("max_retries"),
        thinking_budget=p.get("thinking_budget", 0),
        extra_params=p.get("extra_params") or {},
    )


def create_llm_client_from_preset(preset_name: str) -> LLMClient:
    """从 ``config/config.toml`` 的 ``[llm.presets.<preset_name>]`` 构造客户端。

    preset 字段约定：

    .. code-block:: toml

       [llm.presets.fast]
       model = "deepseek/deepseek-chat"
       temperature = 0.3
       max_tokens = 2048
       timeout = 60
       # 可选: thinking_budget, api_base, api_key, max_retries, extra_params

    ``api_base`` / ``api_key`` 默认走 LiteLLM Proxy（``.env`` + ``[proxy]``）；
    单个 preset 也可在自身字段中强制覆盖。
    """
    from src.utils.config_manager import get_config_manager

    cm = get_config_manager()
    p = cm.get_llm_preset(preset_name)
    if not p:
        presets = cm.get_llm_presets()
        available = ", ".join(sorted(presets.keys())) or "(empty)"
        raise ValueError(f"未知 LLM preset '{preset_name}'，可用: {available}")

    raw_model = p["model"]
    routable_model = _ensure_proxy_routable(raw_model)
    if routable_model != raw_model:
        logger.debug(
            f"create_llm_client_from_preset[{preset_name}]: "
            f"'{raw_model}' → '{routable_model}' (自动补 litellm_proxy/ 前缀)"
        )

    return create_llm_client(
        model=routable_model,
        api_base=p.get("api_base"),
        api_key=p.get("api_key"),
        temperature=p.get("temperature", 0.7),
        max_tokens=p.get("max_tokens", 2048),
        timeout=p.get("timeout"),
        max_retries=p.get("max_retries"),
        thinking_budget=p.get("thinking_budget", 0),
        extra_params=p.get("extra_params") or {},
    )


# ==================== 流式辅助 ====================


def _yield_stream_chunks(chunk: Any) -> Iterator[StreamChunk]:
    """把 LiteLLM 流式输出的一个 chunk 转换为若干 StreamChunk。

    解析的 4 类增量（同一个 LiteLLM chunk 内可能同时出现）：

    1. ``delta.content``           → 正文增量（``is_thought=False``）
    2. ``delta.reasoning_content`` → 思考链增量（``is_thought=True``）
    3. ``delta.tool_calls[*]``     → 工具调用增量（``tool_call_delta`` 非空）
    4. ``finish_reason``           → 流结束信号

    工具调用增量的兼容性说明：
        - OpenAI / DeepSeek / 国产 Qwen 等：按 ``index`` 分多块，首块带 ``id``
          与 ``function.name``，后续块只带 ``function.arguments`` 字符串增量；
        - Anthropic / 部分供应商：一次性给完整 tool_call（首块即包含完整
          ``arguments``）；本函数对两种形态均做规范化输出，调用方只需按
          ``index`` 聚合即可拿到完整 ``ToolCallDelta`` 序列。
    """
    try:
        data = chunk.model_dump() if hasattr(chunk, "model_dump") else dict(chunk)
    except Exception:
        return
    choices = data.get("choices") or []
    model = data.get("model")

    # OpenAI / LiteLLM 在 stream_options.include_usage=True 下，会在流末尾追发
    # 一个 choices=[] 但带顶层 usage 的尾块。这里把它独立透出，让
    # StreamAccumulator.finalize() 能拿到真实 token 计数（否则展示成全 0）。
    usage_raw = data.get("usage") or {}
    if usage_raw:
        completion_details = usage_raw.get("completion_tokens_details") or {}
        thinking_tokens = completion_details.get("reasoning_tokens")
        usage_obj = TokenUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
            completion_tokens=int(usage_raw.get("completion_tokens") or 0),
            thinking_tokens=(
                int(thinking_tokens) if thinking_tokens is not None else None
            ),
            total_tokens=int(usage_raw.get("total_tokens") or 0),
        )
        yield StreamChunk(
            delta="", is_thought=False, finish_reason=None, model=model,
            usage=usage_obj,
        )

    if not choices:
        return
    ch = choices[0]
    delta = ch.get("delta") or {}
    finish = ch.get("finish_reason")

    text = delta.get("content")
    if text:
        yield StreamChunk(delta=text, is_thought=False, finish_reason=None, model=model)

    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
    if reasoning:
        yield StreamChunk(delta=reasoning, is_thought=True, finish_reason=None, model=model)

    raw_tool_calls = delta.get("tool_calls") or []
    for tc in raw_tool_calls:
        try:
            tcd = _parse_tool_call_delta(tc)
        except Exception:  # noqa: BLE001 — 单个增量解析失败不阻断整流
            continue
        if tcd is None:
            continue
        yield StreamChunk(
            delta="",
            is_thought=False,
            tool_call_delta=tcd,
            finish_reason=None,
            model=model,
        )

    if finish:
        yield StreamChunk(delta="", is_thought=False, finish_reason=finish, model=model)


def _parse_tool_call_delta(tc: Any) -> Optional[ToolCallDelta]:
    """把 LiteLLM 的单个 tool_call 增量字典转换为 ``ToolCallDelta``。

    返回 ``None`` 表示该增量无任何可用信息（例如完全为空的 placeholder）。
    """
    if not isinstance(tc, dict):
        return None

    index = tc.get("index")
    if index is None:
        # 部分供应商在非流式 tool_calls 拼回时可能不带 index，按 0 兜底
        index = 0
    try:
        index_int = int(index)
    except (TypeError, ValueError):
        return None
    if index_int < 0:
        return None

    fn = tc.get("function") or {}
    name = fn.get("name")
    args = fn.get("arguments")

    # 仅当至少有一个有效字段时才产出
    if (
        tc.get("id") is None
        and not name
        and (args is None or args == "")
    ):
        return None

    return ToolCallDelta(
        index=index_int,
        id=tc.get("id"),
        name=name if name else None,
        arguments_delta=args if isinstance(args, str) and args else None,
    )
