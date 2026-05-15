#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk_alias_map.py
@Author  : caixiongjiang
@Date    : 2026/05/14
@Function:
    ChunkAliasMap ── chunk_id ↔ session 级短 alias 双向映射

    背景与动机
    ----------
    把真实 chunk_id（``chunk-<uuid>`` ≈ 42 字符）直接喂给 LLM 有三个问题：

    1. **Token 消耗**：一次回答里如果引用 20 个片段，光 id 就消耗 ~800 token；
    2. **数据安全**：内部主键随回答暴露给上游模型方（特别是非自部署模型）；
    3. **LLM 行为脆弱**：长 uuid 容易被某些模型（DeepSeek 在长上下文下尤其
       典型）截断成 8 位短 hash 输出，导致前端拿不到完整 id 进而无法渲染。

    解决方案：给 LLM 看的内容里把 chunk_id 替换为短 alias ``c1 / c2 / c3 ...``
    （4 字节、可读、对 LLM 友好），后端维护双向映射；只有最终持久化到 Mongo /
    下发到前端 ``Citation.chunk_id`` 才用真实 id，前端渲染再做最后一跳查表。

    生命周期
    --------
    - **session 级别**：同一 session 内同一 chunk 始终对应同一个 alias，
      跨 turn 不会重新编号；这样 LLM 在第二 turn 引用第一 turn 出现过的
      chunk 时，alias 仍能正常 unwrap。
    - **增量持久化**：每条 assistant 消息只在 metadata 里写**本轮新分配**
      的 ``alias_additions``；下次 load history 时把所有 assistant 消息的
      delta 累加即可重建完整 map。
    - **无 race**：单 session 内的 chat turn 在 chat_service 里串行执行，
      AliasMap 不需要锁。

    边界
    ----
    - 仅做 ``chunk_id`` 的 alias；``section_id`` / ``document_id`` 沿用真实
      id（``drill_down`` / ``skeleton`` 工具入参需要，且这两个 id 暴露面
      较窄）。
    - alias 命名空间是 ``^c\\d+$``；任何非该模式的字符串都直接走"非 alias"
      路径（既能容忍 LLM 偶尔输出真实 chunk-uuid，也方便单测）。

@Modify History:
    2026-05-14 - 首版（Phase B: chunk alias 节省 token & 防截断）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from loguru import logger


# alias 格式：c + 十进制数字（c1, c2, c10, ...）
ALIAS_RE = re.compile(r"^c(\d+)$")

# 持久化到 ChatMessage.metadata 时使用的 key
METADATA_ALIAS_ADDITIONS_KEY = "alias_additions"


class ChunkAliasMap:
    """session 级 chunk_id ↔ alias 双向映射。

    线程模型
    --------
    单 session 内 chat turn 串行运行；本类不加锁。
    """

    def __init__(self) -> None:
        self._alias_to_chunk: Dict[str, str] = {}
        self._chunk_to_alias: Dict[str, str] = {}
        # 已分配的最大序号；下次新分配从 _counter + 1 开始
        self._counter: int = 0
        # 本 turn 内新增的部分（用于 metadata delta 持久化）
        self._delta_alias_to_chunk: Dict[str, str] = {}

    # ==================== 分配 / 查询 ====================

    def alias_for(self, chunk_id: str) -> str:
        """取或分配 alias；同一 chunk_id 永远映射到同一个 alias。"""
        if not chunk_id:
            return ""
        existing = self._chunk_to_alias.get(chunk_id)
        if existing is not None:
            return existing
        self._counter += 1
        alias = f"c{self._counter}"
        self._alias_to_chunk[alias] = chunk_id
        self._chunk_to_alias[chunk_id] = alias
        self._delta_alias_to_chunk[alias] = chunk_id
        return alias

    def alias_for_many(self, chunk_ids: Iterable[str]) -> List[str]:
        return [self.alias_for(cid) for cid in chunk_ids]

    def resolve_alias(self, alias: str) -> Optional[str]:
        """alias → 真实 chunk_id；未找到返回 None。"""
        return self._alias_to_chunk.get(alias)

    def alias_of(self, chunk_id: str) -> Optional[str]:
        """chunk_id → alias；未分配过返回 None（不自动分配，与 alias_for 区分）。"""
        return self._chunk_to_alias.get(chunk_id)

    def is_alias(self, s: str) -> bool:
        """判断字符串是否符合 alias 命名模式（c\\d+）。"""
        return bool(s) and ALIAS_RE.match(s) is not None

    # ==================== Delta 管理（持久化用） ====================

    def consume_turn_delta(self) -> Dict[str, str]:
        """取出本 turn 内新分配的 alias→chunk 映射，并清空 delta 缓存。

        ChatService 在 ``_persist_assistant`` 之后调用一次；返回值写入
        ``ChatMessage.metadata['alias_additions']``。
        """
        delta = dict(self._delta_alias_to_chunk)
        self._delta_alias_to_chunk.clear()
        return delta

    def absorb_persisted(self, additions: Dict[str, str]) -> None:
        """从历史 assistant.metadata 重建时调用：吸收一段已持久化的 delta。

        如果遇到 alias 编号已存在但 chunk_id 不一致的情况，记录 warning 并
        以"先到为准"——这种场景理论不会发生（同 alias 必同 chunk），出现
        说明持久化有冲突。
        """
        if not additions:
            return
        for alias, chunk_id in additions.items():
            if not alias or not chunk_id:
                continue
            m = ALIAS_RE.match(alias)
            if not m:
                logger.warning(
                    f"ChunkAliasMap.absorb_persisted: 跳过非法 alias={alias!r}"
                )
                continue
            num = int(m.group(1))
            existing = self._alias_to_chunk.get(alias)
            if existing is not None and existing != chunk_id:
                logger.warning(
                    f"ChunkAliasMap.absorb_persisted: alias={alias} "
                    f"已映射到 {existing}, 忽略冲突的 chunk_id={chunk_id}"
                )
                continue
            if existing is None:
                self._alias_to_chunk[alias] = chunk_id
                self._chunk_to_alias.setdefault(chunk_id, alias)
                if num > self._counter:
                    self._counter = num
        # 历史吸收不属于"本 turn delta"
        # （absorb 完后调用方应紧接着开新 turn，delta 已被前面 consume 过）

    # ==================== 文本替换辅助 ====================

    # 真实 chunk_id 的形态：chunk-<uuid>（小写 hex + 4 个连字符）。
    # 同时兼容老消息里 LLM 输出过的截断短 hash（chunk-1ad9521d）—— 我们只识别
    # 完整 chunk_id，截断的不替换（防止误伤）。
    _FULL_CHUNK_ID_RE = re.compile(
        r"\bchunk-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    )

    def replace_chunk_ids_with_aliases(self, text: str) -> str:
        """在自由文本里把所有完整 chunk_id 字面量替换为 alias。

        典型用法：把 ``format_retrieved_chunks_for_context`` / ``format_chunks_for_llm``
        渲染过的文本进一步压成 alias 形态。这里**不分配新 alias**——只对已
        存在于 map 中的 chunk_id 做替换；遇到 map 里没有的 chunk_id 原样保留。
        """
        if not text:
            return text

        def _sub(m: "re.Match[str]") -> str:
            cid = m.group(0)
            return self._chunk_to_alias.get(cid, cid)

        return self._FULL_CHUNK_ID_RE.sub(_sub, text)

    # ==================== 一些可观测属性 ====================

    @property
    def size(self) -> int:
        return len(self._alias_to_chunk)

    @property
    def counter(self) -> int:
        return self._counter

    def snapshot(self) -> Dict[str, str]:
        """完整 alias→chunk_id 映射快照（拷贝；用于下发到前端 message.done）"""
        return dict(self._alias_to_chunk)


# ==================== 历史重建 ====================


def rebuild_alias_map_from_history(history: Sequence[Any]) -> ChunkAliasMap:
    """从历史消息序列重建 ChunkAliasMap。

    遍历所有 assistant 消息，把 ``metadata['alias_additions']`` 累加吸收；
    返回的 AliasMap 内部 ``_counter`` 等于已分配的最大序号，下次 ``alias_for``
    会从 ``_counter + 1`` 起继续编号。

    Args:
        history: ``ChatMessage`` 列表（按 create_time 正序）。

    Returns:
        重建好的 AliasMap；history 里没有 alias_additions 时返回空 map。
    """
    am = ChunkAliasMap()
    for msg in history:
        if getattr(msg, "role", None) != "assistant":
            continue
        metadata = getattr(msg, "metadata", None) or {}
        additions = metadata.get(METADATA_ALIAS_ADDITIONS_KEY) or {}
        if isinstance(additions, dict) and additions:
            am.absorb_persisted(additions)
    # 吸收完后清掉 delta（这部分不属于"当前 turn 新增"）
    am._delta_alias_to_chunk.clear()  # noqa: SLF001 (intentional within module)
    return am


__all__ = [
    "ChunkAliasMap",
    "rebuild_alias_map_from_history",
    "METADATA_ALIAS_ADDITIONS_KEY",
    "ALIAS_RE",
]
