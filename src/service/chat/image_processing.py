#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""图片压缩与 data URL 工具（Chat read_image_chunks 使用）。"""

from __future__ import annotations

import base64
import io
from typing import Tuple

from PIL import Image

DEFAULT_MAX_IMAGE_LONG_EDGE = 512


def resize_image_bytes(
    image_bytes: bytes,
    max_long_edge: int = DEFAULT_MAX_IMAGE_LONG_EDGE,
) -> Tuple[bytes, str]:
    """
    按比例缩放图片：长边不超过 ``max_long_edge``；若原图长边已 <= 阈值则不变。

    Returns:
        (压缩后的 bytes, MIME 类型)
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        width, height = img.size
        long_edge = max(width, height)
        if long_edge > max_long_edge:
            scale = max_long_edge / long_edge
            new_size = (
                max(1, int(width * scale)),
                max(1, int(height * scale)),
            )
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85, optimize=True)
        return buffer.getvalue(), "image/jpeg"


def bytes_to_data_url(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """将图片 bytes 转为 OpenAI 兼容的 data URL。"""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
