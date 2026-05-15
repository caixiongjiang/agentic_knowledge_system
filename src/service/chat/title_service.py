#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : title_service.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    TitleService ── 会话标题异步生成

    场景
    ----
    用户在新会话里发出第一条 ``query`` 后，前端列表上"新会话"这种占位标题
    显然不能长期保留。本服务负责：

    1. 取**首轮 user query + assistant 首段回复**作为输入；
    2. 用 ``fast`` preset（性价比优先）让 LLM 生成 10~20 字的中文短标题；
    3. 通过 ``ChatSessionService.rename_session`` 写回 MySQL；
    4. 整个过程在**后台** ``asyncio.create_task`` 中执行，不阻塞主对话流，
       前端可在下一次列表刷新时拿到新标题。

    设计取舍
    --------
    - 标题失败 → 兜底用 ``query`` 前 20 字截断作为标题，**永不抛出**，
      避免影响主链路；
    - **不走 components.json**：``components.json`` 是 RAG 抽取 Pipeline
      的中央配置簿（每个组件对应一个 Kafka Worker），与 chat 这种在线 LLM
      调用点无关。本服务通过 ``model_preset`` 入参直接引用
      ``config.toml [llm.presets.*]``；运维如需细调，直接在 toml 加自定义
      preset 即可。
    - Prompt 写死中文，因为知识库问答的目标用户是中文场景；多语言演进时再做。
@Modify History:
    2026-05-11 - 首版（Phase 3）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
from typing import Optional

from loguru import logger

from src.client.llm import LLMClient


DEFAULT_TITLE_PROMPT_SYSTEM = (
    "你是会话标题生成器。请基于用户的首条问题与助手的首段答复，"
    "生成一个 5~15 字之间的简短中文标题。要求：\n"
    "- 不要带书名号、引号、句号、感叹号或问号；\n"
    "- 不要前缀 `标题：` 等多余文字；\n"
    "- 直接输出标题文本本身，单行；\n"
    "- 标题应概括会话主题或最核心问题，避免使用通用词如 `对话` / `提问`。"
)


def fallback_title(query: str, max_chars: int = 20) -> str:
    """兜底标题：截取 query 前若干字符（去尾标点）

    本函数**完全离线**，不抛异常。
    """
    s = (query or "新会话").strip()
    if not s:
        return "新会话"
    s = s.replace("\n", " ").replace("\r", " ").strip()
    if len(s) > max_chars:
        s = s[:max_chars]
    for ch in "。.!?！？，,；;":
        s = s.rstrip(ch)
    return s or "新会话"


class TitleService:
    """会话标题生成器（异步、容错）

    Args:
        model_preset: 要使用的 LLM preset 名，引用 ``[llm.presets.<name>]``；
            缺省为 ``"fast"``（性价比优先）。
        client: 直接注入的 ``LLMClient``；优先级最高于 ``model_preset``，
            便于单元测试用 mock 客户端。
    """

    def __init__(
        self,
        *,
        model_preset: str = "fast",
        client: Optional[LLMClient] = None,
    ) -> None:
        self._model_preset = model_preset
        self._client: Optional[LLMClient] = client

    # ============================================================
    # client 装配
    # ============================================================

    def _get_client(self) -> LLMClient:
        """懒加载 LLMClient：按 ``model_preset`` 名直接从 toml preset 构造。"""
        if self._client is not None:
            return self._client
        from src.client.llm import create_llm_client_from_preset

        try:
            client = create_llm_client_from_preset(self._model_preset)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"加载 preset {self._model_preset!r} 失败，回退 fast preset: {e}",
            )
            client = create_llm_client_from_preset("fast")
        self._client = client
        logger.debug(
            f"TitleService 使用 preset={self._model_preset}, model={client.model}"
        )
        return client

    # ============================================================
    # 核心：异步生成标题
    # ============================================================

    async def generate_title(
        self,
        *,
        user_query: str,
        assistant_reply: str = "",
        max_chars: int = 20,
    ) -> str:
        """调 LLM 生成短标题；失败兜底为 ``fallback_title(user_query)``"""
        if not user_query.strip():
            return fallback_title(user_query, max_chars=max_chars)
        try:
            client = self._get_client()
            messages = [
                {"role": "system", "content": DEFAULT_TITLE_PROMPT_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"【用户问题】\n{user_query.strip()}\n\n"
                        f"【助手回复（节选）】\n{assistant_reply.strip()[:300] or '（暂无回复）'}\n\n"
                        f"请直接输出标题（≤{max_chars} 字）："
                    ),
                },
            ]
            resp = await client.agenerate(
                messages=messages,
                temperature=0.3,
                max_tokens=64,
            )
            title = (resp.content or "").strip().splitlines()
            title_text = title[0].strip() if title else ""
            # 去除模型偶尔会附带的 markdown / 引号
            for prefix in ("标题：", "标题:", "Title:", "title:"):
                if title_text.startswith(prefix):
                    title_text = title_text[len(prefix):].strip()
            title_text = title_text.strip("『』「」《》<>\"'`")
            if not title_text:
                return fallback_title(user_query, max_chars=max_chars)
            if len(title_text) > max_chars:
                title_text = title_text[:max_chars]
            return title_text
        except Exception as e:  # noqa: BLE001
            logger.warning(f"标题生成失败，使用兜底: {e}")
            return fallback_title(user_query, max_chars=max_chars)

    # ============================================================
    # 后台触发（fire & forget）
    # ============================================================

    def schedule_in_background(
        self,
        *,
        session_id: str,
        user_id: str,
        user_query: str,
        assistant_reply: str,
        session_service,
        max_chars: int = 20,
    ) -> "asyncio.Task[Optional[str]]":
        """启动后台 Task：生成标题 → 写回 MySQL

        Args:
            session_service: ``ChatSessionService`` 实例（用其 ``rename_session``）

        Returns:
            ``asyncio.Task``——调用方一般不 await，仅做 logging / 取消时持有引用
        """

        async def _runner() -> Optional[str]:
            try:
                title = await self.generate_title(
                    user_query=user_query,
                    assistant_reply=assistant_reply,
                    max_chars=max_chars,
                )
                ok = session_service.rename_session(
                    session_id=session_id,
                    user_id=user_id,
                    title=title,
                )
                if ok is not None:
                    logger.info(
                        f"标题已生成并落库: session={session_id}, title={title!r}",
                    )
                    return title
                logger.warning(
                    f"标题生成成功但 rename 失败: session={session_id}, title={title!r}",
                )
                return None
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.error(f"后台起标题异常: session={session_id}, err={e}")
                return None

        return asyncio.create_task(_runner(), name=f"title:{session_id}")


__all__ = [
    "TitleService",
    "fallback_title",
    "DEFAULT_TITLE_PROMPT_SYSTEM",
]
