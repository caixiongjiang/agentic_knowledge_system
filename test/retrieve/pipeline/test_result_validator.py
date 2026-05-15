#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_result_validator.py
@Date    : 2026/04/09
@Function:
    测试 3: Phase 6 — LLM₂ 结果验证 Agent 联调（全真实调用，无 mock）

    ResultValidator：显式多轮 + 每轮可并行多工具（bind_tools + asyncio.gather），
    与 LangGraph 内部步数无关。

    - 用例 3.1: 充分结果 → Agent 直接 pass（不调用工具）
    - 用例 3.2: 截断结果 → Agent 调用工具补全
    - 用例 3.3: 工具执行成功（补全 items 正确合并）
    - 用例 3.4: 多轮循环（Agent 多次调用工具后收敛）
    - 用例 3.5: max_rounds 上限控制

    运行: python test/retrieve/pipeline/test_result_validator.py
    前提: Milvus / MySQL / MongoDB / Embedding / Reranker / LLM 服务可达；
          至少一个知识库中有已索引文档。

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

TEST_QUERIES = {
    "spec_lookup": "FRT075-33F的保持电流和触发电流分别是多少？",
    "comparison": "FRT系列不同型号的最大电阻值有什么区别？",
    "application": "FRT系列可恢复保险丝适用于哪些应用场景？额定电压和工作温度范围是多少？",
    "material": "FRT系列保险丝的引脚材料和绝缘涂层分别是什么？符合哪些标准认证？",
    "dimension": "FRT075-33F的物理尺寸是多少？引脚线径是多少AWG？",
}
RECALL_TOP_K = 20
FINAL_TOP_K = 5

# 为 true 时打印验证器完整结论文本（调提示词建议打开）
PRINT_FULL_VALIDATOR_REASONING = True


# ---------------------------------------------------------------------------
# 格式化辅助
# ---------------------------------------------------------------------------


def _indent(text: str, prefix: str = "    ") -> str:
    if not text.strip():
        return prefix + "(空)\n"
    return "".join(f"{prefix}{line}\n" for line in text.rstrip().splitlines())


def print_section(title: str, body: str) -> None:
    print(f"\n  ── {title} ──")
    print(_indent(body))


def print_items_preview(items, label: str = "Items", max_items: int = 3) -> None:
    print(f"\n  ── {label} (共 {len(items)} 条) ──")
    for i, item in enumerate(items[:max_items]):
        text_preview = (item.text or "")[:60].replace("\n", " ")
        print(f'    #{i+1} [score={item.score:.4f}] chunk_id={item.chunk_id[:20]}  "{text_preview}..."')
    if len(items) > max_items:
        print(f"    ... 其余 {len(items) - max_items} 条省略")


def print_validation_result(result) -> None:
    print(f"\n  ── ValidationResult ──")
    print(f"    passed:                   {result.passed}")
    print(f"    rounds (LLM 调用次数):     {result.rounds}")
    adj = getattr(result, "adjustment_rounds", 0)
    print(f"    adjustment_rounds:        {adj}")
    print(f"    tool_calls_count:         {result.tool_calls_count}")
    print(f"    total_validation_time_ms: {result.total_validation_time_ms:.0f}ms")
    print(f"    supplemented_items:       {len(result.supplemented_items)} 条")
    if result.tool_calls_summary:
        print(f"    tool_calls_summary:")
        for tc in result.tool_calls_summary:
            print(f"      - {tc}")
    if result.reasoning:
        if PRINT_FULL_VALIDATOR_REASONING:
            print("    reasoning (全文):")
            print(_indent(result.reasoning, prefix="      "))
        else:
            print(f"    reasoning: {result.reasoning[:200]}...")


# ---------------------------------------------------------------------------
# 基础设施检查
# ---------------------------------------------------------------------------


def print_llm_config_info() -> None:
    try:
        from src.client.llm import create_llm_client_from_preset
        c = create_llm_client_from_preset("test")
        print("  当前 LLM 配置 (test preset):")
        print(f"    provider:   {c.provider}")
        print(f"    model:      {c.model_name}")
        print(f"    api_base:   {c.api_base}")
    except Exception as e:
        print(f"  ⚠️ 无法读取 LLM 配置: {e}")


def create_test_client():
    """从 test preset 创建 LiteLLM 客户端"""
    from src.client.llm import create_llm_client_from_preset

    c = create_llm_client_from_preset("test")
    print(f"  创建 LiteLLM 客户端: model={c.model}, api_base={c.api_base or '默认'}")
    return c


async def check_client_reachable(client) -> bool:
    """验证 LiteLLM 客户端是否可用"""
    try:
        resp = await client.agenerate(
            messages=[{"role": "user", "content": "回复 OK"}],
            temperature=0.0,
            max_tokens=32,
        )
        ok = bool(resp and (resp.content or "").strip())
        print(f"  {'✅' if ok else '❌'} LLM 连通性: {'成功' if ok else '失败'}")
        return ok
    except Exception as e:
        print(f"  ❌ LLM 连通性: {e}")
        return False


async def ensure_mongodb() -> bool:
    """确保 MongoDB 已初始化"""
    try:
        from src.db.mongodb.mongodb_manager import MongoDBManager
        await MongoDBManager.get_instance()
        print("  ✅ MongoDB: 连接成功")
        return True
    except Exception as e:
        print(f"  ❌ MongoDB: {e}")
        return False


async def load_chunk_texts(items: List) -> List:
    """为 text=None 的 ChunkItem 从 MongoDB 补充文本"""
    from src.db.mongodb.models.chunk_data import ChunkData

    for item in items:
        if item.text:
            continue
        try:
            doc = await ChunkData.find_one(
                {"chunk_id": item.chunk_id, "deleted": 0},
            )
            if doc and hasattr(doc, "chunk_text"):
                item.text = doc.chunk_text
        except Exception:
            pass
    return items


async def fetch_real_items(kb_id: Optional[str], query_text: str) -> List:
    """通过 retrieve_custom 获取真实 ChunkItem"""
    from src.retrieve.pipeline.types import RouteConfig
    from src.retrieve.types.query import MetadataFilter
    from src.service.knowledge.retrieve_service import RetrieveService

    service = RetrieveService()
    filters = MetadataFilter(knowledge_base_id=kb_id) if kb_id else MetadataFilter()

    response = await service.retrieve_custom(
        routes=[
            RouteConfig(route="chunk_dense", top_k=RECALL_TOP_K),
            RouteConfig(route="bm25_sparse", top_k=RECALL_TOP_K),
        ],
        query_text=query_text,
        filters=filters,
        top_k=FINAL_TOP_K,
        enable_rerank=True,
        enable_validation=False,
    )

    items = response.items
    empty_count = sum(1 for it in items if not it.text)
    if empty_count:
        print(f"  ⚠️ {empty_count}/{len(items)} 条 item text 为空，从 MongoDB 补充...")
        items = await load_chunk_texts(items)
        still_empty = sum(1 for it in items if not it.text)
        if still_empty:
            print(f"  ⚠️ 补充后仍有 {still_empty} 条无文本")
        else:
            print("  ✅ 文本补充完成")
    return items


def make_truncated_items(items: List) -> List:
    """将真实 items 的文本截断，构造"明显不完整"的结果"""
    truncated = []
    suffixes = [
        "…… 具体电气参数见下表：",
        "…… 详细规格参见产品规格书：",
        "…… 以下是各型号参数对比：",
        "…… 更多认证信息参考附录：",
        "…… 完整尺寸图如下所示：",
    ]
    for i, item in enumerate(items):
        copy = item.model_copy()
        original_text = copy.text or ""
        cut_point = min(60, len(original_text) // 3)
        copy.text = original_text[:cut_point] + suffixes[i % len(suffixes)]
        truncated.append(copy)
    return truncated


# ---------------------------------------------------------------------------
# 通用验证辅助
# ---------------------------------------------------------------------------


def validate_result_structure(
    items_out: List,
    result,
    case_id: str,
) -> Tuple[bool, List[str]]:
    """验证 ValidationResult 结构完整性"""
    from src.retrieve.pipeline.types import ValidationResult

    errs: List[str] = []

    if not isinstance(result, ValidationResult):
        errs.append(f"result 类型错误: {type(result)}")
        return False, errs

    if result.rounds < 1:
        errs.append(f"rounds 应 >= 1，实际 {result.rounds}")

    if result.total_validation_time_ms <= 0:
        errs.append(f"total_validation_time_ms 应 > 0，实际 {result.total_validation_time_ms}")

    if items_out is None:
        errs.append("返回 items 为 None")

    return len(errs) == 0, errs


# ---------------------------------------------------------------------------
# 用例 3.1: 充分结果 → Pass
# ---------------------------------------------------------------------------


async def test_3_1_pass(
    validator,
    items: List,
    query_text: str,
) -> Tuple[bool, List[str]]:
    """3.1: 完整结果 → Agent 应直接 pass，不触发工具调用"""
    print(f"\n{'='*60}")
    print(f"  用例 3.1  充分结果 → Pass")
    print(f"{'='*60}")
    print(f"  Query: {query_text}")
    print_items_preview(items, "输入 Items（完整文本）")

    try:
        t0 = time.perf_counter()
        items_out, result = await validator.validate(
            query_text=query_text,
            items=items,
            max_rounds=3,
        )
        elapsed = (time.perf_counter() - t0) * 1000
    except Exception as e:
        print(f"  ❌ validate() 异常: {e}")
        traceback.print_exc()
        return False, [str(e)]

    print(f"\n  耗时: {elapsed:.0f}ms")
    print_validation_result(result)

    ok, errs = validate_result_structure(items_out, result, "3.1")
    if not ok:
        print("  ❌ 结构校验失败:")
        for e in errs:
            print(f"     - {e}")
        return False, errs

    if result.passed and result.tool_calls_count == 0:
        print("  ✅ 判定 SUFFICIENT 且未调用工具（理想路径）")
    elif result.passed and result.tool_calls_count > 0:
        print(f"  ℹ️  判定 SUFFICIENT，经 {result.tool_calls_count} 次工具补全后收敛")
    else:
        print("  ℹ️  判定 INSUFFICIENT（结论文本与 [验证状态] 一致即可，非失败）")

    if result.rounds == 1:
        print("  ✅ 仅 1 次 LLM 调用即结束（无工具或首轮即结论文本）")
    else:
        adj = getattr(result, "adjustment_rounds", 0)
        print(
            f"  ℹ️  LLM 调用 {result.rounds} 次、工具调整批次数 {adj} "
            f"（max_rounds=3 时属正常）"
        )

    print(f"\n  ✅ 用例 3.1 结构校验通过")
    return True, []


# ---------------------------------------------------------------------------
# 用例 3.2-3.4: 截断结果 → Supplement → 工具执行 → 多轮收敛
# ---------------------------------------------------------------------------


async def test_3_2_3_3_3_4_supplement(
    validator,
    truncated_items: List,
    query_text: str,
) -> Tuple[bool, List[str]]:
    """3.2-3.4 联合测试:
    - 3.2: 截断文本 → Agent 调用工具补全
    - 3.3: 工具执行成功（补全 items 正确合并）
    - 3.4: 多轮循环（多次工具调用后收敛）
    """
    print(f"\n{'='*60}")
    print(f"  用例 3.2-3.4  截断结果 → Supplement → 工具执行 → 多轮收敛")
    print(f"{'='*60}")
    print(f"  Query: {query_text}")
    print_items_preview(truncated_items, "输入 Items（截断文本）")

    try:
        t0 = time.perf_counter()
        items_out, result = await validator.validate(
            query_text=query_text,
            items=truncated_items,
            max_rounds=3,
        )
        elapsed = (time.perf_counter() - t0) * 1000
    except Exception as e:
        print(f"  ❌ validate() 异常: {e}")
        traceback.print_exc()
        return False, [str(e)]

    print(f"\n  耗时: {elapsed:.0f}ms")
    print_validation_result(result)
    print_items_preview(items_out, "输出 Items（可能含补全）")

    ok, errs = validate_result_structure(items_out, result, "3.2-3.4")
    if not ok:
        print("  ❌ 结构校验失败:")
        for e in errs:
            print(f"     - {e}")
        return False, errs

    # ── 3.2 验证: Agent 是否调用了工具 ──
    if result.tool_calls_count > 0:
        print(f"  ✅ 3.2: Agent 调用了 {result.tool_calls_count} 次工具（符合预期）")
        for tc in result.tool_calls_summary[:5]:
            print(f"       {tc}")
    else:
        print("  ⚠️  3.2: Agent 未调用工具（截断文本未触发补全）")

    # ── 3.3 验证: 工具执行结果 ──
    if result.supplemented_items:
        print(f"  ✅ 3.3: 工具执行成功，补全了 {len(result.supplemented_items)} 个新 ChunkItem")
        for si in result.supplemented_items[:3]:
            text_preview = (si.text or "")[:50].replace("\n", " ")
            print(f"       chunk_id={si.chunk_id[:20]}, text=\"{text_preview}...\"")

        existing_ids = {item.chunk_id for item in truncated_items}
        new_ids = {si.chunk_id for si in result.supplemented_items}
        merged_ids = {item.chunk_id for item in items_out}

        if new_ids - existing_ids:
            print(f"  ✅ 3.3: 补全 items 去重合并正确 (新增 {len(new_ids - existing_ids)} 个)")
        else:
            print("  ⚠️  3.3: 补全 items 全部与原有重复")

        if new_ids.issubset(merged_ids):
            print("  ✅ 3.3: 补全 items 已正确合并到输出列表")
        else:
            missing = new_ids - merged_ids
            errs.append(f"3.3: 补全 items 未合并到输出: {missing}")
    elif result.tool_calls_count > 0:
        print("  ⚠️  3.3: 调用了工具但 supplemented_items 为空（工具可能未返回结果）")
    else:
        print("  ── 3.3: 未调用工具，跳过验证")

    # ── 3.4 验证: 多轮循环 ──
    adj = getattr(result, "adjustment_rounds", 0)
    if adj >= 2:
        print(f"  ✅ 3.4: 多轮调整生效，adjustment_rounds={adj}（含并行工具批次）")
        print(f"  ✅ 3.4: 多轮调整结束，最终 passed={result.passed}（见 reasoning 末行 [验证状态]）")
    elif result.tool_calls_count > 0:
        print("  ⚠️  3.4: 仅 1 轮工具调整（可能单轮内已并行多工具）")
    else:
        print("  ── 3.4: 未调用工具，多轮循环未触发")

    if errs:
        return False, errs

    print(f"\n  ✅ 用例 3.2-3.4 结构校验通过")
    return True, []


# ---------------------------------------------------------------------------
# 用例 3.5: max_rounds 上限控制
# ---------------------------------------------------------------------------


async def test_3_5_max_rounds(
    validator,
    truncated_items: List,
    query_text: str,
) -> Tuple[bool, List[str]]:
    """3.5: 设 max_rounds=1，Agent 最多完成 1 轮工具调用"""
    print(f"\n{'='*60}")
    print(f"  用例 3.5  max_rounds=1 上限控制")
    print(f"{'='*60}")
    print(f"  Query: {query_text}")
    print_items_preview(truncated_items, "输入 Items（截断文本）", max_items=2)

    try:
        t0 = time.perf_counter()
        items_out, result = await validator.validate(
            query_text=query_text,
            items=truncated_items,
            max_rounds=1,
        )
        elapsed = (time.perf_counter() - t0) * 1000
    except Exception as e:
        print(f"  ❌ validate() 异常: {e}")
        traceback.print_exc()
        return False, [str(e)]

    print(f"\n  耗时: {elapsed:.0f}ms")
    print_validation_result(result)

    ok, errs = validate_result_structure(items_out, result, "3.5")
    if not ok:
        print("  ❌ 结构校验失败:")
        for e in errs:
            print(f"     - {e}")
        return False, errs

    # max_rounds=1 → 含工具的「调整」批次最多 1 次（单批内可并行多工具）
    adj = getattr(result, "adjustment_rounds", 0)
    if adj <= 1:
        print(f"  ✅ adjustment_rounds={adj}（工具调整批次数符合上限）")
    else:
        msg = f"max_rounds=1 但 adjustment_rounds={adj}，预期 <= 1"
        print(f"  ❌ {msg}")
        errs.append(msg)
        return False, errs

    print(f"  ── 最终 passed={result.passed}, tool_calls={result.tool_calls_count}")

    print(f"\n  ✅ 用例 3.5 结构校验通过")
    return True, []


# ---------------------------------------------------------------------------
# 报告生成
# ---------------------------------------------------------------------------


def write_report(
    results: List[Tuple[str, bool]],
    out: Path,
    elapsed_s: float,
) -> None:
    lines = [
        "# ResultValidator Agent 联调 — 测试报告",
        "",
        f"- **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **脚本**: `test/retrieve/pipeline/test_result_validator.py`",
        f"- **说明**: 自动化 3.1–3.5（并行工具批次 + 最多 N 轮调整）",
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


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


async def main() -> int:
    print("=" * 60)
    print("  Pipeline 真实链路测试 — 测试 3: LLM₂ ResultValidator Agent")
    print("=" * 60)

    # ── 模型配置 ──
    print("\n── 模型配置 ──")
    print_llm_config_info()

    # ── 创建 LiteLLM 客户端 ──
    print("\n── 创建 LiteLLM 客户端 ──")
    try:
        llm_client = create_test_client()
    except Exception as e:
        print(f"  ❌ 创建客户端失败: {e}")
        traceback.print_exc()
        return 1

    # ── 客户端连通性 ──
    print("\n── LLM 连通性 ──")
    if not await check_client_reachable(llm_client):
        print("\n❌ LLM 不可用，终止测试")
        return 1

    # ── 基础设施检查 ──
    print("\n── 基础设施检查 ──")
    if not await ensure_mongodb():
        print("\n❌ MongoDB 不可用，终止测试")
        return 1

    kb_id: Optional[str] = None
    try:
        from src.db.mysql.connection.factory import get_mysql_manager
        mysql_mgr = get_mysql_manager()
        with mysql_mgr.get_session() as session:
            from sqlalchemy import text
            row = session.execute(
                text("SELECT knowledge_base_id FROM chunk_section_document "
                     "WHERE deleted=0 LIMIT 1")
            ).fetchone()
            if row:
                kb_id = row[0]
                print(f"  ✅ MySQL: 发现知识库 {kb_id[:24]}...")
    except Exception as e:
        print(f"  ⚠️ MySQL 查询知识库失败: {e}")

    # ── 初始化 ResultValidator Agent ──
    from src.retrieve.pipeline.route_registry import RouteRegistry
    from src.retrieve.validator.result_validator import ResultValidator

    validator = ResultValidator(
        model=llm_client,
        registry=RouteRegistry(),
    )

    # ── 按用例分配查询 ──
    q_3_1 = TEST_QUERIES["spec_lookup"]
    q_3_2 = TEST_QUERIES["comparison"]
    q_3_5 = TEST_QUERIES["application"]

    # ── 获取真实 ChunkItem ──
    print("\n── 获取真实 ChunkItem（通过 retrieve_custom）──")

    items_cache: Dict[str, List] = {}
    for label, q in [("3.1", q_3_1), ("3.2-3.4", q_3_2), ("3.5", q_3_5)]:
        if q in items_cache:
            continue
        print(f"\n  [用例 {label}] 检索: {q}")
        try:
            fetched = await fetch_real_items(kb_id, query_text=q)
        except Exception as e:
            print(f"  ❌ retrieve_custom 失败: {e}")
            traceback.print_exc()
            return 1
        if not fetched:
            print(f"  ❌ retrieve_custom 未返回任何结果 (query={q})")
            return 1
        print(f"  ✅ 获取到 {len(fetched)} 个真实 ChunkItem")
        print_items_preview(fetched, f"真实 Items 预览 ({label})")
        items_cache[q] = fetched

    real_items_3_1 = items_cache[q_3_1]
    real_items_3_2 = items_cache[q_3_2]
    real_items_3_5 = items_cache[q_3_5]

    # ── 构造截断 items ──
    truncated_items_3_2 = make_truncated_items(real_items_3_2)
    truncated_items_3_5 = make_truncated_items(real_items_3_5)
    print_items_preview(truncated_items_3_2, "截断 Items 预览 (3.2-3.4)")

    # ── 执行测试用例 ──
    t_all = time.perf_counter()
    results: List[Tuple[str, bool]] = []

    ok, _ = await test_3_1_pass(validator, real_items_3_1, query_text=q_3_1)
    results.append(("3.1 充分结果 → Pass", ok))

    ok, _ = await test_3_2_3_3_3_4_supplement(validator, truncated_items_3_2, query_text=q_3_2)
    results.append(("3.2-3.4 Supplement + 工具执行 + 多轮", ok))

    ok, _ = await test_3_5_max_rounds(validator, truncated_items_3_5, query_text=q_3_5)
    results.append(("3.5 max_rounds 上限", ok))

    elapsed = time.perf_counter() - t_all
    passed = sum(1 for _, o in results if o)
    total = len(results)

    # ── 汇总 ──
    print("\n" + "=" * 60)
    print(f" 自动化汇总（3.1–3.5）: {passed}/{total} 通过, {elapsed:.1f}s")
    print("=" * 60)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")

    write_report(
        results,
        project_root / "test" / "retrieve" / "pipeline" / "result_validator_test_report.md",
        elapsed,
    )

    # ── 清理 ──
    try:
        from src.db.mongodb.mongodb_manager import MongoDBManager
        mgr = await MongoDBManager.get_instance()
        await mgr.disconnect()
    except Exception:
        pass
    try:
        from src.db.milvus import reset_manager
        reset_manager()
    except Exception:
        pass

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
