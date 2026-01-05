#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_deepseek_client.py
@Author  : caixiongjiang
@Date    : 2026/1/5 18:00
@Function: 
    DeepSeek LLM Client 测试
    测试核心功能：chat、reasoner、流式、异步
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.client.llm import create_llm_client
from src.client.llm.types import LLMResponse


class TestDeepSeekClient:
    """DeepSeek LLM Client 测试类"""
    
    def __init__(self):
        self.test_results = []
        self.provider = "deepseek"
    
    def log_result(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ 通过" if passed else "❌ 失败"
        result = f"{status} - {test_name}"
        if message:
            result += f": {message}"
        print(result)
        self.test_results.append((test_name, passed, message))
    
    def test_basic_chat(self):
        """测试 1: 基础对话（deepseek-chat）"""
        print("\n" + "="*60)
        print("测试 1: 基础对话 - deepseek-chat")
        print("="*60)
        
        try:
            client = create_llm_client(
                provider=self.provider,
                model_name="deepseek-chat",
                temperature=0.7,
                max_tokens=200
            )
            
            response = client.generate(
                messages=[
                    {"role": "user", "content": "用一句话介绍什么是深度学习"}
                ]
            )
            
            assert isinstance(response, LLMResponse), "响应类型错误"
            assert response.content, "响应内容为空"
            assert response.usage.total_tokens > 0, "Token 统计错误"
            assert response.thinking is None, "普通 chat 不应有 thinking"
            
            print(f"\n📝 回答: {response.content}")
            print(f"📊 Token 使用: {response.usage.total_tokens}")
            print(f"🤖 模型: {response.model}")
            
            self.log_result("基础对话", True)
            
        except Exception as e:
            self.log_result("基础对话", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_reasoner_thinking(self):
        """测试 2: 推理功能（deepseek-reasoner）"""
        print("\n" + "="*60)
        print("测试 2: 推理功能 - deepseek-reasoner")
        print("="*60)
        
        try:
            client = create_llm_client(
                provider=self.provider,
                model_name="deepseek-reasoner",
                max_tokens=2000
            )
            
            response = client.generate(
                messages=[
                    {"role": "user", "content": "一个数的平方等于144，这个数是多少？请说明推理过程。"}
                ]
            )
            
            assert response.content, "响应内容为空"
            
            # 验证推理过程
            if response.thinking:
                print(f"\n💭 推理过程:")
                print(f"   {response.thinking.reasoning[:300]}...")
                print(f"\n📊 Thinking Tokens: {response.thinking.tokens_used}")
                print(f"📝 最终答案: {response.content}")
                print(f"📊 总 Token: {response.usage.total_tokens}")
                
                assert response.usage.thinking_tokens is not None, "应该有 thinking tokens"
                self.log_result("推理功能", True)
            else:
                print(f"\n⚠️ 未返回推理过程")
                self.log_result("推理功能", False, "未返回 thinking")
            
        except Exception as e:
            self.log_result("推理功能", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_streaming(self):
        """测试 3: 流式输出"""
        print("\n" + "="*60)
        print("测试 3: 流式输出")
        print("="*60)
        
        try:
            client = create_llm_client(
                provider=self.provider,
                model_name="deepseek-chat",
                max_tokens=200
            )
            
            print(f"\n📝 流式生成中: ", end='', flush=True)
            
            full_content = ""
            chunk_count = 0
            
            for chunk in client.generate_stream(
                messages=[
                    {"role": "user", "content": "用一句话介绍Python编程语言"}
                ]
            ):
                print(chunk.delta, end='', flush=True)
                full_content += chunk.delta
                chunk_count += 1
            
            print()  # 换行
            
            assert full_content, "流式内容为空"
            assert chunk_count > 0, "未收到任何块"
            
            print(f"\n✅ 流式输出成功")
            print(f"📊 总共收到 {chunk_count} 个块")
            print(f"📝 完整内容: {full_content}")
            
            self.log_result("流式输出", True)
            
        except Exception as e:
            self.log_result("流式输出", False, str(e))
            print(f"\n❌ 错误: {e}")
    
    def test_async_call(self):
        """测试 4: 异步调用"""
        print("\n" + "="*60)
        print("测试 4: 异步调用")
        print("="*60)
        
        async def async_test():
            try:
                async with create_llm_client(
                    provider=self.provider,
                    model_name="deepseek-chat",
                    max_tokens=200
                ) as client:
                    response = await client.agenerate(
                        messages=[
                            {"role": "user", "content": "什么是异步编程？"}
                        ]
                    )
                    
                    assert response.content, "响应内容为空"
                    
                    print(f"\n📝 回答: {response.content}")
                    print(f"📊 Token 使用: {response.usage.total_tokens}")
                    print(f"✅ 异步调用成功")
                    
                    return True
                    
            except Exception as e:
                print(f"❌ 错误: {e}")
                return False
        
        try:
            # 运行异步测试
            result = asyncio.run(async_test())
            self.log_result("异步调用", result)
            
        except Exception as e:
            self.log_result("异步调用", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_async_streaming(self):
        """测试 5: 异步流式输出"""
        print("\n" + "="*60)
        print("测试 5: 异步流式输出")
        print("="*60)
        
        async def async_stream_test():
            try:
                async with create_llm_client(
                    provider=self.provider,
                    model_name="deepseek-chat",
                    max_tokens=200
                ) as client:
                    print(f"\n📝 异步流式生成中: ", end='', flush=True)
                    
                    full_content = ""
                    chunk_count = 0
                    
                    async for chunk in client.agenerate_stream(
                        messages=[
                            {"role": "user", "content": "用一句话介绍JavaScript"}
                        ]
                    ):
                        print(chunk.delta, end='', flush=True)
                        full_content += chunk.delta
                        chunk_count += 1
                    
                    print()  # 换行
                    
                    assert full_content, "流式内容为空"
                    assert chunk_count > 0, "未收到任何块"
                    
                    print(f"\n✅ 异步流式输出成功")
                    print(f"📊 总共收到 {chunk_count} 个块")
                    
                    return True
                    
            except Exception as e:
                print(f"\n❌ 错误: {e}")
                return False
        
        try:
            result = asyncio.run(async_stream_test())
            self.log_result("异步流式输出", result)
            
        except Exception as e:
            self.log_result("异步流式输出", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_async_batch(self):
        """测试 6: 异步批量并发"""
        print("\n" + "="*60)
        print("测试 6: 异步批量并发")
        print("="*60)
        
        async def async_batch_test():
            try:
                async with create_llm_client(
                    provider=self.provider,
                    model_name="deepseek-chat",
                    max_tokens=100
                ) as client:
                    # 批量问题
                    questions = [
                        "1+1=?",
                        "2+2=?",
                        "3+3=?"
                    ]
                    
                    # 并发调用
                    tasks = [
                        client.agenerate(messages=[{"role": "user", "content": q}])
                        for q in questions
                    ]
                    
                    responses = await asyncio.gather(*tasks)
                    
                    print(f"\n✅ 成功处理 {len(responses)} 个请求")
                    for i, (q, r) in enumerate(zip(questions, responses), 1):
                        print(f"   {i}. {q} → {r.content[:50]}")
                    
                    assert len(responses) == len(questions), "响应数量不匹配"
                    return True
                    
            except Exception as e:
                print(f"❌ 错误: {e}")
                return False
        
        try:
            result = asyncio.run(async_batch_test())
            self.log_result("异步批量并发", result)
            
        except Exception as e:
            self.log_result("异步批量并发", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_context_manager(self):
        """测试 7: 上下文管理器（资源管理）"""
        print("\n" + "="*60)
        print("测试 7: 上下文管理器")
        print("="*60)
        
        try:
            with create_llm_client(
                provider=self.provider,
                model_name="deepseek-chat",
                max_tokens=100
            ) as client:
                # 多次调用，复用连接
                response1 = client.generate(
                    messages=[{"role": "user", "content": "你好"}]
                )
                
                response2 = client.generate(
                    messages=[{"role": "user", "content": "再见"}]
                )
                
                assert response1.content, "第一次调用失败"
                assert response2.content, "第二次调用失败"
                
                print(f"\n✅ 调用 1: {response1.content[:50]}")
                print(f"✅ 调用 2: {response2.content[:50]}")
                print(f"💡 连接池自动复用和释放")
            
            self.log_result("上下文管理器", True)
            
        except Exception as e:
            self.log_result("上下文管理器", False, str(e))
            print(f"❌ 错误: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("🚀 DeepSeek LLM Client 核心功能测试")
        print("="*60)
        print(f"Provider: {self.provider}")
        print(f"Models: deepseek-chat, deepseek-reasoner")
        print("="*60)
        
        # 运行所有测试
        self.test_basic_chat()
        self.test_reasoner_thinking()
        self.test_streaming()
        self.test_async_call()
        self.test_async_streaming()
        self.test_async_batch()
        self.test_context_manager()
        
        # 汇总结果
        print("\n" + "="*60)
        print("📊 测试结果汇总")
        print("="*60)
        
        passed = sum(1 for _, p, _ in self.test_results if p)
        total = len(self.test_results)
        
        for name, passed_flag, message in self.test_results:
            status = "✅" if passed_flag else "❌"
            print(f"{status} {name}")
            if message and not passed_flag:
                print(f"   {message}")
        
        print("\n" + "="*60)
        print(f"总计: {passed}/{total} 通过")
        print("="*60)


def main():
    """主函数"""
    tester = TestDeepSeekClient()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
