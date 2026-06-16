#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""chunk_search_text 检索/展示文本分离测试。"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.types.utils.chunk_search_text import (
    derive_search_text_from_legacy,
    format_image_display_text,
    format_image_search_text,
    format_table_display_text,
    format_table_search_text,
    format_table_search_text_from_display,
    html_table_to_plain_rows,
    parse_table_display_text,
)
from src.types.models.split_result import ChunkInfo, ChunkType, SplitResult, SplitStatus


FIG8_CAPTION = (
    "Fig.8.Line plots of the change in accuracy(mIoU) in the "
    "distilltion loss weighting parameter ablation study."
)
TABLE_CAP = "Table 2 Deployment performance of different models in the model structure ablation study."
TABLE_BODY = (
    "<table><tr><td>Model</td><td>Params(M)</td></tr>"
    "<tr><td>FastSegFormer-E(ours)</td><td>5.01</td></tr></table>"
)
TABLE_FN = "w/o:without. w/: with."


class TestImageSearchDisplay:
    def test_search_text_no_wrapper(self):
        text = format_image_search_text("图1", "注1")
        assert "[图片]" not in text
        assert "图1" in text
        assert "注1" in text

    def test_display_text_has_wrapper(self):
        text = format_image_display_text("图1", "注1")
        assert text.startswith("[图片]")
        assert "标题：图1" in text
        assert "脚注：注1" in text


class TestTableSearchDisplay:
    def test_html_to_plain_rows(self):
        plain = html_table_to_plain_rows(TABLE_BODY)
        assert "Model | Params(M)" in plain
        assert "FastSegFormer-E(ours) | 5.01" in plain

    def test_display_keeps_prefixes(self):
        display = format_table_display_text(TABLE_BODY, TABLE_CAP, TABLE_FN)
        assert "table_caption:" in display
        assert "table_body:" in display
        assert "table_footnote:" in display

    def test_search_strips_prefixes(self):
        search = format_table_search_text(TABLE_BODY, TABLE_CAP, TABLE_FN)
        assert "table_caption:" not in search
        assert TABLE_CAP in search
        assert "FastSegFormer-E(ours)" in search
        assert TABLE_FN in search

    def test_search_from_display(self):
        display = format_table_display_text(TABLE_BODY, TABLE_CAP, TABLE_FN)
        search = format_table_search_text_from_display(display)
        assert TABLE_CAP in search
        assert "table_caption:" not in search

    def test_parse_display_roundtrip(self):
        display = format_table_display_text(TABLE_BODY, TABLE_CAP, TABLE_FN)
        cap, body, fn = parse_table_display_text(display)
        assert cap == TABLE_CAP
        assert "<table>" in body
        assert fn == TABLE_FN


class TestLegacyDerive:
    def test_image_legacy_wrapped(self):
        display = format_image_display_text(FIG8_CAPTION, None)
        search = derive_search_text_from_legacy(
            chunk_type="image",
            text=display,
            image_caption=FIG8_CAPTION,
        )
        assert "[图片]" not in search
        assert "Fig.8" in search


class TestSplitResultDualTrack:
    def test_image_mongodb_dict_split_fields(self):
        chunk = ChunkInfo(
            chunk_id="chunk-img-1",
            chunk_type=ChunkType.IMAGE,
            image_caption="图1",
            image_footnote="注1",
        )
        chunk.vector_text = chunk.build_image_embedding_text(section_title="引言")
        chunk.display_text = chunk.build_image_display_text(section_title="引言")
        chunk.enhanced_vector_text = f"引言\n{chunk.vector_text}"
        chunk.enhanced_display_text = f"引言\n{chunk.display_text}"

        mongo = chunk.to_mongodb_dict()
        assert mongo["search_text"] == chunk.vector_text
        text_meta = mongo["text_meta"]
        assert text_meta.get("image_caption") == "图1"
        assert text_meta.get("image_footnote") == "注1"
        assert mongo["enhanced_text"] == chunk.enhanced_display_text

    def test_table_mongodb_dict(self):
        display = format_table_display_text(TABLE_BODY, TABLE_CAP, TABLE_FN)
        chunk = ChunkInfo(
            chunk_id="chunk-tbl-1",
            chunk_type=ChunkType.TABLE,
            table_caption=TABLE_CAP,
            table_body=TABLE_BODY,
            table_footnote=TABLE_FN,
            content={"original": {"content": display}, "translations": []},
        )
        chunk.display_text = display
        chunk.vector_text = format_table_search_text_from_display(display)

        mongo = chunk.to_mongodb_dict()
        assert "table_caption:" not in mongo["search_text"]
        assert TABLE_CAP in mongo["search_text"]
        text_meta = mongo["text_meta"]
        assert text_meta.get("table_caption") == TABLE_CAP


def run_tests():
    classes = [
        TestImageSearchDisplay(),
        TestTableSearchDisplay(),
        TestLegacyDerive(),
        TestSplitResultDualTrack(),
    ]
    passed = failed = 0
    for cls in classes:
        for name in sorted(dir(cls)):
            if not name.startswith("test_"):
                continue
            try:
                getattr(cls, name)()
                print(f"✅ {cls.__class__.__name__}.{name}")
                passed += 1
            except Exception as exc:
                print(f"❌ {cls.__class__.__name__}.{name}: {exc}")
                failed += 1
    print(f"\n结果: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
