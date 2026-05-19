#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : tools.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    KnowledgeNavToolKit ── 知识库导航类工具的公共基类

    背景
    ----
    在 ResultValidator 出现之前，"上下钻 / 上下文窗口 / 文档骨架"这类
    **导航类原子能力** 就已经在 ``src/retrieve/capabilities/navigation/``
    沉淀了。LiteLLM 时代 ResultValidator 把它们打包成 5 个工具暴露给 LLM。

    本 Phase 2 把其中 **不依赖外部 ``RouteRegistry``** 的 4 个导航工具
    上提为公共基类 ``KnowledgeNavToolKit``，供：

    - **Chat 模式 Agent**（``src/service/chat/chat_service.py``）：
      默认只暴露 ``context_window / drill_down / skeleton`` 3 个（不暴露
      ``roll_up`` —— 对话场景里"chunk 上溯到 section"价值较低）。
    - **ResultValidator**（``src/retrieve/validator/tools.py``）：在基类
      之上扩展自己的 ``roll_up`` / ``re_retrieve`` 两个工具，仍保持 5 工具。

    这样做的好处：
    1. **避免双份维护**：context_window / drill_down / skeleton 三个 handler
       和 schema 不再在 Chat / Validator 各写一份；
    2. **白名单可控**：通过 ``enabled_tools`` 参数显式声明本次暴露哪些工具，
       避免误把 ``re_retrieve`` / ``roll_up`` 暴露给 Chat；
    3. **扩展友好**：子类只需重写 ``_register_extra_tools()`` 即可加新工具。

    设计取舍
    --------
    - 工具按 **OpenAI 原生 function-calling schema** 暴露，与 ``LLMClient``
      已有的 ``tools=`` 入参直接对接，不引入新协议。
    - ``supplemented_items`` 由调用方注入并共享，工具执行的新 chunk 都会 append 进去，
      上层 ChatService / Validator 收尾时直接读这个列表合 citation。
    - 错误吞掉但返回可读字符串（让 LLM 自己看到错误而不是中断对话循环）。

@Modify History:
    2026-05-11 - 首版（Phase 2）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import contextvars
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

# 并发安全的 tool_call_id 上下文变量：asyncio.gather 并发执行多个工具时，
# 每个 task 有独立的 ContextVar 副本，不会互相覆盖。
_current_tc_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_current_tc_id", default=""
)

from loguru import logger

from src.client.llm.types import ToolSchema
from src.retrieve.types.result import ChunkItem
from src.service.chat.chunk_alias_map import ChunkAliasMap


# ==================== 文本格式化辅助 ====================


def format_chunks_for_llm(
    chunks: List[ChunkItem],
    max_preview: int = 200,
    *,
    alias_map: Optional[ChunkAliasMap] = None,
) -> str:
    """把 ChunkItem 列表渲染为给 LLM 看的文本（与 validator 历史风格保持一致）

    Args:
        chunks: 工具返回的命中片段
        max_preview: 单条文本最大字符
        alias_map: 若提供则把 ``chunk_id`` 替换为 session 级 alias 并就地分配
            新 alias；为 ``None`` 时输出真实 chunk_id（兼容 validator 用法）。
    """
    if not chunks:
        return "未找到相关内容。"
    lines = [f"找到 {len(chunks)} 个相关片段:"]
    for c in chunks:
        text = (c.text or "")[:max_preview]
        doc = c.document_id or "N/A"
        cid_label = alias_map.alias_for(c.chunk_id) if alias_map and c.chunk_id else c.chunk_id
        lines.append(
            f"- chunk_id={cid_label}, document_id={doc}, "
            f"score={c.score:.4f}\n  {text}",
        )
    return "\n".join(lines)


def skeleton_outline_to_text(outline_tree: list) -> str:
    """SkeletonNode 列表转可读文本（带缩进的目录树，含 section_id 供 drill_down 使用）"""
    lines: List[str] = []

    def _walk(node: Any, depth: int = 0) -> None:
        indent = "  " * depth
        section_id = getattr(node, "section_id", "")
        title = getattr(node, "title", "") or "(无标题)"
        chunk_count = getattr(node, "chunk_count", 0)
        lines.append(f"{indent}- [{section_id}] {title}（{chunk_count}个片段）")
        for child in getattr(node, "children", []):
            _walk(child, depth + 1)

    for node in outline_tree:
        _walk(node)
    return "\n".join(lines) if lines else "(空目录)"


# ==================== 基类 ====================


# 在 Chat 模式下默认暴露的导航工具白名单。
# 注意：``roll_up`` 故意未列入，是 ChatService 的产品取舍——
# 对话场景下"chunk 上溯到 section 标题"价值较低，可改用 skeleton 替代。
DEFAULT_NAV_TOOLS: Sequence[str] = ("context_window", "drill_down", "skeleton", "roll_up", "search_knowledge_base")


class KnowledgeNavToolKit:
    """知识库导航工具集（公共基类）。

    内置 4 个导航工具（实现完整）：

    - ``context_window``: 上下文窗口扩展
    - ``drill_down``:     粒度下钻（section/document → chunk）
    - ``roll_up``:        粒度上溯（chunk → section）
    - ``skeleton``:       文档骨架

    通过构造参数 ``enabled_tools`` 决定**实际暴露**给 LLM 的子集；
    若需要新增工具（例如 ``re_retrieve``），子类应：

    1. 重写 ``_register_extra_tools()`` 把新 handler 注册到 ``self._handlers``；
    2. 重写 ``_extra_tool_schemas()`` 返回新工具的 OpenAI schema；
    3. （可选）在 ``__init__`` 里把新工具名追加到 ``enabled_tools``。

    Examples
    --------
    Chat 模式（基类直接用）::

        kit = KnowledgeNavToolKit(supplemented_items=collected)
        schemas = kit.schemas()              # 仅 3 个
        text = await kit.call("context_window", {"chunk_id": "..."})

    Validator 模式（子类扩展）::

        kit = ValidatorToolKit(registry=registry, supplemented_items=collected)
        schemas = kit.schemas()              # 5 个（4 导航 + re_retrieve）
    """

    # 入参字段名 → 是否需要 alias unwrap（chunk_id 类入参才 unwrap）
    # 注：``section_id`` / ``document_id`` 不做 alias，沿用真实 id。
    _CHUNK_ID_ARG_KEYS: Sequence[str] = ("chunk_id",)

    def __init__(
        self,
        supplemented_items: List[ChunkItem],
        *,
        enabled_tools: Optional[Sequence[str]] = None,
        alias_map: Optional[ChunkAliasMap] = None,
        retrieve_service: Optional[Any] = None,
        on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None,
        user_id: str = "",
        knowledge_base_ids: Optional[List[str]] = None,
    ) -> None:
        self._supplemented = supplemented_items
        # capability 懒加载缓存，避免每次 import 都做一次
        self._capabilities: Dict[str, Any] = {}
        # session 级 chunk alias map（None 时回退到老行为：直接用真实 chunk_id）
        self._alias_map = alias_map
        # search_knowledge_base 依赖
        self._retrieve_service = retrieve_service
        self._on_progress = on_progress
        self._user_id = user_id
        self._knowledge_base_ids = knowledge_base_ids or []
        # 检索工具结果暂存：tool_call_id → (chunks_brief, params)
        self._search_results: Dict[str, Tuple[List[Dict[str, Any]], Dict[str, Any]]] = {}

        # 全量注册基类内建 handler
        self._handlers: Dict[str, Callable[..., Awaitable[str]]] = {
            "context_window": self._context_window,
            "drill_down": self._drill_down,
            "roll_up": self._roll_up,
            "skeleton": self._skeleton,
            "search_knowledge_base": self._search_knowledge_base,
        }
        # 给子类一个挂载额外 handler 的钩子
        self._register_extra_tools()

        # 计算实际暴露集合
        candidate = list(enabled_tools) if enabled_tools is not None else list(DEFAULT_NAV_TOOLS)
        unknown = [name for name in candidate if name not in self._handlers]
        if unknown:
            logger.warning(
                f"KnowledgeNavToolKit: 跳过未注册的 enabled_tools={unknown}; "
                f"已注册 handlers={sorted(self._handlers)}"
            )
        self._enabled: List[str] = [name for name in candidate if name in self._handlers]

    # ==================== 子类扩展钩子 ====================

    def _register_extra_tools(self) -> None:
        """子类重写以注册额外 handler（默认空实现）"""
        return None

    def _extra_tool_schemas(self) -> List[ToolSchema]:
        """子类重写以返回额外工具的 OpenAI schema（默认空）"""
        return []

    # ==================== 公共 API ====================

    @property
    def enabled_tools(self) -> List[str]:
        return list(self._enabled)

    def has(self, name: str) -> bool:
        return name in self._enabled

    def schemas(self) -> List[ToolSchema]:
        """返回实际暴露的工具 OpenAI schema 列表"""
        all_schemas = _BUILTIN_NAV_SCHEMAS + self._extra_tool_schemas()
        index = {s["function"]["name"]: s for s in all_schemas}
        return [index[name] for name in self._enabled if name in index]

    async def call(
        self,
        name: str,
        args: Optional[Dict[str, Any]] = None,
        *,
        tool_call_id: str = "",
    ) -> str:
        """路由到对应 handler；未启用工具直接返回错误字符串。

        若构造时注入了 ``alias_map``，会把入参里 ``chunk_id`` 字段做一次
        alias → 真实 chunk_id 的还原（容忍 LLM 传 alias 或真实 id 两种形式）。
        """
        if name not in self._enabled:
            return f"工具未启用或不可用: {name}"
        handler = self._handlers[name]
        # 设置当前 tool_call_id，供 search_knowledge_base 的进度回调使用
        _current_tc_id_var.set(tool_call_id)
        unwrapped = self._unwrap_alias_in_args(args or {})
        try:
            return await handler(**unwrapped)
        except TypeError as e:
            logger.warning(f"工具 {name} 入参不匹配: {e} | args={unwrapped}")
            return f"工具 {name} 入参非法: {e}"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"工具 {name} 执行异常: {e}")
            return f"工具执行失败: {e}"

    def _unwrap_alias_in_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """把入参里的 chunk_id alias 还原成真实 chunk_id。

        策略
        ----
        - ``alias_map=None`` 时直接返回原 args（保留老行为）。
        - 仅对白名单字段（``chunk_id``）做 unwrap；``section_id`` /
          ``document_id`` 不动。
        - 字段值是 ``cN`` 形态且能在 map 里查到才替换，否则原样保留；
          这样既能容忍 LLM 传真实 chunk_id，也能容忍它传了一个错的 alias
          （工具会自然失败，由 LLM 自己看错误信息修正）。
        """
        if self._alias_map is None or not args:
            return dict(args)
        out: Dict[str, Any] = dict(args)
        for k in self._CHUNK_ID_ARG_KEYS:
            v = out.get(k)
            if not isinstance(v, str) or not v:
                continue
            if not self._alias_map.is_alias(v):
                continue
            real = self._alias_map.resolve_alias(v)
            if real is not None:
                out[k] = real
                logger.debug(f"alias unwrap: {k} {v} -> {real[:16]}...")
            else:
                logger.warning(
                    f"alias unwrap 失败：{k}={v} 不在 alias_map 中；"
                    f"已知 size={self._alias_map.size}"
                )
        return out

    # ==================== capability 懒加载 ====================

    def _cap(self, key: str) -> Any:
        if not self._capabilities:
            from src.retrieve.capabilities.navigation import (
                ContextWindow,
                DrillDown,
                RollUp,
                Skeleton,
            )
            self._capabilities.update({
                "context_window": ContextWindow(),
                "drill_down": DrillDown(),
                "roll_up": RollUp(),
                "skeleton": Skeleton(),
            })
        return self._capabilities[key]

    # ==================== 内建 handler 实现 ====================

    async def _context_window(self, chunk_id: str, window_size: int = 2) -> str:
        from src.retrieve.types.enums import GranularityLevel
        from src.retrieve.types.query import NavigationQuery

        cap = self._cap("context_window")
        query = NavigationQuery(
            anchor_id=chunk_id,
            anchor_type=GranularityLevel.CHUNK,
            window_size=window_size,
            include_content=True,
        )
        result = await cap.execute(query=query)
        chunks = [it for it in result.items if isinstance(it, ChunkItem)]
        self._supplemented.extend(chunks)
        logger.debug(f"context_window({chunk_id}) → {len(chunks)} chunks")
        return format_chunks_for_llm(chunks, alias_map=self._alias_map)

    async def _drill_down(
        self,
        section_id: Optional[str] = None,
        document_id: Optional[str] = None,
        target: str = "chunk",
    ) -> str:
        from src.retrieve.types.enums import GranularityLevel
        from src.retrieve.types.query import NavigationQuery
        from src.retrieve.types.result import SectionItem

        anchor_id = section_id or document_id or ""
        if not anchor_id:
            return "drill_down: 必须提供 section_id 或 document_id"
        anchor_type = (
            GranularityLevel.SECTION if section_id else GranularityLevel.DOCUMENT
        )

        target_map = {
            "section": GranularityLevel.SECTION,
            "chunk": GranularityLevel.CHUNK,
        }
        target_granularity = target_map.get(target, GranularityLevel.CHUNK)

        # Section → Section 无意义
        if anchor_type == GranularityLevel.SECTION and target_granularity == GranularityLevel.SECTION:
            return "drill_down: section_id 已经是章节级别，请指定 target=chunk"

        cap = self._cap("drill_down")
        query = NavigationQuery(
            anchor_id=anchor_id,
            anchor_type=anchor_type,
            target_granularity=target_granularity,
            include_content=True,
        )
        result = await cap.execute(query=query)

        if target_granularity == GranularityLevel.SECTION:
            # Document → Section：返回 section 列表
            sections = [it for it in result.items if isinstance(it, SectionItem)]
            if not sections:
                return "未找到章节。"
            lines = [f"找到 {len(sections)} 个章节:"]
            for s in sections:
                title = s.title or "(无标题)"
                doc = s.document_id or "N/A"
                lines.append(
                    f"- section_id={s.section_id}, document_id={doc}\n  {title}"
                )
            logger.debug(f"drill_down({anchor_id}, target=section) → {len(sections)} sections")
            return "\n".join(lines)
        else:
            # Section → Chunk / Document → Chunk：返回 chunk 列表
            chunks = [it for it in result.items if isinstance(it, ChunkItem)]
            self._supplemented.extend(chunks)
            logger.debug(f"drill_down({anchor_id}, target=chunk) → {len(chunks)} chunks")
            return format_chunks_for_llm(chunks, alias_map=self._alias_map)

    async def _roll_up(
        self,
        chunk_id: Optional[str] = None,
        section_id: Optional[str] = None,
        target: str = "section",
    ) -> str:
        from src.retrieve.types.enums import GranularityLevel
        from src.retrieve.types.query import NavigationQuery
        from src.retrieve.types.result import DocumentItem, SectionItem

        if not chunk_id and not section_id:
            return "roll_up: 必须提供 chunk_id 或 section_id"
        if chunk_id and section_id:
            return "roll_up: chunk_id 和 section_id 只能传一个"

        anchor_id = chunk_id or section_id
        anchor_type = GranularityLevel.CHUNK if chunk_id else GranularityLevel.SECTION

        target_map = {
            "section": GranularityLevel.SECTION,
            "document": GranularityLevel.DOCUMENT,
        }
        target_granularity = target_map.get(target, GranularityLevel.SECTION)

        cap = self._cap("roll_up")
        query = NavigationQuery(
            anchor_id=anchor_id,
            anchor_type=anchor_type,
            target_granularity=target_granularity,
            include_content=True,
        )
        result = await cap.execute(query=query)

        # 直接格式化，暴露真实 id 供下游工具使用，不走 alias 系统
        sections: List[SectionItem] = []
        documents: List[DocumentItem] = []
        chunks: List[ChunkItem] = []
        for item in result.items:
            if isinstance(item, SectionItem):
                sections.append(item)
            elif isinstance(item, DocumentItem):
                documents.append(item)
            elif isinstance(item, ChunkItem):
                chunks.append(item)

        lines: List[str] = []

        if documents:
            lines.append(f"找到 {len(documents)} 个所属文档:")
            for d in documents:
                title = d.title or "(无标题)"
                summary = (d.summary or "")[:200]
                lines.append(
                    f"- document_id={d.document_id}, score={d.score:.4f}\n"
                    f"  {title}" + (f"\n  {summary}" if summary else "")
                )

        if sections:
            lines.append(f"找到 {len(sections)} 个所属章节:")
            for s in sections:
                title = s.title or "(无标题)"
                doc = s.document_id or "N/A"
                lines.append(
                    f"- section_id={s.section_id}, document_id={doc}\n  {title}"
                )

        if chunks:
            lines.append(format_chunks_for_llm(chunks, alias_map=self._alias_map))

        logger.debug(
            f"roll_up({anchor_id}, target={target}) → "
            f"{len(documents)} docs, {len(sections)} sections, {len(chunks)} chunks"
        )
        return "\n".join(lines) if lines else "未找到上层信息。"

    async def _search_knowledge_base(
        self,
        query_text: str,
        top_k: int = 10,
    ) -> str:
        """调用完整检索管道（LLM₁ 路由规划 → 多路召回 → 融合 → 精排）"""
        if self._retrieve_service is None:
            return "search_knowledge_base: 检索服务不可用。"

        from src.retrieve.pipeline.types import RetrieveRequest
        from src.retrieve.types.query import MetadataFilter

        filters = MetadataFilter(user_id=self._user_id)
        if self._knowledge_base_ids:
            filters.knowledge_base_id = self._knowledge_base_ids[0]

        # 构建对话历史上下文，注入路由规划器以增强查询生成
        conversation_context = self._build_conversation_context_for_search()

        request = RetrieveRequest(
            query_text=query_text,
            filters=filters,
            top_k=top_k,
            enable_validation=False,
            conversation_context=conversation_context,
        )

        # 进度回调：通过 kit 的 on_progress 传递 tool_call_id
        async def on_progress(stage: str) -> None:
            if self._on_progress is not None:
                try:
                    # tool_call_id 在 call() 中通过 _current_tc_id_var 设置
                    tc_id = _current_tc_id_var.get()
                    await self._on_progress(tc_id, stage)
                except Exception:
                    pass

        try:
            response = await self._retrieve_service.retrieve(
                request, on_progress=on_progress,
            )
            items = list(response.items or [])
            self._supplemented.extend(items)
            logger.debug(
                f"search_knowledge_base({query_text!r}) → {len(items)} chunks"
            )

            # 存储检索结果，供 _exec_tools_parallel 消费后传给前端
            tc_id = _current_tc_id_var.get()
            if tc_id:
                chunks_brief = [
                    {
                        "chunk_id": c.chunk_id,
                        "document_id": c.document_id,
                        "score": c.score,
                        "preview": (c.text or "")[:200],
                    }
                    for c in items
                ]
                params: Dict[str, Any] = {
                    "query_text": query_text,
                    "top_k": top_k,
                }
                if response.route_plan:
                    params["route_plan"] = response.route_plan.model_dump(
                        exclude_none=True,
                    )
                self._search_results[tc_id] = (chunks_brief, params)

            return format_chunks_for_llm(items, alias_map=self._alias_map)
        except Exception as e:
            logger.warning(f"search_knowledge_base 执行异常: {e}")
            return f"检索失败: {e}"

    def _build_conversation_context_for_search(self) -> Optional[str]:
        """从最近的 tool 消息中提取对话上下文（如果有）。

        search_knowledge_base 在工具循环中被调用时，messages 里已有历史。
        但 kit 不直接持有 messages，这里返回 None，
        让 RetrieveService 的路由规划器使用默认上下文。
        """
        return None

    async def _skeleton(self, document_id: str) -> str:
        from src.retrieve.types.enums import GranularityLevel
        from src.retrieve.types.query import NavigationQuery
        from src.retrieve.types.result import SkeletonItem

        cap = self._cap("skeleton")
        query = NavigationQuery(
            anchor_id=document_id,
            anchor_type=GranularityLevel.DOCUMENT,
            include_content=False,
        )
        result = await cap.execute(query=query)

        chunks: List[ChunkItem] = []
        toc_text = ""
        for item in result.items:
            if isinstance(item, SkeletonItem):
                toc_text = skeleton_outline_to_text(item.outline_tree)
                chunks.append(ChunkItem(
                    chunk_id=f"skeleton:{document_id}",
                    score=0.0,
                    document_id=document_id,
                    text=toc_text,
                    metadata={"_source_route": "navkit_skeleton"},
                ))
        self._supplemented.extend(chunks)
        logger.debug(f"skeleton({document_id}) → {len(chunks)} items")
        return toc_text if chunks else "未找到文档骨架。"


# ==================== 4 个内建工具的 schema ====================

_BUILTIN_NAV_SCHEMAS: List[ToolSchema] = [
    {
        "type": "function",
        "function": {
            "name": "context_window",
            "description": (
                "扩展指定 chunk 的上下文窗口，获取同一 section 内前后相邻的 chunk。"
                "适用于结果文本被截断或缺少上下文的情况。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chunk_id": {
                        "type": "string",
                        "description": (
                            "目标 chunk 的引用号（参考片段里显示的 alias，"
                            "形如 c1 / c2 / c10；不是 UUID）。"
                        ),
                    },
                    "window_size": {
                        "type": "integer",
                        "description": "前后各扩展的 chunk 数量",
                        "default": 2,
                        "minimum": 1,
                    },
                },
                "required": ["chunk_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "drill_down",
            "description": (
                "从 document 或 section 级别向下钻取。"
                "支持 document→section、document→chunk、section→chunk 三种路径。"
                "返回真实 id，可继续用于后续导航工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "string", "description": "起始 section 的 ID（与 document_id 二选一）"},
                    "document_id": {"type": "string", "description": "起始 document 的 ID（与 section_id 二选一）"},
                    "target": {
                        "type": "string",
                        "description": "目标粒度：section 或 chunk。document→section 返回章节列表，其余路径返回片段列表",
                        "enum": ["section", "chunk"],
                        "default": "chunk",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "roll_up",
            "description": (
                "从 chunk 或 section 向上回溯。"
                "支持 chunk→section、chunk→document、section→document 三种路径。"
                "返回真实 id，可继续用于后续导航工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chunk_id": {
                        "type": "string",
                        "description": "起始 chunk 的引用号（如 c1 / c2），与 section_id 二选一",
                    },
                    "section_id": {
                        "type": "string",
                        "description": "起始 section 的 ID（真实 id），与 chunk_id 二选一",
                    },
                    "target": {
                        "type": "string",
                        "description": "目标粒度：section 或 document",
                        "enum": ["section", "document"],
                        "default": "section",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skeleton",
            "description": (
                "获取文档的骨架结构（目录树），帮助理解整体组织。"
                "适用于需要了解文档结构以定位相关章节。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "目标 document 的 ID"},
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "在知识库中检索与查询相关的文档片段。"
                "内部会经过大模型路由规划、多路召回、融合和精排，返回最相关的结果。"
                "当已有片段不足以回答用户问题，或需要更多信息时可以调用。"
                "可以用不同的查询文本多次调用以获取不同角度的信息。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_text": {
                        "type": "string",
                        "description": "检索查询文本，描述需要查找的信息",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 30,
                    },
                },
                "required": ["query_text"],
            },
        },
    },
]


__all__ = [
    "KnowledgeNavToolKit",
    "DEFAULT_NAV_TOOLS",
    "format_chunks_for_llm",
    "skeleton_outline_to_text",
]
