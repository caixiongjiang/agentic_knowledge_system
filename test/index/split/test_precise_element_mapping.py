#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
精确 element_ids 溯源测试

验证 _map_chunks_to_elements 和 _flush_text_buffer 能正确地将
每个 chunk 映射到其实际包含文本的 element，而不是粗粒度地把所有
buffer 中的 element_ids 赋给每个 chunk。

测试场景：
  1. 单 element → 单 chunk（一对一）
  2. 单 element → 多 chunk（大文本被切分）
  3. 多 element → 单 chunk（短文本被合并）
  4. 多 element → 多 chunk（经典的 merge+split 场景）
  5. 边界 element 跨 chunk（overlap 导致边界 element 出现在相邻 chunk 中）

用法:
    uv run python test/index/split/test_precise_element_mapping.py
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.service.knowledge.components.text_splitter_service import TextSplitterService
from src.index.common_file_extract.splitter.models import SplitConfig, SplitMethod


def make_service(chunk_size: int = 500, chunk_overlap: int = 50) -> TextSplitterService:
    config = SplitConfig(
        split_method=SplitMethod.STRUCTURE_FIRST,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        enable_text_clean=False,
    )
    return TextSplitterService(config=config)


def test_map_chunks_to_elements_basic():
    """测试 _map_chunks_to_elements 的基础位置匹配"""
    service = make_service(chunk_size=200, chunk_overlap=0)

    texts = ["Hello world", "Foo bar baz", "End text"]
    element_ids = ["E1", "E2", "E3"]
    merged = "\n\n".join(texts)

    ranges = []
    offset = 0
    for i, t in enumerate(texts):
        ranges.append((offset, offset + len(t), element_ids[i]))
        offset += len(t) + 2

    split_texts = [merged]
    result = service._map_chunks_to_elements(merged, split_texts, ranges)

    assert len(result) == 1
    assert result[0] == ["E1", "E2", "E3"], f"全文应关联所有 element，实际: {result[0]}"
    print("[OK] test_map_chunks_to_elements_basic")


def test_single_element_single_chunk():
    """单 element → 单 chunk：文本不超过 chunk_size"""
    service = make_service(chunk_size=500)
    text_buffer = ["这是一段短文本，不会被切分。"]
    buffer_ids = ["E1"]
    chunks = service._flush_text_buffer(
        text_buffer, buffer_ids, 0, "section-1", "doc-1", "zh"
    )

    assert len(chunks) == 1
    assert chunks[0].element_ids == ["E1"], f"应精确关联 E1，实际: {chunks[0].element_ids}"
    assert chunks[0].split_seq == 0
    print("[OK] test_single_element_single_chunk")


def test_single_element_multi_chunks():
    """单 element → 多 chunk：大文本被切分成多个 chunk"""
    service = make_service(chunk_size=100, chunk_overlap=0)

    long_text = "这是第一段内容。" * 20
    text_buffer = [long_text]
    buffer_ids = ["E1"]

    chunks = service._flush_text_buffer(
        text_buffer, buffer_ids, 0, "section-1", "doc-1", "zh"
    )

    assert len(chunks) > 1, f"长文本应被切分成多个 chunk，实际只有 {len(chunks)} 个"
    for i, c in enumerate(chunks):
        assert c.element_ids == ["E1"], (
            f"Chunk {i} 应精确关联 E1，实际: {c.element_ids}"
        )
        assert c.split_seq == i
    print(f"[OK] test_single_element_multi_chunks: {len(chunks)} chunks")


def test_multi_elements_single_chunk():
    """多 element → 单 chunk：多个短文本合并后仍不超过 chunk_size"""
    service = make_service(chunk_size=500)

    text_buffer = ["第一段", "第二段", "第三段"]
    buffer_ids = ["E1", "E2", "E3"]

    chunks = service._flush_text_buffer(
        text_buffer, buffer_ids, 0, "section-1", "doc-1", "zh"
    )

    assert len(chunks) == 1, f"短文本合并后应为 1 个 chunk，实际: {len(chunks)}"
    assert chunks[0].element_ids == ["E1", "E2", "E3"], (
        f"合并 chunk 应关联所有 element，实际: {chunks[0].element_ids}"
    )
    print("[OK] test_multi_elements_single_chunk")


def test_multi_elements_multi_chunks_precise():
    """多 element → 多 chunk：经典 merge+split 场景，验证精确映射

    构造 3 个 element，每个约 300 字符，chunk_size=300。
    merged_text 总长约 900+，必然被切分成多个 chunk。
    关键验证：每个 chunk 的 element_ids 只包含实际贡献文本的 element。
    """
    service = make_service(chunk_size=300, chunk_overlap=0)

    e1_text = "甲方同意按照合同约定向乙方支付货款。" * 18
    e2_text = "乙方应在收到货款后三十日内完成交付。" * 18
    e3_text = "双方对合同条款的解释以中文版本为准。" * 18

    text_buffer = [e1_text, e2_text, e3_text]
    buffer_ids = ["E1", "E2", "E3"]

    chunks = service._flush_text_buffer(
        text_buffer, buffer_ids, 0, "section-1", "doc-1", "zh"
    )

    assert len(chunks) >= 2, f"应至少被切分为 2 个 chunk，实际: {len(chunks)}"

    for i, c in enumerate(chunks):
        assert len(c.element_ids) > 0, f"Chunk {i} 的 element_ids 不应为空"

    has_only_e1 = any(c.element_ids == ["E1"] for c in chunks)
    has_only_e3 = any(c.element_ids == ["E3"] for c in chunks)
    assert has_only_e1 or has_only_e3, (
        "至少应有一个 chunk 仅关联单个 element（证明精确映射生效），"
        f"实际: {[c.element_ids for c in chunks]}"
    )

    all_mapped = set()
    for c in chunks:
        all_mapped.update(c.element_ids)
    assert all_mapped == {"E1", "E2", "E3"}, (
        f"所有 element 应至少被一个 chunk 关联，实际: {all_mapped}"
    )

    print(f"[OK] test_multi_elements_multi_chunks_precise: {len(chunks)} chunks")
    for i, c in enumerate(chunks):
        text_preview = (c.get_text_content() or "")[:40]
        print(f"    Chunk {i} (split_seq={c.split_seq}): "
              f"element_ids={c.element_ids}, text='{text_preview}...'")


def test_overlap_boundary_element():
    """overlap 场景：边界 element 可能同时出现在相邻 chunk 中

    构造 2 个 element，总长度超过 chunk_size，有 overlap。
    验证精确映射在 overlap 场景下仍然工作。
    """
    service = make_service(chunk_size=200, chunk_overlap=50)

    e1_text = "人工智能在医疗领域的应用日益广泛。" * 8
    e2_text = "深度学习算法在图像识别中表现出色。" * 8

    text_buffer = [e1_text, e2_text]
    buffer_ids = ["E1", "E2"]

    chunks = service._flush_text_buffer(
        text_buffer, buffer_ids, 0, "section-1", "doc-1", "zh"
    )

    assert len(chunks) >= 2, f"应至少被切分为 2 个 chunk，实际: {len(chunks)}"

    has_e1 = [i for i, c in enumerate(chunks) if "E1" in c.element_ids]
    has_e2 = [i for i, c in enumerate(chunks) if "E2" in c.element_ids]
    assert len(has_e1) >= 1, "E1 应至少出现在一个 chunk 中"
    assert len(has_e2) >= 1, "E2 应至少出现在一个 chunk 中"

    print(f"[OK] test_overlap_boundary_element: {len(chunks)} chunks")
    for i, c in enumerate(chunks):
        print(f"    Chunk {i}: element_ids={c.element_ids}")


def test_no_coarse_fallback():
    """验证不再出现粗粒度回退：每个 chunk 不会无差别地拿到所有 element_ids

    构造 5 个较长的 element，chunk_size 较小，必然产生多个 chunk。
    每个 chunk 的 element_ids 长度不应等于 5（不应回退到全部）。
    """
    service = make_service(chunk_size=200, chunk_overlap=0)

    texts = [
        "第一节内容讲述了项目背景和研究动机。" * 6,
        "第二节内容讨论了技术方案和架构设计。" * 6,
        "第三节内容阐述了实施计划和时间安排。" * 6,
        "第四节内容说明了预期效果和验收标准。" * 6,
        "第五节内容总结了全文要点和未来展望。" * 6,
    ]
    buffer_ids = [f"E{i+1}" for i in range(5)]

    chunks = service._flush_text_buffer(
        texts, buffer_ids, 0, "section-1", "doc-1", "zh"
    )

    assert len(chunks) >= 2, f"应至少被切分为 2 个 chunk，实际: {len(chunks)}"

    coarse_count = sum(1 for c in chunks if len(c.element_ids) == 5)
    assert coarse_count == 0, (
        f"不应出现粗粒度回退（{coarse_count}/{len(chunks)} 个 chunk 关联了全部 5 个 element）"
    )

    print(f"[OK] test_no_coarse_fallback: {len(chunks)} chunks")
    for i, c in enumerate(chunks):
        print(f"    Chunk {i}: element_ids={c.element_ids}")


def test_split_seq_correctness():
    """验证 split_seq 在精确映射下仍然正确递增"""
    service = make_service(chunk_size=100, chunk_overlap=0)

    long_text = "这是一段用于验证序号的文本。" * 30
    text_buffer = [long_text]
    buffer_ids = ["E1"]

    chunks = service._flush_text_buffer(
        text_buffer, buffer_ids, 0, "section-1", "doc-1", "zh"
    )

    for i, c in enumerate(chunks):
        assert c.split_seq == i, f"Chunk {i} 的 split_seq 应为 {i}，实际: {c.split_seq}"

    print(f"[OK] test_split_seq_correctness: {len(chunks)} chunks, "
          f"split_seq = {[c.split_seq for c in chunks]}")


def main() -> None:
    print("=" * 60)
    print("精确 element_ids 溯源测试")
    print("=" * 60)
    print()

    tests = [
        test_map_chunks_to_elements_basic,
        test_single_element_single_chunk,
        test_single_element_multi_chunks,
        test_multi_elements_single_chunk,
        test_multi_elements_multi_chunks_precise,
        test_overlap_boundary_element,
        test_no_coarse_fallback,
        test_split_seq_correctness,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
        print()

    print("=" * 60)
    print(f"结果: {passed} 通过, {failed} 失败 / 共 {len(tests)} 个测试")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
