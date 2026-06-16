#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : multimodal_image_understanding.py
@Author  : caixiongjiang
@Date    : 2026/1/6 11:01
@Function: 
    函数功能名称
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

"""
Background 阶段图片理解 Prompt（image_understand Worker / read_image_chunks 无 question 兜底）

用途：
- Pipeline 高级阶段 ``image_understand`` Worker 批量理解图片（后续实现）
- Chat 工具 ``read_image_chunks`` 在 **未传 question** 且 MongoDB 尚无
  ``vlm_description`` 时，用同一套背景描述提示词再调一次 VLM

注意：当前 Chat 工具路径 **不做持久化**；Worker 路径后续会 upsert ``text`` /
``vlm_description`` 并 re-embed Milvus（见开发清单 §2.4）。
"""

BACKGROUND_IMAGE_UNDERSTANDING_SYSTEM = """\
你是一名学术/技术文档的图片理解助手。请根据图片内容生成**客观、可检索**的中文描述。

要求：
1. 说明图片类型（折线图、柱状图、流程图、示意图、照片等）。
2. 提取图中可见的关键信息：标题、坐标轴含义、图例、主要趋势或结构关系。
3. 若提供了 caption / footnote / 章节上下文，可与之对照，但以图像可见内容为准。
4. 不要编造图中不存在的数据或结论。
5. 输出 3–8 句连贯段落，不要使用 Markdown 标题。
"""

BACKGROUND_IMAGE_UNDERSTANDING_USER = """\
请理解以下图片并输出描述。

{caption_block}{footnote_block}{section_block}{page_block}
请直接输出图片描述正文。"""


def build_background_user_prompt(
    *,
    image_caption: str | None = None,
    image_footnote: str | None = None,
    section_title: str | None = None,
    page_index: int | None = None,
) -> str:
    caption_block = f"图片标题：{image_caption}\n" if image_caption else ""
    footnote_block = f"图片脚注：{image_footnote}\n" if image_footnote else ""
    section_block = f"所在章节：{section_title}\n" if section_title else ""
    page_block = (
        f"页码：{page_index + 1}\n" if page_index is not None else ""
    )
    return BACKGROUND_IMAGE_UNDERSTANDING_USER.format(
        caption_block=caption_block,
        footnote_block=footnote_block,
        section_block=section_block,
        page_block=page_block,
    )
