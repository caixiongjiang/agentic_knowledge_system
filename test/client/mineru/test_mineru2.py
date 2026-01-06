#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
测试 Mineru Tianshu 客户端
用法（从项目根目录执行）：
    python test/client/test_mineru_tianshu.py <pdf_file_path>
    
示例：
    python test/client/test_mineru_tianshu.py data/demo.pdf
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
    
    你可以根据实际情况修改这里的配置
    """
    return {
        "endpoint": "http://192.168.201.14:18000",  # Mineru API 地址
        "timeout": 600,  # 超时时间（秒）
        "poll_interval": 1,  # 轮询间隔（秒）
        "params": {
            "backend": "pipeline",  # 处理后端：pipeline 或 magic-pdf
            "lang": "ch",  # 语言：ch（中文）或 en（英文）
            "method": "auto",  # 解析方法：auto、ocr、txt
            "formula_enable": True,  # 是否启用公式识别
            "table_enable": True,  # 是否启用表格识别
            "priority": 0  # 任务优先级：0-9，数字越大优先级越高
        }
    }


def test_parse_file(pdf_path: str, output_dir: Optional[str] = None):
    """
    测试解析单个 PDF 文件
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录，默认为 tmp_results/parser/mineru_test/
    """
    logger.info(f"=" * 80)
    logger.info(f"开始测试 Mineru Tianshu 客户端")
    logger.info(f"=" * 80)
    
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
        logger.info(f"✓ 文件读取成功")
    except Exception as e:
        logger.error(f"❌ 文件读取失败: {e}")
        return False
    
    # 创建客户端
    try:
        config = load_config()
        logger.info(f"📡 API 地址: {config['endpoint']}")
        client = Mineru2Client(config)
        logger.info(f"✓ 客户端初始化成功")
    except Exception as e:
        logger.error(f"❌ 客户端初始化失败: {e}")
        return False
    
    # 解析文件
    try:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"开始解析文档...")
        logger.info(f"{'=' * 80}\n")
        
        result = client.parse_file(
            file_bytes=file_bytes,
            file_name=pdf_file.name
        )
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"解析结果统计")
        logger.info(f"{'=' * 80}")
        logger.info(f"✓ 状态: {result.get('status')}")
        logger.info(f"✓ 总页数: {result.get('pages')}")
        logger.info(f"✓ Markdown 内容长度: {len(result.get('content', ''))} 字符")
        
        # 统计元素类型
        type_counts = {}
        for page in result.get('struct_content', {}).get('root', []):
            for elem in page.get('page_info', []):
                elem_type = elem.get('type', 'unknown')
                type_counts[elem_type] = type_counts.get(elem_type, 0) + 1
        
        logger.info(f"\n元素类型统计:")
        for elem_type, count in sorted(type_counts.items()):
            logger.info(f"  - {elem_type}: {count}")
        
        # 保存结果
        if output_dir is None:
            output_dir = project_root / "tmp_results" / "parser" / "mineru_test"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存 JSON 结果
        output_json = output_dir / f"{pdf_file.stem}_result.json"
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"\n✓ JSON 结果已保存: {output_json}")
        
        # 保存 Markdown 内容
        output_md = output_dir / f"{pdf_file.stem}_content.md"
        with open(output_md, 'w', encoding='utf-8') as f:
            f.write(result.get('content', ''))
        logger.info(f"✓ Markdown 内容已保存: {output_md}")
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"✓✓✓ 测试成功完成！")
        logger.info(f"{'=' * 80}\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n{'=' * 80}")
        logger.error(f"❌ 解析失败")
        logger.error(f"{'=' * 80}")
        logger.exception(e)
        return False


def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    pdf_path = "tmp_files/pdf/demo1.pdf"
    output_dir = "tmp_results/parser/pdf"
    
    # 运行测试
    success = test_parse_file(pdf_path, output_dir)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
