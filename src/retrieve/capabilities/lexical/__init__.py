"""
Lexical Capabilities — 字面与关键词检索原子能力

提供三种不依赖语义向量的检索能力:
- BM25Search:     BGE-M3 稀疏向量全文检索（Milvus）
- ExactMatch:     精确 / 前缀 / 正则字面匹配（MongoDB）
- BooleanSearch:  AND / OR / NOT 布尔逻辑检索（MongoDB）
"""

from src.retrieve.capabilities.lexical.bm25_search import BM25Search
from src.retrieve.capabilities.lexical.exact_match import ExactMatch
from src.retrieve.capabilities.lexical.boolean_search import BooleanSearch

__all__ = [
    "BM25Search",
    "ExactMatch",
    "BooleanSearch",
]
