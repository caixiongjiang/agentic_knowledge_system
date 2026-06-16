#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""KnowledgeNavToolKit ── Chat Agent 工具编排器。"""

from __future__ import annotations

from functools import partial
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

from loguru import logger

from src.client.llm.types import ToolSchema
from src.retrieve.types.result import ChunkItem
from src.service.chat.chunk_alias_map import ChunkAliasMap
from src.service.chat.tools.handlers import ALL_TOOL_DEFINITIONS
from src.service.chat.tools.registry import BUILTIN_NAV_SCHEMAS, DEFAULT_NAV_TOOLS
from src.service.chat.tools.runtime import get_current_tool_call_id, set_current_tool_call_id


class KnowledgeNavToolKit:
    """知识库导航工具集（编排层）。

    各工具的具体实现位于 ``src/service/chat/tools/handlers/`` 下，
    新增工具时只需添加 handler 模块并在 ``handlers/__init__.py`` 注册。
    """

    _CHUNK_ID_ARG_KEYS: Sequence[str] = ("chunk_id",)
    _CHUNK_ID_LIST_ARG_KEYS: Sequence[str] = ("chunk_ids",)

    def __init__(
        self,
        supplemented_items: List[ChunkItem],
        *,
        enabled_tools: Optional[Sequence[str]] = None,
        alias_map: Optional[ChunkAliasMap] = None,
        retrieve_service: Optional[Any] = None,
        on_progress: Optional[
            Callable[..., Awaitable[None]]
        ] = None,
        user_id: str = "",
        knowledge_base_ids: Optional[List[str]] = None,
        scope_document_ids: Optional[List[str]] = None,
        scope_kind: str = "kb",
        scope_label: Optional[str] = None,
    ) -> None:
        self.supplemented = supplemented_items
        self.alias_map = alias_map
        self.retrieve_service = retrieve_service
        self.on_progress = on_progress
        self.user_id = user_id
        self.knowledge_base_ids = knowledge_base_ids or []

        self.scope_document_ids: Optional[List[str]] = (
            list(scope_document_ids) if scope_document_ids is not None else None
        )
        self.scope_doc_id_set: frozenset = frozenset(self.scope_document_ids or [])
        self.scope_kind = scope_kind
        self.scope_label = scope_label or (
            f"folder/{scope_label}" if scope_kind == "folder" else "kb"
        )

        self.search_results: Dict[str, Tuple[List[Dict[str, Any]], Dict[str, Any]]] = {}
        self._result_counts: Dict[str, int] = {}
        self._execution_models: Dict[str, str] = {}
        self._capabilities: Dict[str, Any] = {}

        self._handlers: Dict[str, Callable[..., Awaitable[str]]] = {
            definition.name: partial(definition.handler, self)
            for definition in ALL_TOOL_DEFINITIONS
        }

        candidate = list(enabled_tools) if enabled_tools is not None else list(DEFAULT_NAV_TOOLS)
        unknown = [name for name in candidate if name not in self._handlers]
        if unknown:
            logger.warning(
                f"KnowledgeNavToolKit: 跳过未注册的 enabled_tools={unknown}; "
                f"已注册 handlers={sorted(self._handlers)}",
            )
        self._enabled: List[str] = [
            name for name in candidate if name in self._handlers
        ]

    @property
    def enabled_tools(self) -> List[str]:
        return list(self._enabled)

    def has(self, name: str) -> bool:
        return name in self._enabled

    def note_result_count(self, count: int) -> None:
        if count < 0:
            return
        tc_id = get_current_tool_call_id()
        if tc_id:
            self._result_counts[tc_id] = count

    def items_added_for(self, tool_call_id: str) -> int:
        return self._result_counts.pop(tool_call_id, 0) if tool_call_id else 0

    def note_execution_model(self, model: str) -> None:
        if not model:
            return
        tc_id = get_current_tool_call_id()
        if tc_id:
            self._execution_models[tc_id] = model

    def execution_model_for(self, tool_call_id: str) -> Optional[str]:
        if not tool_call_id:
            return None
        return self._execution_models.pop(tool_call_id, None)

    async def emit_progress(
        self,
        stage: str,
        *,
        model: Optional[str] = None,
        channel: str = "retrieval",
    ) -> None:
        if self.on_progress is None:
            return
        tc_id = get_current_tool_call_id()
        if not tc_id:
            return
        try:
            await self.on_progress(
                tc_id,
                stage,
                model=model,
                channel=channel,
            )
        except Exception:
            pass

    def schemas(self) -> List[ToolSchema]:
        index = {schema["function"]["name"]: schema for schema in BUILTIN_NAV_SCHEMAS}
        return [index[name] for name in self._enabled if name in index]

    async def call(
        self,
        name: str,
        args: Optional[Dict[str, Any]] = None,
        *,
        tool_call_id: str = "",
    ) -> str:
        if name not in self._enabled:
            return f"工具未启用或不可用: {name}"
        handler = self._handlers[name]
        set_current_tool_call_id(tool_call_id)
        unwrapped = self._unwrap_alias_in_args(args or {})

        scope_msg = self._enforce_scope(name, unwrapped)
        if scope_msg is not None:
            logger.info(
                f"工具 {name} 被 scope 守卫拦截: kind={self.scope_kind}, "
                f"label={self.scope_label}, reason={scope_msg!r}",
            )
            return scope_msg

        try:
            return await handler(**unwrapped)
        except TypeError as e:
            logger.warning(f"工具 {name} 入参不匹配: {e} | args={unwrapped}")
            return f"工具 {name} 入参非法: {e}"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"工具 {name} 执行异常: {e}")
            return f"工具执行失败: {e}"

    def _enforce_scope(
        self,
        name: str,
        args: Dict[str, Any],
    ) -> Optional[str]:
        if self.scope_kind != "folder":
            return None

        if not self.scope_doc_id_set:
            return (
                f"当前会话锁定在文件夹 {self.scope_label or '(未知)'}，"
                "但该文件夹内没有可检索的文档。"
                "请告知用户：当前文件夹为空或文档尚未完成索引，"
                "无法基于知识回答；可建议用户上传文档或切换文件夹。"
            )

        explicit_doc_id = args.get("document_id")
        if isinstance(explicit_doc_id, str) and explicit_doc_id:
            if explicit_doc_id not in self.scope_doc_id_set:
                return (
                    f"document_id={explicit_doc_id} 不在当前 scope "
                    f"（folder={self.scope_label}，共 "
                    f"{len(self.scope_doc_id_set)} 篇）内。"
                    "请先用 search_knowledge_base / drill_down 在本范围内"
                    "拿到合法的 document_id 后再调用本工具。"
                )
        return None

    def _unwrap_alias_in_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if self.alias_map is None or not args:
            return dict(args)
        out: Dict[str, Any] = dict(args)
        for key in self._CHUNK_ID_ARG_KEYS:
            value = out.get(key)
            if not isinstance(value, str) or not value:
                continue
            if not self.alias_map.is_alias(value):
                continue
            real = self.alias_map.resolve_alias(value)
            if real is not None:
                out[key] = real
                logger.debug(f"alias unwrap: {key} {value} -> {real[:16]}...")
            else:
                logger.warning(
                    f"alias unwrap 失败：{key}={value} 不在 alias_map 中；"
                    f"已知 size={self.alias_map.size}",
                )

        for key in self._CHUNK_ID_LIST_ARG_KEYS:
            raw = out.get(key)
            if not isinstance(raw, list) or not raw:
                continue
            unwrapped: List[Any] = []
            for value in raw:
                if isinstance(value, str) and value and self.alias_map.is_alias(value):
                    real = self.alias_map.resolve_alias(value)
                    if real is not None:
                        unwrapped.append(real)
                        continue
                    logger.warning(
                        f"alias unwrap 失败（列表项）：{key} 中 {value} 不在 alias_map；"
                        f"size={self.alias_map.size}",
                    )
                unwrapped.append(value)
            out[key] = unwrapped
        return out

    def cap(self, key: str) -> Any:
        if not self._capabilities:
            from src.retrieve.capabilities.navigation import (
                ContextWindow,
                DrillDown,
                RollUp,
                Skeleton,
            )

            self._capabilities.update(
                {
                    "context_window": ContextWindow(),
                    "drill_down": DrillDown(),
                    "roll_up": RollUp(),
                    "skeleton": Skeleton(),
                },
            )
        return self._capabilities[key]

    @property
    def _search_results(self) -> Dict[str, Tuple[List[Dict[str, Any]], Dict[str, Any]]]:
        """兼容旧代码对私有字段的访问（chat_service）。"""
        return self.search_results
