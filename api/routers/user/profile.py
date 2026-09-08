#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : profile.py
@Author  : caixiongjiang
@Date    : 2026/09/04
@Function: 
    用户资料与头像管理路由
    提供以下端点：
      GET    /api/user/profile         - 获取当前用户资料
      PUT    /api/user/profile         - 更新当前用户资料（昵称、简介等）
      POST   /api/user/avatar          - 上传并更新用户头像（保存至 MinIO）
      DELETE /api/user/avatar          - 删除用户头像（恢复为默认 Identicon）
      GET    /api/user/avatar/{user_id} - 获取/流式输出指定用户的自定义头像
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import io
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from loguru import logger
from PIL import Image
from sqlalchemy.orm import Session

from api.dependencies.auth import (
    get_current_user_id,
    get_current_user_id_from_token,
)
from api.dependencies.database import get_db_session, get_storage_manager
from api.schemas.common import ApiResponse
from api.schemas.user.profile import (
    AvatarUploadResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from src.db.mysql.models.user.user_profile import UserProfile
from src.db.mysql.repositories.user.user_profile_repo import user_profile_repo
from src.db.storage.manager import StorageManager
from src.utils.config_manager import get_config_manager

router = APIRouter(tags=["User"])

MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
}


def _get_avatar_bucket() -> str:
    """获取头像存放的 MinIO bucket"""
    config = get_config_manager()
    return config.get("storage.minio.default_bucket", "knowledge-files")


def _to_profile_response(profile: UserProfile) -> UserProfileResponse:
    """转换数据库模型为 API 响应"""
    return UserProfileResponse(
        user_id=profile.user_id,
        nickname=profile.nickname,
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        custom_data=profile.custom_data,
        created_at=profile.create_time.isoformat() if profile.create_time else None,
        updated_at=profile.update_time.isoformat() if profile.update_time else None,
    )


def _optimize_avatar_image(raw_bytes: bytes, content_type: str) -> tuple[bytes, str, str]:
    """
    对上传的图片进行尺寸限制和 WebP 格式优化
    
    Returns:
        tuple[bytes, str, str]: (优化后字节, 文件后缀, MIME类型)
    """
    if content_type in ("image/svg+xml", "image/gif"):
        # SVG 与动态 GIF 保持原始格式
        ext = ALLOWED_IMAGE_TYPES.get(content_type, ".png")
        return raw_bytes, ext, content_type

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            # 统一转为 RGBA 或 RGB
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")

            # 缩放至最大 512x512，保持宽高比
            max_size = 512
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # 输出为高质量 WebP
            output = io.BytesIO()
            img.save(output, format="WEBP", quality=90, method=6)
            return output.getvalue(), ".webp", "image/webp"
    except Exception as e:
        logger.warning(f"图片优化处理失败，回退使用原始字节: {e}")
        ext = ALLOWED_IMAGE_TYPES.get(content_type, ".png")
        return raw_bytes, ext, content_type


# ==================== 用户资料查询与更新 ====================


@router.get(
    "/profile",
    response_model=ApiResponse[UserProfileResponse],
    summary="获取当前用户个人资料",
    description="获取当前登录用户的资料。如果记录不存在，将自动初始化一条空记录。",
)
async def get_profile(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[UserProfileResponse]:
    profile = user_profile_repo.get_or_create(session, user_id)
    return ApiResponse.success(
        data=_to_profile_response(profile),
        message="获取用户资料成功",
    )


@router.put(
    "/profile",
    response_model=ApiResponse[UserProfileResponse],
    summary="更新当前用户个人资料",
    description="更新当前登录用户的昵称、个人简介等信息。",
)
async def update_profile(
    body: UserProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[UserProfileResponse]:
    profile = user_profile_repo.update_profile(
        session=session,
        user_id=user_id,
        nickname=body.nickname,
        bio=body.bio,
        custom_data=body.custom_data,
    )
    if not profile:
        raise HTTPException(status_code=500, detail="更新用户资料失败")

    return ApiResponse.success(
        data=_to_profile_response(profile),
        message="个人资料更新成功",
    )


# ==================== 用户头像上传与删除 ====================


@router.post(
    "/avatar",
    response_model=ApiResponse[AvatarUploadResponse],
    summary="上传并保存用户自定义头像",
    description=(
        "接收用户上传的头像图片（PNG/JPEG/WEBP/GIF/SVG），自动优化后上传至 MinIO，"
        "并更新 user_profile 表中的头像路径与访问 URL。"
    ),
)
async def upload_avatar(
    file: UploadFile = File(..., description="头像图片文件（最大 5MB）"),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
    storage: StorageManager = Depends(get_storage_manager),
) -> ApiResponse[AvatarUploadResponse]:
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式: {content_type}。仅支持 JPG、PNG、WEBP、GIF、SVG",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"头像文件过大 ({len(raw_bytes) / 1024 / 1024:.1f}MB)，最大允许 5MB",
        )

    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="头像文件内容为空")

    # 优化压缩
    optimized_bytes, ext, final_mime = _optimize_avatar_image(raw_bytes, content_type)

    # 生成存储路径
    bucket = _get_avatar_bucket()
    timestamp = int(time.time())
    object_path = f"avatars/{user_id}/avatar_{timestamp}{ext}"

    # 查出现有头像路径，准备覆盖时清理旧对象
    existing_profile = user_profile_repo.get_by_user_id(session, user_id)
    old_storage_path = existing_profile.avatar_storage_path if existing_profile else None

    # 上传至 MinIO
    try:
        storage_path = await storage.upload_file(
            file_bytes=optimized_bytes,
            bucket=bucket,
            object_path=object_path,
        )
    except Exception as e:
        logger.error(f"上传头像至 MinIO 失败: user_id={user_id}, error={e}")
        raise HTTPException(status_code=500, detail="头像存储失败")

    # 构建对外公开访问的相对 API URL（含时间戳用于强制刷新前端缓存）
    avatar_url = f"/api/user/avatar/{user_id}?t={timestamp}"

    # 更新数据库记录
    updated_profile = user_profile_repo.update_avatar(
        session=session,
        user_id=user_id,
        avatar_url=avatar_url,
        avatar_storage_path=storage_path,
    )
    if not updated_profile:
        # 回滚 MinIO
        try:
            await storage.delete_file(storage_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="更新用户头像记录失败")

    # 异步清理旧头像文件（如果路径不同）
    if old_storage_path and old_storage_path != storage_path:
        try:
            await storage.delete_file(old_storage_path)
            logger.debug(f"已清理旧头像: {old_storage_path}")
        except Exception as e:
            logger.warning(f"清理旧头像失败 (忽略): {old_storage_path}, error={e}")

    return ApiResponse.success(
        data=AvatarUploadResponse(
            user_id=user_id,
            avatar_url=avatar_url,
            message="头像上传并保存成功",
        ),
        message="头像上传成功",
    )


@router.delete(
    "/avatar",
    response_model=ApiResponse[None],
    summary="删除用户自定义头像（恢复为默认 Identicon）",
    description="清除用户头像记录并从 MinIO 删除对应文件，前端将自动降级展示由 user_id 确定的 Identicon。",
)
async def delete_avatar(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
    storage: StorageManager = Depends(get_storage_manager),
) -> ApiResponse[None]:
    profile = user_profile_repo.get_by_user_id(session, user_id)
    if not profile or not profile.avatar_storage_path:
        # 本来就没有自定义头像，直接返回成功
        return ApiResponse.success(message="头像已处于默认状态")

    old_path = profile.avatar_storage_path

    # 清除数据库记录
    user_profile_repo.clear_avatar(session, user_id)

    # 从 MinIO 删除
    try:
        await storage.delete_file(old_path)
        logger.info(f"已从 MinIO 删除用户头像: user_id={user_id}, path={old_path}")
    except Exception as e:
        logger.warning(f"从 MinIO 删除头像异常 (已清库忽略): {old_path}, error={e}")

    return ApiResponse.success(message="头像已成功重置为默认 Identicon")


# ==================== 头像文件直读流式响应 ====================


@router.get(
    "/avatar/{target_user_id}",
    summary="获取指定用户的自定义头像图片",
    description=(
        "直接返回该用户的头像图片数据流。支持浏览器 img 标签直接引用。"
        "若用户未设置自定义头像，返回 404，以便前端自动回退至 Identicon。"
    ),
)
async def get_user_avatar_image(
    target_user_id: str,
    session: Session = Depends(get_db_session),
    storage: StorageManager = Depends(get_storage_manager),
) -> Response:
    profile = user_profile_repo.get_by_user_id(session, target_user_id)
    if not profile or not profile.avatar_storage_path:
        raise HTTPException(status_code=404, detail="该用户未设置自定义头像")

    try:
        data = await storage.download_file(profile.avatar_storage_path)
    except Exception as e:
        logger.error(f"下载用户头像失败: user_id={target_user_id}, path={profile.avatar_storage_path}, error={e}")
        raise HTTPException(status_code=404, detail="头像文件不存在或读取失败")

    # 推断 MIME 类型
    ext = Path(profile.avatar_storage_path).suffix.lower()
    mime_map = {
        ".webp": "image/webp",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
    }
    media_type = mime_map.get(ext, "image/webp")

    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
            "Content-Disposition": f'inline; filename="avatar_{target_user_id}{ext}"',
        },
    )
