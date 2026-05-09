"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : result_validator.py
@Author  : caixiongjiang
@Date    : 2026/04/03
@Function:
    LLM₂ 结果验证 Agent（LiteLLM 版本，显式多轮 + 每轮并行工具）

    设计要点
    --------
    - 完全脱离 LangChain：直接基于 ``LLMClient`` + OpenAI tool calling 协议；
    - 每轮 LLM 可在一次回复中并行发起多个 ``tool_calls``；
      所有工具用 ``asyncio.gather`` 并行执行后，把结果以 ``role="tool"`` 拼回对话；
    - ``max_rounds`` 控制**含工具调用**的调整轮数上限，到达上限后会做一次「收尾轮」
      强制要求文本结论（不再允许工具调用）；
    - 输出兼容旧 ``ValidationResult``：``passed / rounds / adjustment_rounds /
      tool_calls_count / tool_calls_summary / supplemented_items / reasoning /
      total_validation_time_ms`` 全部保留。

@Modify History:
    2026-04-09 - LangChain Agent
    2026-04-10 - 改为显式循环 + 并行工具
    2026-04-21 - 移除 LangChain，全面切换 LiteLLM + OpenAI native tool calling
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger

from src.client.llm import LLMClient, create_llm_client_from_preset
from src.client.llm.types import LLMResponse, ToolCall
from src.retrieve.pipeline.route_registry import RouteRegistry
from src.retrieve.pipeline.types import ValidationResult
from src.retrieve.types.result import ChunkItem
from src.retrieve.validator.tools import ToolKit
from src.prompts.retrieve.result_validator import build_system_prompt, build_user_prompt


class ResultValidator:
    """LLM₂ 结果验证（LiteLLM 实现）

    每轮模型可并行输出多个工具调用；执行完毕后统一进入下一轮推理。
    ``max_rounds`` = **含工具批次的调整轮数**上限。
    """

    def __init__(
        self,
        model: Union[str, LLMClient, None] = None,
        registry: Optional[RouteRegistry] = None,
    ) -> None:
        if model is None:
            self._client = create_llm_client_from_preset("fast")
        elif isinstance(model, str):
            self._client = create_llm_client_from_preset(model)
        elif isinstance(model, LLMClient):
            self._client = model
        else:
            raise TypeError(
                f"model 必须是 LLMClient / preset 名称 / None，实际 {type(model)}",
            )
        self._registry = registry or RouteRegistry()

    async def validate(
        self,
        query_text: str,
        items: List[ChunkItem],
        max_rounds: int = 3,
    ) -> Tuple[List[ChunkItem], ValidationResult]:
        """验证检索结果并按需补全

        Args:
            query_text: 用户查询
            items:      初始检索结果
            max_rounds: 含工具批次的调整轮数上限（>=1）

        Returns:
            ``(最终 items, ValidationResult)``
        """
        total_start = time.perf_counter()
        max_rounds = max(1, max_rounds)

        supplemented_items: List[ChunkItem] = []
        kit = ToolKit(registry=self._registry, supplemented_items=supplemented_items)
        tools_schema = kit.schemas()

        # ---- 构造首轮 messages ----
        system_prompt = build_system_prompt()
        user_body = build_user_prompt(
            query_text=query_text,
            items=items,
            top_k=len(items),
        )
        user_prompt = (
            f"{user_body}\n\n"
            f"【系统说明】你可以在**单次回复中并行调用多个工具**。"
            f"含工具的补全调整最多进行 **{max_rounds}** 轮；"
            f"若已足够或达到上限，请直接输出最终评估结论，勿再调用工具。"
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        adjustment_rounds = 0
        tool_calls_count = 0
        tool_calls_summary: List[str] = []
        llm_rounds = 0
        last_assistant: Optional[LLMResponse] = None

        # ---- 工具调整循环 ----
        for _ in range(max_rounds):
            resp = await self._client.agenerate(
                messages=messages,
                tools=tools_schema,
                tool_choice="auto",
            )
            llm_rounds += 1
            last_assistant = resp
            messages.append(_assistant_message(resp))

            if not resp.tool_calls:
                break

            tool_calls_count += len(resp.tool_calls)
            for tc in resp.tool_calls:
                tool_calls_summary.append(_tool_call_brief(tc))

            await self._append_tool_results(kit, resp.tool_calls, messages)
            adjustment_rounds += 1

        # ---- 收尾轮：上一条仍是 tool 输出，强制纯文本结论 ----
        if messages and messages[-1].get("role") == "tool":
            messages.append({
                "role": "user",
                "content": (
                    "已达到允许的补全轮次或须结束工具阶段。"
                    "**请勿再调用任何工具**，仅根据当前对话中的检索片段与工具输出，"
                    "用自然语言给出最终评估结论；并务必在**最后一行**输出 "
                    "`[验证状态] SUFFICIENT` 或 `[验证状态] INSUFFICIENT`（与结论一致）。"
                ),
            })
            fin = await self._client.agenerate(
                messages=messages,
                tools=None,
            )
            llm_rounds += 1
            last_assistant = fin
            messages.append(_assistant_message(fin))
            if fin.tool_calls:
                logger.warning("收尾阶段模型仍返回 tool_calls，视为未干净收敛")

        reasoning = self._extract_final_reasoning(messages)
        passed = self._resolve_passed(messages, reasoning)

        # ---- 合并补全 items（去重） ----
        current_items = list(items)
        existing_ids = {c.chunk_id for c in current_items}
        for nc in supplemented_items:
            if nc.chunk_id not in existing_ids:
                current_items.append(nc)
                existing_ids.add(nc.chunk_id)

        total_ms = (time.perf_counter() - total_start) * 1000

        validation_result = ValidationResult(
            passed=passed,
            rounds=llm_rounds,
            adjustment_rounds=adjustment_rounds,
            tool_calls_count=tool_calls_count,
            tool_calls_summary=tool_calls_summary,
            supplemented_items=supplemented_items,
            reasoning=reasoning,
            total_validation_time_ms=total_ms,
        )

        logger.info(
            f"ResultValidator 完成: passed={passed}, llm_rounds={llm_rounds}, "
            f"adjustment_rounds={adjustment_rounds}, tool_calls={tool_calls_count}, "
            f"补全={len(supplemented_items)} 条, 耗时={total_ms:.0f}ms"
        )

        _ = last_assistant  # 保留引用方便调试
        return current_items, validation_result

    # ---- 内部 ----
    @staticmethod
    async def _append_tool_results(
        kit: ToolKit,
        tool_calls: List[ToolCall],
        messages: List[Dict[str, Any]],
    ) -> None:
        async def _one(tc: ToolCall) -> Tuple[str, str]:
            if not kit.has(tc.name):
                return tc.id, f"未知工具: {tc.name}"
            text = await kit.call(tc.name, tc.arguments)
            return tc.id, text

        pairs = await asyncio.gather(*[_one(tc) for tc in tool_calls])
        for tid, content in pairs:
            messages.append({
                "role": "tool",
                "tool_call_id": tid,
                "content": content,
            })

    @staticmethod
    def _extract_final_reasoning(messages: List[Dict[str, Any]]) -> str:
        for msg in reversed(messages):
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                texts = [
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                if texts:
                    return "\n".join(texts).strip()
        return ""

    @staticmethod
    def _resolve_passed(messages: List[Dict[str, Any]], reasoning: str) -> bool:
        """是否通过验证：先要求最终 assistant 不再带 tool_calls，再解析标签或启发式。"""
        if not _last_assistant_clean(messages):
            return False
        tag = _parse_verdict_line(reasoning)
        if tag is not None:
            return tag
        return not _heuristic_insufficient_reasoning(reasoning)


# ==================== messages 构造辅助 ====================


def _assistant_message(resp: LLMResponse) -> Dict[str, Any]:
    """把 LLMResponse 转成符合 OpenAI/LiteLLM 协议的 assistant message。

    若包含 tool_calls，需要按 OpenAI 格式回填到 message 内，
    后续的 ``role="tool"`` 消息才能用 ``tool_call_id`` 关联。
    """
    msg: Dict[str, Any] = {"role": "assistant", "content": resp.content or ""}
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


def _last_assistant_clean(messages: List[Dict[str, Any]]) -> bool:
    """最后一条 assistant 是否为「无 tool_calls」的纯文本结论。"""
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return not msg.get("tool_calls")
    return False


def _tool_call_brief(tc: ToolCall) -> str:
    args = tc.arguments or {}
    brief = ", ".join(f"{k}={str(v)[:30]}" for k, v in args.items())
    return f"{tc.name}({brief})"


# ==================== 文本结论解析 ====================


_VERDICT_TAIL = re.compile(
    r"^\s*\[验证状态\]\s*(SUFFICIENT|INSUFFICIENT)\s*$",
    re.IGNORECASE,
)


def _parse_verdict_line(text: str) -> Optional[bool]:
    """从全文自底向上匹配首行 ``[验证状态] SUFFICIENT|INSUFFICIENT``。"""
    if not text or not text.strip():
        return None
    for line in reversed(text.strip().splitlines()):
        m = _VERDICT_TAIL.match(line)
        if m:
            return m.group(1).upper() == "SUFFICIENT"
    return None


def _heuristic_insufficient_reasoning(text: str) -> bool:
    """无显式标签时，用结论文本尾部做保守判断。"""
    if not text:
        return False
    tail = text[-1500:] if len(text) > 1500 else text
    needles = (
        "检索结果不充分",
        "无法回答用户查询",
        "无法直接回答用户查询",
        "不足以回答用户查询",
        "无法负责任地回答",
        "仍不足以",
        "仍无法回答",
    )
    return any(n in tail for n in needles)
