#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : profile.py
@Author  : caixiongjiang
@Date    : 2026/09/04
@Function: 
    用户个人资料与头像 Pydantic 模型
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    """用户资料响应"""
    user_id: str = Field(..., description="用户唯一标识符")
    nickname: Optional[str] = Field(None, description="用户昵称")
    avatar_url: Optional[str] = Field(None, description="自定义头像 URL（若为空则使用 Identicon）")
    bio: Optional[str] = Field(None, description="用户个人简介")
    custom_data: Optional[Dict[str, Any]] = Field(None, description="自定义扩展数据")
    created_at: Optional[str] = Field(None, description="创建时间 (ISO 格式)")
    updated_at: Optional[str] = Field(None, description="更新时间 (ISO 格式)")


class UserProfileUpdateRequest(BaseModel):
    """用户资料更新请求"""
    nickname: Optional[str] = Field(None, max_length=64, description="用户昵称")
    bio: Optional[str] = Field(None, max_length=1000, description="个人简介")
    custom_data: Optional[Dict[str, Any]] = Field(None, description="自定义扩展数据")


class AvatarUploadResponse(BaseModel):
    """头像上传响应"""
    user_id: str = Field(..., description="用户唯一标识符")
    avatar_url: str = Field(..., description="头像对外访问 URL")
    message: str = Field(default="头像上传成功", description="提示信息")
