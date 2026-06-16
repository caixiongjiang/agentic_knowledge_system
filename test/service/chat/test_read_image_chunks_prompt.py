#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""read_image_chunks 多图 QA prompt 单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def test_build_qa_user_prompt_multi_images() -> None:
    from src.prompts.tool.read_image_chunks import ImagePromptMeta, build_qa_user_prompt

    prompt = build_qa_user_prompt(
        "图 A 和图 B 的趋势是否一致？",
        [
            ImagePromptMeta(
                chunk_id="c1",
                image_caption="Fig.1",
                page_index=0,
            ),
            ImagePromptMeta(
                chunk_id="c2",
                image_caption="Fig.2",
                page_index=1,
            ),
        ],
    )
    assert "以下共 2 张图片" in prompt
    assert "chunk_id=c1" in prompt
    assert "chunk_id=c2" in prompt
    assert "Fig.1" in prompt
    assert "Fig.2" in prompt
    assert "综合" in prompt


if __name__ == "__main__":
    test_build_qa_user_prompt_multi_images()
    print("✅ read_image_chunks prompt tests passed")
