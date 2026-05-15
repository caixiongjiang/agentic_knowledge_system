"""端到端（E2E）测试 / 调试工具

本目录只放"客户端 driver"——脚本**不会**自动启动 uvicorn。
服务端由你自己起，日志由你自己看；脚本只负责发请求 + 实时打印事件流。

典型用法
--------
    # terminal-A：起服务，看服务端日志（含 [chat.retrieve] / [chat.tool.exec] 业务 tag）
    uv run uvicorn main:app --reload --port 8000

    # terminal-B：跑客户端
    uv run python test/e2e/chat_client.py --mode rag
    uv run python test/e2e/chat_client.py --mode agent
    uv run python test/e2e/chat_client.py --mode stop --stop-after 2.0

工具文件
--------
- ``chat_client.py``         — 发请求 + 实时打印 WS 事件流
- ``probe_knowledge_base.py`` — 探测一个"有 chunk 索引"的知识库（被 chat_client 复用，也可独立跑）
"""
