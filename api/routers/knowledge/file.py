#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : file.py
@Author  : caixiongjiang
@Date    : 2026/03/16
@Function: 
    文件操作路由
    提供文件级别的 API 端点：
      PUT    /{file_id}/move     - 移动文件到指定文件夹
      POST   /batch-move         - 批量移动文件
      GET    /{file_id}/preview  - 获取文件预览URL（MinIO 预签名URL）
      DELETE /{file_id}          - 软删除单个文件（移入回收站）
      POST   /batch-delete       - 批量软删除文件
@Modify History:
    2026/03/17 - 从 folder.py 迁入文件软删除接口
    2026/03/18 - 文件移动逻辑抽取到 move_service，增加知识库一致性校验

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from api.dependencies.auth import get_current_user_id
from api.dependencies.database import get_db_session, get_storage_manager
from api.schemas.common import ApiResponse
from api.schemas.knowledge.file import (
    BatchFileDeleteRequest,
    BatchFileDeleteResponse,
    BatchFileMoveRequest,
    BatchFileMoveResponse,
    FileDeleteResponse,
    FileMoveRequest,
    FileMoveResponse,
    FilePreviewResponse,
    SkippedFileDetail,
)
from api.schemas.knowledge.folder import FileInfo, FileListResponse
from src.db.mysql.repositories.business.workspace_file_system_repo import (
    workspace_file_system_repo,
)
from src.db.storage.manager import StorageManager
from src.service.knowledge.delete_service import knowledge_delete_service
from src.service.knowledge.move_service import knowledge_move_service

router = APIRouter(tags=["File"])


# ==================== 文件搜索（供前端 @ 文件选择器） ====================


@router.get(
    "/search",
    response_model=ApiResponse[FileListResponse],
    summary="按文件名搜索知识库内文件",
    description=(
        "在指定知识库内按文件名模糊搜索文件，供前端 @ 文件选择器使用。"
        "q 为空时返回该知识库下的前 limit 个文件。"
    ),
)
async def search_files(
    knowledge_base_id: str = Query(..., description="知识库ID（限定搜索范围）"),
    q: str = Query(default="", description="文件名关键字，空串返回前 limit 个"),
    limit: int = Query(default=20, ge=1, le=50, description="返回条数上限"),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FileListResponse]:
    try:
        records = workspace_file_system_repo.search_by_name(
            session, user_id, knowledge_base_id, q, limit
        )
    except SQLAlchemyError as e:
        logger.error(f"搜索文件失败: {e}")
        raise HTTPException(status_code=500, detail="搜索文件失败")

    files = [
        FileInfo(
            file_id=r.file_id,
            file_name=r.file_name,
            folder_id=r.folder_id,
            file_size=r.file_size,
            mime_type=r.mime_type,
            status=r.status,
            knowledge_base_id=r.knowledge_base_id or "",
            description=r.description,
        )
        for r in records
    ]

    return ApiResponse.success(
        data=FileListResponse(files=files, total=len(files)),
        message="搜索成功",
    )


# ==================== 文件移动 ====================


@router.put(
    "/{file_id}/move",
    response_model=ApiResponse[FileMoveResponse],
    summary="移动文件",
    description=(
        "将文件移动到指定文件夹。target_folder_id 为 null 时移动到知识库根目录。"
        "只能在同一知识库内移动文件。"
    ),
)
async def move_file(
    file_id: str,
    request: FileMoveRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FileMoveResponse]:
    try:
        file_name = knowledge_move_service.move_file(
            session, user_id, file_id, request.target_folder_id
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件不存在或无权限")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SQLAlchemyError as e:
        logger.error(f"移动文件失败: {e}")
        raise HTTPException(status_code=500, detail="移动文件失败")

    return ApiResponse.success(
        data=FileMoveResponse(
            file_id=file_id,
            file_name=file_name,
            folder_id=request.target_folder_id,
            knowledge_base_id="",
        ),
        message="文件移动成功",
    )


@router.post(
    "/batch-move",
    response_model=ApiResponse[BatchFileMoveResponse],
    summary="批量移动文件",
    description="将多个文件移动到指定文件夹。target_folder_id 为 null 时移动到知识库根目录。",
)
async def batch_move_files(
    request: BatchFileMoveRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[BatchFileMoveResponse]:
    try:
        move_result = knowledge_move_service.batch_move_files(
            session, user_id, request.file_ids, request.target_folder_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SQLAlchemyError as e:
        logger.error(f"批量移动文件失败: {e}")
        raise HTTPException(status_code=500, detail="批量移动文件失败")

    return ApiResponse.success(
        data=BatchFileMoveResponse(
            moved_count=move_result.moved_count,
            total_requested=move_result.total_requested,
            skipped_files=[
                SkippedFileDetail(file_id=sf.file_id, reason=sf.reason)
                for sf in move_result.skipped_files
            ],
        ),
        message=f"成功移动 {move_result.moved_count}/{move_result.total_requested} 个文件",
    )


# ==================== 文件预览 ====================


@router.get(
    "/{file_id}/preview",
    response_model=ApiResponse[FilePreviewResponse],
    summary="获取文件预览URL",
    description=(
        "根据 file_id 生成 MinIO 预签名URL 用于文件预览。"
        "URL 默认有效期 1 小时，可通过 expires 参数调整（60 ~ 86400 秒）。"
        "前端页面 /knowledge/file/{file_id} 可调用此接口获取预览地址。"
    ),
)
async def get_file_preview(
    file_id: str,
    expires: int = Query(
        default=3600, ge=60, le=86400,
        description="URL 过期时间（秒），最小 60，最大 86400，默认 3600",
    ),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
    storage: StorageManager = Depends(get_storage_manager),
) -> ApiResponse[FilePreviewResponse]:
    file_record = workspace_file_system_repo.get_by_user_and_file(
        session, user_id, file_id
    )
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在或无权限")

    if not file_record.file_path:
        raise HTTPException(
            status_code=400, detail="文件存储路径缺失，无法生成预览链接"
        )

    try:
        preview_url = await storage.get_preview_url(
            file_record.storage_path, expires
        )
    except Exception as e:
        logger.error(
            f"生成预览URL失败: file_id={file_id}, "
            f"storage_path={file_record.storage_path}, error={e}"
        )
        raise HTTPException(status_code=500, detail="生成预览URL失败")

    return ApiResponse.success(
        data=FilePreviewResponse(
            file_id=file_id,
            file_name=file_record.file_name,
            mime_type=file_record.mime_type,
            file_size=file_record.file_size,
            preview_url=preview_url,
            expires_in=expires,
        ),
        message="预览URL生成成功",
    )


# ==================== 文件删除（软删除，移入回收站） ====================


@router.delete(
    "/{file_id}",
    response_model=ApiResponse[FileDeleteResponse],
    summary="软删除单个文件",
    description="将文件移入回收站（标记为 deleted=1），不会删除关联的文档索引数据。",
)
async def soft_delete_file(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FileDeleteResponse]:
    try:
        success = knowledge_delete_service.soft_delete_file(
            session, user_id, file_id
        )
    except SQLAlchemyError as e:
        logger.error(f"软删除文件失败: {e}")
        raise HTTPException(status_code=500, detail="软删除失败")

    if not success:
        raise HTTPException(status_code=404, detail="文件不存在或已删除")

    return ApiResponse.success(
        data=FileDeleteResponse(file_id=file_id, success=True),
        message="文件已移入回收站",
    )


@router.post(
    "/batch-delete",
    response_model=ApiResponse[BatchFileDeleteResponse],
    summary="批量软删除文件",
    description="将多个文件移入回收站（标记为 deleted=1）。",
)
async def batch_soft_delete_files(
    request: BatchFileDeleteRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[BatchFileDeleteResponse]:
    try:
        deleted_count = knowledge_delete_service.batch_soft_delete_files(
            session, user_id, request.file_ids
        )
    except SQLAlchemyError as e:
        logger.error(f"批量软删除失败: {e}")
        raise HTTPException(status_code=500, detail="批量软删除失败")

    return ApiResponse.success(
        data=BatchFileDeleteResponse(
            deleted_count=deleted_count,
            total_requested=len(request.file_ids),
        ),
        message=f"成功删除 {deleted_count}/{len(request.file_ids)} 个文件",
    )
