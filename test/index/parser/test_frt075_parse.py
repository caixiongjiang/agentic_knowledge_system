#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
测试 FRT075-33F.pdf 的解析结果

重点检查:
- 解析出的元素类型分布（text/image/table）
- text 类型元素中 text_level > 0 的标题分布
- 是否存在 text 为空的元素（这会导致后续 Chunk 空文本）
- 结构化内容的完整性

用法（从项目根目录执行）:
    uv run python test/index/parser/test_frt075_parse.py
"""
import sys
import json
import asyncio
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

from src.client.mineru import Mineru2Client
from src.index.common_file_extract.parser.pdf_parser import PDFParser
from src.utils.config_manager import get_config_manager


TEST_PDF = "tmp_files/pdf/FRT075-33F.pdf"
OUTPUT_DIR = "tmp_results/parser/frt075_test"


def setup_logger() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <level>{message}</level>",
        level="DEBUG"
    )


def create_pdf_parser() -> PDFParser:
    config = get_config_manager()
    mineru_config = {
        "api_url": config.get("mineru.api_url", "http://localhost:18000"),
        "timeout": config.get("mineru.timeout", 300),
    }
    client = Mineru2Client(mineru_config=mineru_config)
    return PDFParser(
        mineru_client=client,
        max_pages_per_request=config.get("mineru.max_pages_per_request", 4),
        max_concurrent_requests=config.get("mineru.max_concurrent_requests", 5),
    )


def analyze_parse_result(result: dict) -> None:
    """深度分析解析结果，重点排查空文本问题"""

    total_pages = result.get("total_pages", 0)
    root_pages = result.get("struct_content", {}).get("root", [])

    logger.info(f"总页数: {total_pages}")
    logger.info(f"struct_content.root 页数: {len(root_pages)}")

    type_counts: dict[str, int] = {}
    text_level_counts: dict[int, int] = {}
    empty_text_elements: list[dict] = []
    all_elements: list[dict] = []
    total_elements = 0

    for page in root_pages:
        page_idx = page.get("page_idx", -1)
        page_info = page.get("page_info", [])

        for elem in page_info:
            total_elements += 1
            elem_type = elem.get("type", "unknown")
            type_counts[elem_type] = type_counts.get(elem_type, 0) + 1

            elem_summary = {
                "page": page_idx,
                "type": elem_type,
                "element_index": elem.get("element_index"),
            }

            if elem_type == "text":
                text = elem.get("text", "")
                text_level = elem.get("text_level", 0)

                if text_level and text_level > 0:
                    text_level_counts[text_level] = text_level_counts.get(text_level, 0) + 1

                elem_summary["text_level"] = text_level
                elem_summary["text_length"] = len(text) if text else 0
                elem_summary["text_preview"] = (text[:80] + "...") if text and len(text) > 80 else text

                if not text or not text.strip():
                    empty_text_elements.append(elem_summary)

            elif elem_type == "table":
                table_body = elem.get("table_body", "")
                elem_summary["table_body_length"] = len(table_body) if table_body else 0

            elif elem_type == "image":
                elem_summary["img_path"] = elem.get("img_path", "")

            all_elements.append(elem_summary)

    # ===== 输出统计 =====
    logger.info(f"\n{'=' * 70}")
    logger.info(f"解析统计")
    logger.info(f"{'=' * 70}")
    logger.info(f"总元素数: {total_elements}")

    logger.info(f"\n元素类型分布:")
    for t, c in sorted(type_counts.items()):
        logger.info(f"  {t}: {c}")

    if text_level_counts:
        logger.info(f"\n标题层级分布 (text_level > 0 → 会成为 Section):")
        for level, count in sorted(text_level_counts.items()):
            logger.info(f"  level {level}: {count}")

    # ===== 重点: 空文本元素 =====
    logger.info(f"\n{'=' * 70}")
    logger.info(f"空文本元素检查（会导致 Chunk/Section 空文本）")
    logger.info(f"{'=' * 70}")

    if empty_text_elements:
        logger.warning(f"发现 {len(empty_text_elements)} 个空文本元素:")
        for i, elem in enumerate(empty_text_elements, 1):
            logger.warning(
                f"  [{i}] page={elem['page']}, "
                f"element_index={elem['element_index']}, "
                f"text_level={elem.get('text_level')}, "
                f"text_length={elem['text_length']}"
            )
    else:
        logger.info("未发现空文本元素")

    # ===== 标题元素详情 =====
    section_elements = [
        e for e in all_elements
        if e["type"] == "text" and e.get("text_level") and e["text_level"] > 0
    ]

    if section_elements:
        logger.info(f"\n{'=' * 70}")
        logger.info(f"标题元素详情（共 {len(section_elements)} 个，将成为 Section）")
        logger.info(f"{'=' * 70}")
        for i, elem in enumerate(section_elements, 1):
            text_preview = elem.get("text_preview", "")
            is_empty = elem.get("text_length", 0) == 0
            flag = " [EMPTY]" if is_empty else ""
            logger.info(
                f"  [{i:2d}] page={elem['page']}, "
                f"level={elem['text_level']}, "
                f"len={elem.get('text_length', 0)}{flag}, "
                f"text=\"{text_preview}\""
            )

    return all_elements, empty_text_elements


def save_results(result: dict, all_elements: list, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_json = output_dir / "FRT075-33F_raw_result.json"
    with open(raw_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"原始解析结果已保存: {raw_json}")

    elements_json = output_dir / "FRT075-33F_elements_summary.json"
    with open(elements_json, "w", encoding="utf-8") as f:
        json.dump(all_elements, f, ensure_ascii=False, indent=2)
    logger.info(f"元素摘要已保存: {elements_json}")

    md_file = output_dir / "FRT075-33F_content.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(result.get("content", ""))
    logger.info(f"Markdown 内容已保存: {md_file}")


async def main() -> None:
    setup_logger()

    pdf_path = Path(TEST_PDF)
    if not pdf_path.exists():
        logger.error(f"测试文件不存在: {pdf_path.absolute()}")
        sys.exit(1)

    logger.info(f"{'#' * 70}")
    logger.info(f"FRT075-33F.pdf 解析测试")
    logger.info(f"{'#' * 70}")
    logger.info(f"文件: {pdf_path}")

    try:
        parser = create_pdf_parser()

        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        logger.info(f"PDF 页数: {len(reader.pages)}")

        logger.info(f"\n开始解析...")
        import time
        start = time.time()

        result = await parser.parse(pdf_path)

        elapsed = time.time() - start
        logger.info(f"解析完成，耗时: {elapsed:.2f}s")

        all_elements, empty_elements = analyze_parse_result(result)

        output_dir = Path(OUTPUT_DIR)
        save_results(result, all_elements, output_dir)

        logger.info(f"\n{'#' * 70}")
        if empty_elements:
            logger.warning(
                f"结论: 存在 {len(empty_elements)} 个空文本元素，"
                f"这些元素进入切分流程后会产生空文本 Chunk/Section"
            )
        else:
            logger.info("结论: 所有 text 元素均有内容，解析结果正常")
        logger.info(f"{'#' * 70}")

    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
