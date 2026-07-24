#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : range_utils.py
@Author  : caixiongjiang
@Date    : 2026/07/24
@Function:
    HTTP ``Range`` 请求头解析工具。

    供对象存储流式端点（``/raw``、``/raw-image``）使用，把浏览器/PDF.js
    发来的 ``Range: bytes=...`` 头解析成 (offset, end, length)，用于向
    MinIO 发起区间读取并回包 ``206 Partial Content``。

    仅支持**单区间**请求（PDF.js / react-pdf 实际只发单区间）；
    多区间（multipart/byteranges）返回 ``None``，由端点退回整文件 200。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional, Tuple


def parse_range_header(
    range_header: Optional[str],
    total: int,
) -> Optional[Tuple[int, int, int]]:
    """
    解析 ``Range`` 请求头为 (offset, end_inclusive, length)。

    支持的三种语法（与 HTTP/1.1 一致）：
      - ``bytes=0-499``     → offset=0, end=499, length=500
      - ``bytes=500-``      → offset=500, end=total-1, length=total-500
      - ``bytes=-500``      → 最后 500 字节：offset=total-500, end=total-1

    Args:
        range_header: 原始 ``Range`` 头字符串，可能为 ``None``
        total: 对象总字节数（来自 ``stat_object``）

    Returns:
        - 解析成功：``(offset, end_inclusive, length)``
        - 无 Range 头 / 多区间 / 语法错误 / 区间不可满足：``None``

    Note:
        ``None`` 中的「不可满足」情况需由调用方自行判断是否回 ``416``。
        本函数不区分「无 Range 头」与「格式错误」，统一返回 ``None``；
        调用方根据是否传入非空 ``range_header`` 区分二者。
    """
    if not range_header or total <= 0:
        return None

    header = range_header.strip()
    if not header.startswith("bytes="):
        return None

    spec = header[len("bytes="):].strip()

    # 仅支持单区间；多区间交给端点退回整文件
    if "," in spec:
        return None

    if "-" not in spec:
        return None

    start_s, _, end_s = spec.partition("-")
    start_s = start_s.strip()
    end_s = end_s.strip()

    try:
        if start_s == "" and end_s == "":
            return None

        if start_s == "":
            # 后缀区间：最后 N 字节
            n = int(end_s)
            if n <= 0:
                return None
            offset = 0 if n >= total else total - n
            end = total - 1
        else:
            offset = int(start_s)
            if end_s == "":
                end = total - 1
            else:
                end = int(end_s)

            if offset < 0 or offset >= total:
                return None
            if end >= total:
                end = total - 1
            if end < offset:
                return None
    except (ValueError, TypeError):
        return None

    length = end - offset + 1
    if length <= 0:
        return None

    return offset, end, length


def is_range_satisfiable(range_header: Optional[str], total: int) -> bool:
    """
    判断一个非空 ``Range`` 头是否可被满足（用于区分 ``None`` 的两种语义）。

    当 ``range_header`` 非空但 ``parse_range_header`` 返回 ``None`` 时，
    若本函数返回 ``False``，则应回 ``416 Range Not Satisfiable``；
    若返回 ``True``（例如多区间），则端点退回整文件 ``200``。
    """
    if not range_header:
        return True
    header = range_header.strip()
    if not header.startswith("bytes="):
        return True
    spec = header[len("bytes="):].strip()
    # 多区间：不满足「单区间」语义，但 HTTP 上仍可退回 200
    if "," in spec:
        return True
    # 单区间：交给 parse_range_header 判定
    return parse_range_header(range_header, total) is not None
