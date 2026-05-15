#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chat_service.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    ChatService ── 知识库对话核心编排

    模块定位
    --------
    把 Phase 0~2 的所有能力（流式累积、Mongo/MySQL 持久化、KnowledgeNavToolKit、
    Chat prompts、History 压缩）串联成"一次完整 chat 轮次"的事件流。
    本服务是个 **async generator**：``chat_stream(request)`` 产出 ``ChatEvent``，
    供上层（Phase 4 WS / SSE 端点）直接迭代转发。

    两种执行路径
    ------------
    1. **RAG 单轮（``agent_mode=False``）**：
        - 服务端先做一次知识库检索（``RetrieveService.retrieve``）；
        - 把命中片段以 ``role=user`` 形式注入到最新 user 之前；
        - 一次性 ``LLMClient.astream`` 拉流，**不暴露 tools**；
        - 适合简单问答、低成本、低延迟。
    2. **Agent 工具循环（``agent_mode=True``）**：
        - 服务端先做一次"种子检索"，结果作为最初引用；
        - 以 ``KnowledgeNavToolKit`` 暴露 3 个导航工具
          （``context_window`` / ``drill_down`` / ``skeleton``）；
        - 每轮 ``astream`` 流出文本/思考/tool_call 增量；
        - 若收到 tool_calls，并行 ``asyncio.gather`` 执行后把结果以
          ``role=tool`` 拼回 messages，进入下一轮；
        - 工具循环上限 ``max_tool_rounds`` 由 ``ChatSession`` / 请求覆盖；
        - 达上限后做一次**收尾轮**强制纯文本（参考 ``ResultValidator``）。

    与现有模块的协作
    ----------------
    - 历史加载：``ChatSessionService.load_history`` →
      ``compose_chat_messages``（含 history 反序列化）
    - 检索：``RetrieveService.retrieve(RetrieveRequest)``
    - 流式：``LLMClient.astream`` + ``StreamAccumulator`` 翻译事件
    - 工具：``KnowledgeNavToolKit`` 提供 schemas / dispatch / supplemented_items
    - 持久化：每轮 assistant + 每条 tool 写 MongoDB；末尾 ``touch`` MySQL
    - 标题：首轮结束后 ``TitleService.schedule_in_background`` 异步起标题

    设计取舍
    --------
    - **citations 合并**：初始检索命中 + 工具补充统一汇入
      ``supplemented_items``；写最后一条 assistant 的 ``citations`` 时去重；
      中间轮 assistant 的 ``citations`` 仅写"本轮工具新增的"，可观测但不重复。
    - **错误隔离**：检索失败、工具执行失败都不中断会话——以
      ``ChatEvent(ERROR)`` 透出，主流程继续；只有 LLM 调用本身彻底崩溃才
      抛出（由 WS 层捕获）。
    - **持久化粒度**：每条消息单独写一次 MongoDB，``touch`` 在轮次末尾
      一次性更新计数；避免每条消息触发 MySQL update。
    - **背压**：本 generator 是"边算边出"，与上层消费速度耦合；若上层
      WS 写入慢会自动反压到 LLM 拉流，无需额外缓冲。
@Modify History:
    2026-05-11 - 首版（Phase 3）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from loguru import logger

from src.chat.stream_buffer import (
    StreamAccumulator,
    StreamEvent,
    StreamEventType,
)
from src.client.llm import LLMClient
from src.client.llm.types import LLMResponse, ToolCall
from src.db.mongodb.models.conversation.chat_message import (
    ChatMessage,
    ChatRole,
    Citation,
    ToolCallRecord,
    TokenUsageRecord,
)
from src.db.mongodb.repositories.conversation import chat_message_repo
from src.service.chat.chunk_alias_map import (
    ChunkAliasMap,
    METADATA_ALIAS_ADDITIONS_KEY,
    rebuild_alias_map_from_history,
)
from src.service.chat.chunk_enricher import ChunkMeta, TurnEnrichCache
from src.prompts.chat import (
    DEFAULT_CHAT_SYSTEM,
    apply_history_window,
    apply_token_window,
    build_chat_system_prompt,
    compose_chat_messages,
    compress_history_to_summary,
    drop_assistant_tool_dangling,
    estimate_history_tokens,
)
from src.retrieve.pipeline.types import RetrieveRequest
from src.retrieve.types.query import MetadataFilter
from src.retrieve.types.result import ChunkItem
from src.service.chat.session_service import (
    ChatSessionService,
    generate_message_id,
)
from src.service.chat.title_service import TitleService
from src.service.chat.tools import KnowledgeNavToolKit
from src.service.chat.types import (
    ChatEvent,
    ChatEventType,
    ChatRequest,
    ChatTurnContext,
    ChatTurnResult,
)


# ============================================================
# 配置
# ============================================================


class ChatServiceConfig:
    """ChatService 运行时配置

    设计原则
    --------
    - **测试友好**：直接 ``ChatServiceConfig()`` 返回硬编码默认值，不读 toml；
    - **生产装配**：API 端点 / WS 路由通过 ``from_config_manager()`` 从
      ``config.toml [chat]`` 节加载，覆盖任何字段；
    - **不读 components.json**：``components.json`` 服务于 RAG 抽取 Pipeline
      的 Kafka Worker 组件，与 chat 这种在线请求路径无关。Chat 直接通过
      ``agent_model_preset`` / ``title_model_preset`` 引用 ``[llm.presets.*]``。
    """

    # ---------- 检索 ----------
    retrieve_top_k: int = 8
    """初始服务端检索 top_k"""

    enable_validation_for_chat: bool = False
    """RAG 单轮路径是否启用 LLM₂ 结果验证（默认关，省一次 LLM 调用）"""

    # ---------- 上下文 ----------
    max_history_messages: int = 40
    """加载历史消息上限（条数维度，先按轮再按 token 滑窗收紧）"""

    max_context_tokens: int = 8000
    """``apply_token_window`` 的预算上限"""

    max_history_turns: int = 12
    """``apply_history_window`` 的轮数上限（防御性，与 token 滑窗叠加）"""

    summary_compress_threshold_turns: int = 15
    """超过该轮数时启用摘要压缩（``0`` 时关闭摘要）"""

    summary_keep_recent_turns: int = 4
    """摘要压缩后保留的最近轮数"""

    # ---------- 输出 ----------
    max_completion_tokens: Optional[int] = None
    """单轮 assistant 输出 token 上限；``None`` 表示由模型 / preset 决定"""

    thinking_budget: int = 4096
    """启用思考链时透传给 ``LLMClient.astream(thinking_budget=...)`` 的预算"""

    # ---------- LLM 选型 ----------
    agent_model_preset: str = "fast"
    """主对话 LLM 的 preset 名（``ChatRequest`` / ``ChatSession`` 都未指定时使用）"""

    title_model_preset: str = "fast"
    """异步起标题的 preset 名（一次性短调用，性价比优先）"""

    # ---------- session 默认（仅当 ChatRequest 与 ChatSession 都未指定时使用） ----------
    default_agent_mode: bool = True
    default_enable_thinking: bool = False
    default_max_tool_rounds: int = 5

    # ============================================================
    # 配置加载
    # ============================================================

    @classmethod
    def from_config_manager(cls, manager: Optional[Any] = None) -> "ChatServiceConfig":
        """从 ``config.toml [chat]`` 节加载；缺失字段使用类默认值。

        Args:
            manager: ``ConfigManager`` 实例；不传则使用全局单例。

        Returns:
            ``ChatServiceConfig`` 实例
        """
        try:
            if manager is None:
                from src.utils.config_manager import get_config_manager
                manager = get_config_manager()
            chat_cfg: Dict[str, Any] = manager.get_section("chat") or {}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"加载 [chat] 配置失败，使用默认值: {e}")
            return cls()

        retrieval = chat_cfg.get("retrieval", {}) or {}
        history = chat_cfg.get("history", {}) or {}

        inst = cls()

        # 顶层
        inst.thinking_budget = int(chat_cfg.get("thinking_budget", inst.thinking_budget))
        max_ct = chat_cfg.get("max_completion_tokens")
        # 0 / None → 透传 None（让模型/preset 决定）
        inst.max_completion_tokens = (
            int(max_ct) if isinstance(max_ct, int) and max_ct > 0 else None
        )
        inst.agent_model_preset = str(
            chat_cfg.get("agent_model_preset", inst.agent_model_preset),
        )
        inst.title_model_preset = str(
            chat_cfg.get("title_model_preset", inst.title_model_preset),
        )
        inst.default_agent_mode = bool(
            chat_cfg.get("default_agent_mode", inst.default_agent_mode),
        )
        inst.default_enable_thinking = bool(
            chat_cfg.get("default_enable_thinking", inst.default_enable_thinking),
        )
        inst.default_max_tool_rounds = int(
            chat_cfg.get("default_max_tool_rounds", inst.default_max_tool_rounds),
        )

        # [chat.retrieval]
        inst.retrieve_top_k = int(retrieval.get("top_k", inst.retrieve_top_k))
        inst.enable_validation_for_chat = bool(
            retrieval.get("enable_validation", inst.enable_validation_for_chat),
        )

        # [chat.history]
        inst.max_history_messages = int(
            history.get("max_messages", inst.max_history_messages),
        )
        inst.max_history_turns = int(history.get("max_turns", inst.max_history_turns))
        inst.max_context_tokens = int(history.get("max_tokens", inst.max_context_tokens))
        inst.summary_compress_threshold_turns = int(
            history.get(
                "summary_compress_threshold_turns",
                inst.summary_compress_threshold_turns,
            ),
        )
        inst.summary_keep_recent_turns = int(
            history.get(
                "summary_keep_recent_turns", inst.summary_keep_recent_turns,
            ),
        )

        logger.info(
            f"ChatServiceConfig 已从 [chat] 加载: "
            f"agent_preset={inst.agent_model_preset}, "
            f"title_preset={inst.title_model_preset}, "
            f"top_k={inst.retrieve_top_k}, "
            f"max_tokens={inst.max_context_tokens}, "
            f"summary_threshold={inst.summary_compress_threshold_turns}, "
            f"thinking_budget={inst.thinking_budget}"
        )
        return inst


# ============================================================
# ChatService
# ============================================================


class ChatService:
    """知识库对话主编排（async generator 风格）

    用法::

        service = ChatService(
            session_service=ChatSessionService(),
            retrieve_service=RetrieveService(),
            title_service=TitleService(),
        )
        async for ev in service.chat_stream(req):
            ws.send(ev)

    """

    def __init__(
        self,
        *,
        session_service: Optional[ChatSessionService] = None,
        retrieve_service: Optional[Any] = None,  # RetrieveService（避免循环 import）
        title_service: Optional[TitleService] = None,
        config: Optional[ChatServiceConfig] = None,
    ) -> None:
        self._cfg = config or ChatServiceConfig()
        self._session_service = session_service or ChatSessionService()
        self._retrieve_service = retrieve_service  # 延迟加载，见 _get_retrieve_service
        # TitleService 用 config 里指定的 preset；显式注入优先
        self._title_service = title_service or TitleService(
            model_preset=self._cfg.title_model_preset,
        )
        # LLM 客户端按 preset 名缓存
        self._client_cache: Dict[str, LLMClient] = {}

    # ============================================================
    # 依赖装配（懒加载）
    # ============================================================

    def _get_retrieve_service(self):
        if self._retrieve_service is None:
            from src.service.knowledge.retrieve_service import RetrieveService

            self._retrieve_service = RetrieveService()
        return self._retrieve_service

    def _get_llm_client(self, model_preset: str) -> LLMClient:
        """按 ``model_preset`` 取 LLMClient（按 preset 名缓存）。

        chat 模块**不走 ``components.json``**：``components.json`` 是 RAG 抽取
        Pipeline（Kafka Worker）的中央配置簿，与 chat 这种在线请求路径无关。

        如需对主对话 / 起标题做细调（``temperature`` / ``max_tokens`` /
        ``thinking_budget`` / ``api_base`` 等），运维在
        ``config.toml [llm.presets.<name>]`` 加自定义 preset，再把
        ``[chat].agent_model_preset`` / ``[chat].title_model_preset`` 指向
        ``<name>`` 即可，无需改代码。
        """
        cached = self._client_cache.get(model_preset)
        if cached is not None:
            return cached

        from src.client.llm import create_llm_client_from_preset

        client = create_llm_client_from_preset(model_preset)
        self._client_cache[model_preset] = client
        logger.debug(
            f"ChatService LLMClient: preset={model_preset}, model={client.model}"
        )
        return client

    # ============================================================
    # 配置合并：ChatRequest + ChatSession → ChatTurnContext
    # ============================================================

    def _resolve_turn_context(
        self,
        request: ChatRequest,
        session,
    ) -> ChatTurnContext:
        """把请求级覆盖与会话默认合并成一份"本轮有效配置"。"""
        sys_prompt = (
            request.custom_system_prompt
            or session.system_prompt
            or build_chat_system_prompt(
                enabled_tools=("context_window", "drill_down", "skeleton")
                if (request.agent_mode if request.agent_mode is not None else session.agent_mode)
                else None,
            )
        )
        return ChatTurnContext(
            session_id=session.session_id,
            user_id=session.user_id,
            query=request.query,
            agent_mode=(
                request.agent_mode if request.agent_mode is not None else session.agent_mode
            ),
            enable_thinking=(
                request.enable_thinking
                if request.enable_thinking is not None
                else session.enable_thinking
            ),
            model_preset=(
                request.model_preset
                or session.model_preset
                or self._cfg.agent_model_preset
            ),
            max_tool_rounds=(
                request.max_tool_rounds
                if request.max_tool_rounds is not None
                else session.max_tool_rounds
            ),
            retrieve_top_k=request.retrieve_top_k or self._cfg.retrieve_top_k,
            system_prompt=sys_prompt,
            knowledge_base_ids=list(session.knowledge_base_ids or []),
            skip_retrieval=request.skip_retrieval,
        )

    # ============================================================
    # 主入口：流式对话
    # ============================================================

    async def chat_stream(
        self,
        request: ChatRequest,
    ) -> AsyncIterator[ChatEvent]:
        """单轮对话事件流（async generator）

        事件顺序（典型路径）::

            SESSION_READY
            RETRIEVAL_STARTED
            RETRIEVAL_DONE
            ( CONTENT_DELTA | THINKING_DELTA | TOOL_CALL_* ... )*
            MESSAGE_DONE             # 每轮 assistant 落库后
            ( TOOL_CALL_COMPLETED ... TOOL_ROUND_DONE )*   # Agent 才有
            TURN_DONE

        异常路径会在对应阶段透出 ``ERROR``，主流程继续直到 ``TURN_DONE``。
        """
        total_start = time.perf_counter()
        result = ChatTurnResult(
            session_id=request.session_id,
            user_message_id="",
        )

        # ---- 1) 权限 + 加载 session ----
        try:
            session = self._session_service.get_session(
                session_id=request.session_id, user_id=request.user_id,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"加载 session 异常: {e}")
            yield ChatEvent(
                ChatEventType.ERROR,
                {"phase": "load_session", "error": str(e)},
            )
            return
        if session is None:
            yield ChatEvent(
                ChatEventType.ERROR,
                {"phase": "load_session", "error": "session not found or forbidden"},
            )
            return

        ctx = self._resolve_turn_context(request, session)
        is_first_turn = (session.message_count or 0) == 0

        # turn 级 chunk 元数据缓存：同 chunk_id 在本 turn 内只查 4 张表 1 次。
        # 三个使用点：
        #   1) retrieval.done 帧（方案 B：种子 chunks 提前 enrich 下发）
        #   2) _build_citations_for_round（每轮 assistant 落库 + message.done 下发）
        #   3) tool_call.completed（如未来扩展到工具补充 chunks 也要 enrich）
        enrich_cache = TurnEnrichCache(
            user_id=ctx.user_id,
            knowledge_base_id=(
                ctx.knowledge_base_ids[0] if ctx.knowledge_base_ids else None
            ),
        )

        # session 级 chunk_id ↔ alias 映射：从历史 assistant.metadata.alias_additions
        # 累加重建。本 turn 新分配的 alias 在 _persist_assistant 里写回。
        # 占位创建，下面加载历史后再 rebuild。
        alias_map = ChunkAliasMap()

        # ---- 2) 持久化 user message ----
        user_msg_id = generate_message_id()
        result.user_message_id = user_msg_id
        try:
            await chat_message_repo.create(
                creator=ctx.user_id,
                _id=user_msg_id,
                session_id=ctx.session_id,
                user_id=ctx.user_id,
                role=ChatRole.USER.value,
                content=ctx.query,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"写入 user 消息失败: {e}")
            yield ChatEvent(
                ChatEventType.ERROR,
                {"phase": "persist_user", "error": str(e)},
            )
            return

        yield ChatEvent(
            ChatEventType.SESSION_READY,
            {
                "session_id": ctx.session_id,
                "user_message_id": user_msg_id,
                "agent_mode": ctx.agent_mode,
                "model_preset": ctx.model_preset,
            },
        )

        # ---- 3) 加载历史 ----
        try:
            history = await self._session_service.load_history(
                session_id=ctx.session_id,
                limit=self._cfg.max_history_messages,
            )
            # 把刚写入的 user 消息排除（避免它出现在 history + user_message 两处）
            history = [m for m in history if m.id != user_msg_id]
        except Exception as e:  # noqa: BLE001
            logger.warning(f"加载历史异常，按空历史继续: {e}")
            history = []

        # 从历史 assistant.metadata.alias_additions 累加重建 alias_map。
        # 这样下面 retrieval 阶段为新 chunks 分配 alias 时不会与历史冲突，
        # 历史 assistant content 里的 [cN] 在下一轮也仍能被 unwrap 成真实 chunk_id。
        try:
            alias_map = rebuild_alias_map_from_history(history)
            logger.debug(
                f"alias_map 重建完成：size={alias_map.size}, counter={alias_map.counter}"
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"alias_map 重建失败（按空 map 继续）: {e}")
            alias_map = ChunkAliasMap()

        # ---- 4) 检索 ----
        retrieved_hits: List[ChunkItem] = []
        if not ctx.skip_retrieval:
            yield ChatEvent(
                ChatEventType.RETRIEVAL_STARTED,
                {"query": ctx.query, "top_k": ctx.retrieve_top_k},
            )
            retrieval_start = time.perf_counter()
            try:
                retrieved_hits = await self._do_retrieve(ctx)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"检索失败，按空命中继续: {e}")
                yield ChatEvent(
                    ChatEventType.ERROR,
                    {"phase": "retrieve", "error": str(e)},
                )
            result.retrieval_time_ms = (time.perf_counter() - retrieval_start) * 1000

            # 方案 B：把种子 chunks 提前 enrich，让前端 LLM 一吐引用就能渲染彩色 chip。
            # enrich 失败不阻塞主流程——chunks 仍然能下发，只是没有 file_name 等扩展字段。
            try:
                await enrich_cache.ensure(retrieved_hits)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"enrich 种子 chunks 失败（忽略，按裸数据下发）: {e}")

            # 提前给种子 chunks 分配 alias（必须先于 retrieval.done 帧；前端要靠
            # alias 把 LLM 输出里的 [cN] chip 解析回 citation）。后续
            # compose_chat_messages 渲染参考片段时这些 alias 命中缓存，不会重复分配。
            seed_aliases: Dict[str, str] = {}
            for c in retrieved_hits:
                if c.chunk_id:
                    seed_aliases[c.chunk_id] = alias_map.alias_for(c.chunk_id)

            yield ChatEvent(
                ChatEventType.RETRIEVAL_DONE,
                {
                    "hit_count": len(retrieved_hits),
                    "time_ms": result.retrieval_time_ms,
                    "chunks": [
                        self._chunk_brief(
                            c,
                            meta=enrich_cache.get(c.chunk_id),
                            alias=seed_aliases.get(c.chunk_id),
                        )
                        for c in retrieved_hits
                    ],
                },
            )

        # ---- 5) 收敛历史（轮 → token → 摘要） ----
        client = self._get_llm_client(ctx.model_preset)
        history = drop_assistant_tool_dangling(history)
        history = apply_history_window(
            history, max_turns=self._cfg.max_history_turns, keep_system=False,
        )
        history = apply_token_window(
            history,
            max_tokens=self._cfg.max_context_tokens,
            model=client.model,
            keep_system=False,
        )
        # 摘要压缩（仅当依然超阈值时启用；Phase 3 默认 ChatService 自带的 fast preset 做摘要）
        summary_dict: Optional[Dict[str, Any]] = None
        if (
            self._cfg.summary_compress_threshold_turns
            and self._cfg.summary_compress_threshold_turns > 0
        ):
            user_count = sum(1 for m in history if m.role == "user")
            if user_count > self._cfg.summary_compress_threshold_turns:
                summary_dict, history = await compress_history_to_summary(
                    history,
                    summarize_fn=self._build_summarize_fn(),
                    keep_recent_turns=self._cfg.summary_keep_recent_turns,
                )

        # ---- 6) 组装首轮 messages ----
        messages: List[Dict[str, Any]] = compose_chat_messages(
            system_prompt=ctx.system_prompt,
            history=history,
            user_message=ctx.query,
            retrieved_chunks=retrieved_hits,
            alias_map=alias_map,
        )
        if summary_dict is not None:
            messages.insert(1, summary_dict)

        # ---- 7) 进入执行路径 ----
        supplemented: List[ChunkItem] = []
        kit: Optional[KnowledgeNavToolKit] = None
        if ctx.agent_mode:
            kit = KnowledgeNavToolKit(
                supplemented_items=supplemented,
                alias_map=alias_map,
            )

        assistant_msg_ids: List[str] = []
        tool_msg_ids: List[str] = []

        if ctx.agent_mode:
            tools_schema = kit.schemas() if kit else None
            max_rounds = max(1, ctx.max_tool_rounds)
        else:
            tools_schema = None
            max_rounds = 1
        thinking_budget = self._cfg.thinking_budget if ctx.enable_thinking else None

        llm_start = time.perf_counter()
        try:
            async for ev in self._run_loop_real(
                ctx=ctx,
                client=client,
                kit=kit,
                messages=messages,
                seed_hits=retrieved_hits,
                supplemented=supplemented,
                assistant_msg_ids=assistant_msg_ids,
                tool_msg_ids=tool_msg_ids,
                result=result,
                enrich_cache=enrich_cache,
                alias_map=alias_map,
                max_rounds=max_rounds,
                tools_schema=tools_schema,
                thinking_budget=thinking_budget,
            ):
                yield ev
        except asyncio.CancelledError:
            logger.info(f"会话 {ctx.session_id} 主循环被取消")
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"对话主循环异常: {e}")
            yield ChatEvent(
                ChatEventType.ERROR,
                {"phase": "llm_loop", "error": str(e)},
            )
            result.error = str(e)
        result.llm_time_ms = (time.perf_counter() - llm_start) * 1000 - result.tool_time_ms

        # ---- 8) 收尾：touch session + turn.done ----
        result.assistant_message_ids = assistant_msg_ids
        result.tool_message_ids = tool_msg_ids
        new_msg_count = 1 + len(assistant_msg_ids) + len(tool_msg_ids)
        try:
            self._session_service.touch_session(
                session_id=ctx.session_id, delta=new_msg_count,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"touch session 失败: {e}")

        # ---- 9) 后台异步起标题（仅首轮） ----
        if is_first_turn and assistant_msg_ids:
            try:
                # 取首条 assistant 文本作为助手回复输入
                first_asst_text = await self._fetch_first_assistant_text(
                    assistant_msg_ids[0],
                )
                self._title_service.schedule_in_background(
                    session_id=ctx.session_id,
                    user_id=ctx.user_id,
                    user_query=ctx.query,
                    assistant_reply=first_asst_text,
                    session_service=self._session_service,
                )
            except Exception as e:  # noqa: BLE001
                logger.debug(f"调度起标题任务失败（忽略）: {e}")

        result.total_time_ms = (time.perf_counter() - total_start) * 1000
        result.citations_count = self._merge_citations_count(retrieved_hits, supplemented)
        yield ChatEvent(
            ChatEventType.TURN_DONE,
            {
                "session_id": ctx.session_id,
                "user_message_id": result.user_message_id,
                "assistant_message_ids": result.assistant_message_ids,
                "tool_message_ids": result.tool_message_ids,
                "rounds": result.rounds,
                "tool_rounds": result.tool_rounds,
                "tool_calls_count": result.tool_calls_count,
                "citations_count": result.citations_count,
                "finish_reason": result.final_finish_reason,
                "total_time_ms": result.total_time_ms,
                "retrieval_time_ms": result.retrieval_time_ms,
                "llm_time_ms": result.llm_time_ms,
                "tool_time_ms": result.tool_time_ms,
                "error": result.error,
            },
        )

    # ============================================================
    # 主循环（RAG / Agent 统一）
    # ============================================================

    async def _run_loop_real(
        self,
        *,
        ctx: ChatTurnContext,
        client: LLMClient,
        kit: Optional[KnowledgeNavToolKit],
        messages: List[Dict[str, Any]],
        seed_hits: List[ChunkItem],
        supplemented: List[ChunkItem],
        assistant_msg_ids: List[str],
        tool_msg_ids: List[str],
        result: ChatTurnResult,
        enrich_cache: TurnEnrichCache,
        alias_map: ChunkAliasMap,
        max_rounds: int,
        tools_schema: Optional[List[Dict[str, Any]]],
        thinking_budget: Optional[int],
    ) -> AsyncIterator[ChatEvent]:
        """RAG 单轮 / Agent 工具循环 + 收尾轮的统一执行体"""

        for round_idx in range(max_rounds):
            assistant_msg_id = generate_message_id()
            acc = StreamAccumulator(model=client.model)

            # 流式拉一轮
            try:
                stream = client.astream(
                    messages=messages,
                    tools=tools_schema,
                    tool_choice="auto" if tools_schema else None,
                    thinking_budget=thinking_budget,
                    max_tokens=self._cfg.max_completion_tokens,
                )
                async for chunk in stream:
                    for sev in acc.feed(chunk):
                        ev = self._stream_event_to_chat_event(sev)
                        if ev is not None:
                            yield ev
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.error(f"LLM 流式调用失败: {e}")
                yield ChatEvent(
                    ChatEventType.ERROR,
                    {"phase": "llm_stream", "error": str(e), "round": round_idx},
                )
                result.error = str(e)
                return

            resp = acc.finalize()
            result.rounds += 1

            # 把本轮 assistant 拼回 messages（继续下一轮 / 收尾用）
            messages.append(_assistant_message(resp))

            # ---- 分支 A: 无 tool_calls → 直接持久化 + message.done + 退出 ----
            if not resp.tool_calls:
                # 种子 + 本 turn 内工具已累计补充的 chunk（多轮时后续轮仍可能引用 [c1]）
                citations_this_round = await self._build_citations_for_round(
                    seed_hits=seed_hits,
                    added_chunks=supplemented,
                    enrich_cache=enrich_cache,
                    alias_map=alias_map,
                )
                await self._persist_assistant(
                    ctx=ctx,
                    message_id=assistant_msg_id,
                    resp=resp,
                    citations=citations_this_round,
                    alias_map=alias_map,
                )
                assistant_msg_ids.append(assistant_msg_id)
                yield ChatEvent(
                    ChatEventType.MESSAGE_DONE,
                    {
                        "message_id": assistant_msg_id,
                        "role": "assistant",
                        "round": round_idx,
                        "finish_reason": resp.finish_reason,
                        "tool_calls_count": 0,
                        "citations_count": len(citations_this_round),
                        "citations": [c.model_dump() for c in citations_this_round],
                        "has_thinking": bool(resp.thinking),
                        "usage": {
                            "prompt_tokens": resp.usage.prompt_tokens,
                            "completion_tokens": resp.usage.completion_tokens,
                            "total_tokens": resp.usage.total_tokens,
                        },
                    },
                )
                result.final_finish_reason = resp.finish_reason
                return

            # ---- 分支 B: 有 tool_calls，但 RAG 模式不允许 → 仍持久化空 results 后退出 ----
            if kit is None:
                # RAG 路径理论上不会到这里（tools_schema=None 模型不应返工具）
                logger.warning(
                    "RAG 模式收到 tool_calls，忽略并退出",
                )
                citations_this_round = await self._build_citations_for_round(
                    seed_hits=seed_hits,
                    added_chunks=supplemented,
                    enrich_cache=enrich_cache,
                    alias_map=alias_map,
                )
                await self._persist_assistant(
                    ctx=ctx,
                    message_id=assistant_msg_id,
                    resp=resp,
                    citations=citations_this_round,
                    alias_map=alias_map,
                )
                assistant_msg_ids.append(assistant_msg_id)
                yield ChatEvent(
                    ChatEventType.MESSAGE_DONE,
                    {
                        "message_id": assistant_msg_id,
                        "role": "assistant",
                        "round": round_idx,
                        "finish_reason": resp.finish_reason,
                        "tool_calls_count": len(resp.tool_calls),
                        "citations_count": len(citations_this_round),
                        "citations": [c.model_dump() for c in citations_this_round],
                        "has_thinking": bool(resp.thinking),
                        "usage": {
                            "prompt_tokens": resp.usage.prompt_tokens,
                            "completion_tokens": resp.usage.completion_tokens,
                            "total_tokens": resp.usage.total_tokens,
                        },
                    },
                )
                result.final_finish_reason = "tool_calls"
                return

            # ---- 分支 C: Agent 模式，有 tool_calls ----
            # 关键：先把工具跑完，把 result_brief / items_added 一并合并进 assistant 落库
            # ——这样历史回放时 UI 也能拿到工具结果（修复 "工具未返回摘要" / "新增 0 段"）。
            # 注意事件顺序仍然是：(content/tool_call stream) → message.done →
            #                    tool_call.completed × N → tool_round.done，
            # 前端 useKnowledgeChat 的 lastAssistantIdRef 逻辑依赖该顺序。
            result.tool_rounds += 1
            result.tool_calls_count += len(resp.tool_calls)
            tool_t0 = time.perf_counter()
            tool_results = await self._exec_tools_parallel(kit, resp.tool_calls)
            result.tool_time_ms += (time.perf_counter() - tool_t0) * 1000

            citations_this_round = await self._build_citations_for_round(
                seed_hits=seed_hits,
                added_chunks=supplemented,
                enrich_cache=enrich_cache,
                alias_map=alias_map,
            )
            await self._persist_assistant(
                ctx=ctx,
                message_id=assistant_msg_id,
                resp=resp,
                citations=citations_this_round,
                tool_results=tool_results,
                alias_map=alias_map,
            )
            assistant_msg_ids.append(assistant_msg_id)

            yield ChatEvent(
                ChatEventType.MESSAGE_DONE,
                {
                    "message_id": assistant_msg_id,
                    "role": "assistant",
                    "round": round_idx,
                    "finish_reason": resp.finish_reason,
                    "tool_calls_count": len(resp.tool_calls),
                    "citations_count": len(citations_this_round),
                    "citations": [c.model_dump() for c in citations_this_round],
                    "has_thinking": bool(resp.thinking),
                    "usage": {
                        "prompt_tokens": resp.usage.prompt_tokens,
                        "completion_tokens": resp.usage.completion_tokens,
                        "total_tokens": resp.usage.total_tokens,
                    },
                },
            )

            tool_round_brief: List[Dict[str, Any]] = []
            for tc, content, items_added, time_ms in tool_results:
                tool_msg_id = generate_message_id()
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": content,
                })
                await self._persist_tool_message(
                    ctx=ctx,
                    message_id=tool_msg_id,
                    tc=tc,
                    content=content,
                )
                tool_msg_ids.append(tool_msg_id)

                brief = (content or "")[:200]
                tool_round_brief.append({
                    "id": tc.id,
                    "name": tc.name,
                    "args": tc.arguments,
                    "result_brief": brief,
                    "items_added": items_added,
                    "time_ms": time_ms,
                })
                yield ChatEvent(
                    ChatEventType.TOOL_CALL_COMPLETED,
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "args": tc.arguments,
                        "result_brief": brief,
                        "items_added": items_added,
                        "time_ms": time_ms,
                        "tool_message_id": tool_msg_id,
                    },
                )

            yield ChatEvent(
                ChatEventType.TOOL_ROUND_DONE,
                {"round": round_idx, "tool_calls": tool_round_brief},
            )

        # ---- 达到 max_rounds 仍含 tool_calls → 收尾轮强制纯文本 ----
        if messages and messages[-1].get("role") == "tool":
            messages.append({
                "role": "user",
                "content": (
                    "已达到允许的工具调用轮次。**请勿再调用任何工具**，"
                    "仅基于当前对话中的检索片段与工具输出，"
                    "用自然语言给出最终答复。"
                ),
            })
            final_msg_id = generate_message_id()
            acc = StreamAccumulator(model=client.model)
            try:
                async for chunk in client.astream(
                    messages=messages,
                    tools=None,
                    thinking_budget=thinking_budget,
                    max_tokens=self._cfg.max_completion_tokens,
                ):
                    for sev in acc.feed(chunk):
                        ev = self._stream_event_to_chat_event(sev)
                        if ev is not None:
                            yield ev
            except Exception as e:  # noqa: BLE001
                logger.error(f"收尾轮 LLM 调用失败: {e}")
                yield ChatEvent(
                    ChatEventType.ERROR,
                    {"phase": "finalize", "error": str(e)},
                )
                return

            fin = acc.finalize()
            if fin.tool_calls:
                logger.warning(
                    "收尾轮模型仍返回 tool_calls（已忽略，按纯文本处理）",
                )
            messages.append(_assistant_message(fin))
            result.rounds += 1
            citations_final = await self._build_citations_for_round(
                seed_hits=seed_hits,
                added_chunks=supplemented,
                enrich_cache=enrich_cache,
                alias_map=alias_map,
            )
            await self._persist_assistant(
                ctx=ctx,
                message_id=final_msg_id,
                resp=fin,
                citations=citations_final,
                alias_map=alias_map,
            )
            assistant_msg_ids.append(final_msg_id)
            yield ChatEvent(
                ChatEventType.MESSAGE_DONE,
                {
                    "message_id": final_msg_id,
                    "role": "assistant",
                    "round": "final",
                    "finish_reason": fin.finish_reason,
                    "tool_calls_count": 0,
                    "citations_count": len(citations_final),
                    "citations": [c.model_dump() for c in citations_final],
                    "has_thinking": bool(fin.thinking),
                    "usage": {
                        "prompt_tokens": fin.usage.prompt_tokens,
                        "completion_tokens": fin.usage.completion_tokens,
                        "total_tokens": fin.usage.total_tokens,
                    },
                },
            )
            result.final_finish_reason = fin.finish_reason

    # ============================================================
    # 子功能：检索
    # ============================================================

    async def _do_retrieve(self, ctx: ChatTurnContext) -> List[ChunkItem]:
        """调用 ``RetrieveService`` 做种子检索"""
        rs = self._get_retrieve_service()
        # MetadataFilter：限定到会话允许的 KB
        filters = MetadataFilter(
            user_id=ctx.user_id,
        )
        if ctx.knowledge_base_ids:
            # MetadataFilter 没有原生 list 字段，按首个 KB 过滤 + Phase 4 再扩展
            filters.knowledge_base_id = ctx.knowledge_base_ids[0]
        request = RetrieveRequest(
            query_text=ctx.query,
            filters=filters,
            top_k=ctx.retrieve_top_k,
            enable_validation=self._cfg.enable_validation_for_chat,
        )
        response = await rs.retrieve(request)
        return list(response.items or [])

    # ============================================================
    # 子功能：工具并行执行
    # ============================================================

    @staticmethod
    async def _exec_tools_parallel(
        kit: KnowledgeNavToolKit,
        tool_calls: List[ToolCall],
    ) -> List[Tuple[ToolCall, str, int, float]]:
        """并行执行多个 tool_calls；返回 ``[(tc, content, items_added, time_ms), ...]``"""

        async def _one(tc: ToolCall) -> Tuple[ToolCall, str, int, float]:
            t0 = time.perf_counter()
            before = len(kit._supplemented)  # noqa: SLF001 (intentional)
            if not kit.has(tc.name):
                text = f"未知工具或未启用: {tc.name}"
            else:
                text = await kit.call(tc.name, tc.arguments)
            elapsed = (time.perf_counter() - t0) * 1000
            added = max(0, len(kit._supplemented) - before)  # noqa: SLF001
            return tc, text, added, elapsed

        return await asyncio.gather(*[_one(tc) for tc in tool_calls])

    # ============================================================
    # 子功能：StreamEvent → ChatEvent 翻译
    # ============================================================

    @staticmethod
    def _stream_event_to_chat_event(sev: StreamEvent) -> Optional[ChatEvent]:
        if sev.type == StreamEventType.CONTENT_DELTA:
            return ChatEvent(ChatEventType.CONTENT_DELTA, {"text": sev.text})
        if sev.type == StreamEventType.THINKING_DELTA:
            return ChatEvent(ChatEventType.THINKING_DELTA, {"text": sev.text})
        if sev.type == StreamEventType.TOOL_CALL_STARTED:
            return ChatEvent(
                ChatEventType.TOOL_CALL_STARTED,
                {
                    "index": sev.tool_call_index,
                    "id": sev.tool_call_id,
                    "name": sev.tool_call_name,
                },
            )
        if sev.type == StreamEventType.TOOL_CALL_ARGS_DELTA:
            return ChatEvent(
                ChatEventType.TOOL_CALL_ARGS_DELTA,
                {"index": sev.tool_call_index, "text": sev.text},
            )
        # FINISH 不直接透出（用 MESSAGE_DONE 取代）
        return None

    # ============================================================
    # 子功能：持久化
    # ============================================================

    @staticmethod
    async def _persist_assistant(
        *,
        ctx: ChatTurnContext,
        message_id: str,
        resp: LLMResponse,
        citations: List[Citation],
        tool_results: Optional[List[Tuple[ToolCall, str, int, float]]] = None,
        alias_map: Optional[ChunkAliasMap] = None,
    ) -> None:
        """落 assistant 消息到 MongoDB（thinking / tool_calls / citations / usage 全保留）

        Args:
            tool_results: 本轮工具执行结果，``[(tc, content, items_added, time_ms), ...]``。
                传入时会按 ``tc.id`` 合并到 ``ToolCallRecord.result_brief`` /
                ``items_added``——这样历史回放时前端也能拿到工具结果。
                None 表示 LLM 这轮没返工具调用、或 RAG 模式异常忽略工具。
            alias_map: 若提供，会把"本轮新分配的 alias delta"写入
                ``metadata['alias_additions']``，便于下一 turn 重建累加。
                同时把 tool_calls 入参里的 ``chunk_id`` alias 还原成真实 id 落库
                （Mongo 里保存语义稳定的真实 id，前端历史回放就不必依赖 alias）。
        """
        try:
            # tc.id → (result_brief, items_added)
            results_by_id: Dict[str, Tuple[str, int]] = {}
            for tr_tc, tr_content, tr_items_added, _ in (tool_results or []):
                results_by_id[tr_tc.id] = (
                    (tr_content or "")[:200],
                    tr_items_added,
                )

            tool_call_records = []
            for tc in (resp.tool_calls or []):
                brief, items_added = results_by_id.get(tc.id, (None, 0))
                # 落库前把入参里的 alias 还原回真实 id（仅 chunk_id 字段；
                # section_id / document_id 本来就不走 alias）
                args = dict(tc.arguments or {})
                if alias_map is not None:
                    raw = args.get("chunk_id")
                    if isinstance(raw, str) and alias_map.is_alias(raw):
                        real = alias_map.resolve_alias(raw)
                        if real:
                            args["chunk_id"] = real
                tool_call_records.append(
                    ToolCallRecord(
                        id=tc.id,
                        name=tc.name,
                        arguments=args,
                        result_brief=brief,
                        items_added=items_added,
                    )
                )
            usage = TokenUsageRecord(
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
                total_tokens=resp.usage.total_tokens,
                thinking_tokens=(
                    getattr(resp.usage, "thinking_tokens", None)
                ),
            )
            metadata: Dict[str, Any] = {"model": resp.model or ""}
            if alias_map is not None:
                delta = alias_map.consume_turn_delta()
                if delta:
                    metadata[METADATA_ALIAS_ADDITIONS_KEY] = delta
            await chat_message_repo.create(
                creator=ctx.user_id,
                _id=message_id,
                session_id=ctx.session_id,
                user_id=ctx.user_id,
                role=ChatRole.ASSISTANT.value,
                content=resp.content or "",
                thinking=(resp.thinking.reasoning if resp.thinking else None),
                tool_calls=tool_call_records,
                citations=citations,
                usage=usage,
                finish_reason=resp.finish_reason,
                metadata=metadata,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"持久化 assistant 失败: msg={message_id}, err={e}",
            )

    @staticmethod
    async def _persist_tool_message(
        *,
        ctx: ChatTurnContext,
        message_id: str,
        tc: ToolCall,
        content: str,
    ) -> None:
        """落 role=tool 消息"""
        try:
            await chat_message_repo.create(
                creator=ctx.user_id,
                _id=message_id,
                session_id=ctx.session_id,
                user_id=ctx.user_id,
                role=ChatRole.TOOL.value,
                content=content,
                tool_call_id=tc.id,
                metadata={"tool_name": tc.name},
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"持久化 tool 消息失败: msg={message_id}, err={e}")

    # ============================================================
    # 子功能：citations 合并
    # ============================================================

    @staticmethod
    async def _build_citations_for_round(
        *,
        seed_hits: List[ChunkItem],
        added_chunks: List[ChunkItem],
        enrich_cache: TurnEnrichCache,
        alias_map: Optional[ChunkAliasMap] = None,
    ) -> List[Citation]:
        """构造 assistant 落库 / message.done 用的 citations，并把渲染元数据 enrich。

        调用方应传入本 user turn 内需要覆盖的 chunk 集合，典型为::

            seed_hits + supplemented   # 种子 + 工具链路上累计补充（去重由本函数完成）

        这样任意一轮 assistant 的正文里引用 ``[c1]``（种子）或工具返回的
        ``[cN]``，同一条消息的 ``citations`` 都能带上 ``alias``，刷新后前端可解析。

        - 去重按 ``chunk_id``。
        - 元数据通过 ``enrich_cache`` 共享，相同 chunk_id 跨轮不会重复查表。
        - ``alias_map`` 若提供则给每条 Citation 填 ``alias``（``alias_for`` 须在
          更早阶段已为相关 chunk 分配过）。
        """
        seen: set = set()
        unique_chunks: List[ChunkItem] = []
        for c in list(seed_hits) + list(added_chunks):
            if not c.chunk_id or c.chunk_id in seen:
                continue
            seen.add(c.chunk_id)
            unique_chunks.append(c)

        if not unique_chunks:
            return []

        # 触发本轮所需 chunks 的 enrich（命中缓存的部分零成本）
        try:
            await enrich_cache.ensure(unique_chunks)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"enrich citations 失败（按裸数据落库）: {e}")

        items: List[Citation] = []
        # 调试统计：本轮 chunks 的 file_id / file_name / section_title 命中率
        hit_file = 0
        hit_section = 0
        for c in unique_chunks:
            meta = enrich_cache.get(c.chunk_id)
            if meta and meta.file_id:
                hit_file += 1
            if meta and meta.section_title:
                hit_section += 1
            preview = (c.text or "").strip()
            if preview:
                preview = preview[:200]
            items.append(Citation(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                knowledge_base_id=c.knowledge_base_id,
                score=c.score or 0.0,
                alias=alias_map.alias_of(c.chunk_id) if alias_map else None,
                chunk_type=meta.chunk_type if meta else None,
                page_index=meta.page_index if meta else None,
                section_title=meta.section_title if meta else None,
                file_id=meta.file_id if meta else None,
                file_name=meta.file_name if meta else None,
                preview=preview or None,
            ))
        total = len(unique_chunks)
        logger.info(
            f"[citations] 本轮 enrich 命中：file_id {hit_file}/{total}，"
            f"section_title {hit_section}/{total}（缓存 size={enrich_cache.size}）"
        )
        if hit_file == 0 and total > 0:
            sample_cids = ", ".join(c.chunk_id for c in unique_chunks[:3])
            sample_dids = ", ".join((c.document_id or "?") for c in unique_chunks[:3])
            logger.warning(
                f"[citations] ⚠ 所有 chunks 都没拿到 file_id；样例 chunk_id=[{sample_cids}]，"
                f"document_id=[{sample_dids}]。请检查 workspace_file_system 表中 "
                f"(user_id, document_id) 是否存在记录。"
            )
        return items

    @staticmethod
    def _merge_citations_count(
        seed_hits: List[ChunkItem],
        supplemented: List[ChunkItem],
    ) -> int:
        seen: set = set()
        for c in list(seed_hits) + list(supplemented):
            if c.chunk_id:
                seen.add(c.chunk_id)
        return len(seen)

    @staticmethod
    def _chunk_brief(
        c: ChunkItem,
        *,
        meta: Optional[ChunkMeta] = None,
        alias: Optional[str] = None,
    ) -> Dict[str, Any]:
        """retrieval.done / tool_call.completed 帧里的 chunk 简要表示。

        在方案 B 下，前端拿到种子 chunks 时就直接能用 meta 字段渲染彩色 chip。
        Phase B 后多带一个 ``alias`` 字段（``c1`` / ``c2`` ...）；前端把 LLM
        输出里的 ``[c1]`` 解析为 chip 时按 alias 反查 citation。
        meta=None / alias=None 时降级输出（兼容路径，前端按 Optional 兜底）。
        """
        brief: Dict[str, Any] = {
            "chunk_id": c.chunk_id,
            "document_id": c.document_id,
            "score": c.score,
            "preview": ((c.text or "")[:120]),
        }
        if alias:
            brief["alias"] = alias
        if meta is not None:
            brief.update({
                "chunk_type": meta.chunk_type,
                "page_index": meta.page_index,
                "section_title": meta.section_title,
                "file_id": meta.file_id,
                "file_name": meta.file_name,
            })
        return brief

    # ============================================================
    # 子功能：摘要回调（fast preset）
    # ============================================================

    def _build_summarize_fn(self):
        """返回一个绑定到主对话 preset 的 ``summarize_fn``。

        history_compressor 的 ``SummarizeFn`` 是 ``Callable[[Sequence[Any]],
        Awaitable[str]]``；本函数把它绑到 ``self._cfg.agent_model_preset``
        指向的 LLMClient，避免摘要意外使用与主对话不同的模型造成上下文漂移。
        """
        summarize_preset = self._cfg.agent_model_preset

        async def _summarize(early_history) -> str:
            try:
                client = self._get_llm_client(summarize_preset)
            except Exception:  # noqa: BLE001
                from src.client.llm import create_llm_client_from_preset

                client = create_llm_client_from_preset(summarize_preset)
            # 拼一段非常短的 instruction
            text_parts: List[str] = []
            for m in early_history:
                role = getattr(m, "role", None)
                content = getattr(m, "content", "") or ""
                if role and content:
                    text_parts.append(f"[{role}] {content}")
            transcript = "\n".join(text_parts)[:6000]
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是对话历史压缩助手。请将下面这段多轮对话压缩为 200 字"
                        "以内的中文要点列表，保留：用户主要诉求、助手已给出的关键"
                        "结论、命中的 chunk_id（如有）；删除冗余对话和闲聊。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"对话片段：\n\n{transcript}\n\n要点摘要：",
                },
            ]
            resp = await client.agenerate(
                messages=messages, temperature=0.2, max_tokens=400,
            )
            return (resp.content or "").strip()

        return _summarize

    # ============================================================
    # 辅助：取首条 assistant 的 content
    # ============================================================

    @staticmethod
    async def _fetch_first_assistant_text(message_id: str) -> str:
        try:
            obj = await chat_message_repo.get_by_id(message_id)
            if obj and obj.content:
                return obj.content
        except Exception:  # noqa: BLE001
            pass
        return ""


# ============================================================
# 辅助：assistant message 序列化
# ============================================================


def _assistant_message(resp: LLMResponse) -> Dict[str, Any]:
    """把 LLMResponse 转成 OpenAI/LiteLLM 协议的 assistant message dict

    特殊处理
    --------
    - DeepSeek 在 thinking mode（含 ``deepseek-reasoner`` 和开启 ``thinking_budget``
      的 ``deepseek-chat``）下，要求上一轮 assistant 的 ``reasoning_content``
      必须**原样**回传到下一轮 messages，否则 round 1+ 会被 DeepSeek 以
      ``"The reasoning_content in the thinking mode must be passed back to
      the API."`` 报 400。这里只要 ``resp.thinking`` 非空就附带 ``reasoning_content``
      字段；其他厂商（OpenAI / Anthropic / Qwen 等）会忽略未知字段，不影响兼容性。
    """
    msg: Dict[str, Any] = {"role": "assistant", "content": resp.content or ""}
    if resp.thinking and resp.thinking.reasoning:
        msg["reasoning_content"] = resp.thinking.reasoning
    if resp.tool_calls:
        import json as _json

        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": _json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
            for tc in resp.tool_calls
        ]
    return msg


__all__ = [
    "ChatService",
    "ChatServiceConfig",
]
