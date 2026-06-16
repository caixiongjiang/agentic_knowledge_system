#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""工具运行时上下文（避免 kit ↔ handler 循环依赖）。"""

from __future__ import annotations

import contextvars

_current_tc_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_current_tc_id", default="",
)


def get_current_tool_call_id() -> str:
    return _current_tc_id_var.get()


def set_current_tool_call_id(tool_call_id: str) -> None:
    _current_tc_id_var.set(tool_call_id)
