#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : auth.py
@Author  : caixiongjiang
@Date    : 2026/01/21 10:00
@Function: 
    认证依赖模块
    提供 API 认证相关的依赖注入功能
@Modify History:
    2026/02/18 - 实现简化版用户认证（Header 提取 user_id）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from fastapi import Header, HTTPException


async def get_current_user_id(
    x_user_id: str = Header(..., alias="X-User-Id", description="用户ID")
) -> str:
    """
    从请求头中提取当前用户ID

    生产环境应替换为 JWT Token 验证逻辑。

    Args:
        x_user_id: 请求头中的用户ID

    Returns:
        用户ID字符串

    Raises:
        HTTPException: 如果用户ID为空
    """
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(status_code=401, detail="缺少有效的用户标识")
    return x_user_id.strip()
