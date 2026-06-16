#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""检索结果附带的 LLM 提示文案（无业务依赖，避免循环导入）。"""

from __future__ import annotations

# 语义检索结果附带的字面扫描提示（策略 D：与 grep_chunks 分工）
SEMANTIC_RECALL_LITERAL_HINT = (
    "提示：以上为语义相关的 Top 结果，未做全文逐字扫描。"
    "若需穷举某词的全部出现或确认精确数值，请先 `grep_chunks` 再 `read_chunks` 后作答。"
)

__all__ = ["SEMANTIC_RECALL_LITERAL_HINT"]
