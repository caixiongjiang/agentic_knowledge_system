#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
数据模型类型定义

提供系统中使用的各种数据模型。
"""

from src.types.models.parse_result import (
    ParseResult,
    ParseStatus,
    ElementInfo,
    ElementType
)

__all__ = [
    "ParseResult",
    "ParseStatus",
    "ElementInfo",
    "ElementType"
]
