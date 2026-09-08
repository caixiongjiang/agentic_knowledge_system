#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : user_profile.py
@Author  : caixiongjiang
@Date    : 2026/09/04
@Function: 
    UserProfile Schema 定义（用户个人资料与头像表）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from sqlalchemy import Column, String, Text, JSON, Index
from src.db.mysql.models.base_model import BaseModel


class UserProfile(BaseModel):
    """
    用户资料与头像表

    管理用户个性化信息、自定义头像存储路径及 URL。
    当用户未上传头像时，前端降级至由 user_id 确定的 Identicon。
    """
    __tablename__ = "user_profile"

    __table_args__ = (
        Index("idx_user_profile_deleted", "deleted"),
    )

    user_id = Column(
        String(64),
        primary_key=True,
        comment="用户唯一标识符（UUID 或 Logto sub）",
    )

    nickname = Column(
        String(64),
        nullable=True,
        comment="用户昵称 / 显示名称",
    )

    avatar_url = Column(
        String(512),
        nullable=True,
        comment="自定义头像对外访问 URL",
    )

    avatar_storage_path = Column(
        String(512),
        nullable=True,
        comment="头像在 MinIO 上的存储路径 (bucket/object_path)",
    )

    bio = Column(
        Text,
        nullable=True,
        comment="用户个人简介 / 签名",
    )

    custom_data = Column(
        JSON,
        nullable=True,
        comment="扩展自定义 JSON 配置",
    )

    # BaseModel 字段会自动继承：
    # - status, creator, create_time, updater, update_time, deleted
