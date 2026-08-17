#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
全量模型 LiteLLM 适配性与能力矩阵自动化测试
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.client.embedding import EmbeddingClient
from src.client.llm.client import create_llm_client, create_llm_client_from_preset
from src.client.llm.registry import get_litellm_registry
from src.client.reranker import RerankerClient
from src.utils.config_manager import get_config_manager
from src.utils.env_manager import get_env_manager

VALID_RED_PNG_B64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAfElEQVR4nNXOQREAMAjAsK7+PTMRPLhGQd7QJnESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ES53Vg6wNShQF/fRSLfgAAAABJRU5ErkJggg=="

WEATHER_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市当前的天气和气温",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称，例如 '北京', '上海'"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"},
            },
            "required": ["city"],
        },
    },
}

class ModelTestResult:
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.tests: Dict[str, Dict[str, Any]] = {}

    def record(self, test_name: str, passed: bool, detail: str = "", cost_ms: float = 0.0, extra: Any = None):
        self.tests[test_name] = {
            "passed": passed,
            "detail": detail,
            "cost_ms": round(cost_ms, 1),
            "extra": extra,
        }

    @property
    def all_passed(self) -> bool:
        return all(t["passed"] for t in self.tests.values())


async def test_llm_model(model_name: str, registry_info: Any) -> ModelTestResult:
    full_model_id = f"litellm_proxy/{model_name}"
    res = ModelTestResult(model_name)
    print(f"\n{'='*70}\n🚀 开始测试模型: {model_name} (ID: {full_model_id})\n{'='*70}")

    # 使用工厂方法 create_llm_client 自动注入 proxy 环境变量 api_base / api_key
    client = create_llm_client(
        model=full_model_id,
        temperature=0.1,
        max_tokens=1024,
        timeout=60.0,
    )

    # 1. 基础对话生成
    t0 = time.perf_counter()
    try:
        resp = await client.agenerate([{"role": "user", "content": "请回答：1+1等于几？用一句话简短回答。"}])
        cost = (time.perf_counter() - t0) * 1000
        content = (resp.content or "").strip()
        thinking = resp.thinking.reasoning.strip() if resp.thinking else ""
        passed = bool(content or thinking)
        detail = f"输出: '{content[:50]}...'" if len(content) > 50 else f"输出: '{content}'"
        if thinking:
            detail += f" (含思考 {len(thinking)} 字)"
        res.record("1.基础对话", passed, detail, cost)
        print(f"  {'✅' if passed else '❌'} 1.基础对话: {detail} ({cost:.1f}ms)")
    except Exception as e:
        cost = (time.perf_counter() - t0) * 1000
        res.record("1.基础对话", False, f"异常: {e}", cost)
        print(f"  ❌ 1.基础对话失败: {e} ({cost:.1f}ms)")

    # 2. 异步流式输出
    t0 = time.perf_counter()
    try:
        collected_chunks = []
        collected_thinking = []
        finish_reason = None
        async for chunk in client.astream([{"role": "user", "content": "请输出：A B C D E"}]):
            if chunk.delta:
                if chunk.is_thought:
                    collected_thinking.append(chunk.delta)
                else:
                    collected_chunks.append(chunk.delta)
            if chunk.finish_reason:
                finish_reason = chunk.finish_reason
        cost = (time.perf_counter() - t0) * 1000
        full_text = "".join(collected_chunks).strip()
        full_thinking = "".join(collected_thinking).strip()
        passed = len(collected_chunks) > 0 or len(collected_thinking) > 0
        detail = f"{len(collected_chunks)} chunks, 文本: '{full_text[:40]}', finish={finish_reason}"
        if full_thinking:
            detail += f" (思考 {len(full_thinking)} 字)"
        res.record("2.流式输出", passed, detail, cost)
        print(f"  {'✅' if passed else '❌'} 2.流式输出: {detail} ({cost:.1f}ms)")
    except Exception as e:
        cost = (time.perf_counter() - t0) * 1000
        res.record("2.流式输出", False, f"异常: {e}", cost)
        print(f"  ❌ 2.流式输出失败: {e} ({cost:.1f}ms)")

    # 3. 思考强度测试
    supported_levels = getattr(registry_info, "thinking_levels", [])
    if getattr(registry_info, "supports_thinking", False):
        for lvl in ["off", "low", "medium", "high"]:
            if lvl not in supported_levels:
                continue
            t0 = time.perf_counter()
            try:
                spec = registry_info.thinking_spec if hasattr(registry_info, "thinking_spec") else None
                effort = spec.resolve_reasoning_effort(lvl) if spec else (None if lvl == "off" else lvl)
                resp = await client.agenerate(
                    [{"role": "user", "content": "9.11 和 9.9 哪个大？请简要说明理由。"}],
                    reasoning_effort=effort,
                )
                cost = (time.perf_counter() - t0) * 1000
                thinking_text = resp.thinking.reasoning if resp.thinking else ""
                thinking_len = len(thinking_text)
                
                if lvl == "off":
                    passed = True
                    detail = f"off档位(effort={effort}): content={len(resp.content)}字, thinking={thinking_len}字"
                else:
                    passed = bool(resp.content or thinking_text)
                    detail = f"{lvl}档位(effort='{effort}'): content={len(resp.content)}字, thinking={thinking_len}字"

                res.record(f"3.思考-{lvl}", passed, detail, cost)
                print(f"  {'✅' if passed else '❌'} 3.思考强度[{lvl}]: {detail} ({cost:.1f}ms)")
            except Exception as e:
                cost = (time.perf_counter() - t0) * 1000
                res.record(f"3.思考-{lvl}", False, f"异常: {e}", cost)
                print(f"  ❌ 3.思考强度[{lvl}]失败: {e} ({cost:.1f}ms)")
    else:
        res.record("3.思考能力", True, "模型声明不支持思考 (已跳过)", 0.0)
        print("  ℹ️ 3.思考能力: 模型声明不支持思考，跳过")

    # 4. 工具调用
    t0 = time.perf_counter()
    try:
        messages = [{"role": "user", "content": "请帮我调用工具查询上海今天的天气。"}]
        resp1 = await client.agenerate(
            messages,
            tools=[WEATHER_TOOL],
            tool_choice="auto",
        )
        cost1 = (time.perf_counter() - t0) * 1000
        has_tools = bool(resp1.tool_calls and len(resp1.tool_calls) > 0)
        if has_tools:
            tc = resp1.tool_calls[0]
            tc_name = tc.name
            tc_args = tc.arguments
            tool_result = json.dumps({"city": "上海", "weather": "晴朗", "temp": "25℃"}, ensure_ascii=False)
            
            asst_msg = {
                "role": "assistant",
                "content": resp1.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False) if isinstance(tc.arguments, dict) else str(tc.arguments),
                        },
                    }
                ],
            }
            messages.append(asst_msg)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc_name,
                "content": tool_result,
            })
            t1 = time.perf_counter()
            resp2 = await client.agenerate(messages)
            cost2 = (time.perf_counter() - t1) * 1000
            final_content = (resp2.content or "").strip()
            total_cost = (time.perf_counter() - t0) * 1000
            passed = bool(final_content)
            detail = f"触发工具 {tc_name}({tc_args}) -> 闭环回答: '{final_content[:40]}...'"
            res.record("4.工具调用", passed, detail, total_cost)
            print(f"  {'✅' if passed else '❌'} 4.工具调用闭环: {detail} ({total_cost:.1f}ms)")
        else:
            cost = (time.perf_counter() - t0) * 1000
            detail = f"模型未发起工具调用，直接回复: '{resp1.content[:40]}...'"
            res.record("4.工具调用", False, detail, cost)
            print(f"  ⚠️ 4.工具调用: {detail} ({cost:.1f}ms)")
    except Exception as e:
        cost = (time.perf_counter() - t0) * 1000
        res.record("4.工具调用", False, f"异常: {e}", cost)
        print(f"  ❌ 4.工具调用失败: {e} ({cost:.1f}ms)")

    # 5. 多模态视觉输入
    is_multimodal = getattr(registry_info, "supports_multimodal", False)
    t0 = time.perf_counter()
    try:
        mm_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": "这张图片的主色调是什么颜色？请简短回答。"},
                {"type": "image_url", "image_url": {"url": VALID_RED_PNG_B64}},
            ],
        }
        resp = await client.agenerate([mm_message])
        cost = (time.perf_counter() - t0) * 1000
        content = (resp.content or "").strip()
        thinking_text = resp.thinking.reasoning if resp.thinking else ""
        passed = bool(content or thinking_text)
        detail = f"识图响应: '{content[:40]}...'" if len(content) > 40 else f"识图响应: '{content}'"
        res.record("5.多模态识图", passed, detail, cost)
        print(f"  {'✅' if passed else '⚠️'} 5.多模态识图: {detail} (声明支持={is_multimodal}, {cost:.1f}ms)")
    except Exception as e:
        cost = (time.perf_counter() - t0) * 1000
        if is_multimodal:
            res.record("5.多模态识图", False, f"多模态模型报错: {e}", cost)
            print(f"  ❌ 5.多模态识图失败: {e} ({cost:.1f}ms)")
        else:
            res.record("5.多模态识图", True, f"非多模态模型拦截(预期内): {type(e).__name__}", cost)
            print(f"  ℹ️ 5.多模态识图(纯文本模型预期拦截): {type(e).__name__} ({cost:.1f}ms)")

    # 6. 结构化 JSON 提取
    t0 = time.perf_counter()
    try:
        prompt = "从文本中提取人名和年龄，并以合法 JSON 格式输出：{\"name\": string, \"age\": int}。文本：小明今年18岁。"
        resp = await client.agenerate([{"role": "user", "content": prompt}], response_format={"type": "json_object"})
        cost = (time.perf_counter() - t0) * 1000
        content = (resp.content or "").strip()
        try:
            parsed = json.loads(content)
            passed = isinstance(parsed, dict) and "name" in parsed
            detail = f"JSON解析成功: {parsed}"
        except Exception:
            passed = "小明" in content and "18" in content
            detail = f"文本包含正确信息但非严格JSON: '{content[:40]}'"
        res.record("6.结构化输出", passed, detail, cost)
        print(f"  {'✅' if passed else '❌'} 6.结构化输出: {detail} ({cost:.1f}ms)")
    except Exception as e:
        cost = (time.perf_counter() - t0) * 1000
        res.record("6.结构化输出", False, f"异常: {e}", cost)
        print(f"  ❌ 6.结构化输出失败: {e} ({cost:.1f}ms)")

    return res


async def test_embedding_model() -> ModelTestResult:
    model_name = "qwen3-embedding-0.6b"
    res = ModelTestResult(model_name)
    print(f"\n{'='*70}\n🚀 开始测试 Embedding 模型: {model_name}\n{'='*70}")

    try:
        client = EmbeddingClient()
        print(f"  Client Model: {client.model_name}, Dim: {client.dimension}, Batch: {client.batch_size}")

        # 单条测试
        t0 = time.perf_counter()
        vec = await client.aembed("人工智能与知识库检索系统")
        cost1 = (time.perf_counter() - t0) * 1000
        dim_ok = len(vec) == 1024
        res.record("1.单条向量化", dim_ok, f"维度={len(vec)}, 样例值=[{vec[0]:.4f}, {vec[1]:.4f}...]", cost1)
        print(f"  {'✅' if dim_ok else '❌'} 1.单条向量化: 维度={len(vec)} (期望 1024), 耗时 {cost1:.1f}ms")

        # 批量测试
        t0 = time.perf_counter()
        texts = [
            "向量数据库 Milvus 索引原理",
            "深度学习自然语言处理模型",
            "Agent 协同架构设计与实践",
        ]
        vecs = await client.aembed_batch(texts)
        cost2 = (time.perf_counter() - t0) * 1000
        batch_ok = len(vecs) == 3 and all(len(v) == 1024 for v in vecs)
        res.record("2.批量向量化", batch_ok, f"成功生成 {len(vecs)} 条 1024 维向量", cost2)
        print(f"  {'✅' if batch_ok else '❌'} 2.批量向量化: 批大小={len(vecs)}, 耗时 {cost2:.1f}ms")

        # 健康检查
        t0 = time.perf_counter()
        health = await client.ahealth_check()
        cost3 = (time.perf_counter() - t0) * 1000
        res.record("3.健康检查", health, f"status={'ok' if health else 'fail'}", cost3)
        print(f"  {'✅' if health else '❌'} 3.健康检查: {'OK' if health else 'FAIL'} ({cost3:.1f}ms)")

    except Exception as e:
        res.record("Embedding总体", False, f"异常: {e}", 0.0)
        print(f"  ❌ Embedding 测试失败: {e}")

    return res


async def test_reranker_model() -> ModelTestResult:
    model_name = "qwen3-reranker-0.6b"
    res = ModelTestResult(model_name)
    print(f"\n{'='*70}\n🚀 开始测试 Reranker 模型: {model_name}\n{'='*70}")

    try:
        client = RerankerClient()
        print(f"  Client Model: {client.model_name}, Top-K: {client.default_top_k}")

        query = "什么是深度学习？"
        docs = [
            "苹果公司今天发布了最新一代智能手机和配件产品。",
            "深度学习是机器学习的一个分支，基于人工神经网络对数据进行表征学习与特征提取。",
            "明天北京的天气预报显示有小雨，气温在15度左右。",
            "机器学习和深度神经网络近年来在计算机视觉与NLP领域取得了突破性进展。",
        ]

        t0 = time.perf_counter()
        results = await client.arerank(query=query, documents=docs, top_k=3)
        cost = (time.perf_counter() - t0) * 1000

        top_idx = results[0].index if results else -1
        top_score = results[0].score if results else -1.0
        passed = len(results) == 3 and top_idx in (1, 3)

        detail = f"Top1 Doc Index={top_idx} (Score={top_score:.4f}): '{results[0].text[:30]}...'"
        res.record("1.文档重排序", passed, detail, cost)
        print(f"  {'✅' if passed else '❌'} 1.文档重排序: {detail} ({cost:.1f}ms)")
        for i, r in enumerate(results):
            print(f"     Rank {i+1}: Doc #{r.index} (score={r.score:.4f}) -> '{r.text[:40]}'")

        # 健康检查
        t0 = time.perf_counter()
        health = await client.ahealth_check()
        cost_h = (time.perf_counter() - t0) * 1000
        res.record("2.健康检查", health, f"status={'ok' if health else 'fail'}", cost_h)
        print(f"  {'✅' if health else '❌'} 2.健康检查: {'OK' if health else 'FAIL'} ({cost_h:.1f}ms)")

    except Exception as e:
        res.record("Reranker总体", False, f"异常: {e}", 0.0)
        print(f"  ❌ Reranker 测试失败: {e}")

    return res


async def test_llm_presets() -> List[Dict[str, Any]]:
    print(f"\n{'='*70}\n🚀 开始测试 config.toml [llm.presets.*] 预设配置\n{'='*70}")
    cfg_mgr = get_config_manager()
    presets_cfg = cfg_mgr.get("llm.presets", {})
    results = []

    for preset_name, p_info in presets_cfg.items():
        model_str = p_info.get("model", "")
        t0 = time.perf_counter()
        try:
            client = create_llm_client_from_preset(preset_name)
            resp = await client.agenerate([{"role": "user", "content": "Hello! Reply 'OK'"}])
            cost = (time.perf_counter() - t0) * 1000
            content = (resp.content or "").strip()
            thinking_text = resp.thinking.reasoning if resp.thinking else ""
            passed = bool(content or thinking_text)
            detail = f"model={client.config.model}, effort={client.config.default_reasoning_effort}, resp='{content[:20]}'"
            print(f"  {'✅' if passed else '❌'} Preset [{preset_name}]: {detail} ({cost:.1f}ms)")
            results.append({"preset": preset_name, "passed": passed, "detail": detail, "cost_ms": cost})
        except Exception as e:
            cost = (time.perf_counter() - t0) * 1000
            print(f"  ❌ Preset [{preset_name}] (model={model_str}) 失败: {e} ({cost:.1f}ms)")
            results.append({"preset": preset_name, "passed": False, "detail": str(e), "cost_ms": cost})

    return results


async def main():
    print("=" * 80)
    print(" 🛠️  LiteLLM 全量模型适配与连通性综合评测")
    print("=" * 80)

    reg = get_litellm_registry()
    models = reg.list_models()
    print(f"\n📋 LiteLLM Proxy 注册的 Chat 模型数量: {len(models)}")
    for m in models:
        print(f"  - {m.id} (Thinking: {m.supports_thinking}, Multimodal: {m.supports_multimodal})")

    # 1. 测试所有 Chat 模型
    chat_results: List[ModelTestResult] = []
    for m in models:
        raw_name = m.id.replace("litellm_proxy/", "")
        res = await test_llm_model(raw_name, m)
        chat_results.append(res)

    # 2. 测试 Embedding 模型
    emb_res = await test_embedding_model()

    # 3. 测试 Reranker 模型
    rerank_res = await test_reranker_model()

    # 4. 测试 Presets
    preset_res = await test_llm_presets()

    # 汇总输出报告
    print("\n" + "=" * 80)
    print(" 📊 全量模型测试结果总览")
    print("=" * 80)

    print("\n【Chat / Reasoning / Vision LLM 模型矩阵】")
    header = f"{'模型名称':<22} | {'基础对话':<8} | {'流式输出':<8} | {'思考档位':<8} | {'工具调用':<8} | {'多模态':<8} | {'结构化':<8} | {'状态'}"
    print("-" * 90)
    print(header)
    print("-" * 90)

    for r in chat_results:
        t_basic = "✅" if r.tests.get("1.基础对话", {}).get("passed") else "❌"
        t_stream = "✅" if r.tests.get("2.流式输出", {}).get("passed") else "❌"
        
        thinking_tests = [v for k, v in r.tests.items() if k.startswith("3.思考")]
        t_think = "✅" if all(t["passed"] for t in thinking_tests) else ("⚠️" if any(t["passed"] for t in thinking_tests) else "❌")
        
        t_tool = "✅" if r.tests.get("4.工具调用", {}).get("passed") else "❌"
        t_mm = "✅" if r.tests.get("5.多模态识图", {}).get("passed") else "❌"
        t_json = "✅" if r.tests.get("6.结构化输出", {}).get("passed") else "❌"
        status = "🟢 全部适配" if r.all_passed else "🟡 部分未适配"

        row = f"{r.model_id:<20} | {t_basic:<8} | {t_stream:<8} | {t_think:<8} | {t_tool:<8} | {t_mm:<8} | {t_json:<8} | {status}"
        print(row)

    print("\n【专项模型（Embedding & Reranker）】")
    print(f"- Embedding ({emb_res.model_id}): {'🟢 适配正常 (1024维/批处理正常)' if emb_res.all_passed else '🔴 存在异常'}")
    for k, v in emb_res.tests.items():
        print(f"    * {k}: {'✅ 通过' if v['passed'] else '❌ 失败'} - {v['detail']} ({v['cost_ms']}ms)")

    print(f"- Reranker ({rerank_res.model_id}): {'🟢 适配正常 (重排打分正常)' if rerank_res.all_passed else '🔴 存在异常'}")
    for k, v in rerank_res.tests.items():
        print(f"    * {k}: {'✅ 通过' if v['passed'] else '❌ 失败'} - {v['detail']} ({v['cost_ms']}ms)")

    print("\n【LLM Presets 预设联动】")
    all_preset_pass = all(p["passed"] for p in preset_res)
    print(f"预设整体状态: {'🟢 全部预设通过' if all_preset_pass else '🔴 部分预设失败'}")
    for p in preset_res:
        print(f"  - [{p['preset']}]: {'✅' if p['passed'] else '❌'} {p['detail']} ({p['cost_ms']:.1f}ms)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
