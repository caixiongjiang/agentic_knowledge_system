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

from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

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
    """SkeletonNode 列表转可读文本（带缩进的目录树）"""
    lines: List[str] = []

    def _walk(node: Any, depth: int = 0) -> None:
        indent = "  " * depth
        title = getattr(node, "title", "")
        lines.append(f"{indent}- {title}")
        for child in getattr(node, "children", []):
            _walk(child, depth + 1)

    for node in outline_tree:
        _walk(node)
    return "\n".join(lines) if lines else "(空目录)"


# ==================== 基类 ====================


# 在 Chat 模式下默认暴露的导航工具白名单。
# 注意：``roll_up`` 故意未列入，是 ChatService 的产品取舍——
# 对话场景下"chunk 上溯到 section 标题"价值较低，可改用 skeleton 替代。
DEFAULT_NAV_TOOLS: Sequence[str] = ("context_window", "drill_down", "skeleton")


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
    ) -> None:
        self._supplemented = supplemented_items
        # capability 懒加载缓存，避免每次 import 都做一次
        self._capabilities: Dict[str, Any] = {}
        # session 级 chunk alias map（None 时回退到老行为：直接用真实 chunk_id）
        self._alias_map = alias_map

        # 全量注册基类内建 handler
        self._handlers: Dict[str, Callable[..., Awaitable[str]]] = {
            "context_window": self._context_window,
            "drill_down": self._drill_down,
            "roll_up": self._roll_up,
            "skeleton": self._skeleton,
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

    async def call(self, name: str, args: Optional[Dict[str, Any]] = None) -> str:
        """路由到对应 handler；未启用工具直接返回错误字符串。

        若构造时注入了 ``alias_map``，会把入参里 ``chunk_id`` 字段做一次
        alias → 真实 chunk_id 的还原（容忍 LLM 传 alias 或真实 id 两种形式）。
        """
        if name not in self._enabled:
            return f"工具未启用或不可用: {name}"
        handler = self._handlers[name]
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
    ) -> str:
        from src.retrieve.types.enums import GranularityLevel
        from src.retrieve.types.query import NavigationQuery

        anchor_id = section_id or document_id or ""
        if not anchor_id:
            return "drill_down: 必须提供 section_id 或 document_id"
        anchor_type = (
            GranularityLevel.SECTION if section_id else GranularityLevel.DOCUMENT
        )
        cap = self._cap("drill_down")
        query = NavigationQuery(
            anchor_id=anchor_id,
            anchor_type=anchor_type,
            target_granularity=GranularityLevel.CHUNK,
            include_content=True,
        )
        result = await cap.execute(query=query)
        chunks = [it for it in result.items if isinstance(it, ChunkItem)]
        self._supplemented.extend(chunks)
        logger.debug(f"drill_down({anchor_id}) → {len(chunks)} chunks")
        return format_chunks_for_llm(chunks, alias_map=self._alias_map)

    async def _roll_up(self, chunk_id: str) -> str:
        from src.retrieve.types.enums import GranularityLevel
        from src.retrieve.types.query import NavigationQuery
        from src.retrieve.types.result import SectionItem

        cap = self._cap("roll_up")
        query = NavigationQuery(
            anchor_id=chunk_id,
            anchor_type=GranularityLevel.CHUNK,
            target_granularity=GranularityLevel.SECTION,
            include_content=True,
        )
        result = await cap.execute(query=query)

        chunks: List[ChunkItem] = []
        for item in result.items:
            if isinstance(item, ChunkItem):
                chunks.append(item)
            elif isinstance(item, SectionItem):
                chunks.append(ChunkItem(
                    chunk_id=f"rollup:{item.section_id}",
                    score=item.score,
                    document_id=item.document_id,
                    text=item.title,
                    metadata={
                        "_source_route": "navkit_rollup",
                        "_section_id": item.section_id,
                    },
                ))
        self._supplemented.extend(chunks)
        logger.debug(f"roll_up({chunk_id}) → {len(chunks)} items")
        return format_chunks_for_llm(chunks, alias_map=self._alias_map)

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
                "从 section 或 document 级别向下钻取到子 chunk 列表。"
                "适用于需要查看某个章节或文档下的完整内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "string", "description": "目标 section 的 ID"},
                    "document_id": {"type": "string", "description": "目标 document 的 ID"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "roll_up",
            "description": (
                "从 chunk 上溯到所属 section 的标题和摘要，提供全局视角。"
                "适用于需要了解某个 chunk 在文档中所处的位置和上层结构。"
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
                },
                "required": ["chunk_id"],
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
]


__all__ = [
    "KnowledgeNavToolKit",
    "DEFAULT_NAV_TOOLS",
    "format_chunks_for_llm",
    "skeleton_outline_to_text",
]
