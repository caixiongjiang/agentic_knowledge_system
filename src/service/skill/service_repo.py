#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""SkillServiceRepository：通过 HTTP 调用 skill-service REST API 实现 SkillRepository 协议。

知识系统后端只读，不写。写操作走 skill-service 直接调用。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from skill_core.ports import SkillRepository
from skill_core.types import CustomSkillRecord


class SkillServiceRepository:
    """通过 HTTP 调用 skill-service 实现 SkillRepository 协议（只读）。"""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=10.0)
        self._cached_version: int = -1

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # SkillRepository 协议实现（只读）
    # ------------------------------------------------------------------

    def list_custom(self) -> list[CustomSkillRecord]:
        try:
            resp = self._client.get("/skills", params={"enabled_only": "false"})
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            return [
                CustomSkillRecord(
                    name=item["name"],
                    description=item["description"],
                    category=item.get("category", "custom"),
                    tags=tuple(item.get("tags", [])),
                    version=item.get("version", "1.0.0"),
                    requires_tools=tuple(item.get("requires_tools", [])),
                    fallback_for_tools=tuple(item.get("fallback_for_tools", [])),
                    body="",  # 列表不返回正文
                    created_by="",
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                for item in items
                if item.get("source") == "custom"
            ]
        except Exception as e:
            logger.warning(f"skill-service list_custom 失败: {e}")
            return []

    def get(self, name: str) -> CustomSkillRecord | None:
        try:
            resp = self._client.get(f"/skills/{name}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json().get("data", {})
            desc = data.get("descriptor", {})
            if desc.get("source") != "custom":
                return None
            return CustomSkillRecord(
                name=desc["name"],
                description=desc["description"],
                category=desc.get("category", "custom"),
                tags=tuple(desc.get("tags", [])),
                version=desc.get("version", "1.0.0"),
                requires_tools=tuple(desc.get("requires_tools", [])),
                fallback_for_tools=tuple(desc.get("fallback_for_tools", [])),
                body=data.get("body", ""),
                created_by="",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        except Exception as e:
            logger.warning(f"skill-service get({name}) 失败: {e}")
            return None

    def get_states(self) -> dict[str, bool]:
        try:
            resp = self._client.get("/skills/descriptors", params={"enabled_only": "false"})
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return {
                d["name"]: d.get("enabled", True)
                for d in data.get("descriptors", [])
            }
        except Exception as e:
            logger.warning(f"skill-service get_states 失败: {e}")
            return {}

    def table_version(self) -> int:
        try:
            resp = self._client.get("/skills/descriptors")
            resp.raise_for_status()
            data = resp.json().get("data", {})
            version = data.get("version", 0)
            self._cached_version = version
            return version
        except Exception as e:
            logger.warning(f"skill-service table_version 失败: {e}")
            return self._cached_version

    # ------------------------------------------------------------------
    # 写方法：知识系统后端不写，抛异常
    # ------------------------------------------------------------------

    def create(self, rec: CustomSkillRecord) -> None:
        raise NotImplementedError("知识系统后端不写技能，请直接调用 skill-service")

    def update(self, rec: CustomSkillRecord) -> None:
        raise NotImplementedError("知识系统后端不写技能，请直接调用 skill-service")

    def delete(self, name: str) -> None:
        raise NotImplementedError("知识系统后端不写技能，请直接调用 skill-service")

    def set_state(self, name: str, enabled: bool) -> None:
        raise NotImplementedError("知识系统后端不写技能，请直接调用 skill-service")
