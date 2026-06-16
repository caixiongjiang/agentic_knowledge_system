#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : chunk.py
@Author  : caixiongjiang
@Date    : 2026/06/09
@Function:
    Chunk 操作路由
    提供 chunk 级别的 API 端点：
      GET /{chunk_id}/image-preview - 获取图片 chunk 的预览 URL（MinIO 预签名URL）
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.orm import Session

from api.dependencies.auth import get_current_user_id
from api.dependencies.database import get_db_session, get_storage_manager
from api.schemas.common import ApiResponse
from api.schemas.knowledge.file import ChunkImagePreviewResponse, ChunkPositionResponse, ElementPosition
from src.db.mysql.repositories.base.chunk_meta_info_repo import chunk_meta_info_repo
from src.db.mysql.repositories.base.element_meta_info_repo import element_meta_info_repo
from src.db.storage.manager import StorageManager

router = APIRouter(tags=["Chunk"])

# MinerU pipeline content_list bbox：左上角原点，[x0,y0,x1,y1]，各轴映射到 0~1000
MINERU_COORD_SPACE = "mineru-normalized-1000"
MINERU_COORD_RANGE = 1000


# ==================== Chunk 图片预览 ====================


@router.get(
    "/{chunk_id}/image-preview",
    response_model=ApiResponse[ChunkImagePreviewResponse],
    summary="获取图片 chunk 的预览 URL",
    description=(
        "根据 chunk_id 生成图片 chunk 的 MinIO 预签名 URL。"
        "仅支持 chunk_type=image 且具有有效存储路径的 chunk。"
        "URL 默认有效期 1 小时，可通过 expires 参数调整（60 ~ 86400 秒）。"
    ),
)
async def get_chunk_image_preview(
    chunk_id: str,
    expires: int = Query(
        default=3600, ge=60, le=86400,
        description="URL 过期时间（秒），最小 60，最大 86400，默认 3600",
    ),
    _user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
    storage: StorageManager = Depends(get_storage_manager),
) -> ApiResponse[ChunkImagePreviewResponse]:
    # 1. 查询 ChunkMetaInfo
    meta = chunk_meta_info_repo.get_by_id(session, chunk_id)
    if not meta or getattr(meta, "deleted", 0) != 0:
        raise HTTPException(status_code=404, detail="Chunk 不存在或已删除")

    if meta.chunk_type != "image":
        raise HTTPException(
            status_code=400, detail="非图片类型 chunk，无法生成图片预览"
        )

    if not meta.bucket_name or not meta.image_file_path:
        raise HTTPException(
            status_code=404, detail="图片存储路径缺失，无法生成预览链接"
        )

    # 2. 生成 presigned URL
    storage_path = f"{meta.bucket_name}/{meta.image_file_path}"
    try:
        preview_url = await storage.get_preview_url(storage_path, expires)
    except Exception as e:
        logger.error(
            f"生成 chunk 图片预览URL失败: chunk_id={chunk_id}, "
            f"storage_path={storage_path}, error={e}"
        )
        raise HTTPException(status_code=500, detail="生成预览URL失败")

    return ApiResponse.success(
        data=ChunkImagePreviewResponse(
            chunk_id=chunk_id,
            preview_url=preview_url,
            expires_in=expires,
            file_name=getattr(meta, "image_file_name", None),
        ),
        message="图片预览URL生成成功",
    )


# ==================== Chunk 定位信息 ====================


@router.get(
    "/{chunk_id}/position",
    response_model=ApiResponse[ChunkPositionResponse],
    summary="获取 chunk 的定位信息",
    description=(
        "根据 chunk_id 返回其关联元素的位置坐标（MinerU bbox），"
        "用于文件预览中的定位高亮。"
    ),
)
async def get_chunk_position(
    chunk_id: str,
    _user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[ChunkPositionResponse]:
    # 1. 查询 ChunkMetaInfo
    meta = chunk_meta_info_repo.get_by_id(session, chunk_id)
    if not meta or getattr(meta, "deleted", 0) != 0:
        raise HTTPException(status_code=404, detail="Chunk 不存在或已删除")

    # 2. 查询关联的 Element 位置信息
    elements: list[ElementPosition] = []
    raw_element_ids = getattr(meta, "element_ids", None) or []
    if raw_element_ids:
        for eid in raw_element_ids:
            el = element_meta_info_repo.get_by_id(session, eid)
            if not el or getattr(el, "deleted", 0) != 0:
                continue
            # 解析 page_position JSON 字符串
            pos = getattr(el, "page_position", None)
            parsed_pos = None
            if pos:
                try:
                    import json as _json
                    parsed_pos = _json.loads(pos)
                    if not isinstance(parsed_pos, list):
                        parsed_pos = None
                except Exception:
                    parsed_pos = None
            elements.append(
                ElementPosition(
                    element_id=getattr(el, "element_id", eid),
                    element_type=getattr(el, "element_type", "unknown"),
                    page_position=parsed_pos,
                )
            )

    return ApiResponse.success(
        data=ChunkPositionResponse(
            chunk_id=chunk_id,
            chunk_type=getattr(meta, "chunk_type", None),
            page_index=getattr(meta, "page_index", None),
            coord_space=MINERU_COORD_SPACE,
            coord_range=MINERU_COORD_RANGE,
            elements=elements,
        ),
    )
