#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_numbering.py
@Function:
    Section 标题编号解析工具（无第三方依赖）。

    用途：MinerU 输出 heading 时不给可靠的 text_level（常常全部标为 1），
    导致 split 阶段把父/子 section 摊平成同级，父 section 挂不到 chunk。
    本工具从标题的编号前缀推断真实层级与父子关系，供 SectionSummaryService
    建 section 树 + 自下而上滚动摘要使用。

    支持的编号格式：
    - 阿拉伯数字点号：`2` / `2.1` / `2.1.3` / `2.1.3.4`
    - 章节前缀（level=1）：`Chapter 2` / `第 2 章` / `第二章` / `Section 2` / `第 5 节`
    - 附录：`Appendix A` / `A.1` / `A.1.2`（字母段 + 数字段）
    - 罗马数字：`I.` / `II.1` / `IV.2.3`（罗马数字段 + 数字段）

    不识别的标题（如「Introduction」这类无编号 heading）返回 None，
    调用方需自行走 fallback（挂根 or 挂最近祖先）。

    设计原则：
    - 段（segment）统一表示为字符串（如 "2" / "A" / "III"），
      用元组 (`segments`) 表达完整编号；父编号 = segments[:-1]
    - level = len(segments)
    - 段类型允许混合（如 `Appendix A.1` → ("A", "1")）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class NumberingInfo:
    """解析后的编号信息。

    Attributes:
        segments: 编号分段（如 ("2", "1", "3") 表示 2.1.3；
            ("A", "1") 表示 Appendix A.1；("III",) 表示罗马数字 III）
        raw: 从标题中匹配到的原始编号字符串（用于日志/调试）
        style: 编号风格，用于统计与调试
            - "arabic"     纯阿拉伯数字点号
            - "chapter"    Chapter/第X章/Section/第X节 等章节前缀
            - "appendix"   Appendix A / A.x 附录
            - "roman"      罗马数字（I. / II.1 等）
    """
    segments: Tuple[str, ...]
    raw: str
    style: str

    @property
    def level(self) -> int:
        """编号推断的层级深度（1=一级，2=二级，…）。"""
        return len(self.segments)

    def parent(self) -> Optional["NumberingInfo"]:
        """返回父编号；已是顶级则返回 None。"""
        if len(self.segments) <= 1:
            return None
        return NumberingInfo(
            segments=self.segments[:-1],
            raw=".".join(self.segments[:-1]),
            style=self.style,
        )

    def key(self) -> str:
        """规范化 key（供哈希/比较用），"2.1.3" / "A.1" / "III"。"""
        return ".".join(self.segments)


# ========== 内部正则 ==========

# 阿拉伯数字点号：2 / 2.1 / 2.1.3.4，允许结尾一个点号
# MinerU 常输出紧凑格式（如 "1.Introduction" / "2.6.1.Network structures"），
# 编号后**不一定**有空格；因此不要求 `\s+`，只用零宽前瞻确保编号结束后紧跟
# 空白或非数字/非点字符（避免把 "2024" 里的 "2" 误识别为编号）。
_ARABIC_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)*)\.?"
    r"(?=\s|[^\d.\s])"
)

# Chapter/Section 前缀（英文）
_CHAPTER_EN_RE = re.compile(
    r"^\s*(?:chapter|section|part)\s+(\d+)\b",
    re.IGNORECASE,
)

# 第 X 章 / 第 X 节 / 第 X 部分（中文，X 支持阿拉伯或中文数字）
_CHAPTER_ZH_RE = re.compile(
    r"^\s*第\s*([0-9零一二三四五六七八九十百千]+)\s*[章节篇部]"
)

# Appendix A / Appendix B（大写字母作附录标识）
_APPENDIX_LEAD_RE = re.compile(
    r"^\s*(?:appendix|附录)\s+([A-Z])\b(?:\.(\d+(?:\.\d+)*))?",
    re.IGNORECASE,
)

# 单独的字母.数字[.数字]* 起始（如 "A.1" / "B.2.3"），要求字母为大写单字符
_APPENDIX_SHORT_RE = re.compile(r"^\s*([A-Z])\.(\d+(?:\.\d+)*)\b")

# 罗马数字：I / II / III / IV / V / VI / VII / VIII / IX / X ... 后跟 . 或空白或数字段
# 只匹配大写 I-X 范围内的合法组合，避免把英文缩写误当罗马数字
_ROMAN_RE = re.compile(
    r"^\s*(M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3}))"
    r"(?:\.(\d+(?:\.\d+)*))?\.?\s+"
)

# 中文小写数字 → 阿拉伯（十位以内够用）
_ZH_NUM = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def _zh_to_int(s: str) -> Optional[int]:
    """把中文小数（≤ 99）转换为 int；不支持则返回 None。"""
    if s.isdigit():
        return int(s)
    if not s:
        return None
    # 处理 "十" / "十一" / "二十" / "二十一"
    if s == "十":
        return 10
    if s.startswith("十"):
        rest = s[1:]
        if len(rest) == 1 and rest in _ZH_NUM:
            return 10 + _ZH_NUM[rest]
    if "十" in s:
        parts = s.split("十")
        if len(parts) == 2:
            tens = _ZH_NUM.get(parts[0]) if parts[0] else 1
            ones = _ZH_NUM.get(parts[1]) if parts[1] else 0
            if tens is not None and ones is not None:
                return tens * 10 + ones
    if len(s) == 1 and s in _ZH_NUM:
        return _ZH_NUM[s]
    return None


def _roman_to_int(s: str) -> Optional[int]:
    """罗马数字（≤ MMMCMXCIX）转 int；不合法返回 None。"""
    if not s:
        return None
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(s.upper()):
        if ch not in values:
            return None
        v = values[ch]
        if v < prev:
            total -= v
        else:
            total += v
        prev = v
    # 验证：能否往回还原（避免 IIII 之类的伪罗马）
    return total if total > 0 else None


# ========== 主入口 ==========


def parse_numbering(title: Optional[str]) -> Optional[NumberingInfo]:
    """
    从 section 标题解析编号信息。

    Args:
        title: section 标题（可能含前后空白、markdown 前缀 `#` 等）

    Returns:
        NumberingInfo，无法识别时返回 None
    """
    if not title:
        return None

    # 去掉常见的 markdown 标题前缀 `##` 与前后空白
    text = title.lstrip("#").strip()
    if not text:
        return None

    # 1) 章节前缀（英文）：Chapter 2 / Section 5 → level=1
    m = _CHAPTER_EN_RE.match(text)
    if m:
        num = m.group(1)
        return NumberingInfo(
            segments=(num,),
            raw=m.group(0).strip(),
            style="chapter",
        )

    # 2) 章节前缀（中文）：第 2 章 / 第二章 / 第 5 节 / 第一部分
    m = _CHAPTER_ZH_RE.match(text)
    if m:
        n = _zh_to_int(m.group(1))
        if n is not None:
            return NumberingInfo(
                segments=(str(n),),
                raw=m.group(0).strip(),
                style="chapter",
            )

    # 3) Appendix A / Appendix A.1
    m = _APPENDIX_LEAD_RE.match(text)
    if m:
        letter = m.group(1).upper()
        tail = m.group(2)
        segs: Tuple[str, ...]
        if tail:
            segs = (letter,) + tuple(tail.split("."))
        else:
            segs = (letter,)
        return NumberingInfo(
            segments=segs,
            raw=m.group(0).strip(),
            style="appendix",
        )

    # 4) 单独的 "A.1" / "B.2.3"（附录短形式）
    m = _APPENDIX_SHORT_RE.match(text)
    if m:
        letter = m.group(1)
        tail = m.group(2)
        segs = (letter,) + tuple(tail.split("."))
        return NumberingInfo(
            segments=segs,
            raw=m.group(0).strip(),
            style="appendix",
        )

    # 5) 阿拉伯数字点号：2 / 2.1 / 2.1.3
    m = _ARABIC_RE.match(text)
    if m:
        num_str = m.group(1)
        segs = tuple(num_str.split("."))
        return NumberingInfo(
            segments=segs,
            raw=num_str,
            style="arabic",
        )

    # 6) 罗马数字：I. / II.1 / IV.2.3
    m = _ROMAN_RE.match(text)
    if m:
        roman = m.group(1)
        n = _roman_to_int(roman)
        if n is not None and n > 0:
            tail = m.group(2)
            if tail:
                segs = (str(n),) + tuple(tail.split("."))
            else:
                segs = (str(n),)
            return NumberingInfo(
                segments=segs,
                raw=m.group(0).strip(),
                style="roman",
            )

    return None
