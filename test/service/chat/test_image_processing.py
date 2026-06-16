#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""image_processing 单元测试。"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def _make_jpeg(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_resize_keeps_small_image_unchanged_size() -> None:
    from src.service.chat.image_processing import resize_image_bytes

    raw = _make_jpeg(400, 300)
    out, mime = resize_image_bytes(raw, max_long_edge=512)
    assert mime == "image/jpeg"
    with Image.open(io.BytesIO(out)) as img:
        assert img.size == (400, 300)


def test_resize_scales_long_edge_to_512() -> None:
    from src.service.chat.image_processing import resize_image_bytes

    raw = _make_jpeg(1024, 768)
    out, _ = resize_image_bytes(raw, max_long_edge=512)
    with Image.open(io.BytesIO(out)) as img:
        width, height = img.size
        assert max(width, height) == 512
        assert width == 512
        assert height == 384


def test_bytes_to_data_url_prefix() -> None:
    from src.service.chat.image_processing import bytes_to_data_url

    url = bytes_to_data_url(b"abc", "image/jpeg")
    assert url.startswith("data:image/jpeg;base64,")


if __name__ == "__main__":
    test_resize_keeps_small_image_unchanged_size()
    test_resize_scales_long_edge_to_512()
    test_bytes_to_data_url_prefix()
    print("✅ image_processing tests passed")
