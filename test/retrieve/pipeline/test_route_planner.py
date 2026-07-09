#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_route_planner.py
@Date    : 2026/04/08
@Function:
    测试 2: Phase 1 — LLM₁ 路由规划器联调（全真实调用，无 mock）

    - 用例 2.1–2.4: 真实 LLM（config/config.toml [llm.presets.test] + LiteLLM Proxy）调用 RoutePlanner.plan()
    - 用例 2.5: 直接调用 _parse_plan，传入多种非法文本，验证抛出异常
    - 用例 2.6: 直接调用 _validate_plan，构造含幻觉路由的 RoutePlan，验证过滤与回退

    运行: python test/retrieve/pipeline/test_route_planner.py
    配置: ``config/config.toml`` → ``[llm.presets.test]``；Proxy 凭据见 ``.env``

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# ---------------------------------------------------------------------------
# 用例查询（与 Pipeline真实链路测试清单 一致）
# ---------------------------------------------------------------------------

QUERIES = {
    "2.1": "STM32G030C6 的 Flash 容量和最大主频",
    "2.2": "请概述知识蒸馏的核心方法",
    "2.3": "什么是 RAG？",
    "2.4": "它的性能怎么样？",
}


def _indent_block(text: str, prefix: str = "  ") -> str:
    """每行前加前缀，便于与控制台缩进对齐。"""
    if not text.strip():
        return prefix + "(空)\n"
    return "".join(f"{prefix}{line}\n" for line in text.rstrip().splitlines())


def format_route_plan_pretty(plan) -> str:
    """将 RoutePlan 序列化为可读的多行 JSON。"""
    data = plan.model_dump(mode="json")
    return json.dumps(data, ensure_ascii=False, indent=2)


def print_section(title: str, body: str) -> None:
    """带标题的分块输出，标题与正文之间换行。"""
    print(f"\n  ── {title} ──")
    print(_indent_block(body, prefix="    "))


def print_llm_text_preview(label: str, content: Optional[str], max_chars: int = 1200) -> None:
    """打印 LLM 返回文本：尽量格式化为 JSON，否则按行缩进。"""
    print(f"\n  ── {label} ──")
    if content is None or not str(content).strip():
        print("    (空)")
        return
    raw = str(content).strip()
    if len(raw) > max_chars:
        raw = raw[:max_chars] + f"\n    … (截断，共 {len(content)} 字符)"

    # 尝试解析为 JSON 并美化
    try_json = raw
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if m:
        try_json = m.group(1).strip()
    try:
        obj = json.loads(try_json)
        pretty = json.dumps(obj, ensure_ascii=False, indent=2)
        print(_indent_block(pretty, prefix="    "))
    except (json.JSONDecodeError, TypeError):
        print(_indent_block(raw, prefix="    "))


def _validate_route_plan_structure(
    plan,
    registry,
) -> Tuple[bool, List[str]]:
    """清单「每个用例的验证项」— 结构硬断言。"""
    errs: List[str] = []

    if plan is None:
        return False, ["RoutePlan 为 None"]

    qa = plan.query_analysis
    if not (qa.intent or "").strip():
        errs.append("query_analysis.intent 为空")

    if len(plan.route_plan) < 2:
        errs.append(f"route_plan 长度应 >= 2，实际 {len(plan.route_plan)}")

    if plan.rerank_top_n <= 0 or plan.rerank_top_n > 200:
        errs.append(
            f"rerank_top_n 应在 (0, 200]，实际 {plan.rerank_top_n}",
        )

    for i, rc in enumerate(plan.route_plan):
        if rc.top_k <= 0:
            errs.append(f"route_plan[{i}].top_k 应 > 0，实际 {rc.top_k}")
        if not registry.has(rc.route):
            errs.append(f"未注册路由: {rc.route}")

    for rc in plan.route_plan:
        if rc.route == "exact_match":
            kws = rc.params.get("keywords") if rc.params else None
            if not kws:
                errs.append("exact_match 路由存在但 params.keywords 为空")

    return len(errs) == 0, errs


def _scenario_hints(case_id: str, route_names: Set[str]) -> List[str]:
    """业务预期：仅生成提示文案，不作为硬失败依据。"""
    hints: List[str] = []
    if case_id == "2.1":
        if "exact_match" not in route_names:
            hints.append("预期含 exact_match（专有名词），当前未出现")
        if "chunk_dense" not in route_names:
            hints.append("预期含 chunk_dense，当前未出现")
        if "bm25_sparse" not in route_names:
            hints.append("预期含 bm25_sparse，当前未出现")
    elif case_id == "2.2":
        if "section_dense" not in route_names and "section_summary_dense" not in route_names and "file_summary_dense" not in route_names:
            hints.append("预期含 section_dense / section_summary_dense / file_summary_dense（主题探索），当前均未出现")
    elif case_id == "2.3":
        if "qa_dense" not in route_names:
            hints.append("预期含 qa_dense（问答型），当前未出现")
    elif case_id == "2.4":
        if "enhanced_chunk_dense" not in route_names:
            hints.append("预期含 enhanced_chunk_dense（代词/上下文），当前未出现")
    return hints


def print_llm_client_info() -> None:
    """打印当前 LLM 客户端解析到的配置（便于核对 config / 模型）。"""
    try:
        from src.client.llm import create_llm_client_from_preset

        c = create_llm_client_from_preset("test")
        print("  当前 LLM 客户端 (test preset):")
        print(f"    provider:   {c.provider}")
        print(f"    model:      {c.model_name}")
        print(f"    api_base:   {c.api_base}")
    except Exception as e:
        print(f"  ⚠️ 无法读取 LLMClient 配置: {e}")


async def check_llm_reachable() -> bool:
    """真实 HTTP 调用：最小请求验证连通性。"""
    try:
        from src.client.llm import create_llm_client_from_preset

        client = create_llm_client_from_preset("test")
        resp = await client.agenerate(
            messages=[
                {"role": "user", "content": '只回复 JSON: {"ok": true}'},
            ],
            temperature=0.0,
            max_tokens=64,
        )
        ok = bool(resp and (resp.content or "").strip())
        if ok:
            print("  ✅ LLM: agenerate 调用成功，content 非空")
            print_llm_text_preview("连通性检查 · LLM 原始 content", getattr(resp, "content", None))
        else:
            print("  ❌ LLM: 响应 content 为空")
        return ok
    except Exception as e:
        print(f"  ❌ LLM: {e}")
        traceback.print_exc()
        return False


async def run_case_llm(
    case_id: str,
    query: str,
    planner,
    registry,
) -> Tuple[bool, List[str]]:
    """真实调用 plan() 并做结构校验 + 预期提示。"""
    print(f"\n{'='*60}")
    print(f"  用例 {case_id}  Query: {query}")
    print(f"{'='*60}")

    try:
        t0 = time.perf_counter()
        plan = await planner.plan(
            query_text=query,
            filters=None,
            top_k=10,
            route_hints=None,
        )
        elapsed = (time.perf_counter() - t0) * 1000
    except Exception as e:
        print(f"  ❌ RoutePlanner.plan 异常: {e}")
        traceback.print_exc()
        return False, [str(e)]

    routes = [r.route for r in plan.route_plan]
    raw = getattr(planner, "last_llm_raw_text", None)
    if raw:
        print_llm_text_preview("LLM 原始响应（解析前）", raw)

    print(f"\n  耗时: {elapsed:.0f}ms")
    print_section("RoutePlan（解析后 · JSON）", format_route_plan_pretty(plan))
    print(f"\n  路由一览: {', '.join(routes)}  |  rerank_top_n={plan.rerank_top_n}")

    ok, errs = _validate_route_plan_structure(plan, registry)
    if not ok:
        print("  ❌ 结构校验失败:")
        for e in errs:
            print(f"     - {e}")
        return False, errs

    hints = _scenario_hints(case_id, set(routes))
    if hints:
        print("  ⚠️  业务预期提示（非失败条件）:")
        for h in hints:
            print(f"     - {h}")
    else:
        print("  ✅ 业务预期路由与清单一致（或已覆盖）")

    print(f"\n  ✅ 用例 {case_id} 结构校验通过")
    return True, []


def run_case_2_5(planner) -> Tuple[bool, List[str]]:
    """用例 2.5: LLM 返回非 JSON → _parse_plan 应抛异常。

    直接调用 _parse_plan，传入多种非法文本，验证每种都能正确抛出 ValueError。
    """
    print(f"\n{'='*60}")
    print("  用例 2.5  _parse_plan 非 JSON 容错")
    print(f"{'='*60}")

    bad_inputs = [
        ("纯自然语言", "抱歉，我无法理解你的问题，请提供更多信息。"),
        ("空字符串", ""),
        ("残缺 JSON", '{ "query_analysis": { "intent": "factual"'),
        ("Markdown 非 JSON 块", "```\nthis is not json at all\n```"),
        ("含 JSON 关键字但结构错误", '{"route_plan": [invalid]}'),
    ]

    errs: List[str] = []
    for label, text in bad_inputs:
        try:
            planner._parse_plan(text)
            msg = f"输入「{label}」未抛异常，预期应抛出 ValueError"
            print(f"  ❌ {msg}")
            errs.append(msg)
        except (ValueError, Exception) as e:
            print(f"  ✅ 输入「{label}」→ 正确抛出 {type(e).__name__}: {e}")

    if errs:
        return False, errs
    print(f"\n  ✅ 用例 2.5 全部通过（{len(bad_inputs)} 种非法输入均正确抛异常）")
    return True, []


def run_case_2_6(planner, registry) -> Tuple[bool, List[str]]:
    """用例 2.6: _validate_plan 过滤无效路由 / 全部无效时回退默认。

    直接调用 _validate_plan，构造含幻觉路由名的 RoutePlan，验证过滤与回退逻辑。
    """
    from src.retrieve.pipeline.types import QueryAnalysis, RouteConfig, RoutePlan

    print(f"\n{'='*60}")
    print("  用例 2.6  _validate_plan 无效路由过滤")
    print(f"{'='*60}")

    errs: List[str] = []

    # ── 场景 A: 部分路由无效 → 仅保留有效路由 ──
    print("\n  ── 场景 A: 部分路由无效 ──")
    plan_a = RoutePlan(
        query_analysis=QueryAnalysis(intent="factual"),
        route_plan=[
            RouteConfig(route="chunk_dense", top_k=20),
            RouteConfig(route="graph_explore", top_k=20),      # 幻觉路由
            RouteConfig(route="bm25_sparse", top_k=20),
            RouteConfig(route="knowledge_graph", top_k=15),     # 幻觉路由
        ],
        rerank_top_n=50,
    )
    validated_a = planner._validate_plan(plan_a, top_k=10)
    valid_names_a = [r.route for r in validated_a.route_plan]
    print(f"    输入路由: chunk_dense, graph_explore, bm25_sparse, knowledge_graph")
    print(f"    过滤后:   {valid_names_a}")

    if set(valid_names_a) != {"chunk_dense", "bm25_sparse"}:
        msg = f"场景 A: 预期保留 chunk_dense + bm25_sparse，实际 {valid_names_a}"
        print(f"  ❌ {msg}")
        errs.append(msg)
    else:
        print("  ✅ 场景 A: 幻觉路由被正确过滤，有效路由保留")

    # ── 场景 B: 全部路由无效 → 回退默认两路 ──
    print("\n  ── 场景 B: 全部路由无效 ──")
    plan_b = RoutePlan(
        query_analysis=QueryAnalysis(intent="exploratory"),
        route_plan=[
            RouteConfig(route="graph_explore", top_k=20),
            RouteConfig(route="non_existent", top_k=15),
            RouteConfig(route="hallucinated_route", top_k=10),
        ],
        rerank_top_n=50,
    )
    validated_b = planner._validate_plan(plan_b, top_k=10)
    valid_names_b = {r.route for r in validated_b.route_plan}
    print(f"    输入路由: graph_explore, non_existent, hallucinated_route")
    print(f"    回退后:   {sorted(valid_names_b)}")

    if valid_names_b != {"chunk_dense", "bm25_sparse"}:
        msg = f"场景 B: 预期回退 chunk_dense + bm25_sparse，实际 {sorted(valid_names_b)}"
        print(f"  ❌ {msg}")
        errs.append(msg)
    else:
        print("  ✅ 场景 B: 全部无效路由 → 正确回退默认两路")

    # ── 场景 C: 回退路由的 top_k 与传入 top_k 挂钩 ──
    print("\n  ── 场景 C: 回退路由 top_k 正确性 ──")
    for tk in (5, 10, 20):
        plan_c = RoutePlan(
            query_analysis=QueryAnalysis(intent="test"),
            route_plan=[RouteConfig(route="fake_route", top_k=99)],
            rerank_top_n=50,
        )
        validated_c = planner._validate_plan(plan_c, top_k=tk)
        expected_top_k = tk * 3
        actual_top_ks = [r.top_k for r in validated_c.route_plan]
        if all(t == expected_top_k for t in actual_top_ks):
            print(f"    top_k={tk} → 回退路由 top_k={actual_top_ks} ✅")
        else:
            msg = f"场景 C: top_k={tk} 时回退路由 top_k 应为 {expected_top_k}，实际 {actual_top_ks}"
            print(f"    ❌ {msg}")
            errs.append(msg)

    # ── 场景 D: 全部路由有效 → 不做任何过滤 ──
    print("\n  ── 场景 D: 全部路由有效（不应被过滤）──")
    plan_d = RoutePlan(
        query_analysis=QueryAnalysis(intent="factual"),
        route_plan=[
            RouteConfig(route="chunk_dense", top_k=20),
            RouteConfig(route="bm25_sparse", top_k=20),
            RouteConfig(route="section_dense", top_k=15),
        ],
        rerank_top_n=50,
    )
    validated_d = planner._validate_plan(plan_d, top_k=10)
    valid_names_d = [r.route for r in validated_d.route_plan]
    if valid_names_d == ["chunk_dense", "bm25_sparse", "section_dense"]:
        print(f"    路由保持不变: {valid_names_d} ✅")
    else:
        msg = f"场景 D: 全部有效路由不应被过滤，实际 {valid_names_d}"
        print(f"  ❌ {msg}")
        errs.append(msg)

    if errs:
        return False, errs
    print(f"\n  ✅ 用例 2.6 全部通过（4 个场景）")
    return True, []


def write_report(
    results: List[Tuple[str, bool]],
    out: Path,
    elapsed_s: float,
) -> None:
    lines = [
        "# RoutePlanner 联调 — 测试报告",
        "",
        f"- **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **脚本**: `test/retrieve/pipeline/test_route_planner.py`",
        f"- **说明**: 自动化 2.1–2.6（2.1–2.4 真实 LLM；2.5/2.6 直接方法调用验证容错逻辑）",
        f"- **总耗时**: {elapsed_s:.1f}s",
        "",
        "| 用例 | 结果 |",
        "|------|------|",
    ]
    for name, ok in results:
        lines.append(f"| {name} | {'通过' if ok else '失败'} |")
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n📄 报告已写入: {out}")


async def main() -> int:
    print("=" * 60)
    print("  Pipeline 真实链路测试 — 测试 2: LLM₁ RoutePlanner（无 mock）")
    print("=" * 60)

    print("\n── 模型配置（config.toml [llm.presets.test]）──")
    print_llm_client_info()

    print("\n── LLM 连通性（真实请求）──")
    if not await check_llm_reachable():
        print("\n❌ LLM 不可用，请检查 config/config.toml [llm]、.env LITELLM_PROXY_* 与网络后重试")
        return 1

    from src.client.llm import create_llm_client_from_preset
    from src.retrieve.pipeline.route_registry import RouteRegistry
    from src.retrieve.planner.route_planner import RoutePlanner

    registry = RouteRegistry()
    planner = RoutePlanner(
        registry=registry,
        llm_client=create_llm_client_from_preset("test"),
    )

    t_all = time.perf_counter()
    results: List[Tuple[str, bool]] = []

    for cid, q in QUERIES.items():
        ok, _ = await run_case_llm(cid, q, planner, registry)
        results.append((f"{cid} LLM 规划", ok))

    # 用例 2.5: _parse_plan 非 JSON 容错
    ok_25, _ = run_case_2_5(planner)
    results.append(("2.5 非 JSON 容错", ok_25))

    # 用例 2.6: _validate_plan 无效路由过滤
    ok_26, _ = run_case_2_6(planner, registry)
    results.append(("2.6 无效路由过滤", ok_26))

    elapsed = time.perf_counter() - t_all
    passed = sum(1 for _, o in results if o)
    total = len(results)

    print("\n" + "=" * 60)
    print(f" 自动化汇总（2.1–2.6）: {passed}/{total} 通过, {elapsed:.1f}s")
    print("=" * 60)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")

    write_report(
        results,
        project_root / "test" / "retrieve" / "pipeline" / "route_planner_test_report.md",
        elapsed,
    )

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
