"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : tools.py
@Date    : 2026/04/21
@Function:
    LLM₂ ResultValidator 可调用工具集

    LiteLLM 时代设计：
        - 工具定义为 **OpenAI 原生 function-calling schema**（dict）；
        - 实现为本模块内的 ``async`` 函数，由 ``ToolKit.call(name, args)`` 路由执行；
        - 与具体 LLM 客户端解耦，业务侧无须依赖 LangChain。

    5 个工具封装了已有的导航/检索能力：
        - context_window: 上下文窗口扩展
        - drill_down:    粒度下钻
        - roll_up:       粒度上溯
        - skeleton:      文档骨架
        - re_retrieve:   改写查询重检索

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger

from src.client.llm.types import ToolSchema
from src.retrieve.pipeline.route_registry import RouteRegistry
from src.retrieve.types.result import ChunkItem


# ==================== ChunkItem 列表展示辅助 ====================


def _format_chunks(chunks: List[ChunkItem], max_preview: int = 200) -> str:
    """将 ChunkItem 列表格式化为 LLM 可读的文本摘要"""
    if not chunks:
        return "未找到相关内容。"
    lines = [f"找到 {len(chunks)} 个相关片段:"]
    for c in chunks:
        text = (c.text or "")[:max_preview]
        doc = c.document_id or "N/A"
        lines.append(
            f"- chunk_id={c.chunk_id}, document_id={doc}, "
            f"score={c.score:.4f}\n  {text}",
        )
    return "\n".join(lines)


# ==================== ToolKit ====================


class ToolKit:
    """OpenAI 原生工具集合：负责 schema 暴露 + 调用路由

    用法::

        kit = ToolKit(registry=..., supplemented_items=collected)
        schemas = kit.schemas()                  # 给 LLMClient.agenerate(tools=...)
        text = await kit.call("context_window", {"chunk_id": "..."})
    """

    def __init__(
        self,
        registry: RouteRegistry,
        supplemented_items: List[ChunkItem],
    ) -> None:
        self._registry = registry
        self._supplemented = supplemented_items
        self._capabilities: Dict[str, Any] = {}
        self._handlers: Dict[str, Callable[..., Awaitable[str]]] = {
            "context_window": self._context_window,
            "drill_down": self._drill_down,
            "roll_up": self._roll_up,
            "skeleton": self._skeleton,
            "re_retrieve": self._re_retrieve,
        }
        self._schemas: List[ToolSchema] = _build_tool_schemas()

    # ---- 暴露 schema / 调用入口 ----
    def schemas(self) -> List[ToolSchema]:
        return self._schemas

    def has(self, name: str) -> bool:
        return name in self._handlers

    async def call(self, name: str, args: Optional[Dict[str, Any]] = None) -> str:
        handler = self._handlers.get(name)
        if handler is None:
            return f"未知工具: {name}"
        try:
            return await handler(**(args or {}))
        except TypeError as e:
            logger.warning(f"工具 {name} 入参不匹配: {e} | args={args}")
            return f"工具 {name} 入参非法: {e}"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"工具 {name} 执行异常: {e}")
            return f"工具执行失败: {e}"

    # ---- capability 懒加载 ----
    def _cap(self, key: str):
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

    # ---- handler: context_window ----
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
        return _format_chunks(chunks)

    # ---- handler: drill_down ----
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
        return _format_chunks(chunks)

    # ---- handler: roll_up ----
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
                        "_source_route": "validator_rollup",
                        "_section_id": item.section_id,
                    },
                ))
        self._supplemented.extend(chunks)
        logger.debug(f"roll_up({chunk_id}) → {len(chunks)} items")
        return _format_chunks(chunks)

    # ---- handler: skeleton ----
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
                toc_text = _skeleton_to_text(item.outline_tree)
                chunks.append(ChunkItem(
                    chunk_id=f"skeleton:{document_id}",
                    score=0.0,
                    document_id=document_id,
                    text=toc_text,
                    metadata={"_source_route": "validator_skeleton"},
                ))
        self._supplemented.extend(chunks)
        logger.debug(f"skeleton({document_id}) → {len(chunks)} items")
        return toc_text if chunks else "未找到文档骨架。"

    # ---- handler: re_retrieve ----
    async def _re_retrieve(
        self,
        query_text: str,
        route: str = "chunk_dense",
        top_k: int = 10,
    ) -> str:
        from src.retrieve.pipeline.parallel_recall import (
            build_query_for_route,
            normalize_to_chunk_items,
        )
        from src.retrieve.pipeline.types import RouteConfig
        from src.retrieve.types.query import MetadataFilter

        if not self._registry.has(route):
            logger.warning(f"re_retrieve: 未知路由 {route}, 回退 chunk_dense")
            route = "chunk_dense"

        route_cfg = RouteConfig(route=route, top_k=top_k)
        capability = self._registry.get(route)

        try:
            query = build_query_for_route(
                route_cfg=route_cfg,
                query_text=query_text,
                filters=MetadataFilter(),
            )
        except ValueError as e:
            logger.warning(f"re_retrieve: 构造 query 失败 ({e}), 回退 chunk_dense")
            route = "chunk_dense"
            capability = self._registry.get(route)
            query = build_query_for_route(
                route_cfg=RouteConfig(route=route, top_k=top_k),
                query_text=query_text,
                filters=MetadataFilter(),
            )

        result = await capability.execute(query=query)
        chunks = normalize_to_chunk_items(result, route)
        self._supplemented.extend(chunks)
        logger.debug(
            f"re_retrieve(route={route}, '{query_text[:30]}...') → {len(chunks)} chunks",
        )
        return _format_chunks(chunks)


# ==================== schema 构造 ====================


def _build_tool_schemas() -> List[ToolSchema]:
    """OpenAI function-calling 风格 schema 列表（与 ToolKit handler 保持同名同参）"""
    return [
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
                        "chunk_id": {"type": "string", "description": "目标 chunk 的 ID"},
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
                        "chunk_id": {"type": "string", "description": "目标 chunk 的 ID"},
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
        {
            "type": "function",
            "function": {
                "name": "re_retrieve",
                "description": (
                    "用改写后的 query 重新做一次检索，补充原始召回不足的内容。"
                    "仅在原始结果明显偏题或信息严重不足时使用。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_text": {"type": "string", "description": "改写后的查询文本"},
                        "route": {
                            "type": "string",
                            "description": (
                                "使用的路由名称（chunk_dense / enhanced_chunk_dense / "
                                "section_dense / qa_dense / summary_dense / bm25_sparse / "
                                "exact_match / boolean_search）"
                            ),
                            "default": "chunk_dense",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "召回数量",
                            "default": 10,
                            "minimum": 1,
                        },
                    },
                    "required": ["query_text"],
                },
            },
        },
    ]


def _skeleton_to_text(outline_tree: list) -> str:
    """将 SkeletonNode 列表转为可读文本"""
    lines: list[str] = []

    def _walk(node, depth: int = 0) -> None:
        indent = "  " * depth
        title = getattr(node, "title", "")
        lines.append(f"{indent}- {title}")
        for child in getattr(node, "children", []):
            _walk(child, depth + 1)

    for node in outline_tree:
        _walk(node)
    return "\n".join(lines) if lines else "(空目录)"


# ==================== 兼容旧 API ====================


def create_validation_tools(
    registry: RouteRegistry,
    supplemented_items: List[ChunkItem],
) -> ToolKit:
    """旧 API 名称兼容入口：返回 ``ToolKit`` 实例。

    旧调用方使用 ``[t.name for t in tools]`` 这类语义已不再适用；
    新代码请直接 ``ToolKit(...)``。
    """
    return ToolKit(registry=registry, supplemented_items=supplemented_items)
