#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : user_profile_repo.py
@Author  : caixiongjiang
@Date    : 2026/09/04
@Function: 
    UserProfile Repository（用户资料及头像仓储层）
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime
from typing import Optional, Dict, Any

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.db.mysql.models.user.user_profile import UserProfile
from src.db.mysql.repositories.base_repository import BaseRepository


class UserProfileRepository(BaseRepository[UserProfile]):
    """UserProfile Repository"""

    def __init__(self) -> None:
        super().__init__(UserProfile)

    def get_by_user_id(
        self,
        session: Session,
        user_id: str,
    ) -> Optional[UserProfile]:
        """按 user_id 查询用户资料（未删除）"""
        try:
            return (
                session.query(self.model)
                .filter(
                    self.model.user_id == user_id,
                    self.model.deleted == 0,
                )
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"查询用户资料失败: user_id={user_id}, error={e}")
            return None

    def get_or_create(
        self,
        session: Session,
        user_id: str,
        nickname: Optional[str] = None,
    ) -> UserProfile:
        """获取用户资料，若不存在则创建一条默认记录"""
        profile = self.get_by_user_id(session, user_id)
        if profile is not None:
            return profile

        now = datetime.now()
        profile = UserProfile(
            user_id=user_id,
            nickname=nickname,
            creator=user_id,
            updater=user_id,
            create_time=now,
            update_time=now,
            deleted=0,
            status=0,
        )
        try:
            session.add(profile)
            session.commit()
            session.refresh(profile)
            logger.info(f"成功初始化用户资料记录: user_id={user_id}")
            return profile
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"初始化用户资料失败: user_id={user_id}, error={e}")
            # 并发保护：再次尝试查询
            existing = self.get_by_user_id(session, user_id)
            if existing:
                return existing
            raise

    def update_profile(
        self,
        session: Session,
        user_id: str,
        nickname: Optional[str] = None,
        bio: Optional[str] = None,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserProfile]:
        """更新用户昵称、简介等基本信息"""
        profile = self.get_or_create(session, user_id)
        try:
            if nickname is not None:
                profile.nickname = nickname.strip() if nickname else None
            if bio is not None:
                profile.bio = bio.strip() if bio else None
            if custom_data is not None:
                profile.custom_data = custom_data

            profile.updater = user_id
            profile.update_time = datetime.now()
            session.commit()
            session.refresh(profile)
            logger.info(f"成功更新用户资料: user_id={user_id}")
            return profile
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新用户资料失败: user_id={user_id}, error={e}")
            return None

    def update_avatar(
        self,
        session: Session,
        user_id: str,
        avatar_url: str,
        avatar_storage_path: str,
    ) -> Optional[UserProfile]:
        """更新用户头像路径与 URL"""
        profile = self.get_or_create(session, user_id)
        try:
            profile.avatar_url = avatar_url
            profile.avatar_storage_path = avatar_storage_path
            profile.updater = user_id
            profile.update_time = datetime.now()
            session.commit()
            session.refresh(profile)
            logger.info(f"成功更新用户头像: user_id={user_id}, path={avatar_storage_path}")
            return profile
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新用户头像失败: user_id={user_id}, error={e}")
            return None

    def clear_avatar(
        self,
        session: Session,
        user_id: str,
    ) -> Optional[UserProfile]:
        """清除用户自定义头像（恢复为默认 Identicon）"""
        profile = self.get_by_user_id(session, user_id)
        if not profile:
            return None

        try:
            profile.avatar_url = None
            profile.avatar_storage_path = None
            profile.updater = user_id
            profile.update_time = datetime.now()
            session.commit()
            session.refresh(profile)
            logger.info(f"成功清除用户头像: user_id={user_id}")
            return profile
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"清除用户头像失败: user_id={user_id}, error={e}")
            return None


# 全局单例
user_profile_repo = UserProfileRepository()
