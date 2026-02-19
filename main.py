#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : main.py
@Author  : caixiongjiang
@Date    : 2025/12/29 11:40
@Function: 
    FastAPI 应用入口
    启动方式: uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
@Modify History:
    2026/02/18 - 重写为 FastAPI 应用，集成 Knowledge API 路由
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from loguru import logger

from src.utils.log_config import setup_dev_logging

setup_dev_logging()

from api.routers import knowledge_router
from src.db.kafka.connection.factory import close_kafka_manager
from src.db.mysql.connection.factory import get_mysql_manager
from src.db.redis.connection.factory import RedisManagerFactory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理：启动时初始化资源，关闭时释放连接"""
    logger.info("应用启动中...")
    get_mysql_manager().init_db()
    yield
    logger.info("应用关闭中，释放资源...")
    get_mysql_manager().close()
    await close_kafka_manager()
    await RedisManagerFactory.close_all()
    logger.info("所有资源已释放")


app = FastAPI(
    title="Agentic Knowledge System",
    description="智能知识管理系统 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(knowledge_router)


if __name__ == "__main__":
    import os
    import uvicorn

    # Python 3.12+ 的 resource_tracker 在 reload 模式下会误报信号量泄漏
    # 这些信号量由 SQLAlchemy/Redis/loguru 等库内部创建，OS 会自动回收
    os.environ["PYTHONWARNINGS"] = "ignore::UserWarning:multiprocessing.resource_tracker"
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
