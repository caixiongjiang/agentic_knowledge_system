#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""SkillRegistry 全局单例。

在应用启动时由 main.py 调用 init_registry() 初始化，
后续通过 get_registry() 获取 registry 实例。

读路径：通过 SkillServiceRepository 调用 skill-service REST API。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from skill_core import SkillRegistry

_registry: SkillRegistry | None = None


def init_registry() -> None:
    """初始化全局 SkillRegistry 单例（读路径：调 skill-service API）。"""
    global _registry

    from skill_core import SkillRegistry
    from src.service.skill.service_repo import SkillServiceRepository

    skill_service_url = os.getenv("SKILL_SERVICE_URL", "http://localhost:8001")
    repo = SkillServiceRepository(base_url=skill_service_url)

    import skill_core as _sc
    builtin_dir = Path(_sc.__file__).resolve().parent / "skills"
    _registry = SkillRegistry(builtin_dir=builtin_dir, repo=repo)
    logger.info(f"SkillRegistry 已初始化 (skill_service={skill_service_url}, builtin_dir={builtin_dir})")


def get_registry() -> SkillRegistry:
    """获取全局 SkillRegistry 单例。

    Raises:
        RuntimeError: 若尚未调用 init_registry()。
    """
    if _registry is None:
        raise RuntimeError("SkillRegistry 尚未初始化，请确认 main.py lifespan 中调用了 init_registry()")
    return _registry
