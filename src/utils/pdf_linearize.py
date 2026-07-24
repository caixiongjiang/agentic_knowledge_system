#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : pdf_linearize.py
@Author  : caixiongjiang
@Date    : 2026/07/24
@Function:
    PDF 线性化（fast web view）工具。

    线性化后的 PDF 把交叉引用表（xref）与首页字节前置，配合 ``/raw`` 端点
    的 HTTP Range 支持，让 PDF.js 首屏只取首页字节即可渲染，滚动时按页
    按需取字节，避免整文件预下载。在上传时对 PDF 做一次线性化，存入对象
    存储的就是线性化版本，浏览器预览直接受益。

    底层使用 ``pikepdf``（libqpdf 的 Python 绑定）。任何异常都回退原始
    字节，绝不阻断上传流程；``pikepdf`` 未安装时同样回退。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from io import BytesIO
from typing import Optional

from loguru import logger


def is_pdf(bytes_head: bytes) -> bool:
    """根据文件头快速判断是否为 PDF。"""
    return bytes_head[:5] == b"%PDF-"


def linearize_pdf(file_bytes: bytes) -> bytes:
    """
    对 PDF 字节做线性化（fast web view），返回线性化后的字节。

    幂等：已经是线性化的 PDF 再次线性化无副作用。
    安全：任何异常（加密、损坏、pikepdf 未安装等）都回退原始字节，
    只记录 warning，不抛出，确保上传主流程不被阻断。

    Args:
        file_bytes: 原始 PDF 字节

    Returns:
        线性化后的字节；失败时返回原字节。
    """
    if not file_bytes or not is_pdf(file_bytes):
        return file_bytes

    try:
        import pikepdf
    except ImportError:
        logger.warning("pikepdf 未安装，跳过 PDF 线性化（预览仍可用，仅首屏非最优）")
        return file_bytes

    try:
        with pikepdf.open(BytesIO(file_bytes)) as pdf:
            out = BytesIO()
            # linearize=True 生成 fast web view 布局；兼容性保持原 PDF 版本
            pdf.save(out, linearize=True)
            linearized = out.getvalue()
        logger.debug(f"PDF 线性化完成: {len(file_bytes)} -> {len(linearized)} bytes")
        return linearized
    except Exception as e:  # noqa: BLE001
        logger.warning(f"PDF 线性化失败，回退原始字节: {e}")
        return file_bytes


def maybe_linearize(file_bytes: bytes, ext: Optional[str]) -> bytes:
    """
    按文件后缀按需线性化：仅对 ``.pdf`` 做线性化，其余原样返回。

    Args:
        file_bytes: 原始文件字节
        ext: 文件后缀（不含点，小写），如 ``"pdf"``、``"docx"``

    Returns:
        处理后的字节
    """
    if ext and ext.lower() == "pdf":
        return linearize_pdf(file_bytes)
    return file_bytes
