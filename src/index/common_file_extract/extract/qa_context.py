#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : qa_context.py
@Function:
    Atomic QA 抽取的上下文构造层（v1.1 section 级）。

    对应 section_context.py 的角色：把 Service 层从 DB 读到的原始文档
    转成 extract 层用的内存聚合体，并组装 LLM 输入文本。纯函数，
    无 LLM / 无 DB 依赖。

    - build_qa_sections_from_db_data：从 section_data + chunk_data 构造
      QASection 列表（chunk 按 section_data.chunk_id_list 顺序）
    - build_qa_batch_text：将一个 section 的一批 chunk（≤ N 个）拼接为
      带 [Cn] 代号前缀的文本，返回 (batch_text, chunk_code_map)。
      chunk_code_map = {"C1": chunk_id, ...}，供 qa_summarizer 后处理
      把 LLM 输出的 [Cn] 占位符替换为真实 chunk_id，实现 chunk 级溯源。
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Dict, List, Tuple

from loguru import logger

from src.index.common_file_extract.extract.models import QAChunk, QASection


def build_qa_sections_from_db_data(
    section_docs: List[Dict[str, Any]],
    chunk_docs: List[Dict[str, Any]],
) -> List[QASection]:
    """
    从 DB 读到的 section_data + chunk_data 构造 QASection 列表。

    不访问任何数据库；输入由 Service 层从 DB 读好后传入（混合取数：
    section/chunk 已稳定落盘，file_summary 走消息体）。

    Args:
        section_docs: section_data 文档列表，每项含
            section_id / text（section 标题或正文）/ chunk_id_list（有序）
        chunk_docs: chunk_data 文档列表，每项含
            chunk_id / search_text（检索/正文文本）/ type

    Returns:
        QASection 列表（仅保留有 chunk 的 section；顺序与 section_docs 一致）
    """
    chunk_map: Dict[str, Dict[str, Any]] = {
        c.get("chunk_id"): c for c in chunk_docs if c.get("chunk_id")
    }

    result: List[QASection] = []
    for s in section_docs:
        section_id = s.get("section_id")
        if not section_id:
            continue
        chunk_id_list = s.get("chunk_id_list") or []
        section_chunks: List[QAChunk] = []
        for cid in chunk_id_list:
            if not cid:
                continue
            c = chunk_map.get(cid)
            if c is None:
                continue
            text = (c.get("search_text") or "").strip()
            if not text:
                # 无正文（如纯图片 chunk 无 caption）跳过，避免喂空给 LLM
                continue
            section_chunks.append(QAChunk(
                chunk_id=cid,
                text=text,
                chunk_type=c.get("type") or "text",
            ))
        if not section_chunks:
            # 该 section 无可用 chunk 文本，跳过（不发起 LLM 调用）
            continue
        result.append(QASection(
            section_id=section_id,
            title=(s.get("text") or "").strip(),
            chunks=section_chunks,
        ))

    logger.info(
        f"TextAnalyzer: 从 DB 数据构造 QA 上下文 sections={len(result)}, "
        f"chunks={len(chunk_map)}"
    )
    return result


def build_qa_batch_text(
    section: QASection,
    start_index: int,
    batch_size: int,
) -> Tuple[str, Dict[str, str]]:
    """
    将 section 的一个 chunk 批次（[start_index, start_index+batch_size)）
    拼接为带 [Cn] 代号前缀的文本。

    代号从 C1 开始（每批本地编号，不跨批累加），便于 LLM 在 source_chunks
    里引用；chunk_code_map 记录 Cn → chunk_id 映射，供后处理替换。

    Args:
        section: QASection
        start_index: 起始 chunk 索引（含）
        batch_size: 本批 chunk 数量上限（N=chunk_batch_size）

    Returns:
        (batch_text, chunk_code_map)
        - batch_text：形如 "[C1]\\n<chunk1 文本>\\n\\n[C2]\\n<chunk2 文本>..."
        - chunk_code_map：{"C1": chunk_id, "C2": chunk_id, ...}
        若切片越界返回 ("", {})。
    """
    batch_chunks = section.chunks[start_index:start_index + batch_size]
    if not batch_chunks:
        return "", {}

    parts: List[str] = []
    chunk_code_map: Dict[str, str] = {}
    for i, qc in enumerate(batch_chunks, start=1):
        code = f"C{i}"
        chunk_code_map[code] = qc.chunk_id
        parts.append(f"[{code}]\n{qc.text}")

    batch_text = "\n\n".join(parts)
    return batch_text, chunk_code_map


def split_into_batches(
    total: int,
    batch_size: int,
) -> List[Tuple[int, int]]:
    """
    生成 (start_index, actual_batch_size) 批次列表，供分批抽取。

    Args:
        total: chunk 总数
        batch_size: 单批上限 N

    Returns:
        [(0, n0), (n0, n1), ...]
    """
    if total <= 0 or batch_size <= 0:
        return []
    batches: List[Tuple[int, int]] = []
    start = 0
    while start < total:
        n = min(batch_size, total - start)
        batches.append((start, n))
        start += n
    return batches
