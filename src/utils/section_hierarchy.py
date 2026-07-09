#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : section_hierarchy.py
@Function:
    从 section 标题编号推断真实层级树。

    背景：MinerU 把所有标题都标成同一 text_level（扁平），无法反映真实层级。
    但标题文本本身通常带编号（"1"、"1.1"、"2.6.1.Network structures"），层级
    信息藏在编号里。本模块解析编号、建树，产出每个 section 的 parent_section_id
    与修正后的 level，供 split 阶段持久化、section_summary 阶段做自底向上 rollup。

    判定规则：
    - 编号正则 ^(\\d+(?:\\.\\d+)*)[.\\s]*?(.*)$ 提取前导点分编号
    - path = [1, 6, 1] 表示 "1.6.1" 下的三级标题
    - 按文档顺序维护祖先栈，parent = 栈中 path 为当前 path 真前缀的最近祖先
    - 无编号标题（Abstract / References / 参考文献）→ path=[]，parent=None，
      不压栈，不干扰编号栈
    - 缺失中间标题（如出现 2.1 但无 2）→ 找不到 [2] 祖先，parent=None，level 仍为 2

    纯函数，无 IO / 无 DB 依赖，可在 split 与 section_summary 两侧复用。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# 前导点分编号：1 / 1.1 / 2.6.1 / 1.1.2 等，后接可选分隔符（. 或空白）
_NUMBERING_RE = re.compile(r"^(\d+(?:\.\d+)*)[.\s]*")


@dataclass
class HierarchyInfo:
    """单个 section 的层级推断结果。"""
    section_id: str
    parent_section_id: Optional[str] = None
    level: int = 1                      # 修正后的层级（1 起）
    numbering: Optional[str] = None     # 原始编号字符串，如 "2.6.1"；无编号为 None
    title_clean: str = ""               # 去掉前导编号后的标题文本
    path: Tuple[int, ...] = field(default_factory=tuple)   # 编号数字序列，如 (2, 6, 1)
    order: int = 0                      # 文档内顺序（0 起）


def parse_numbering(title: str) -> Tuple[Optional[str], Tuple[int, ...], str]:
    """
    解析标题前导编号。

    Args:
        title: 原始标题文本，如 "2.6.1.Network structures" / "1 Introduction" / "Abstract"

    Returns:
        (numbering_str, path_tuple, title_clean)
        - numbering_str: "2.6.1" 或 None
        - path_tuple: (2, 6, 1) 或 ()
        - title_clean: 去掉编号与紧随分隔符后的标题，如 "Network structures"
    """
    if not title:
        return None, (), ""
    text = title.strip()
    m = _NUMBERING_RE.match(text)
    if not m:
        return None, (), text
    numbering_str = m.group(1)
    path = tuple(int(p) for p in numbering_str.split("."))
    # 去掉编号 + 紧随的分隔符（正则已吞掉尾部的 . 或空白）
    title_clean = text[m.end():].strip()
    return numbering_str, path, title_clean


def infer_section_hierarchy(
    sections_in_order: List[Dict[str, Any]],
    id_field: str = "section_id",
    title_field: str = "title",
    fallback_level_field: str = "level",
) -> Dict[str, HierarchyInfo]:
    """
    从按文档顺序排列的 section 列表推断层级树。

    Args:
        sections_in_order: 按文档顺序的 section dict 列表，每项至少含 id_field 与
            title_field；可选 fallback_level_field（MinerU 的 text_level，仅作
            无编号时的兜底 level 参考）。
        id_field: section id 字段名。
        title_field: 标题字段名。
        fallback_level_field: 无编号时取该字段作为 level 兜底（默认 1）。

    Returns:
        {section_id → HierarchyInfo}。无 id 的项跳过。

    算法：
        维护祖先栈 [(path, section_id)]，按顺序遍历：
        1. 解析当前 title → (numbering, path, title_clean)
        2. 弹栈直到栈顶 path 是当前 path 的真前缀（即栈顶是当前的直接祖先）
        3. parent_section_id = 栈顶 id（无则 None）
        4. level = len(path) if path else (fallback or 1)
        5. 若 path 非空：压栈（无编号 section 不压栈，不干扰编号栈）
    """
    result: Dict[str, HierarchyInfo] = {}
    # 栈元素：(path_tuple, section_id)
    stack: List[Tuple[Tuple[int, ...], str]] = []

    for idx, s in enumerate(sections_in_order):
        section_id = s.get(id_field)
        if not section_id:
            continue
        title = s.get(title_field) or ""
        numbering, path, title_clean = parse_numbering(title)

        # 弹栈：栈顶 path 必须是当前 path 的真前缀才是祖先
        # 真前缀：长度 < 当前 path，且 stack_top[:len(stack_top)] == path[:len(stack_top)]
        # 无编号 section（path=()）不参与弹栈，避免清空编号栈影响后续 section
        if path:
            while stack:
                top_path, _ = stack[-1]
                if len(top_path) < len(path) and path[:len(top_path)] == top_path:
                    break
                stack.pop()

        parent_section_id = stack[-1][1] if stack else None

        if path:
            level = len(path)
            stack.append((path, section_id))
        else:
            # 无编号：用 fallback level 兜底，不压栈
            fb = s.get(fallback_level_field)
            level = int(fb) if isinstance(fb, (int, float)) and fb >= 1 else 1

        result[section_id] = HierarchyInfo(
            section_id=section_id,
            parent_section_id=parent_section_id,
            level=level,
            numbering=numbering,
            title_clean=title_clean,
            path=path,
            order=idx,
        )

    return result


def build_children_map(
    hierarchy: Dict[str, HierarchyInfo],
) -> Dict[str, List[str]]:
    """
    从 HierarchyInfo 表构造 {parent_section_id → [child_section_id, ...]}。
    根级 section（parent=None）不出现在结果的 key 里。

    Returns:
        {parent_id → [child_id...]}，按文档顺序。
    """
    children: Dict[str, List[str]] = {}
    # 按 order 排序保证子节顺序
    for info in sorted(hierarchy.values(), key=lambda h: h.order):
        if info.parent_section_id:
            children.setdefault(info.parent_section_id, []).append(info.section_id)
    return children
