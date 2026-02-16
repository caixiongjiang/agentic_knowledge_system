#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
文档切分模块

提供文档切分的核心功能：
- 文本切分（多种算法）
- 表格切分（智能切分）
- 元素处理（转换为Chunk）
- 文本清洗

配置从 config/components.json 加载，通过 ComponentConfigManager 管理。
"""

from src.index.common_file_extract.splitter.models import SplitConfig, SplitMethod
from src.index.common_file_extract.splitter.text_splitter import TextSplitter
from src.index.common_file_extract.splitter.table_splitter import TableSplitter
from src.index.common_file_extract.splitter.element_processor import ElementProcessor
from src.index.common_file_extract.splitter.text_cleaner import TextCleaner

__all__ = [
    "SplitConfig",
    "SplitMethod",
    "TextSplitter",
    "TableSplitter",
    "ElementProcessor",
    "TextCleaner",
]
