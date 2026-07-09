#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : language_detector.py
@Function:
    轻量级语言检测（基于 Unicode 脚本统计，无第三方依赖）。

    用途：parse 阶段从 MinerU 产出的全文文本检测文档主语言，填入
    ParseResult.document_language，沿 ParseEndMessage → split → SplitEndMessage
    → section_summary 链路透传，供 Milvus 检索结果与 agent 执行做语言判断。

    覆盖常见脚本：
    - CJK 统一表意文字 + 平假名/片假名 → ja（有假名）/ zh（无假名）
    - 谚文 → ko
    - 西里尔 → ru
    - 阿拉伯 → ar
    - 天城文 → hi
    - 泰文 → th
    - 其余（含拉丁为主） → en

    局限：纯脚本统计，不区分同脚本下的语种（如英文 vs 德文 vs 法文均归 en）。
    对知识库场景（区分中/英/日/韩等）足够；需要细粒度语种时再引入 langdetect。

    判定策略（v2，占比主导）：
    - 先统计各脚本字符数；无可识别脚本 → fallback
    - 日文：假名 >= 3 且占总脚本字符 >= 5% → ja（避免个别假名误判）
    - 其余：取计数最大的主导脚本（CJK→zh, 谚文→ko, 西里尔→ru, 阿拉伯→ar,
      天城文→hi, 泰文→th, 拉丁→en）
    - 不再用「存在即命中」，避免英文文本里混入少量汉字被误判 zh
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional


def detect_language(text: Optional[str], fallback: str = "en") -> str:
    """
    基于 Unicode 脚本统计检测文本主语言。

    Args:
        text: 待检测文本（通常为文档全文或前若干字符）
        fallback: 无法判断时的回退语言码

    Returns:
        BCP-47 风格的语言码（zh / en / ja / ko / ru / ar / hi / th / fallback）
    """
    if not text:
        return fallback

    # 脚本字符计数
    cjk = 0          # CJK 统一表意文字
    hiragana = 0     # 平假名
    katakana = 0     # 片假名
    hangul = 0       # 谚文
    cyrillic = 0     # 西里尔
    arabic = 0       # 阿拉伯
    devanagari = 0   # 天城文
    thai = 0         # 泰文
    latin = 0        # 拉丁

    for ch in text:
        cp = ord(ch)
        # 跳过空白与常见标点/控制符，避免噪声
        if ch.isspace() or cp < 0x80 and not ch.isalpha():
            continue

        # CJK 统一表意文字（含扩展A）
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
            cjk += 1
        elif 0x3040 <= cp <= 0x309F:        # 平假名
            hiragana += 1
        elif 0x30A0 <= cp <= 0x30FF:        # 片假名
            katakana += 1
        elif 0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF:  # 谚文
            hangul += 1
        elif 0x0400 <= cp <= 0x04FF:        # 西里尔
            cyrillic += 1
        elif 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F:  # 阿拉伯
            arabic += 1
        elif 0x0900 <= cp <= 0x097F:        # 天城文
            devanagari += 1
        elif 0x0E00 <= cp <= 0x0E7F:        # 泰文
            thai += 1
        elif 0x0041 <= cp <= 0x005A or 0x0061 <= cp <= 0x007A or 0x00C0 <= cp <= 0x024F:
            latin += 1
        # 其余字符忽略

    total = (
        cjk + hiragana + katakana + hangul
        + cyrillic + arabic + devanagari + thai + latin
    )
    if total == 0:
        return fallback

    # 日文：假名是日文独有强信号，但要求非平凡数量，避免英文/中文文本里混入
    # 个别假名（如引用日文术语）被误判为 ja。阈值：假名 >= 3 且占总脚本字符 >= 5%。
    kana = hiragana + katakana
    if kana >= 3 and (kana / total) >= 0.05:
        return "ja"

    # 其余脚本：取计数最大的主导脚本（CJK 归 zh，ja 已在上面分流）
    # 用「主导脚本」而非「存在即命中」，避免英文文本里混入少量汉字被误判 zh。
    candidates = [
        ("zh", cjk),
        ("ko", hangul),
        ("ru", cyrillic),
        ("ar", arabic),
        ("hi", devanagari),
        ("th", thai),
        ("en", latin),
    ]
    best_lang, best_count = fallback, 0
    for lang, cnt in candidates:
        if cnt > best_count:
            best_lang, best_count = lang, cnt

    # total > 0 保证至少有一个脚本 cnt > 0，best_count 必 > 0
    return best_lang
