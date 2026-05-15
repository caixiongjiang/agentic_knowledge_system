#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : test_chat_persistence.py
@Author  : caixiongjiang
@Date    : 2026/05/09
@Function:
    Chat 持久化层（Phase 1）集成测试

    覆盖目标
    --------
    1. **MySQL ChatSession**
       - 创建会话 / list_by_user 分页 / get_by_id_and_user 权限校验
       - touch 原子更新 message_count + last_message_at
       - rename / soft_delete_by_user
    2. **MongoDB ChatMessage**
       - 写入 user / assistant（含 tool_calls + thinking + citations + usage）/
         tool / 最终 assistant 4 条消息
       - list_by_session 拉历史（按 create_time 正序）
       - find_last_assistant 用于 regenerate
       - count_by_session / count_by_user
       - soft_delete_by_session 级联清理
    3. **跨库一致性**
       - touch 后 ChatSession.message_count == count_by_session

    运行::

        uv run python test/db/conversation/test_chat_persistence.py

    依赖
    ----
    需要 MySQL（``[mysql]``） + MongoDB（``[mongodb]``）真实连通。
    若需保留测试数据，设置 ``KEEP_TEST_DATA=true``。

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import asyncio
import os
import sys
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 加载 .env，确保 DB 连接信息进环境变量
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(project_root / ".env")
except Exception:  # noqa: BLE001
    pass


TEST_USER_ID = "test_user_phase1"


# ==================== 输出辅助 ====================


def _hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


def _info(msg: str) -> None:
    print(f"  · {msg}")


def _gen_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:16]}"


def _gen_message_id() -> str:
    return f"chatmsg_{uuid.uuid4().hex}"


# ==================== Test 1: MySQL ChatSession 基础 ====================


async def test_chat_session_crud() -> Tuple[bool, str]:
    _hr("Test 1 · MySQL ChatSession CRUD（含 list / touch / rename / 软删）")

    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.conversation import chat_session_repo

    manager = get_mysql_manager()
    manager.init_db()  # 自动建表（含新加的 chat_session）

    sess_id = _gen_session_id()

    with manager.get_session() as db:
        # 1) 创建
        obj = chat_session_repo.create(
            db,
            session_id=sess_id,
            user_id=TEST_USER_ID,
            title="Phase 1 测试会话",
            knowledge_base_ids=["kb_a", "kb_b"],
            model_preset="fast",
            agent_mode=True,
            enable_thinking=False,
            max_tool_rounds=5,
            creator=TEST_USER_ID,
        )
        if obj is None:
            _fail("创建会话失败")
            return False, ""
        _info(f"已创建 session_id={obj.session_id}, title={obj.title!r}")

        # 2) get_by_id_and_user 权限校验
        got = chat_session_repo.get_by_id_and_user(db, sess_id, TEST_USER_ID)
        if got is None or got.session_id != sess_id:
            _fail("权限校验查询失败")
            return False, sess_id
        bad_user = chat_session_repo.get_by_id_and_user(db, sess_id, "bad_user")
        if bad_user is not None:
            _fail("跨用户权限校验失效")
            return False, sess_id
        _ok("权限校验：本人 ✅，他人 ❌")

        # 3) touch 计数 + 时间
        if not chat_session_repo.touch(db, sess_id, delta=3):
            _fail("touch 失败")
            return False, sess_id
        refreshed = chat_session_repo.get_by_id_and_user(db, sess_id, TEST_USER_ID)
        if refreshed is None or refreshed.message_count != 3:
            _fail(f"touch 后 message_count 应为 3，实际 {refreshed.message_count if refreshed else None}")
            return False, sess_id
        if refreshed.last_message_at is None:
            _fail("touch 后 last_message_at 应非空")
            return False, sess_id
        _ok(f"touch 计数+3：message_count={refreshed.message_count}, "
            f"last_message_at={refreshed.last_message_at}")

        # 4) list_by_user 分页
        items, total = chat_session_repo.list_by_user(
            db, TEST_USER_ID, limit=10, offset=0,
        )
        if total < 1 or sess_id not in [it.session_id for it in items]:
            _fail(f"list_by_user 未返回新建会话；total={total}")
            return False, sess_id
        _ok(f"list_by_user 命中：total={total}, current_page={len(items)}")

        # 5) rename
        renamed = chat_session_repo.rename(
            db, sess_id, TEST_USER_ID, "重命名后的会话", updater=TEST_USER_ID,
        )
        if renamed is None or renamed.title != "重命名后的会话":
            _fail("rename 失败")
            return False, sess_id
        _ok(f"rename 成功：title={renamed.title!r}")

    return True, sess_id


# ==================== Test 2: MongoDB ChatMessage 基础 ====================


async def test_chat_messages_full_turn(session_id: str) -> Tuple[bool, List[str]]:
    _hr("Test 2 · MongoDB ChatMessage 写入完整一轮（user → assistant(tool_calls) → tool → assistant(final)）")

    from src.db.mongodb.mongodb_manager import get_mongodb_manager
    from src.db.mongodb.models.conversation.chat_message import (
        ChatRole,
        Citation,
        ToolCallRecord,
        TokenUsageRecord,
    )
    from src.db.mongodb.repositories.conversation import chat_message_repo

    await get_mongodb_manager()  # 触发 Beanie 初始化

    created_ids: List[str] = []

    # 1) user 消息
    user_id = _gen_message_id()
    await chat_message_repo.create(
        creator=TEST_USER_ID,
        _id=user_id,
        session_id=session_id,
        user_id=TEST_USER_ID,
        role=ChatRole.USER.value,
        content="上海现在天气怎么样？",
    )
    created_ids.append(user_id)
    _info(f"user message ✅ id={user_id}")

    # 2) assistant 消息（含 thinking + tool_calls）
    assistant1_id = _gen_message_id()
    tool_call = ToolCallRecord(
        id="call_abc",
        name="get_weather",
        arguments={"city": "上海", "unit": "celsius"},
        result_brief="22°C，多云",
        items_added=0,
    )
    await chat_message_repo.create(
        creator=TEST_USER_ID,
        _id=assistant1_id,
        session_id=session_id,
        user_id=TEST_USER_ID,
        role=ChatRole.ASSISTANT.value,
        content="好的，我来查询上海的天气情况。",
        thinking="用户问的是上海天气，我应该调用 get_weather 工具。",
        tool_calls=[tool_call],
        usage=TokenUsageRecord(
            prompt_tokens=120,
            completion_tokens=18,
            thinking_tokens=22,
            total_tokens=160,
        ),
        finish_reason="tool_calls",
        metadata={"model": "deepseek/deepseek-chat", "round": 1},
    )
    created_ids.append(assistant1_id)
    _info(f"assistant(tool_calls) ✅ id={assistant1_id}, tool_calls=1")

    # 3) tool 消息（关联 assistant1.tool_calls[0].id）
    tool_msg_id = _gen_message_id()
    await chat_message_repo.create(
        creator=TEST_USER_ID,
        _id=tool_msg_id,
        session_id=session_id,
        user_id=TEST_USER_ID,
        role=ChatRole.TOOL.value,
        content='{"city":"上海","temp":"22°C","desc":"多云，湿度 65%"}',
        tool_call_id="call_abc",
    )
    created_ids.append(tool_msg_id)
    _info(f"tool message ✅ id={tool_msg_id}, tool_call_id=call_abc")

    # 4) assistant 最终回答（含 citations）
    assistant2_id = _gen_message_id()
    await chat_message_repo.create(
        creator=TEST_USER_ID,
        _id=assistant2_id,
        session_id=session_id,
        user_id=TEST_USER_ID,
        role=ChatRole.ASSISTANT.value,
        content="上海现在 22°C，多云，湿度 65%。体感比较舒适。",
        citations=[
            Citation(
                chunk_id="ck_weather_001",
                document_id="doc_weather_2026",
                knowledge_base_id="kb_a",
                score=0.91,
            ),
        ],
        usage=TokenUsageRecord(
            prompt_tokens=200, completion_tokens=42, total_tokens=242,
        ),
        finish_reason="stop",
        metadata={"model": "deepseek/deepseek-chat", "round": 2},
    )
    created_ids.append(assistant2_id)
    _info(f"assistant(final) ✅ id={assistant2_id}, citations=1")

    # 5) list_by_session 按 create_time 正序拉
    history = await chat_message_repo.list_by_session(
        session_id=session_id, limit=50,
    )
    if len(history) != 4:
        _fail(f"history 长度应为 4，实际 {len(history)}")
        return False, created_ids
    if [m.role for m in history] != ["user", "assistant", "tool", "assistant"]:
        _fail(f"history role 顺序错误：{[m.role for m in history]}")
        return False, created_ids
    _ok(f"list_by_session 顺序正确：{[m.role for m in history]}")

    # 6) tool_calls / citations / thinking / usage 的反序列化
    a1 = history[1]
    if not a1.tool_calls or a1.tool_calls[0].name != "get_weather":
        _fail("assistant1 tool_calls 反序列化失败")
        return False, created_ids
    if a1.tool_calls[0].arguments != {"city": "上海", "unit": "celsius"}:
        _fail(f"tool_calls.arguments 反序列化错误: {a1.tool_calls[0].arguments}")
        return False, created_ids
    if not a1.thinking:
        _fail("assistant1 thinking 丢失")
        return False, created_ids
    if a1.usage is None or a1.usage.thinking_tokens != 22:
        _fail("assistant1 usage 反序列化失败")
        return False, created_ids
    a2 = history[3]
    if not a2.citations or a2.citations[0].chunk_id != "ck_weather_001":
        _fail("assistant2 citations 反序列化失败")
        return False, created_ids
    _ok("嵌套字段（tool_calls / citations / thinking / usage）反序列化全部正确")

    # 7) find_last_assistant
    last = await chat_message_repo.find_last_assistant(session_id)
    if last is None or last.id != assistant2_id:
        _fail(f"find_last_assistant 应返回 assistant2，实际 {last.id if last else None}")
        return False, created_ids
    _ok(f"find_last_assistant 命中最近 assistant: {last.id}")

    # 8) 计数
    cnt = await chat_message_repo.count_by_session(session_id)
    if cnt != 4:
        _fail(f"count_by_session 应为 4，实际 {cnt}")
        return False, created_ids
    _ok(f"count_by_session = {cnt}")

    return True, created_ids


# ==================== Test 3: 跨库一致性 ====================


async def test_cross_db_consistency(session_id: str) -> bool:
    _hr("Test 3 · 跨库一致性（chat_session.message_count 与 MongoDB count 对齐）")

    from src.db.mongodb.repositories.conversation import chat_message_repo
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.conversation import chat_session_repo

    # 把 message_count 重置为 MongoDB 真实数量
    actual = await chat_message_repo.count_by_session(session_id)

    with get_mysql_manager().get_session() as db:
        sess = chat_session_repo.get_by_id_and_user(db, session_id, TEST_USER_ID)
        if sess is None:
            _fail("会话已不存在")
            return False
        # 先把刚才 Test 1 的 +3 reset 掉，再按 actual 加上去
        delta = actual - sess.message_count
        if delta != 0:
            ok = chat_session_repo.touch(db, session_id, delta=delta)
            if not ok:
                _fail("二次 touch 失败")
                return False
        sess = chat_session_repo.get_by_id_and_user(db, session_id, TEST_USER_ID)
        if sess.message_count != actual:
            _fail(f"对齐失败：MySQL={sess.message_count}, MongoDB={actual}")
            return False
        _ok(f"MySQL.message_count = MongoDB.count = {actual}")
    return True


# ==================== Test 4: 软删除级联 ====================


async def test_soft_delete_cascade(session_id: str) -> bool:
    _hr("Test 4 · 软删除级联（删 session → 级联软删消息）")

    from src.db.mongodb.repositories.conversation import chat_message_repo
    from src.db.mysql.connection.factory import get_mysql_manager
    from src.db.mysql.repositories.conversation import chat_session_repo

    with get_mysql_manager().get_session() as db:
        if not chat_session_repo.soft_delete_by_user(
            db, session_id, TEST_USER_ID, updater=TEST_USER_ID,
        ):
            _fail("会话软删除失败")
            return False
        # 软删除后查不到
        if chat_session_repo.get_by_id_and_user(db, session_id, TEST_USER_ID) is not None:
            _fail("软删除后仍可查到会话")
            return False
    _ok("ChatSession 软删除成功")

    # MongoDB 端级联软删消息
    deleted_count = await chat_message_repo.soft_delete_by_session(
        session_id=session_id, updater=TEST_USER_ID,
    )
    if deleted_count != 4:
        _fail(f"级联软删消息数应为 4，实际 {deleted_count}")
        return False
    remaining = await chat_message_repo.count_by_session(session_id)
    if remaining != 0:
        _fail(f"级联后 active 消息应为 0，实际 {remaining}")
        return False
    _ok(f"ChatMessage 级联软删 {deleted_count} 条，剩余活跃 0 条")
    return True


# ==================== 数据清理 ====================


async def cleanup(test_session_ids: List[str], message_ids: List[str]) -> None:
    """清理本次测试数据；除非 KEEP_TEST_DATA=true 才保留"""
    if os.getenv("KEEP_TEST_DATA", "false").lower() in ("true", "1", "yes"):
        print("\n  💾 KEEP_TEST_DATA=true，保留测试数据供查看")
        print(f"     session_ids = {test_session_ids}")
        print(f"     message_ids = {message_ids[:3]}...")
        return

    # MongoDB 物理清理（测试数据，无需保留软删记录）
    try:
        from src.db.mongodb.models.conversation.chat_message import ChatMessage
        if message_ids:
            res = await ChatMessage.find(
                {"_id": {"$in": message_ids}}
            ).delete()
            print(f"\n  🧹 物理删除 ChatMessage: {res.deleted_count if res else 0} 条")
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠️ ChatMessage 清理失败（忽略）: {e}")

    # MySQL 物理清理
    try:
        from src.db.mysql.connection.factory import get_mysql_manager
        from src.db.mysql.models.conversation.chat_session import ChatSession
        with get_mysql_manager().get_session() as db:
            n = (
                db.query(ChatSession)
                .filter(ChatSession.session_id.in_(test_session_ids))
                .delete(synchronize_session=False)
            )
            db.commit()
            print(f"  🧹 物理删除 ChatSession: {n} 条")
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠️ ChatSession 清理失败（忽略）: {e}")


# ==================== 主入口 ====================


async def main() -> int:
    print("=" * 70)
    print("  Chat 持久化层（Phase 1）集成测试")
    print(f"  test user = {TEST_USER_ID}")
    print(f"  start time = {datetime.now().isoformat()}")
    print("=" * 70)

    results: List[Tuple[str, bool]] = []
    test_session_ids: List[str] = []
    test_message_ids: List[str] = []

    try:
        ok1, sess_id = await test_chat_session_crud()
        results.append(("session_crud", ok1))
        if sess_id:
            test_session_ids.append(sess_id)

        if ok1 and sess_id:
            ok2, msg_ids = await test_chat_messages_full_turn(sess_id)
            results.append(("messages_full_turn", ok2))
            test_message_ids.extend(msg_ids)

            if ok2:
                ok3 = await test_cross_db_consistency(sess_id)
                results.append(("cross_db_consistency", ok3))

                ok4 = await test_soft_delete_cascade(sess_id)
                results.append(("soft_delete_cascade", ok4))
            else:
                results.append(("cross_db_consistency", False))
                results.append(("soft_delete_cascade", False))
        else:
            results.append(("messages_full_turn", False))
            results.append(("cross_db_consistency", False))
            results.append(("soft_delete_cascade", False))
    except Exception as e:  # noqa: BLE001
        print(f"\n❌ 未捕获异常：{e}")
        traceback.print_exc()
    finally:
        await cleanup(test_session_ids, test_message_ids)

    print("\n" + "=" * 70)
    passed = sum(1 for _, ok in results if ok)
    print(f"  汇总: {passed}/{len(results)} 通过")
    for name, ok in results:
        print(f"    {'✅' if ok else '❌'} {name}")
    print("=" * 70)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
