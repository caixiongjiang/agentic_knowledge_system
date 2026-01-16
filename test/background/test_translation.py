#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_translation.py
@Author  : caixiongjiang
@Date    : 2026/1/14 17:35
@Function: 
    测试文本翻译功能
    - 从 mineru 解析的 PDF 结果中提取文本和表格
    - 使用多种目标语言进行翻译测试
    - 使用 OpenAI 格式调用模型
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.client.llm import create_llm_client
from src.prompts.background.translation import (
    language_translation_system_prompt,
    language_translation_user_prompt
)
from loguru import logger


# 支持的目标语言列表
TARGET_LANGUAGES = [
    {"code": "zh-CN", "name": "Simplified Chinese"},
    {"code": "zh-TW", "name": "Traditional Chinese"},
    # {"code": "en", "name": "English"},
    # {"code": "ru", "name": "Russian"},
    # {"code": "ja", "name": "Japanese"},
    # {"code": "ko", "name": "Korean"},
    # {"code": "fr", "name": "French"},
    # {"code": "de", "name": "German"},
    # {"code": "es", "name": "Spanish"},
    # {"code": "pt", "name": "Portuguese"},
    # {"code": "it", "name": "Italian"},
    # {"code": "pl", "name": "Polish"},
    # {"code": "vi", "name": "Vietnamese"}, 
    # {"code": "hi", "name": "Hindi"},
    # {"code": "es-MX", "name": "Mexican Spanish"}
]


class TranslationTester:
    """翻译测试类"""
    
    def __init__(
        self,
        provider: str = "openai",
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 8000,
        timeout: int = 300
    ):
        """
        初始化翻译测试器
        
        Args:
            provider: LLM 提供商（默认 openai）
            model_name: 模型名称（默认 gpt-4o-mini）
            temperature: 温度参数
            max_tokens: 最大token数
            timeout: 请求超时时间（秒），默认300秒（5分钟）
        """
        self.provider = provider
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        logger.info(
            f"初始化翻译测试器 - Provider: {provider}, Model: {model_name}, "
            f"Timeout: {timeout}s"
        )
    
    def load_mineru_result(self, json_path: str) -> List[Dict[str, Any]]:
        """
        加载 mineru 解析结果
        
        Args:
            json_path: content_list.json 文件路径
            
        Returns:
            解析后的内容列表
        """
        logger.info(f"加载 mineru 解析结果: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            content_list = json.load(f)
        
        logger.info(f"加载完成，共 {len(content_list)} 个元素")
        return content_list
    
    def extract_text_and_tables_by_page(
        self,
        content_list: List[Dict[str, Any]],
        page_limit: Optional[int] = None
    ) -> Dict[int, str]:
        """
        从 mineru 结果中按页提取文本和表格内容
        
        Args:
            content_list: mineru 解析的内容列表
            page_limit: 限制提取的页数（默认为None，表示提取所有页）
            
        Returns:
            字典，key为页码，value为该页的拼接文本内容
        """
        page_info = "所有页" if page_limit is None else f"前{page_limit}页"
        logger.info(f"开始按页提取文本和表格内容（页数限制: {page_info}）")
        
        # 按页组织内容
        pages_content = {}
        
        for item in content_list:
            page_idx = item.get("page_idx", 0)
            
            # 只提取指定页数的内容（如果page_limit为None则提取所有页）
            if page_limit is not None and page_idx >= page_limit:
                continue
            
            # 初始化该页的内容列表
            if page_idx not in pages_content:
                pages_content[page_idx] = []
            
            item_type = item.get("type")
            
            # 提取文本类型
            if item_type == "text":
                text = item.get("text", "").strip()
                if text:
                    pages_content[page_idx].append(text)
                    logger.debug(f"页{page_idx}: 提取文本: {text[:50]}...")
            
            # 提取表格类型
            elif item_type == "table":
                # 表格标题
                table_caption = item.get("table_caption", [])
                if table_caption:
                    caption_text = " ".join(table_caption)
                    pages_content[page_idx].append(f"table_caption: {caption_text}")
                    logger.debug(f"页{page_idx}: 提取表格标题: {caption_text[:50]}...")
                
                # 表格主体（HTML格式）
                table_body = item.get("table_body", "").strip()
                if table_body:
                    pages_content[page_idx].append(f"table_body: {table_body}")
                    logger.debug(f"页{page_idx}: 提取表格主体: {table_body[:100]}...")
                
                # 表格脚注
                table_footnote = item.get("table_footnote", [])
                if table_footnote:
                    footnote_text = " ".join(table_footnote)
                    pages_content[page_idx].append(f"table_footnote: {footnote_text}")
                    logger.debug(f"页{page_idx}: 提取表格脚注: {footnote_text[:50]}...")
        
        # 拼接每页的内容
        pages_text = {}
        for page_idx in sorted(pages_content.keys()):
            page_text = "\n\n".join(pages_content[page_idx])
            pages_text[page_idx] = page_text
            logger.info(f"页{page_idx}: 提取完成，长度: {len(page_text)} 字符")
        
        logger.info(f"总共提取 {len(pages_text)} 页内容")
        return pages_text
    
    def translate_text(
        self,
        text: str,
        target_language_code: str,
        target_language_name: str
    ) -> Dict[str, Any]:
        """
        翻译文本到目标语言
        
        Args:
            text: 待翻译的文本
            target_language_code: 目标语言代码（如 zh-CN）
            target_language_name: 目标语言名称（如 Simplified Chinese）
            
        Returns:
            翻译结果字典，包含翻译内容、token使用等信息
        """
        logger.info(f"开始翻译到 {target_language_name} ({target_language_code})")
        
        # 构建系统提示词
        system_prompt = language_translation_system_prompt.format(
            TARGET_LANGUAGE_CODE=target_language_code,
            TARGET_LANGUAGE_NAME=target_language_name
        )
        
        # 构建用户提示词
        user_prompt = language_translation_user_prompt.format(
            input_text=text
        )
        
        # 创建客户端并进行翻译
        try:
            with create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout
            ) as client:
                response = client.generate(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                
                # 提取翻译结果（移除代码块标记）
                translated_content = response.content.strip()
                
                # 移除 Markdown 代码块包裹（如果有）
                if translated_content.startswith("````"):
                    lines = translated_content.split("\n")
                    # 移除第一行和最后一行的四个反引号
                    if len(lines) > 2:
                        translated_content = "\n".join(lines[1:-1])
                elif translated_content.startswith("```"):
                    lines = translated_content.split("\n")
                    # 移除第一行和最后一行的三个反引号
                    if len(lines) > 2:
                        translated_content = "\n".join(lines[1:-1])
                
                logger.info(
                    f"翻译完成 - Token使用: {response.usage.total_tokens}, "
                    f"翻译内容长度: {len(translated_content)} 字符"
                )
                
                # 打印翻译内容预览（前500字符）
                print("\n" + "=" * 80)
                print(f"翻译语言: {target_language_name} ({target_language_code})")
                print(f"模型: {response.model}")
                print(f"Token使用: 提示={response.usage.prompt_tokens}, "
                      f"完成={response.usage.completion_tokens}, "
                      f"总计={response.usage.total_tokens}")
                print("-" * 80)
                print("翻译内容预览（前500字符）:")
                print(translated_content[:500])
                if len(translated_content) > 500:
                    print(f"\n... (还有 {len(translated_content) - 500} 个字符)")
                print("=" * 80 + "\n")
                
                return {
                    "target_language_code": target_language_code,
                    "target_language_name": target_language_name,
                    "translated_content": translated_content,
                    "model": response.model,
                    "tokens_used": response.usage.total_tokens,
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "finish_reason": response.finish_reason
                }
        
        except Exception as e:
            logger.error(f"翻译失败: {e}")
            
            # 打印错误信息
            print("\n" + "=" * 80)
            print(f"❌ 翻译失败: {target_language_name} ({target_language_code})")
            print(f"错误信息: {str(e)}")
            print("=" * 80 + "\n")
            
            return {
                "target_language_code": target_language_code,
                "target_language_name": target_language_name,
                "error": str(e)
            }
    
    def run_translation_tests(
        self,
        mineru_json_path: str,
        output_dir: str,
        page_limit: Optional[int] = None,
        language_limit: Optional[int] = None
    ):
        """
        运行翻译测试
        
        Args:
            mineru_json_path: mineru 解析结果的 content_list.json 路径
            output_dir: 输出目录
            page_limit: 限制提取的页数（默认为None，表示提取所有页）
            language_limit: 限制测试的语言数量（None表示测试所有语言）
        """
        # 打印测试开始信息
        print("\n" + "🚀" * 40)
        print("🌐 翻译测试开始")
        print(f"📌 提供商: {self.provider}")
        print(f"🤖 模型: {self.model_name}")
        print(f"⏱️  超时时间: {self.timeout}秒")
        print(f"🎯 最大Token: {self.max_tokens}")
        print(f"📄 源文件: {mineru_json_path}")
        print("🚀" * 40 + "\n")
        
        logger.info("=" * 80)
        logger.info("开始翻译测试")
        logger.info("=" * 80)
        
        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 1. 加载 mineru 结果
        content_list = self.load_mineru_result(mineru_json_path)
        
        # 2. 按页提取文本和表格
        pages_text = self.extract_text_and_tables_by_page(content_list, page_limit)
        
        # 保存每页的源文本
        for page_idx, page_text in pages_text.items():
            source_file = output_path / f"source_text_page_{page_idx}.txt"
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(page_text)
            logger.info(f"页{page_idx}源文本已保存: {source_file}")
        
        total_chars = sum(len(text) for text in pages_text.values())
        print(f"📝 源文本已保存: {len(pages_text)} 页")
        print(f"📊 总长度: {total_chars} 字符\n")
        
        # 3. 对每种语言进行翻译测试
        test_languages = TARGET_LANGUAGES[:language_limit] if language_limit else TARGET_LANGUAGES
        print(f"🎯 将测试 {len(test_languages)} 种语言: {', '.join([lang['code'] for lang in test_languages])}\n")
        
        all_results = []
        
        for i, lang in enumerate(test_languages, 1):
            # 打印测试开始信息
            print("\n" + "🌍" * 40)
            print(f"📝 开始测试 {i}/{len(test_languages)}: {lang['name']} ({lang['code']})")
            print("🌍" * 40 + "\n")
            
            logger.info(f"\n{'=' * 80}")
            logger.info(f"测试 {i}/{len(test_languages)}: {lang['name']} ({lang['code']})")
            logger.info(f"{'=' * 80}")
            
            # 对每一页进行翻译
            page_results = {}
            all_pages_success = True
            
            for page_idx in sorted(pages_text.keys()):
                page_text = pages_text[page_idx]
                
                print(f"\n  📄 正在翻译第 {page_idx} 页 ({len(page_text)} 字符)...")
                logger.info(f"翻译第 {page_idx} 页到 {lang['name']}")
                
                # 翻译该页
                result = self.translate_text(
                    text=page_text,
                    target_language_code=lang["code"],
                    target_language_name=lang["name"]
                )
                
                page_results[page_idx] = result
                
                # 保存该页的翻译结果
                if "error" not in result:
                    translation_file = output_path / f"translated_{lang['code']}_page_{page_idx}.txt"
                    with open(translation_file, 'w', encoding='utf-8') as f:
                        f.write(result["translated_content"])
                    logger.info(f"✅ 页{page_idx}翻译结果已保存: {translation_file}")
                    print(f"  ✅ 页{page_idx}已保存: {translation_file}\n")
                else:
                    all_pages_success = False
                    logger.error(f"❌ 页{page_idx}翻译失败: {result['error']}")
            
            # 汇总该语言的所有页翻译结果
            combined_result = {
                "target_language_code": lang["code"],
                "target_language_name": lang["name"],
                "pages": page_results,
                "all_pages_success": all_pages_success,
                "total_tokens": sum(r.get("tokens_used", 0) for r in page_results.values() if "error" not in r)
            }
            
            all_results.append(combined_result)
        
        # 4. 保存完整的测试结果
        summary_file = output_path / "translation_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                "provider": self.provider,
                "model": self.model_name,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "total_pages": len(pages_text),
                "total_chars": sum(len(text) for text in pages_text.values()),
                "page_limit": page_limit,
                "test_languages": [lang["code"] for lang in test_languages],
                "results": all_results
            }, f, ensure_ascii=False, indent=2)
        
        # 统计信息
        success_count = sum(1 for r in all_results if r.get("all_pages_success", False))
        fail_count = len(all_results) - success_count
        total_tokens = sum(r.get("total_tokens", 0) for r in all_results)
        
        # 打印测试完成信息
        print("\n" + "🎉" * 40)
        print("✅ 翻译测试完成！")
        print("=" * 80)
        print("📊 测试统计:")
        print(f"  📄 总页数: {len(pages_text)}")
        print(f"  🌐 测试语言数: {len(all_results)}")
        print(f"  ✅ 全部成功: {success_count}/{len(all_results)}")
        print(f"  ❌ 部分/全部失败: {fail_count}/{len(all_results)}")
        print(f"  🪙 总Token使用: {total_tokens:,}")
        print(f"  📁 结果保存在: {output_path}")
        print(f"  📄 测试摘要: {summary_file}")
        print("=" * 80)
        print("🎉" * 40 + "\n")
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"翻译测试完成！")
        logger.info(f"结果保存在: {output_path}")
        logger.info(f"测试摘要: {summary_file}")
        logger.info(f"{'=' * 80}\n")
        
        logger.info("测试统计:")
        logger.info(f"  - 总页数: {len(pages_text)}")
        logger.info(f"  - 测试语言数: {len(all_results)}")
        logger.info(f"  - 全部成功: {success_count}")
        logger.info(f"  - 部分/全部失败: {fail_count}")
        logger.info(f"  - 总Token使用: {total_tokens}")


def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # 配置参数
    mineru_json_path = project_root / "tmp_results" / "parser" / "mineru" / "content_list.json"
    output_dir = project_root / "tmp_results" / "translation_test"
    
    # 创建翻译测试器
    tester = TranslationTester(
        provider="openai",  # 使用 OpenAI
        model_name="ali/qwen3-max",
        temperature=0.3,
        max_tokens=32000,
        timeout=600
    )
    
    # 运行翻译测试
    tester.run_translation_tests(
        mineru_json_path=str(mineru_json_path),
        output_dir=str(output_dir),
        page_limit=None,  # 设置为None可测试所有页
        language_limit=None  # 设置为None可测试所有语言
    )


if __name__ == "__main__":
    main()
