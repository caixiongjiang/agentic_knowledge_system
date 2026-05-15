#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_tools.py
@Author  : caixiongjiang
@Date    : 2026/05/11
@Function:
    KnowledgeNavToolKit / ValidatorToolKit 单元测试（Phase 2）

    覆盖目标
    --------
    1. **基类 enabled_tools 默认值**：Chat 模式默认暴露 3 个工具
       （context_window / drill_down / skeleton），且 ``roll_up`` 不在列表里。
    2. **基类 schema 与 handler 同步**：``schemas()`` 返回项的 ``function.name``
       与 ``enabled_tools`` 完全对齐。
    3. **基类自定义白名单**：传 ``enabled_tools=("skeleton",)`` 仅暴露 1 个；
       传未注册名字会被丢弃 + warn。
    4. **基类未知工具拒调用**：``has("re_retrieve")`` 在基类下为 ``False``；
       ``call("re_retrieve", ...)`` 返回错误字符串。
    5. **子类 ValidatorToolKit 工具齐全**：``ToolKit`` / ``ValidatorToolKit`` /
       ``create_validation_tools`` 三种入口下，``enabled_tools`` 都是 5 个，
       且 ``re_retrieve`` schema 与 handler 都接入。
    6. **handler 执行（mock capability）**：替换 ``self._cap()``，验证：
       - ``context_window`` 返回 chunk 描述文本，并把新 chunk append 进
         ``supplemented_items``；
       - 调用异常被吞掉，返回带 "工具执行失败" 的字符串，不抛到上层。

    运行::
        uv run python test/service/chat/test_tools.py

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path
from typing import Any, List

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def _hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


# ==================== Test 1: 基类默认白名单 ====================


async def test_default_chat_whitelist() -> bool:
    _hr("Test 1 · KnowledgeNavToolKit 默认白名单（Chat 模式 3 工具）")
    from src.service.chat.tools import DEFAULT_NAV_TOOLS, KnowledgeNavToolKit
    from src.retrieve.types.result import ChunkItem

    supp: List[ChunkItem] = []
    kit = KnowledgeNavToolKit(supplemented_items=supp)

    expected = list(DEFAULT_NAV_TOOLS)
    if kit.enabled_tools != expected:
        _fail(f"enabled_tools={kit.enabled_tools}, want={expected}")
        return False
    print(f"  enabled_tools = {kit.enabled_tools}")

    if "roll_up" in kit.enabled_tools:
        _fail("Chat 模式默认不应启用 roll_up")
        return False
    if not kit.has("context_window") or not kit.has("drill_down") or not kit.has("skeleton"):
        _fail("3 个必备工具未全部启用")
        return False

    schema_names = [s["function"]["name"] for s in kit.schemas()]
    if schema_names != expected:
        _fail(f"schemas() names 不一致：got={schema_names}, want={expected}")
        return False
    _ok(f"schemas() 顺序与 enabled_tools 完全对齐：{schema_names}")
    return True


# ==================== Test 2: 自定义白名单 ====================


async def test_custom_whitelist() -> bool:
    _hr("Test 2 · 自定义 enabled_tools（含未知名字应被丢弃）")
    from src.service.chat.tools import KnowledgeNavToolKit
    from src.retrieve.types.result import ChunkItem

    supp: List[ChunkItem] = []
    kit = KnowledgeNavToolKit(
        supplemented_items=supp,
        enabled_tools=("skeleton", "context_window", "nonexistent_tool"),
    )

    # 顺序保持入参顺序；未知工具被丢弃
    if kit.enabled_tools != ["skeleton", "context_window"]:
        _fail(f"enabled_tools={kit.enabled_tools}, "
              f"want=['skeleton','context_window']")
        return False
    _ok(f"白名单过滤后 enabled_tools={kit.enabled_tools}")

    if kit.has("drill_down"):
        _fail("drill_down 不应启用")
        return False
    if kit.has("nonexistent_tool"):
        _fail("不存在的工具不应启用")
        return False

    schema_names = [s["function"]["name"] for s in kit.schemas()]
    if schema_names != ["skeleton", "context_window"]:
        _fail(f"schemas 顺序错误: {schema_names}")
        return False
    _ok("schemas 严格按 enabled_tools 顺序输出")
    return True


# ==================== Test 3: 基类未启用的工具不可调用 ====================


async def test_base_no_re_retrieve() -> bool:
    _hr("Test 3 · 基类不暴露 re_retrieve（call 应返回错误字符串而非异常）")
    from src.service.chat.tools import KnowledgeNavToolKit
    from src.retrieve.types.result import ChunkItem

    kit = KnowledgeNavToolKit(supplemented_items=[])

    if kit.has("re_retrieve"):
        _fail("基类不应暴露 re_retrieve")
        return False
    if kit.has("roll_up"):
        _fail("Chat 默认不暴露 roll_up")
        return False

    out = await kit.call("re_retrieve", {"query_text": "test"})
    if "未启用" not in out and "不可用" not in out:
        _fail(f"call(re_retrieve) 返回非预期错误文本：{out!r}")
        return False
    _ok(f"call(re_retrieve) 安全拒绝：{out!r}")
    return True


# ==================== Test 4: ValidatorToolKit 5 工具齐全 ====================


async def test_validator_kit_full_set() -> bool:
    _hr("Test 4 · ValidatorToolKit 5 工具齐全（含 re_retrieve schema）")
    from src.retrieve.pipeline.route_registry import RouteRegistry
    from src.retrieve.validator.tools import (
        ToolKit,
        ValidatorToolKit,
        create_validation_tools,
    )

    if ToolKit is not ValidatorToolKit:
        _fail("ToolKit 与 ValidatorToolKit 兼容别名未生效")
        return False
    _ok("ToolKit ≡ ValidatorToolKit（兼容别名生效）")

    registry = RouteRegistry()
    kit = ValidatorToolKit(registry=registry, supplemented_items=[])

    expected = {"context_window", "drill_down", "roll_up", "skeleton", "re_retrieve"}
    if set(kit.enabled_tools) != expected:
        _fail(f"enabled_tools={kit.enabled_tools}, want={expected}")
        return False
    _ok(f"enabled_tools 全集 = {sorted(kit.enabled_tools)}")

    schema_names = {s["function"]["name"] for s in kit.schemas()}
    if schema_names != expected:
        _fail(f"schemas names={schema_names}, want={expected}")
        return False
    _ok("schemas 覆盖 5 个工具")

    # 兼容入口
    kit2 = create_validation_tools(registry=registry, supplemented_items=[])
    if not isinstance(kit2, ValidatorToolKit):
        _fail("create_validation_tools 返回类型异常")
        return False
    _ok("create_validation_tools(...) 返回 ValidatorToolKit 实例")
    return True


# ==================== Test 5: handler 执行（mock capability） ====================


class _FakeNavQuery:
    """占位的 NavigationQuery 替身（仅记录 anchor_id 供回填）"""

    def __init__(self, anchor_id: str) -> None:
        self.anchor_id = anchor_id


class _FakeResult:
    def __init__(self, items: list) -> None:
        self.items = items


class _FakeCap:
    """伪装的 capability：根据 query.anchor_id 返回一组 ChunkItem"""

    def __init__(self, returns: List[Any]) -> None:
        self._returns = returns
        self.called_with: List[Any] = []

    async def execute(self, query: Any) -> _FakeResult:
        self.called_with.append(query)
        return _FakeResult(self._returns)


class _FailingCap:
    async def execute(self, query: Any) -> Any:
        raise RuntimeError("capability blow up")


async def test_handler_dispatch_and_supplement() -> bool:
    _hr("Test 5 · handler 执行 + supplemented_items 回填 + 异常吞掉")
    from src.retrieve.types.result import ChunkItem
    from src.service.chat.tools import KnowledgeNavToolKit

    supp: List[ChunkItem] = []
    kit = KnowledgeNavToolKit(supplemented_items=supp)

    fake_chunk = ChunkItem(
        chunk_id="ck_99", score=0.95, document_id="doc_a", text="extended text",
    )
    fake_cap = _FakeCap(returns=[fake_chunk])
    # 直接绕过懒加载，注入伪装
    kit._capabilities["context_window"] = fake_cap  # noqa: SLF001

    out = await kit.call("context_window", {"chunk_id": "ck_origin", "window_size": 2})
    if "ck_99" not in out:
        _fail(f"context_window 返回文本未含 chunk_id：{out!r}")
        return False
    if len(supp) != 1 or supp[0].chunk_id != "ck_99":
        _fail(f"supplemented_items 未正确回填：{supp}")
        return False
    if not fake_cap.called_with:
        _fail("fake capability 未被调用")
        return False
    _ok(f"context_window → 文本含命中 chunk_id；supplemented_items 增 1 → {len(supp)}")

    # 入参非法（缺 chunk_id），应返回 "入参非法" 字符串
    bad = await kit.call("context_window", {"window_size": 3})
    if "入参非法" not in bad:
        _fail(f"缺必填参数应返回 '入参非法'，实际：{bad!r}")
        return False
    _ok("缺必填参数被 TypeError 捕获并返回友好错误")

    # 异常吞掉
    kit._capabilities["drill_down"] = _FailingCap()  # noqa: SLF001
    fail_out = await kit.call("drill_down", {"section_id": "sec_x"})
    if "工具执行失败" not in fail_out:
        _fail(f"capability 异常未被吞掉：{fail_out!r}")
        return False
    _ok(f"capability 异常被吞掉并返回友好错误：{fail_out!r}")
    return True


# ==================== 主入口 ====================


async def main() -> int:
    print("=" * 70)
    print("  KnowledgeNavToolKit / ValidatorToolKit 单元测试")
    print("=" * 70)

    tests = [
        ("default_chat_whitelist", test_default_chat_whitelist),
        ("custom_whitelist", test_custom_whitelist),
        ("base_no_re_retrieve", test_base_no_re_retrieve),
        ("validator_kit_full_set", test_validator_kit_full_set),
        ("handler_dispatch_and_supplement", test_handler_dispatch_and_supplement),
    ]
    results = []
    for name, fn in tests:
        try:
            ok = await fn()
            results.append((name, ok))
        except Exception as e:  # noqa: BLE001
            print(f"\n❌ {name} 异常：{e}")
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 70)
    passed = sum(1 for _, ok in results if ok)
    print(f"  汇总: {passed}/{len(results)} 通过")
    for name, ok in results:
        print(f"    {'✅' if ok else '❌'} {name}")
    print("=" * 70)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
