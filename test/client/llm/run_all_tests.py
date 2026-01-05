#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : run_all_tests.py
@Author  : caixiongjiang
@Date    : 2026/1/5 18:00
@Function: 
    运行所有 LLM Client 测试
    支持按供应商分别运行或全部运行
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from test_openai_client import TestOpenAIClient
from test_deepseek_client import TestDeepSeekClient
from test_gemini_client import TestGeminiClient
from test_anthropic_client import TestAnthropicClient


def print_banner(text: str):
    """打印横幅"""
    width = 60
    print("\n" + "="*width)
    print(f"{text:^{width}}")
    print("="*width)


def run_specific_provider(provider: str):
    """运行特定供应商的测试"""
    if provider == "openai":
        print_banner("OpenAI 测试")
        tester = TestOpenAIClient()
        tester.run_all_tests()
    elif provider == "deepseek":
        print_banner("DeepSeek 测试")
        tester = TestDeepSeekClient()
        tester.run_all_tests()
    elif provider == "gemini":
        print_banner("Gemini 测试")
        tester = TestGeminiClient()
        tester.run_all_tests()
    elif provider == "anthropic":
        print_banner("Anthropic (Claude) 测试")
        tester = TestAnthropicClient()
        tester.run_all_tests()
    else:
        print(f"❌ 未知的供应商: {provider}")
        print("可用的供应商: openai, deepseek, gemini, anthropic")


def run_all_tests():
    """运行所有供应商的测试"""
    print_banner("🚀 LLM Client 完整测试套件")
    
    print("\n📋 测试计划:")
    print("   1. OpenAI - 标准格式测试")
    print("   2. DeepSeek - Thinking 功能测试")
    print("   3. Gemini - 多模态和格式转换测试")
    print("   4. Anthropic (Claude) - 参数验证测试")
    
    input("\n按 Enter 开始测试...")
    
    all_results = []
    
    # OpenAI 测试
    try:
        print_banner("1/4 - OpenAI 测试")
        tester_openai = TestOpenAIClient()
        tester_openai.run_all_tests()
        all_results.append(("OpenAI", tester_openai.test_results))
    except Exception as e:
        print(f"❌ OpenAI 测试失败: {e}")
        all_results.append(("OpenAI", []))
    
    input("\n按 Enter 继续下一个测试...")
    
    # DeepSeek 测试
    try:
        print_banner("2/4 - DeepSeek 测试")
        tester_deepseek = TestDeepSeekClient()
        tester_deepseek.run_all_tests()
        all_results.append(("DeepSeek", tester_deepseek.test_results))
    except Exception as e:
        print(f"❌ DeepSeek 测试失败: {e}")
        all_results.append(("DeepSeek", []))
    
    input("\n按 Enter 继续下一个测试...")
    
    # Gemini 测试
    try:
        print_banner("3/4 - Gemini 测试")
        tester_gemini = TestGeminiClient()
        tester_gemini.run_all_tests()
        all_results.append(("Gemini", tester_gemini.test_results))
    except Exception as e:
        print(f"❌ Gemini 测试失败: {e}")
        all_results.append(("Gemini", []))
    
    input("\n按 Enter 继续下一个测试...")
    
    # Anthropic 测试
    try:
        print_banner("4/4 - Anthropic 测试")
        tester_anthropic = TestAnthropicClient()
        tester_anthropic.run_all_tests()
        all_results.append(("Anthropic", tester_anthropic.test_results))
    except Exception as e:
        print(f"❌ Anthropic 测试失败: {e}")
        all_results.append(("Anthropic", []))
    
    # 汇总所有结果
    print_banner("📊 总体测试报告")
    
    total_passed = 0
    total_tests = 0
    
    for provider, results in all_results:
        passed = sum(1 for _, p, _ in results if p)
        total = len(results)
        total_passed += passed
        total_tests += total
        
        print(f"\n{provider}:")
        print(f"   通过: {passed}/{total} ({passed/total*100:.1f}%)" if total > 0 else "   无测试结果")
        
        # 显示失败的测试
        failed_tests = [(name, msg) for name, p, msg in results if not p]
        if failed_tests:
            print(f"   失败的测试:")
            for name, msg in failed_tests:
                print(f"      - {name}: {msg}")
    
    print("\n" + "="*60)
    print(f"总计: {total_passed}/{total_tests} 通过 ({total_passed/total_tests*100:.1f}%)" if total_tests > 0 else "无测试结果")
    print("="*60)


def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 运行特定供应商的测试
        provider = sys.argv[1].lower()
        run_specific_provider(provider)
    else:
        # 运行所有测试
        print("\n💡 使用方法:")
        print("   - 运行所有测试: python run_all_tests.py")
        print("   - 运行特定测试: python run_all_tests.py <provider>")
        print("     可用的 provider: openai, deepseek, gemini, anthropic")
        print()
        
        choice = input("是否运行所有测试？(y/n): ").strip().lower()
        
        if choice == 'y' or choice == 'yes':
            run_all_tests()
        else:
            provider = input("请输入要测试的供应商 (openai/deepseek/gemini/anthropic): ").strip().lower()
            run_specific_provider(provider)


if __name__ == "__main__":
    main()
