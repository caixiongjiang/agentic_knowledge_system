#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chat_client.py
@Author  : caixiongjiang
@Date    : 2026/05/12
@Function:
    Chat 客户端 driver（单一职责：发请求 + 实时打印事件流）

    使用前提
    --------
    服务端由你自己启动，本脚本**不会** spawn uvicorn。例：

        # terminal-A：启动服务（看服务端日志）
        uv run uvicorn main:app --reload --port 8000

        # terminal-B：跑客户端（看 WS 事件流）
        uv run python test/e2e/chat_client.py --mode rag
        uv run python test/e2e/chat_client.py --mode agent
        uv run python test/e2e/chat_client.py --mode stop --stop-after 2.0

    输出语义
    --------
    - 每行 `[HH:MM:SS.mmm] <kind>  <payload>`：
        - kind=`HTTP→` / `HTTP←` —— REST 调用
        - kind=`WS→`   / `WS←`   —— WS 帧（控制 + 业务）
    - ``content.delta`` 与 ``thinking.delta`` 默认像打字机一样**实时拼在同一行**，
      其它事件类型出现时先把当前行 flush 掉再独占一行。
    - 默认把所有 ServerFrame 原文落到 ``logs/e2e/<ts>/events.jsonl``，
      可用 ``--no-save`` 关掉。

    退出条件
    --------
    收到 ``turn.done``、``error(cancelled=true)``、或 WS 断开。

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
import websockets  # noqa: E402

WS_SUBPROTOCOL = "aks-chat-v1"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"


# ============================================================
# 终端输出小工具
# ============================================================


class Printer:
    """带"打字机式拼接 + 事件流换行"的极简打印器"""

    def __init__(self) -> None:
        self._typewriter_open = False  # 当前是否在一行打字机模式
        self._typewriter_chars = 0     # 已拼字符数（用于尾部统计）

    @staticmethod
    def _ts() -> str:
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def line(self, kind: str, payload: Any = "") -> None:
        """打印独占一行的事件；如有未结束的打字机行，先收尾。"""
        self._flush_typewriter()
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        print(f"[{self._ts()}] {kind:<8} {text}", flush=True)

    def typewriter(self, kind: str, text: str) -> None:
        """打字机式追加；首次会换行 + 打前缀，后续直接 sys.stdout.write 字符。"""
        if not text:
            return
        if not self._typewriter_open:
            sys.stdout.write(f"[{self._ts()}] {kind:<8} ")
            self._typewriter_open = True
            self._typewriter_chars = 0
        sys.stdout.write(text)
        sys.stdout.flush()
        self._typewriter_chars += len(text)

    def _flush_typewriter(self) -> None:
        if self._typewriter_open:
            sys.stdout.write(f"  ({self._typewriter_chars} chars)\n")
            sys.stdout.flush()
            self._typewriter_open = False
            self._typewriter_chars = 0

    def close(self) -> None:
        self._flush_typewriter()


# ============================================================
# REST：创 session
# ============================================================


def create_session(
    *,
    base_url: str,
    user_id: str,
    knowledge_base_id: str,
    agent_mode: bool,
    model_preset: str,
    printer: Printer,
) -> Dict[str, Any]:
    url = f"{base_url}/api/chat/sessions"
    headers = {"X-User-Id": user_id, "Content-Type": "application/json"}
    body = {
        "title": f"client driver · agent={agent_mode}",
        "knowledge_base_ids": [knowledge_base_id],
        "agent_mode": agent_mode,
        "enable_thinking": False,
        "model_preset": model_preset,
    }
    printer.line("HTTP→", f"POST {url}  body={json.dumps(body, ensure_ascii=False)}")
    with httpx.Client(timeout=30.0) as c:
        r = c.post(url, headers=headers, json=body)
    printer.line(
        "HTTP←",
        f"status={r.status_code}  body={r.text[:300]}",
    )
    r.raise_for_status()
    data = (r.json() or {}).get("data") or {}
    if not data.get("session_id"):
        raise RuntimeError(f"创建 session 失败: {r.text}")
    return data


# ============================================================
# WS：跑一轮
# ============================================================


async def run_turn(
    *,
    base_url: str,
    user_id: str,
    session_id: str,
    query: str,
    agent_mode: bool,
    enable_thinking: bool,
    model_preset: Optional[str],
    stop_after: Optional[float],
    save_path: Optional[Path],
    printer: Printer,
) -> None:
    ws_url = (
        base_url.replace("http://", "ws://").replace("https://", "wss://")
        + f"/api/chat/ws?token={user_id}"
    )
    printer.line("WS→", f"connect {ws_url}  subprotocol={WS_SUBPROTOCOL}")

    f_save = save_path.open("w", encoding="utf-8") if save_path else None

    async with websockets.connect(
        ws_url,
        subprotocols=[WS_SUBPROTOCOL],
        max_size=8 * 1024 * 1024,
        ping_interval=None,
    ) as ws:
        # 等 ready
        ready_raw = await asyncio.wait_for(ws.recv(), timeout=10)
        ready = json.loads(ready_raw)
        if f_save:
            f_save.write(ready_raw + "\n")
            f_save.flush()
        printer.line("WS←", f"ready  {json.dumps(ready.get('data') or {}, ensure_ascii=False)}")
        if ready.get("type") != "ready":
            printer.line("ERR", f"未收到 ready：{ready}")
            return

        # 发 start
        start = {
            "type": "start",
            "data": {
                "session_id": session_id,
                "query": query,
                "agent_mode": agent_mode,
                "enable_thinking": enable_thinking,
                **({"model_preset": model_preset} if model_preset else {}),
            },
        }
        await ws.send(json.dumps(start))
        printer.line("WS→", f"start  {json.dumps(start['data'], ensure_ascii=False)}")

        started = time.time()
        tick = 0.5
        stop_sent = False

        while True:
            elapsed = time.time() - started
            if (
                stop_after is not None
                and not stop_sent
                and elapsed >= stop_after
            ):
                await ws.send(json.dumps({"type": "stop"}))
                stop_sent = True
                printer.line("WS→", f"stop  (after {elapsed:.2f}s)")

            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=tick)
            except asyncio.TimeoutError:
                continue
            except websockets.ConnectionClosed as e:
                printer.line(
                    "WS←",
                    f"closed  code={getattr(e, 'code', None)} reason={getattr(e, 'reason', None)!r}",
                )
                break

            if f_save:
                f_save.write(raw + "\n")
                f_save.flush()
            try:
                frame = json.loads(raw)
            except Exception as e:  # noqa: BLE001
                printer.line("ERR", f"non-JSON frame: {e}  head={raw[:120]!r}")
                continue

            ftype = frame.get("type", "?")
            data = frame.get("data") or {}

            if ftype == "content.delta":
                printer.typewriter("content", data.get("text") or data.get("delta") or "")
            elif ftype == "thinking.delta":
                printer.typewriter("thinking", data.get("text") or data.get("delta") or "")
            elif ftype == "tool_call.args_delta":
                # tool args 也是流式：用 tag 区分；同样按打字机展示
                tcid = data.get("tool_call_id") or data.get("id") or "?"
                printer.typewriter(f"tool[{tcid[:8]}]args", data.get("text") or data.get("delta") or "")
            else:
                printer.line(f"WS← {ftype}", data)

            if ftype == "turn.done":
                printer.line("DONE", f"turn.done received，elapsed={time.time() - started:.2f}s")
                break
            if ftype == "error" and data.get("cancelled"):
                printer.line("DONE", f"error(cancelled=True) received，elapsed={time.time() - started:.2f}s")
                break

    if f_save:
        f_save.close()


# ============================================================
# kb 自动探测（可选）
# ============================================================


def auto_probe(printer: Printer) -> Dict[str, Any]:
    from probe_knowledge_base import find_usable_kb  # local import 减少启动开销

    info = find_usable_kb()
    if info is None:
        raise SystemExit("未找到带 chunk 索引的知识库；请用 --kb-id / --user-id 显式指定")
    printer.line(
        "PROBE",
        f"kb_id={info['knowledge_base_id']}  user_id={info['user_id']}  chunks={info['chunk_count']}",
    )
    return info


# ============================================================
# 入口
# ============================================================


_DEFAULT_QUERIES = {
    "rag":   "请用一句话概括这个知识库的主要内容。",
    "agent": "请基于知识库回答：里面讲了哪些主题？必要时可以调用工具继续探索。",
    "stop":  "请基于知识库回答：里面讲了哪些主题？必要时可以调用工具继续探索。",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chat 客户端 driver — 发请求 + 实时打印事件流（服务端日志请自己起 main.py 看）",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"服务端 base url（默认 {DEFAULT_BASE_URL}）")
    parser.add_argument("--mode", choices=["rag", "agent", "stop"], default="rag",
                        help="rag=agent_mode=false；agent=agent_mode=true；stop=agent + 中途发 stop")
    parser.add_argument("--query", default=None, help="覆盖默认 query")
    parser.add_argument("--enable-thinking", action="store_true", help="启用思考链")
    parser.add_argument("--model-preset", default=None, help="覆盖 model_preset（默认走服务端 [chat].agent_model_preset）")
    parser.add_argument("--stop-after", type=float, default=2.0,
                        help="--mode stop 时，连上 WS 后多少秒发 stop（默认 2s）")
    parser.add_argument("--kb-id", default=None, help="知识库 ID；不传则自动探测")
    parser.add_argument("--user-id", default=None, help="X-User-Id；不传则用探测到的 kb 的 owner")
    parser.add_argument("--session-id", default=None, help="复用已有 session；不传则自动创建")
    parser.add_argument("--no-save", action="store_true", help="不把事件流落 jsonl")
    args = parser.parse_args()

    printer = Printer()
    try:
        # 1) 解析 kb / user
        if args.kb_id and args.user_id:
            kb_info = {
                "knowledge_base_id": args.kb_id,
                "user_id": args.user_id,
                "knowledge_base_name": "(CLI)",
                "chunk_count": -1,
            }
            printer.line(
                "PROBE",
                f"kb_id={kb_info['knowledge_base_id']}  user_id={kb_info['user_id']}  (CLI 指定)",
            )
        else:
            kb_info = auto_probe(printer)
            if args.user_id:
                kb_info["user_id"] = args.user_id

        # 2) save 路径
        save_path: Optional[Path] = None
        if not args.no_save:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = project_root / "logs" / "e2e" / f"{ts}_{args.mode}"
            out_dir.mkdir(parents=True, exist_ok=True)
            save_path = out_dir / "events.jsonl"
            printer.line("SAVE", f"events → {save_path}")

        # 3) session
        agent_mode = args.mode in ("agent", "stop")
        if args.session_id:
            session_id = args.session_id
            printer.line("SESSION", f"复用 {session_id}")
        else:
            sess = create_session(
                base_url=args.base_url,
                user_id=kb_info["user_id"],
                knowledge_base_id=kb_info["knowledge_base_id"],
                agent_mode=agent_mode,
                model_preset=args.model_preset or "fast",
                printer=printer,
            )
            session_id = sess["session_id"]
            printer.line("SESSION", f"新建 {session_id}  title={sess.get('title')!r}")

        # 4) 跑一轮
        query = args.query or _DEFAULT_QUERIES[args.mode]
        stop_after = args.stop_after if args.mode == "stop" else None
        asyncio.run(run_turn(
            base_url=args.base_url,
            user_id=kb_info["user_id"],
            session_id=session_id,
            query=query,
            agent_mode=agent_mode,
            enable_thinking=args.enable_thinking,
            model_preset=args.model_preset,
            stop_after=stop_after,
            save_path=save_path,
            printer=printer,
        ))
        return 0
    except KeyboardInterrupt:
        printer.line("INT", "用户中断")
        return 130
    except Exception:
        printer.close()
        traceback.print_exc()
        return 1
    finally:
        printer.close()


if __name__ == "__main__":
    sys.exit(main())
