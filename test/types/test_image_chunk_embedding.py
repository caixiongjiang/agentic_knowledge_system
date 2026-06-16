#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""图片 Chunk embedding 文本组装与 SplitResult 消息生成测试。"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.types.utils.image_chunk_text import (
    format_image_chunk_embed_text,
    format_image_chunk_placeholder,
    has_image_caption_or_footnote,
)
from src.types.utils.chunk_search_text import format_image_display_text
from src.types.models.split_result import ChunkInfo, ChunkType, SplitResult, SplitStatus


class TestImageChunkText:
    def test_has_caption_or_footnote(self):
        assert has_image_caption_or_footnote("图1", None) is True
        assert has_image_caption_or_footnote(None, "见注") is True
        assert has_image_caption_or_footnote("  ", "") is False

    def test_embed_text_with_caption(self):
        text = format_image_chunk_embed_text(
            image_caption="系统架构图",
            image_footnote="数据来源：内部文档",
        )
        assert "[图片]" not in text
        assert "系统架构图" in text
        assert "数据来源：内部文档" in text

    def test_embed_text_caption_only(self):
        text = format_image_chunk_embed_text(image_caption="图1", image_footnote=None)
        assert text == "图1"

    def test_embed_text_fallback_section_page(self):
        text = format_image_chunk_embed_text(
            section_title="3.2 系统架构",
            page_index=11,
        )
        assert text == "3.2 系统架构 page 12"

    def test_placeholder_format(self):
        text = format_image_chunk_placeholder(image_caption=None, image_footnote=None)
        assert text == "[图片]\n标题：无\n脚注：无"

    def test_display_text_has_wrapper(self):
        text = format_image_display_text(image_caption="图1", image_footnote="注1")
        assert text.startswith("[图片]")


class TestSplitResultImageEmbedding:
    def _image_chunk(
        self,
        caption=None,
        footnote=None,
        page_index=2,
        section_id="section-1",
    ) -> ChunkInfo:
        return ChunkInfo(
            chunk_id="chunk-img-1",
            chunk_type=ChunkType.IMAGE,
            section_id=section_id,
            page_index=page_index,
            image_caption=caption,
            image_footnote=footnote,
        )

    def test_embedding_messages_use_search_text(self):
        chunk = self._image_chunk(caption="图1")
        chunk.vector_text = chunk.build_image_embedding_text(section_title="引言")
        chunk.display_text = chunk.build_image_display_text(section_title="引言")
        split = SplitResult(
            user_id="u1",
            file_id="f1",
            filename="test.pdf",
            status=SplitStatus.SUCCESS,
            chunks=[chunk],
        )
        messages = split.get_embedding_messages()
        assert len(messages) == 1
        assert messages[0]["text"] == chunk.vector_text
        assert "[图片]" not in messages[0]["text"]
        assert messages[0]["collection_type"] == "chunk"

    def test_enhanced_embedding_messages_for_image(self):
        chunk = self._image_chunk()
        embed = chunk.build_image_embedding_text(section_title="第二章")
        chunk.vector_text = embed
        chunk.enhanced_vector_text = f"第二章\n{embed}"
        split = SplitResult(
            user_id="u1",
            file_id="f1",
            filename="test.pdf",
            status=SplitStatus.SUCCESS,
            chunks=[chunk],
        )
        messages = split.get_enhanced_chunk_embedding_messages()
        assert len(messages) == 1
        assert messages[0]["text"].startswith("第二章\n")
        assert "[图片]" not in messages[0]["text"]

    def test_mongodb_dict_splits_search_and_display(self):
        chunk = self._image_chunk(caption="图1", footnote="注1")
        chunk.vector_text = chunk.build_image_embedding_text(section_title="第一章")
        chunk.display_text = chunk.build_image_display_text(section_title="第一章")
        chunk.enhanced_vector_text = f"第一章\n{chunk.vector_text}"
        chunk.enhanced_display_text = f"第一章\n{chunk.display_text}"
        mongo = chunk.to_mongodb_dict()
        assert mongo["search_text"] == chunk.vector_text
        text_meta = mongo["text_meta"]
        assert text_meta.get("image_caption") == "图1"
        assert text_meta.get("image_footnote") == "注1"
        assert "embedding_text" not in mongo

    def test_mongodb_dict_text_chunk_has_enhanced_text(self):
        chunk = ChunkInfo(
            chunk_id="chunk-txt-1",
            chunk_type=ChunkType.TEXT,
            section_id="section-1",
            page_index=0,
            content={"original": {"content": "正文内容"}, "translations": []},
        )
        chunk.vector_text = "正文内容"
        chunk.display_text = "正文内容"
        chunk.enhanced_vector_text = "第一章\n正文内容"
        chunk.enhanced_display_text = "第一章\n正文内容"
        mongo = chunk.to_mongodb_dict()
        assert mongo["search_text"] == "正文内容"
        assert mongo["text"] == "正文内容"
        assert mongo["enhanced_text"] == "第一章\n正文内容"
        assert "embedding_text" not in mongo


def run_tests():
    test_classes = [TestImageChunkText(), TestSplitResultImageEmbedding()]
    passed = failed = 0
    for cls in test_classes:
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
    ok = run_tests()
    sys.exit(0 if ok else 1)
