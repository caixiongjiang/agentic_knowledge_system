#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
read_image_chunks 工具专用 Prompt（带 question 的按需理解）

与 background 阶段提示词分离：
- **有 question**：多张图片 + 同一问题 → **一次 VLM 调用**综合回答。
- **无 question**：每张图单独走 background 描述（一图一描述，与 Pipeline 一致）。

当前 Chat 工具路径 **不做 MongoDB / Milvus 持久化**；结果仅固化在对话历史的 tool 消息中。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

READ_IMAGE_CHUNKS_QA_SYSTEM = """\
你是一名文档图片问答助手。用户会提供**一张或多张**图片和一个具体问题。

要求：
1. **综合所有图片**回答用户问题；若信息分布在不同图中，请合并说明。
2. **只回答用户问题**，不要输出与问题无关的泛泛描述。
3. 以图片可见内容为准；可结合每张图的 caption / 章节上下文，但不得编造。
4. 若所有图片仍无法回答该问题，明确说明“从图中无法判断”，并简要说明原因。
5. 使用简洁中文，优先给直接答案，必要时补充 1–3 句依据。
"""

READ_IMAGE_CHUNKS_QA_USER = """\
用户问题：{question}

以下共 {image_count} 张图片，请综合全部图片回答上述问题。

{images_block}
请基于以上全部图片综合回答。"""

_IMAGE_BLOCK_TEMPLATE = """\
--- 图片 {index} (chunk_id={chunk_id}) ---
{meta_block}"""


@dataclass(frozen=True)
class ImagePromptMeta:
    chunk_id: str
    image_caption: Optional[str] = None
    image_footnote: Optional[str] = None
    section_title: Optional[str] = None
    page_index: Optional[int] = None


def _format_image_meta_block(
    *,
    image_caption: Optional[str] = None,
    image_footnote: Optional[str] = None,
    section_title: Optional[str] = None,
    page_index: Optional[int] = None,
) -> str:
    lines: List[str] = []
    if image_caption:
        lines.append(f"标题：{image_caption}")
    if image_footnote:
        lines.append(f"脚注：{image_footnote}")
    if section_title:
        lines.append(f"所在章节：{section_title}")
    if page_index is not None:
        lines.append(f"页码：{page_index + 1}")
    return "\n".join(lines) if lines else "(无额外元数据)"


def build_qa_user_prompt(
    question: str,
    images: List[ImagePromptMeta],
) -> str:
    blocks: List[str] = []
    for index, img in enumerate(images, start=1):
        blocks.append(
            _IMAGE_BLOCK_TEMPLATE.format(
                index=index,
                chunk_id=img.chunk_id,
                meta_block=_format_image_meta_block(
                    image_caption=img.image_caption,
                    image_footnote=img.image_footnote,
                    section_title=img.section_title,
                    page_index=img.page_index,
                ),
            ),
        )
    return READ_IMAGE_CHUNKS_QA_USER.format(
        question=question.strip(),
        image_count=len(images),
        images_block="\n\n".join(blocks),
    )
