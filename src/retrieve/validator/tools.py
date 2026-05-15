"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : tools.py
@Date    : 2026/04/21
@Function:
    LLM₂ ResultValidator 可调用工具集

    历史演化
    --------
    - 2026/04/21：首版，把 navigation 能力打包为 5 个 OpenAI function 工具，
      实现独立放在本文件内。
    - **2026/05/11 (Phase 2)**：将 ``context_window / drill_down / roll_up /
      skeleton`` 4 个**导航类**工具上提到 ``src/service/chat/tools.py
      ::KnowledgeNavToolKit`` 公共基类，本文件仅保留 ``ValidatorToolKit``，
      在基类之上扩展自己的 ``re_retrieve`` 工具——避免 Chat / Validator 双份
      维护同一组导航工具。

    与基类的关系
    ------------
    - 基类 ``KnowledgeNavToolKit`` 内建 4 个导航 handler 与 schema；
    - ``ValidatorToolKit`` 通过 ``_register_extra_tools()`` 钩子加上
      ``re_retrieve``，构造时把 5 个工具全部启用；
    - 旧 ``ToolKit`` 名称保留为兼容别名（``ToolKit = ValidatorToolKit``），
      ``result_validator.py`` 等已有调用方零改动。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

from typing import List, Optional

from loguru import logger

from src.client.llm.types import ToolSchema
from src.retrieve.pipeline.route_registry import RouteRegistry
from src.retrieve.types.result import ChunkItem
from src.service.chat.tools import (
    KnowledgeNavToolKit,
    format_chunks_for_llm,
)


# ==================== ValidatorToolKit ====================


class ValidatorToolKit(KnowledgeNavToolKit):
    """LLM₂ ResultValidator 使用的工具集（5 个）

    在 ``KnowledgeNavToolKit`` 的 4 个导航工具基础上，扩展验证场景专属的
    ``re_retrieve`` —— 用改写后的 query 重新检索，补充原始召回不足的内容。

    这一工具需要 ``RouteRegistry`` 来按路由调用具体的检索 capability，
    因此构造签名比基类多一个 ``registry`` 参数。
    """

    def __init__(
        self,
        registry: RouteRegistry,
        supplemented_items: List[ChunkItem],
    ) -> None:
        self._registry = registry
        # 验证场景默认 5 个工具全开
        super().__init__(
            supplemented_items=supplemented_items,
            enabled_tools=(
                "context_window",
                "drill_down",
                "roll_up",
                "skeleton",
                "re_retrieve",
            ),
        )

    # ---- 注册额外 handler ----
    def _register_extra_tools(self) -> None:
        self._handlers["re_retrieve"] = self._re_retrieve

    def _extra_tool_schemas(self) -> List[ToolSchema]:
        return _EXTRA_VALIDATOR_SCHEMAS

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
        return format_chunks_for_llm(chunks)


# ==================== Validator 专属工具 schema ====================

_EXTRA_VALIDATOR_SCHEMAS: List[ToolSchema] = [
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


# ==================== 兼容旧 API ====================
# 旧名字保留，让 ``result_validator.py`` 等已有调用方零改动通过 ``ToolKit`` 使用 5 工具。

ToolKit = ValidatorToolKit


def create_validation_tools(
    registry: RouteRegistry,
    supplemented_items: List[ChunkItem],
) -> ValidatorToolKit:
    """旧 API 名称兼容入口：返回 ``ValidatorToolKit`` 实例。"""
    return ValidatorToolKit(registry=registry, supplemented_items=supplemented_items)


__all__ = [
    "ValidatorToolKit",
    "ToolKit",  # 兼容旧名
    "create_validation_tools",
]
