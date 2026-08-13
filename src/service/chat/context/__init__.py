#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""对话上下文预算与压缩（Cursor 式第二版）

- ``ModelContextCatalog`` ── 按模型解析 max_context / max_output / tokenizer
- ``ContextBudgeter`` ── 完整请求 token 计量与超窗决策
- ``HierarchicalSummarizer`` ── map-reduce 分层摘要（手动/自动统一）
- ``truncate_tool_output`` ── 单条工具结果硬顶截断
"""

from src.service.chat.context.budgeter import (
    TOOL_OUTPUT_ELIDED,
    ContextBudgetInput,
    ContextBudgetReport,
    ContextBudgeter,
    ContextOverflowError,
    ContextShrinkOutcome,
    truncate_tool_output,
)
from src.service.chat.context.catalog import (
    ModelContextCatalog,
    ModelContextSpec,
    get_model_context_catalog,
)
from src.service.chat.context.hierarchical_summarizer import HierarchicalSummarizer

__all__ = [
    "TOOL_OUTPUT_ELIDED",
    "ContextShrinkOutcome",
    "ModelContextCatalog",
    "ModelContextSpec",
    "get_model_context_catalog",
    "ContextBudgetInput",
    "ContextBudgetReport",
    "ContextBudgeter",
    "ContextOverflowError",
    "truncate_tool_output",
    "HierarchicalSummarizer",
]
