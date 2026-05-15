#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : stream_buffer.py
@Author  : caixiongjiang
@Date    : 2026/05/09
@Function:
    流式累积器（StreamAccumulator）

    职责
    ----
    在 ChatService 的 Agent 循环中，每一轮都需要：

    1. 边消费 ``LLMClient.astream(...)`` 的 ``StreamChunk``，
       边把"思考增量 / 正文增量 / 工具调用增量"分类透出（前端 WS 协议）；
    2. 在流结束时把累积的工具调用增量合成完整的 ``ToolCall`` 列表，
       与正文 / 思考一起组装成等价于 ``LLMClient.agenerate`` 返回的
       ``LLMResponse``，供下一轮上下文拼接 / 工具 dispatch / 持久化使用。

    设计要点
    --------
    - 工具调用按 ``index`` 聚合：``id`` / ``name`` 取首次出现的非空值，
      ``arguments`` 字符串拼接所有增量后再 JSON 解析；
    - JSON 解析失败保留原文于 ``{"_raw": "..."}``，与
      ``parse_litellm_response`` 行为对齐，避免业务侧需要分支；
    - 不直接产生协议事件，由 ChatService 在外部消费 ``feed`` 的返回，
      这一层只负责"语义归一化"，与传输层（WS / SSE）解耦；
    - 完全 sync，无 IO，所有方法可在异步上下文里直接调用。

@Modify History:
    2026-05-09 - 首版（Phase 0）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.client.llm.types import (
    LLMResponse,
    StreamChunk,
    TokenUsage,
    ThinkingContent,
    ToolCall,
)


class StreamEventType(str, Enum):
    """``StreamAccumulator.feed`` 透出的事件类型

    由 ChatService 翻译为 WS / SSE 协议事件；本模块不耦合具体协议。
    """

    CONTENT_DELTA = "content.delta"
    THINKING_DELTA = "thinking.delta"
    TOOL_CALL_STARTED = "tool_call.started"   # 首次出现某 index 的 tool_call
    TOOL_CALL_ARGS_DELTA = "tool_call.args_delta"  # 后续 arguments 增量
    FINISH = "finish"


@dataclass
class StreamEvent:
    """累积器透出的语义事件（与传输协议解耦）"""

    type: StreamEventType
    text: str = ""                                # CONTENT/THINKING/ARGS_DELTA 用
    tool_call_index: Optional[int] = None         # TOOL_CALL_* 用
    tool_call_id: Optional[str] = None            # TOOL_CALL_STARTED 用
    tool_call_name: Optional[str] = None          # TOOL_CALL_STARTED 用
    finish_reason: Optional[str] = None           # FINISH 用


@dataclass
class _ToolCallBuf:
    """单个工具调用的累积缓冲"""

    index: int
    id: Optional[str] = None
    name: Optional[str] = None
    arguments_chunks: List[str] = field(default_factory=list)
    started_emitted: bool = False

    def merged_arguments(self) -> str:
        return "".join(self.arguments_chunks)

    def to_tool_call(self) -> ToolCall:
        raw = self.merged_arguments()
        if raw.strip():
            try:
                args: Dict[str, Any] = json.loads(raw)
            except Exception:
                args = {"_raw": raw}
        else:
            args = {}
        return ToolCall(
            id=str(self.id or ""),
            name=str(self.name or ""),
            arguments=args,
        )


class StreamAccumulator:
    """流式累积器：``feed`` 喂入 StreamChunk，``finalize`` 输出 LLMResponse

    用法::

        acc = StreamAccumulator(model="deepseek/deepseek-chat")
        async for chunk in client.astream(messages, tools=...):
            for ev in acc.feed(chunk):
                # 翻译为 WS 协议事件并推送
                ...
        resp: LLMResponse = acc.finalize()  # 等价于 agenerate 的返回
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self._content_parts: List[str] = []
        self._thinking_parts: List[str] = []
        self._tool_buffers: Dict[int, _ToolCallBuf] = {}
        self._finish_reason: Optional[str] = None
        self._model: Optional[str] = model
        self._closed: bool = False
        # OpenAI / LiteLLM 在 stream_options.include_usage=True 下，会在流末尾
        # 追发一个携带 usage 的尾块；这里缓存下来，finalize 时若调用方没显式
        # 传 usage，就用这个缓存值，避免 LLMResponse.usage 退化为全 0。
        self._usage: Optional[TokenUsage] = None

    # ==================== 属性访问 ====================

    @property
    def content(self) -> str:
        return "".join(self._content_parts)

    @property
    def thinking_text(self) -> str:
        return "".join(self._thinking_parts)

    @property
    def finish_reason(self) -> Optional[str]:
        return self._finish_reason

    @property
    def has_tool_calls(self) -> bool:
        return bool(self._tool_buffers)

    @property
    def model(self) -> Optional[str]:
        return self._model

    # ==================== 核心：feed ====================

    def feed(self, chunk: StreamChunk) -> List[StreamEvent]:
        """喂入一个 StreamChunk，返回本块产生的语义事件列表

        多数情况返回 0 / 1 个事件；同一 chunk 同时携带正文 + tool_call 时
        按发生顺序返回 2 个。
        """
        if self._closed:
            return []

        events: List[StreamEvent] = []

        # 模型名补齐（首块拿到即可）
        if self._model is None and chunk.model:
            self._model = chunk.model

        # usage 尾块：缓存以供 finalize 使用，本身不产生语义事件
        if chunk.usage is not None:
            self._usage = chunk.usage

        # 正文 / 思考增量
        if chunk.delta and chunk.tool_call_delta is None:
            if chunk.is_thought:
                self._thinking_parts.append(chunk.delta)
                events.append(StreamEvent(
                    type=StreamEventType.THINKING_DELTA,
                    text=chunk.delta,
                ))
            else:
                self._content_parts.append(chunk.delta)
                events.append(StreamEvent(
                    type=StreamEventType.CONTENT_DELTA,
                    text=chunk.delta,
                ))

        # 工具调用增量
        if chunk.tool_call_delta is not None:
            tcd = chunk.tool_call_delta
            buf = self._tool_buffers.setdefault(
                tcd.index, _ToolCallBuf(index=tcd.index),
            )
            # id / name 取首次非空
            if buf.id is None and tcd.id:
                buf.id = tcd.id
            if buf.name is None and tcd.name:
                buf.name = tcd.name
            # arguments 增量累积
            if tcd.arguments_delta:
                buf.arguments_chunks.append(tcd.arguments_delta)

            # 首次拿到可识别字段（id 或 name）→ 发 STARTED
            if (not buf.started_emitted) and (buf.id or buf.name):
                buf.started_emitted = True
                events.append(StreamEvent(
                    type=StreamEventType.TOOL_CALL_STARTED,
                    tool_call_index=buf.index,
                    tool_call_id=buf.id,
                    tool_call_name=buf.name,
                ))

            # 有 arguments 增量 → 发 ARGS_DELTA（前端可实时渲染参数）
            if tcd.arguments_delta:
                events.append(StreamEvent(
                    type=StreamEventType.TOOL_CALL_ARGS_DELTA,
                    text=tcd.arguments_delta,
                    tool_call_index=buf.index,
                ))

        # finish_reason
        if chunk.finish_reason:
            self._finish_reason = chunk.finish_reason
            events.append(StreamEvent(
                type=StreamEventType.FINISH,
                finish_reason=chunk.finish_reason,
            ))

        return events

    # ==================== 收口：finalize ====================

    def finalize(self, usage: Optional[TokenUsage] = None) -> LLMResponse:
        """合成等价于 ``LLMClient.agenerate`` 的 ``LLMResponse``

        Args:
            usage: 显式覆盖。优先级：``参数传入 > feed 期间缓存的尾块 usage > 全 0``。
                LiteLLM 在 ``stream_options.include_usage=True`` 下会在流末尾
                追发一个 ``choices=[]`` 但带顶层 ``usage`` 的尾块，本累积器在
                ``feed`` 阶段已自动缓存到 ``self._usage``，调用方一般无需再传。
        """
        self._closed = True

        tool_calls = [
            self._tool_buffers[idx].to_tool_call()
            for idx in sorted(self._tool_buffers)
        ]

        thinking: Optional[ThinkingContent] = None
        if self._thinking_parts:
            thinking = ThinkingContent(reasoning=self.thinking_text)
            # 若 usage 给了 thinking_tokens，回灌到 ThinkingContent.tokens_used
            effective_usage = usage or self._usage
            if (
                effective_usage is not None
                and effective_usage.thinking_tokens is not None
            ):
                thinking.tokens_used = int(effective_usage.thinking_tokens)

        finish = self._finish_reason
        # 若模型未给 finish_reason 但累积到了 tool_calls，规范化为 tool_calls
        if not finish and tool_calls:
            finish = "tool_calls"
        finish = _normalize_stream_finish_reason(finish)

        return LLMResponse(
            content=self.content,
            thinking=thinking,
            tool_calls=tool_calls,
            usage=usage or self._usage or TokenUsage(),
            model=self._model or "",
            finish_reason=finish,  # type: ignore[arg-type]
        )


def _normalize_stream_finish_reason(raw: Optional[str]) -> str:
    """与 ``parse_litellm_response`` 的归一化保持一致"""
    if not raw:
        return "stop"
    s = str(raw).lower()
    if s in ("end_turn", "stop"):
        return "stop"
    if s in ("max_tokens", "length"):
        return "length"
    if s in ("tool_use", "function_call", "tool_calls"):
        return "tool_calls"
    if s in ("content_filter", "safety", "blocked"):
        return "content_filter"
    if s == "error":
        return "error"
    return "stop"


__all__ = [
    "StreamEventType",
    "StreamEvent",
    "StreamAccumulator",
]
