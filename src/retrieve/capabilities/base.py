#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : base.py
@Author  : caixiongjiang
@Date    : 2026/02/28
@Function: 
    原子能力抽象基类，提供统一的生命周期管理
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

from loguru import logger

from src.retrieve.types.result import RetrieveResult


@dataclass
class CapabilityDescriptor:
    """原子能力自描述信息

    用于 Skill 层自动发现可用能力，以及 Tool 层生成 Agent 工具描述。

    Attributes:
        name: 能力唯一标识（如 chunk_vector_search）
        display_name: 人类可读名称（如「Chunk 向量语义检索」）
        description: 能力用途的自然语言描述
        input_schema: 输入参数的 JSON Schema 描述
        output_type: 输出结果的类型名
    """
    name: str
    display_name: str
    description: str
    input_schema: Dict[str, Any]
    output_type: str


class BaseCapability(ABC):
    """原子能力抽象基类

    所有 capabilities/ 下的具体能力都继承此类。
    基类提供统一的生命周期管理：日志、计时、异常转化。

    子类只需实现：
    - _do_execute(): 核心检索逻辑
    - describe(): 能力自描述
    """

    def __init__(self) -> None:
        self.logger = logger.bind(capability=self.__class__.__name__)

    async def execute(self, **kwargs: Any) -> RetrieveResult:
        """执行原子能力（模板方法）

        自动处理计时、日志和异常捕获，子类不应覆盖此方法。

        Args:
            **kwargs: 子类定义的具体参数

        Returns:
            统一的检索结果容器

        Raises:
            RetrieveError: 所有底层异常统一包装后抛出
        """
        capability_name = self.describe().name
        self.logger.debug(f"开始执行能力: {capability_name}")
        start = time.perf_counter()

        try:
            result = await self._do_execute(**kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            result.source_capability = capability_name
            result.execution_time_ms = elapsed_ms
            self.logger.info(
                f"能力 {capability_name} 执行完成: "
                f"{result.total_count} 条结果, 耗时 {elapsed_ms:.1f}ms"
            )
            return result
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.logger.error(
                f"能力 {capability_name} 执行失败 ({elapsed_ms:.1f}ms): {e}",
                exc_info=True,
            )
            raise

    @abstractmethod
    async def _do_execute(self, **kwargs: Any) -> RetrieveResult:
        """子类实现的核心检索逻辑"""
        ...

    @abstractmethod
    def describe(self) -> CapabilityDescriptor:
        """返回该能力的自描述信息"""
        ...
