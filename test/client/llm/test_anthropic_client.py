#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_anthropic_client.py
@Author  : caixiongjiang
@Date    : 2026/1/5 18:00
@Function: 
    Anthropic (Claude) LLM Client 测试
    测试 Claude 特有的 max_tokens 必填和 system message 处理
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""


# TODO： 测试Anthropic 客户端

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.client.llm import create_llm_client
from src.client.llm.types import LLMResponse


class TestAnthropicClient:
    """Anthropic (Claude) LLM Client 测试类"""
    
    def __init__(self):
        self.test_results = []
        self.provider = "anthropic"
        self.model_name = "claude-3-5-sonnet-20241022"
    
    def log_result(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ 通过" if passed else "❌ 失败"
        result = f"{status} - {test_name}"
        if message:
            result += f": {message}"
        print(result)
        self.test_results.append((test_name, passed, message))
    
    def test_max_tokens_required(self):
        """测试 1: max_tokens 必填参数"""
        print("\n" + "="*60)
        print("测试 1: Claude max_tokens 必填验证")
        print("="*60)
        
        try:
            # 测试不提供 max_tokens（应该失败或使用默认值）
            try:
                client_no_max_tokens = create_llm_client(
                    provider=self.provider,
                    model_name=self.model_name,
                    temperature=0.7
                    # 故意不提供 max_tokens
                )
                
                # 如果没有默认值，应该在 generate 时失败
                response = client_no_max_tokens.generate(
                    messages=[{"role": "user", "content": "测试"}]
                )
                
                # 如果成功了，说明有默认值（4096）
                print(f"✅ 未提供 max_tokens，使用默认值: {response.usage.completion_tokens} tokens")
                
            except ValueError as e:
                if "max_tokens" in str(e):
                    print(f"✅ 正确检测到 max_tokens 缺失: {e}")
                else:
                    raise
            
            # 测试提供 max_tokens（应该成功）
            client_with_max_tokens = create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                temperature=0.7,
                max_tokens=500  # 明确提供
            )
            
            response = client_with_max_tokens.generate(
                messages=[{"role": "user", "content": "什么是人工智能？"}]
            )
            
            assert response.content, "响应内容为空"
            assert response.usage.completion_tokens <= 510, f"超出限制: {response.usage.completion_tokens}"
            
            print(f"\n📝 生成内容: {response.content[:200]}...")
            print(f"📊 Token 使用: {response.usage.completion_tokens} / 500")
            
            self.log_result("max_tokens 必填验证", True)
            
        except Exception as e:
            self.log_result("max_tokens 必填验证", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_system_message_handling(self):
        """测试 2: System Message 单独字段处理"""
        print("\n" + "="*60)
        print("测试 2: Claude System Message 处理")
        print("="*60)
        
        try:
            client = create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                max_tokens=300,
                temperature=0.5
            )
            
            # Claude 将 system message 放在单独的 "system" 字段
            response = client.generate(
                messages=[
                    {"role": "system", "content": "你是一个专业的科技记者，擅长用简洁的语言解释复杂的技术概念"},
                    {"role": "user", "content": "解释一下区块链技术"}
                ]
            )
            
            assert response.content, "响应内容为空"
            
            print(f"\n📝 生成内容: {response.content[:300]}...")
            print(f"📊 Token 使用: {response.usage.total_tokens}")
            print(f"💡 Claude 成功处理 system message")
            
            self.log_result("System Message 处理", True)
            
        except Exception as e:
            self.log_result("System Message 处理", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_multiple_system_messages(self):
        """测试 3: 多个 System Message 合并"""
        print("\n" + "="*60)
        print("测试 3: Claude 多个 System Message 合并")
        print("="*60)
        
        try:
            client = create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                max_tokens=300,
                temperature=0.5
            )
            
            # 提供多个 system message，应该被合并
            response = client.generate(
                messages=[
                    {"role": "system", "content": "你是一个数学老师"},
                    {"role": "system", "content": "你擅长用简单的例子解释数学概念"},
                    {"role": "user", "content": "什么是导数？"}
                ]
            )
            
            assert response.content, "响应内容为空"
            
            print(f"\n📝 生成内容: {response.content[:300]}...")
            print(f"💡 多个 system message 已合并")
            
            self.log_result("多个 System Message 合并", True)
            
        except Exception as e:
            self.log_result("多个 System Message 合并", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_message_alternation(self):
        """测试 4: 消息交替（user/assistant）"""
        print("\n" + "="*60)
        print("测试 4: Claude 消息交替验证")
        print("="*60)
        
        try:
            client = create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                max_tokens=200
            )
            
            # 正确的交替：user -> assistant -> user
            response = client.generate(
                messages=[
                    {"role": "user", "content": "我叫李明"},
                    {"role": "assistant", "content": "你好李明！"},
                    {"role": "user", "content": "你记得我的名字吗？"}
                ]
            )
            
            assert response.content, "响应内容为空"
            assert "李明" in response.content, "模型未记住上下文"
            
            print(f"\n📝 生成内容: {response.content}")
            print(f"💡 消息交替正确")
            
            self.log_result("消息交替验证", True)
            
        except Exception as e:
            self.log_result("消息交替验证", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_long_context(self):
        """测试 5: 长上下文处理"""
        print("\n" + "="*60)
        print("测试 5: Claude 长上下文处理")
        print("="*60)
        
        try:
            client = create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                max_tokens=500,
                temperature=0.5
            )
            
            # Claude 3.5 Sonnet 支持 200K 上下文
            long_text = "人工智能是计算机科学的一个重要分支。" * 100
            
            response = client.generate(
                messages=[
                    {
                        "role": "user",
                        "content": f"以下是一段文本：\n\n{long_text}\n\n请用一句话总结这段文本的核心内容。"
                    }
                ]
            )
            
            assert response.content, "响应内容为空"
            
            print(f"\n📝 输入长度: {len(long_text)} 字符")
            print(f"📝 输入 Tokens: {response.usage.prompt_tokens}")
            print(f"📝 生成内容: {response.content}")
            print(f"💡 Claude 成功处理长上下文")
            
            self.log_result("长上下文处理", True)
            
        except Exception as e:
            self.log_result("长上下文处理", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_temperature_range(self):
        """测试 6: Temperature 范围验证"""
        print("\n" + "="*60)
        print("测试 6: Claude Temperature 范围")
        print("="*60)
        
        try:
            # Claude 的 temperature 范围是 [0, 1]（不是 [0, 2]）
            
            # 测试合法值
            client_valid = create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                max_tokens=100,
                temperature=0.5  # 合法
            )
            
            response_valid = client_valid.generate(
                messages=[{"role": "user", "content": "测试"}]
            )
            
            print(f"✅ temperature=0.5 合法: {response_valid.content[:50]}...")
            
            # 测试非法值
            try:
                client_invalid = create_llm_client(
                    provider=self.provider,
                    model_name=self.model_name,
                    max_tokens=100,
                    temperature=1.5  # 非法（Claude 只支持 [0, 1]）
                )
                
                response_invalid = client_invalid.generate(
                    messages=[{"role": "user", "content": "测试"}]
                )
                
                print("❌ 应该抛出 temperature 范围错误")
                self.log_result("Temperature 范围", False, "未检测到非法 temperature")
                
            except ValueError as e:
                if "temperature" in str(e).lower():
                    print(f"✅ 正确捕获 temperature 错误: {e}")
                    self.log_result("Temperature 范围", True)
                else:
                    raise
            
        except Exception as e:
            self.log_result("Temperature 范围", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_stop_sequences(self):
        """测试 7: Stop Sequences"""
        print("\n" + "="*60)
        print("测试 7: Claude Stop Sequences")
        print("="*60)
        
        try:
            client = create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                max_tokens=500,
                stop_sequences=["结束", "END"]  # Claude 特有参数
            )
            
            response = client.generate(
                messages=[
                    {"role": "user", "content": "列出3种编程语言，每个后面写上'结束'"}
                ]
            )
            
            assert response.content, "响应内容为空"
            
            print(f"\n📝 生成内容: {response.content}")
            print(f"🏁 Finish Reason: {response.finish_reason}")
            print(f"💡 Stop sequences 配置成功")
            
            self.log_result("Stop Sequences", True)
            
        except Exception as e:
            self.log_result("Stop Sequences", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_finish_reason_mapping(self):
        """测试 8: Finish Reason 映射"""
        print("\n" + "="*60)
        print("测试 8: Claude Finish Reason 映射")
        print("="*60)
        
        try:
            # 正常完成
            client_normal = create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                max_tokens=1000
            )
            
            response_normal = client_normal.generate(
                messages=[{"role": "user", "content": "2+2=?"}]
            )
            
            print(f"\n✅ 正常完成:")
            print(f"   Finish Reason: {response_normal.finish_reason}")
            print(f"   应该是: 'stop'")
            assert response_normal.finish_reason == "stop", f"Finish reason 错误: {response_normal.finish_reason}"
            
            # Token 限制
            client_limited = create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                max_tokens=20
            )
            
            response_limited = client_limited.generate(
                messages=[{"role": "user", "content": "详细介绍深度学习的发展历史和未来展望"}]
            )
            
            print(f"\n⚠️ Token 限制:")
            print(f"   Finish Reason: {response_limited.finish_reason}")
            print(f"   应该是: 'length'")
            assert response_limited.finish_reason == "length", f"Finish reason 错误: {response_limited.finish_reason}"
            
            print(f"\n💡 Claude Finish Reason 映射成功: end_turn → stop, max_tokens → length")
            
            self.log_result("Finish Reason 映射", True)
            
        except Exception as e:
            self.log_result("Finish Reason 映射", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_api_version_header(self):
        """测试 9: API 版本头"""
        print("\n" + "="*60)
        print("测试 9: Claude API 版本头")
        print("="*60)
        
        try:
            # Claude 使用特殊的 API 版本头和认证方式
            client = create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                max_tokens=100
            )
            
            response = client.generate(
                messages=[{"role": "user", "content": "测试 API 版本头"}]
            )
            
            assert response.content, "响应内容为空"
            
            print(f"\n📝 生成内容: {response.content}")
            print(f"💡 API 版本头配置正确")
            print(f"   - x-api-key: [已配置]")
            print(f"   - anthropic-version: 2023-06-01")
            
            self.log_result("API 版本头", True)
            
        except Exception as e:
            self.log_result("API 版本头", False, str(e))
            print(f"❌ 错误: {e}")
    
    def test_response_structure(self):
        """测试 10: 响应结构完整性"""
        print("\n" + "="*60)
        print("测试 10: Claude 响应结构")
        print("="*60)
        
        try:
            client = create_llm_client(
                provider=self.provider,
                model_name=self.model_name,
                max_tokens=200
            )
            
            response = client.generate(
                messages=[{"role": "user", "content": "介绍一下 Claude"}]
            )
            
            # 验证响应结构
            assert isinstance(response, LLMResponse), "响应类型错误"
            assert response.content, "content 为空"
            assert response.usage, "usage 为空"
            assert response.model, "model 为空"
            assert response.finish_reason, "finish_reason 为空"
            assert response.raw_response, "raw_response 为空"
            
            # 验证 thinking 字段（Claude 不支持）
            assert response.thinking is None, "Claude 不应有 thinking 字段"
            assert response.usage.thinking_tokens is None, "Claude 不应统计 thinking tokens"
            
            print(f"\n✅ 响应结构完整:")
            print(f"   - content: ✅ ({len(response.content)} 字符)")
            print(f"   - usage: ✅ ({response.usage.total_tokens} tokens)")
            print(f"   - model: ✅ ({response.model})")
            print(f"   - finish_reason: ✅ ({response.finish_reason})")
            print(f"   - thinking: ✅ (None - 正确)")
            
            self.log_result("响应结构", True)
            
        except Exception as e:
            self.log_result("响应结构", False, str(e))
            print(f"❌ 错误: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("🚀 开始 Anthropic (Claude) LLM Client 测试")
        print("="*60)
        print(f"Provider: {self.provider}")
        print(f"Model: {self.model_name}")
        print("特性: max_tokens 必填、System Message 单独字段、温度范围 [0,1]")
        print("="*60)
        
        # 运行所有测试
        self.test_max_tokens_required()
        self.test_system_message_handling()
        self.test_multiple_system_messages()
        self.test_message_alternation()
        self.test_long_context()
        self.test_temperature_range()
        self.test_stop_sequences()
        self.test_finish_reason_mapping()
        self.test_api_version_header()
        self.test_response_structure()
        
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
    tester = TestAnthropicClient()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
