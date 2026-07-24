#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""read_image_chunks 工具结果的 image_url 块注入助手。

为什么需要本模块
----------------
``read_image_chunks`` 在 ``return_image_url=true`` 时，把图片以
``image_url: <公网URL>`` 文本行写进 ``role=tool`` 消息正文。但 OpenAI 多模态
协议要求图片以结构化 ``image_url`` 内容块传入，MLLM 不会自动去抓取纯文本里
的 URL。因此需要在 tool 消息之后**追加一条 user 消息**，把图片以
``{"type": "image_url", "image_url": {"url": ...}}`` 块显式喂给模型。

跨轮持久化与厂商 prompt 缓存
--------------------------
DeepSeek / Anthropic / OpenAI 的 prompt 缓存都缓存 messages 的**前缀**，命中
条件是前缀逐字节一致。若只在"同轮内存"里注入图片块，下一轮从 MongoDB 重放
历史时图片块消失，前缀变化 → 缓存 miss 且模型看不到图。因此**同轮注入**与
**历史重放注入**必须产出**逐字节相同**的 user 消息——本模块是两者的唯一构造
入口，保证一致 → 跨轮前缀稳定 → 命中厂商缓存价。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# 匹配 tool 消息正文里的 ``image_url: <url>`` 行（行首匹配，避免误伤 note 行）。
_IMAGE_URL_LINE = re.compile(r"^image_url:\s*(\S+)\s*$", re.MULTILINE)

# 跟随 user 消息的固定引导文本——任何改动都会破坏跨轮缓存命中，请勿随意修改。
_FOLLOWUP_TEXT = "（read_image_chunks 返回的图片，供你直接查看原图内容）"


def extract_image_urls(tool_content: str) -> List[str]:
    """从 read_image_chunks 的 tool 结果文本中抽取所有 ``image_url:`` 指向的 URL。

    仅匹配行首 ``image_url:`` 形式，note 行（``note: image_url 为...``）不会被
    误伤。返回顺序与原文出现顺序一致，去重保留首次出现。
    """
    if not tool_content:
        return []
    seen: List[str] = []
    for m in _IMAGE_URL_LINE.finditer(tool_content):
        url = m.group(1)
        if url and url not in seen:
            seen.append(url)
    return seen


def build_image_followup_message(urls: List[str]) -> Optional[Dict[str, Any]]:
    """构造紧随 tool 消息之后的 user 消息（多模态 image_url 块）。

    Args:
        urls: read_image_chunks 返回的公网图片 URL 列表。

    Returns:
        OpenAI 兼容的 user 消息 dict；``urls`` 为空时返回 ``None``（不注入）。

    输出对同一 ``urls`` 列表**确定性且稳定**——同轮与跨轮调用此函数得到完全
    相同的字节序列，是命中厂商 prompt 缓存的前提。
    """
    if not urls:
        return None
    content: List[Dict[str, Any]] = [{"type": "text", "text": _FOLLOWUP_TEXT}]
    for url in urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    return {"role": "user", "content": content}


__all__ = ["extract_image_urls", "build_image_followup_message"]
