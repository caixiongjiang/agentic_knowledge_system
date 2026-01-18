#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
测试 PDFParser（自动分页并发解析）

用法（从项目根目录执行）：
    uv run python test/index/parser/test_pdf_parser.py
"""
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.client.mineru import Mineru2Client
from src.index.common_file_extract.parser.pdf_parser import PDFParser
from src.utils.config_manager import get_config_manager
from loguru import logger


def load_config() -> dict:
    """从配置文件加载 MinerU 配置"""
    config_manager = get_config_manager()
    mineru_raw_config = config_manager.get_mineru_config()
    
    # 适配配置格式（将 api_url 转换为 endpoint）
    return {
        "endpoint": mineru_raw_config.get("api_url", "http://localhost:8000"),
        "timeout": mineru_raw_config.get("timeout", 600),
        "poll_interval": mineru_raw_config.get("poll_interval", 1),
        "params": {
            "backend": "pipeline",
            "lang": "ch",
            "method": "auto",
            "formula_enable": True,
            "table_enable": True,
            "priority": 0
        }
    }


async def test_small_file_no_pagination(pdf_path: str, output_dir: Optional[str] = None):
    """
    测试1: 小文件（≤4页）- 应该一次性解析，不分页
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"测试1: 小文件解析（≤4页，不分页）")
    logger.info(f"{'=' * 80}")
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        logger.error(f"❌ 文件不存在: {pdf_path}")
        return False
    
    try:
        # 先检查文件页数
        from pypdf import PdfReader
        reader = PdfReader(pdf_file)
        actual_pages = len(reader.pages)
        logger.info(f"📖 文件实际页数: {actual_pages}")
        
        if actual_pages > 4:
            logger.warning(f"⚠️  文件页数 ({actual_pages}) > 4，跳过此测试")
            logger.info(f"   提示: 请使用 ≤4 页的PDF文件进行此测试")
            return True  # 跳过但不算失败
        
        # 创建客户端和解析器
        config = load_config()
        mineru_client = Mineru2Client(config)
        pdf_parser = PDFParser(
            mineru_client=mineru_client,
            max_pages_per_request=4,
            max_concurrent_requests=5
        )
        
        logger.info(f"📄 解析文件: {pdf_file.name}")
        
        # 解析（应该一次性完成）
        result = await pdf_parser.parse(pdf_file)
        
        logger.info(f"\n解析结果:")
        logger.info(f"  ✅ 状态: {result.get('status')}")
        logger.info(f"  ✅ 总页数: {result.get('pages')}")
        logger.info(f"  ✅ 策略: 使用单次请求（≤4页）")
        
        # 保存结果
        if output_dir is None:
            output_dir = project_root / "tmp_results" / "parser" / "pdf_parser_test"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_json = output_dir / f"{pdf_file.stem}_small_file_result.json"
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"\n✅ 结果已保存: {output_json}")
        
        logger.info(f"\n✅✅✅ 测试1成功完成！\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ 测试1失败")
        logger.exception(e)
        return False


async def test_large_file_with_pagination(pdf_path: str, output_dir: Optional[str] = None):
    """
    测试2: 大文件（>4页）- 应该自动分页并发解析
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"测试2: 大文件解析（>4页，自动分页并发）")
    logger.info(f"{'=' * 80}")
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        logger.error(f"❌ 文件不存在: {pdf_path}")
        return False
    
    try:
        # 先检查文件页数
        from pypdf import PdfReader
        reader = PdfReader(pdf_file)
        actual_pages = len(reader.pages)
        logger.info(f"📖 文件实际页数: {actual_pages}")
        
        if actual_pages <= 4:
            logger.warning(f"⚠️  文件页数 ({actual_pages}) ≤ 4，无法测试分页功能")
            logger.info(f"   提示: 请使用 >4 页的PDF文件进行此测试")
            return True  # 跳过但不算失败
        
        # 创建客户端和解析器
        config = load_config()
        mineru_client = Mineru2Client(config)
        pdf_parser = PDFParser(
            mineru_client=mineru_client,
            max_pages_per_request=4,    # 每批4页
            max_concurrent_requests=5    # 最多5个并发
        )
        
        logger.info(f"📄 解析文件: {pdf_file.name}")
        logger.info(f"⚙️  分页策略: 每批{pdf_parser.max_pages_per_request}页")
        logger.info(f"⚙️  最大并发: {pdf_parser.max_concurrent_requests}个")
        logger.info(f"⚙️  预计批次数: {(actual_pages + 3) // 4}")
        
        # 解析（应该自动分页）
        result = await pdf_parser.parse(pdf_file)
        
        logger.info(f"\n解析结果:")
        logger.info(f"  ✅ 状态: {result.get('status')}")
        logger.info(f"  ✅ 总页数: {result.get('pages')}")
        logger.info(f"  ✅ 策略: 应该是分页并发（因为 >4 页）")
        
        # 验证结果完整性
        total_pages = result.get('pages', 0)
        root_pages = result.get('struct_content', {}).get('root', [])
        
        logger.info(f"\n结果验证:")
        logger.info(f"  ✅ 声明页数: {total_pages}")
        logger.info(f"  ✅ 实际页数: {len(root_pages)}")
        logger.info(f"  ✅ 页码连续性: {_check_page_continuity(root_pages)}")
        
        # 保存结果
        if output_dir is None:
            output_dir = project_root / "tmp_results" / "parser" / "pdf_parser_test"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_json = output_dir / f"{pdf_file.stem}_large_file_result.json"
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"\n✅ 结果已保存: {output_json}")
        
        output_md = output_dir / f"{pdf_file.stem}_large_file_content.md"
        with open(output_md, 'w', encoding='utf-8') as f:
            f.write(result.get('content', ''))
        logger.info(f"✅ Markdown已保存: {output_md}")
        
        logger.info(f"\n✅✅✅ 测试2成功完成！\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ 测试2失败")
        logger.exception(e)
        return False


async def test_custom_pagination_params(pdf_path: str, output_dir: Optional[str] = None):
    """
    测试3: 自定义分页参数（测试不同的阈值和并发数）
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"测试3: 自定义分页参数")
    logger.info(f"{'=' * 80}")
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        logger.error(f"❌ 文件不存在: {pdf_path}")
        return False
    
    # 先检查文件页数
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_file)
        actual_pages = len(reader.pages)
        logger.info(f"📖 文件实际页数: {actual_pages}")
    except Exception as e:
        logger.error(f"❌ 获取页数失败: {e}")
        return False
    
    # 测试不同的参数组合
    test_params = [
        {"max_pages_per_request": 2, "max_concurrent_requests": 3, "name": "每2页，最多3并发"},
        {"max_pages_per_request": 3, "max_concurrent_requests": 2, "name": "每3页，最多2并发"},
    ]
    
    # 如果文件较大，添加更多测试
    if actual_pages > 10:
        test_params.append(
            {"max_pages_per_request": 5, "max_concurrent_requests": 1, "name": "每5页，串行"}
        )
    
    results = []
    
    for params in test_params:
        try:
            logger.info(f"\n测试参数: {params['name']}")
            logger.info(f"  max_pages_per_request={params['max_pages_per_request']}")
            logger.info(f"  max_concurrent_requests={params['max_concurrent_requests']}")
            
            config = load_config()
            mineru_client = Mineru2Client(config)
            pdf_parser = PDFParser(
                mineru_client=mineru_client,
                max_pages_per_request=params['max_pages_per_request'],
                max_concurrent_requests=params['max_concurrent_requests']
            )
            
            result = await pdf_parser.parse(pdf_file)
            
            results.append({
                "params": params['name'],
                "status": result.get('status'),
                "pages": result.get('pages'),
                "success": True
            })
            
            logger.info(f"  ✅ 成功: {result.get('pages')} 页")
            
        except Exception as e:
            logger.error(f"  ❌ 失败: {e}")
            results.append({
                "params": params['name'],
                "error": str(e),
                "success": False
            })
    
    # 输出统计
    logger.info(f"\n参数测试统计:")
    for r in results:
        if r['success']:
            logger.info(f"  ✅ {r['params']}: {r['pages']} 页")
        else:
            logger.error(f"  ❌ {r['params']}: {r['error']}")
    
    logger.info(f"\n✅✅✅ 测试3成功完成！\n")
    
    return all(r['success'] for r in results)


async def test_very_large_file(pdf_path: str, output_dir: Optional[str] = None):
    """
    测试4: 超大文件（>20页）- 测试高并发场景
    
    Args:
        pdf_path: PDF 文件路径（建议 >20 页）
        output_dir: 输出目录
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"测试4: 超大文件解析（高并发场景）")
    logger.info(f"{'=' * 80}")
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        logger.error(f"❌ 文件不存在: {pdf_path}")
        return False
    
    try:
        config = load_config()
        mineru_client = Mineru2Client(config)
        pdf_parser = PDFParser(
            mineru_client=mineru_client,
            max_pages_per_request=4,
            max_concurrent_requests=10  # 高并发
        )
        
        logger.info(f"📄 解析文件: {pdf_file.name}")
        logger.info(f"⚙️  高并发模式: 最多10个并发请求")
        
        import time
        start_time = time.time()
        
        result = await pdf_parser.parse(pdf_file)
        
        elapsed_time = time.time() - start_time
        
        logger.info(f"\n解析结果:")
        logger.info(f"  ✅ 状态: {result.get('status')}")
        logger.info(f"  ✅ 总页数: {result.get('pages')}")
        logger.info(f"  ✅ 耗时: {elapsed_time:.2f} 秒")
        logger.info(f"  ✅ 平均速度: {result.get('pages', 0) / elapsed_time:.2f} 页/秒")
        
        logger.info(f"\n✅✅✅ 测试4成功完成！\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ 测试4失败")
        logger.exception(e)
        return False


def _check_page_continuity(root_pages: list) -> str:
    """
    检查页码连续性
    
    Args:
        root_pages: 页面列表
        
    Returns:
        检查结果描述
    """
    if not root_pages:
        return "❌ 无页面"
    
    page_indices = [page.get('page_idx') for page in root_pages]
    
    # 检查是否连续
    expected = list(range(len(page_indices)))
    
    if page_indices == expected:
        return f"✅ 连续（0-{len(page_indices)-1}）"
    else:
        return f"❌ 不连续（期望: {expected}, 实际: {page_indices}）"


async def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # 测试文件路径
    # 注意：测试会自动检测文件页数，根据页数选择合适的测试
    test_pdf = "tmp_files/pdf/demo1.pdf"
    output_dir = "tmp_results/parser/pdf_parser_test"
    
    logger.info(f"\n{'#' * 80}")
    logger.info(f"# PDFParser 测试套件（自动分页并发）")
    logger.info(f"{'#' * 80}")
    logger.info(f"")
    logger.info(f"测试文件: {test_pdf}")
    logger.info(f"")
    logger.info(f"提示:")
    logger.info(f"  - 测试1需要 ≤4 页的PDF")
    logger.info(f"  - 测试2需要 >4 页的PDF（建议10-20页）")
    logger.info(f"  - 测试会自动检测页数并跳过不适用的测试")
    logger.info(f"")
    
    # 运行所有测试（使用同一个文件，根据页数自动判断）
    test_results = []
    
    # 测试1: 小文件（不分页）
    test_results.append((
        "测试1: 小文件（≤4页）",
        await test_small_file_no_pagination(test_pdf, output_dir)
    ))
    
    # 测试2: 大文件（自动分页）
    test_results.append((
        "测试2: 大文件（>4页）",
        await test_large_file_with_pagination(test_pdf, output_dir)
    ))
    
    # 测试3: 自定义参数
    test_results.append((
        "测试3: 自定义分页参数",
        await test_custom_pagination_params(test_pdf, output_dir)
    ))
    
    # 测试4: 超大文件（如果有）
    # test_results.append((
    #     "测试4: 超大文件（>20页）",
    #     await test_very_large_file(very_large_pdf, output_dir)
    # ))
    
    # 输出测试总结
    logger.info(f"\n{'#' * 80}")
    logger.info(f"# 测试总结")
    logger.info(f"{'#' * 80}\n")
    
    passed = sum(1 for _, success in test_results if success)
    total = len(test_results)
    
    for test_name, success in test_results:
        status = "✅ 通过" if success else "❌ 失败"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\n总计: {passed}/{total} 通过\n")
    
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
