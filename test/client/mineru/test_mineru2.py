#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
测试 Mineru2Client（新版本客户端）
支持分页功能测试

用法（从项目根目录执行）：
    uv run python test/client/mineru/test_mineru2.py
"""
import sys
import json
from pathlib import Path
from typing import Optional

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.client.mineru import Mineru2Client
from loguru import logger


def load_config() -> dict:
    """
    加载配置，返回 Mineru 客户端配置字典
    """
    return {
        "endpoint": "http://192.168.201.14:18000",  # Mineru API 地址
        "timeout": 600,  # 超时时间（秒）
    }


def test_parse_full_file(pdf_path: str, output_dir: Optional[str] = None):
    """
    测试1: 解析完整文件（不分页）
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"测试1: 解析完整文件（不分页）")
    logger.info(f"{'=' * 80}")
    
    # 检查文件是否存在
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        logger.error(f"❌ 文件不存在: {pdf_path}")
        return False
    
    logger.info(f"📄 PDF 文件: {pdf_file.name}")
    logger.info(f"📏 文件大小: {pdf_file.stat().st_size / 1024:.2f} KB")
    
    # 读取文件内容
    try:
        with open(pdf_file, 'rb') as f:
            file_bytes = f.read()
        logger.info(f"✅ 文件读取成功")
    except Exception as e:
        logger.error(f"❌ 文件读取失败: {e}")
        return False
    
    # 创建客户端
    try:
        config = load_config()
        logger.info(f"📡 API 地址: {config['endpoint']}")
        client = Mineru2Client(config)
        logger.info(f"✅ 客户端初始化成功")
    except Exception as e:
        logger.error(f"❌ 客户端初始化失败: {e}")
        return False
    
    # 解析文件（不分页）
    try:
        logger.info(f"\n开始解析文档（完整文件）...")
        
        result = client.parse_file(
            file_bytes=file_bytes,
            file_name=pdf_file.name,
            backend="pipeline",  # 处理后端：pipeline 或 magic-pdf
            lang="ch",  # 语言：ch（中文）或 en（英文）
            method="auto",  # 解析方法：auto、ocr、txt
            formula_enable=True,  # 是否启用公式识别
            table_enable=True,  # 是否启用表格识别
            priority=0  # 任务优先级：0-9，数字越大优先级越高
        )
        
        logger.info(f"\n解析结果统计:")
        logger.info(f"  ✅ 状态: {result.get('status')}")
        logger.info(f"  ✅ 总页数: {result.get('pages')}")
        logger.info(f"  ✅ Markdown 内容长度: {len(result.get('content', ''))} 字符")
        
        # 统计元素类型
        type_counts = {}
        for page in result.get('struct_content', {}).get('root', []):
            for elem in page.get('page_info', []):
                elem_type = elem.get('type', 'unknown')
                type_counts[elem_type] = type_counts.get(elem_type, 0) + 1
        
        logger.info(f"\n  元素类型统计:")
        for elem_type, count in sorted(type_counts.items()):
            logger.info(f"    - {elem_type}: {count}")
        
        # 保存结果
        if output_dir is None:
            output_dir = project_root / "tmp_results" / "parser" / "mineru_test"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存 JSON 结果
        output_json = output_dir / f"{pdf_file.stem}_full_result.json"
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"\n✅ JSON 结果已保存: {output_json}")
        
        # 保存 Markdown 内容
        output_md = output_dir / f"{pdf_file.stem}_full_content.md"
        with open(output_md, 'w', encoding='utf-8') as f:
            f.write(result.get('content', ''))
        logger.info(f"✅ Markdown 内容已保存: {output_md}")
        
        logger.info(f"\n✅✅✅ 测试1成功完成！\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ 测试1失败")
        logger.exception(e)
        return False


def test_parse_with_pagination(pdf_path: str, output_dir: Optional[str] = None):
    """
    测试2: 分页解析（测试前10页）
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"测试2: 分页解析（只解析前10页）")
    logger.info(f"{'=' * 80}")
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        logger.error(f"❌ 文件不存在: {pdf_path}")
        return False
    
    # 读取文件
    try:
        with open(pdf_file, 'rb') as f:
            file_bytes = f.read()
    except Exception as e:
        logger.error(f"❌ 文件读取失败: {e}")
        return False
    
    # 创建客户端
    try:
        config = load_config()
        client = Mineru2Client(config)
    except Exception as e:
        logger.error(f"❌ 客户端初始化失败: {e}")
        return False
    
    # 只解析前10页（页码 0-9）
    try:
        logger.info(f"\n开始解析文档（只处理前10页：页码 0-9）...")
        
        result = client.parse_file(
            file_bytes=file_bytes,
            file_name=pdf_file.name,
            start_page_id=0,
            end_page_id=9,
            backend="pipeline",
            lang="ch",
            method="auto",
            formula_enable=True,
            table_enable=True,
            priority=0
        )
        
        logger.info(f"\n解析结果统计:")
        logger.info(f"  ✅ 状态: {result.get('status')}")
        logger.info(f"  ✅ 解析页数: {result.get('pages')} 页（应该是10页）")
        
        # 保存结果
        if output_dir is None:
            output_dir = project_root / "tmp_results" / "parser" / "mineru_test"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_json = output_dir / f"{pdf_file.stem}_page_0_9_result.json"
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"\n✅ JSON 结果已保存: {output_json}")
        
        logger.info(f"\n✅✅✅ 测试2成功完成！\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ 测试2失败")
        logger.exception(e)
        return False


def test_parse_multiple_ranges(pdf_path: str, output_dir: Optional[str] = None):
    """
    测试3: 多个分页范围（模拟并发分页）
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"测试3: 多个分页范围（模拟并发分页）")
    logger.info(f"{'=' * 80}")
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        logger.error(f"❌ 文件不存在: {pdf_path}")
        return False
    
    # 读取文件
    try:
        with open(pdf_file, 'rb') as f:
            file_bytes = f.read()
    except Exception as e:
        logger.error(f"❌ 文件读取失败: {e}")
        return False
    
    # 先获取PDF总页数
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_file)
        total_pages = len(reader.pages)
        logger.info(f"📖 PDF 总页数: {total_pages}")
    except Exception as e:
        logger.error(f"❌ 获取页数失败: {e}")
        return False
    
    # 创建客户端
    try:
        config = load_config()
        client = Mineru2Client(config)
    except Exception as e:
        logger.error(f"❌ 客户端初始化失败: {e}")
        return False
    
    # 根据实际页数动态生成测试范围（每4页一批）
    page_ranges = []
    for start in range(0, total_pages, 4):
        end = min(start + 3, total_pages - 1)
        page_ranges.append((start, end))
    
    logger.info(f"📋 测试方案: {len(page_ranges)} 个批次")
    
    results = []
    
    for idx, (start, end) in enumerate(page_ranges, 1):
        try:
            logger.info(f"\n处理批次{idx}: 页码 {start}-{end}")
            
            result = client.parse_file(
                file_bytes=file_bytes,
                file_name=pdf_file.name,
                start_page_id=start,
                end_page_id=end,
                backend="pipeline",
                lang="ch",
                method="auto",
                formula_enable=True,
                table_enable=True,
                priority=0
            )
            
            results.append({
                "batch": idx,
                "page_range": f"{start}-{end}",
                "pages": result.get('pages'),
                "status": result.get('status'),
                "success": True
            })
            
            logger.info(f"  ✅ 批次{idx}完成: {result.get('pages')} 页")
            
        except Exception as e:
            logger.error(f"  ❌ 批次{idx}失败: {e}")
            results.append({
                "batch": idx,
                "page_range": f"{start}-{end}",
                "error": str(e),
                "success": False
            })
    
    # 输出统计
    logger.info(f"\n批次处理统计:")
    success_count = 0
    for r in results:
        if r.get("success"):
            logger.info(f"  ✅ 批次{r['batch']} ({r['page_range']}): {r['pages']} 页")
            success_count += 1
        else:
            logger.error(f"  ❌ 批次{r['batch']} ({r['page_range']}): {r.get('error', 'Unknown')}")
    
    # 判断测试是否成功
    all_success = success_count == len(results)
    
    if all_success:
        logger.info(f"\n✅✅✅ 测试3成功完成！\n")
    else:
        logger.warning(f"\n⚠️  测试3部分失败: {success_count}/{len(results)} 批次成功\n")
    
    return all_success


def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # 测试文件路径
    pdf_path = "tmp_files/pdf/demo1.pdf"
    output_dir = "tmp_results/parser/pdf"
    
    logger.info(f"\n{'#' * 80}")
    logger.info(f"# Mineru2Client 测试套件")
    logger.info(f"{'#' * 80}\n")
    
    # 运行所有测试
    test_results = []
    
    # 测试1: 完整文件解析
    test_results.append(("测试1: 完整文件解析", test_parse_full_file(pdf_path, output_dir)))
    
    # 测试2: 分页解析
    test_results.append(("测试2: 分页解析（前10页）", test_parse_with_pagination(pdf_path, output_dir)))
    
    # 测试3: 多个分页范围
    test_results.append(("测试3: 多个分页范围", test_parse_multiple_ranges(pdf_path, output_dir)))
    
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
    main()
