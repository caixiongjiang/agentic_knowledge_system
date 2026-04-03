#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : folder.py
@Author  : caixiongjiang
@Date    : 2026/02/18
@Function: 
    文件夹管理路由
    提供文件夹相关的 API 端点：
      POST   /create            - 创建文件夹
      GET    /list              - 获取用户在某知识库下的文件夹列表
      GET    /children          - 获取指定文件夹的直接子文件夹
      GET    /{folder_id}       - 获取单个文件夹详情
      GET    /{folder_id}/files - 获取文件夹内的文件列表
      PUT    /{folder_id}/rename - 重命名文件夹
      PUT    /{folder_id}/move   - 移动文件夹
      DELETE /{folder_id}       - 删除文件夹（软删除，含后代）
@Modify History:
    2026/03/17 - 文件软删除迁移到 file.py 模块

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from api.dependencies.auth import get_current_user_id
from api.dependencies.database import get_db_session
from api.schemas.common import ApiResponse
from api.schemas.knowledge.folder import (
    FileInfo,
    FileListResponse,
    FolderCreateRequest,
    FolderCreateResponse,
    FolderDeleteResponse,
    FolderInfo,
    FolderListResponse,
    FolderMoveRequest,
    FolderRenameRequest,
)
from src.db.mysql.models.business.workspace_file_system import WorkspaceFileSystem
from src.db.mysql.models.business.workspace_folder import WorkspaceFolder
from src.db.mysql.repositories.business.knowledge_base_repo import (
    knowledge_base_repo,
)
from src.db.mysql.repositories.business.workspace_file_system_repo import (
    workspace_file_system_repo,
)
from src.db.mysql.repositories.business.workspace_folder_repo import (
    workspace_folder_repo,
)

router = APIRouter(tags=["Folder"])


def _to_file_info(file: WorkspaceFileSystem) -> FileInfo:
    """将文件 ORM 模型转为 Pydantic 响应模型"""
    return FileInfo(
        file_id=file.file_id,
        file_name=file.file_name,
        folder_id=file.folder_id,
        file_size=file.file_size,
        mime_type=file.mime_type,
        status=file.status,
        knowledge_base_id=file.knowledge_base_id or "",
        description=file.description,
    )


def _to_folder_info(folder: WorkspaceFolder) -> FolderInfo:
    """将 ORM 模型转为 Pydantic 响应模型"""
    return FolderInfo(
        folder_id=folder.folder_id,
        folder_name=folder.folder_name,
        full_path=folder.full_path,
        parent_folder_id=folder.parent_folder_id,
        depth=folder.depth,
        is_default=folder.is_default,
        knowledge_base_id=folder.knowledge_base_id or "",
        description=folder.description,
    )


# ==================== 创建 ====================


@router.post(
    "/create",
    response_model=ApiResponse[FolderCreateResponse],
    summary="创建文件夹",
    description="在指定知识库下创建文件夹。可通过 parent_folder_id 指定父文件夹以实现嵌套。",
)
async def create_folder(
    request: FolderCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FolderCreateResponse]:
    kb = knowledge_base_repo.get_by_id_and_user(
        session, request.knowledge_base_id, user_id
    )
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在或无权限")

    parent_path = "/"
    depth = 0

    if request.parent_folder_id:
        parent_folder = session.query(WorkspaceFolder).filter(
            WorkspaceFolder.folder_id == request.parent_folder_id,
            WorkspaceFolder.user_id == user_id,
            WorkspaceFolder.deleted == 0,
        ).first()
        if not parent_folder:
            raise HTTPException(status_code=404, detail="父文件夹不存在或无权限")
        parent_path = parent_folder.full_path
        depth = parent_folder.depth + 1

    full_path = f"{parent_path}{request.folder_name}/"

    existing = workspace_folder_repo.get_by_full_path(session, user_id, full_path)
    if existing and existing.knowledge_base_id == request.knowledge_base_id:
        raise HTTPException(status_code=409, detail=f"同路径文件夹已存在: {full_path}")

    folder_id = f"folder-{uuid.uuid4()}"
    folder = workspace_folder_repo.create(
        session,
        folder_id=folder_id,
        user_id=user_id,
        folder_name=request.folder_name,
        parent_folder_id=request.parent_folder_id,
        full_path=full_path,
        depth=depth,
        sort_order=0,
        is_default=0,
        knowledge_base_id=request.knowledge_base_id,
        knowledge_base_name=kb.knowledge_base_name,
        description=request.description,
        creator=user_id,
    )
    if not folder:
        raise HTTPException(status_code=500, detail="创建文件夹失败")

    logger.info(
        f"创建文件夹: user_id={user_id}, folder_id={folder_id}, "
        f"path={full_path}, kb_id={request.knowledge_base_id}"
    )

    return ApiResponse.success(
        data=FolderCreateResponse(
            folder_id=folder_id,
            folder_name=request.folder_name,
            full_path=full_path,
            parent_folder_id=request.parent_folder_id,
            depth=depth,
            knowledge_base_id=request.knowledge_base_id,
        ),
        message="文件夹创建成功",
    )


# ==================== 查询 ====================


@router.get(
    "/list",
    response_model=ApiResponse[FolderListResponse],
    summary="获取完整文件夹树（平铺）",
    description=(
        "一次性返回用户在指定知识库下的所有层级文件夹（平铺列表，按 depth + sort_order 排序）。"
        "适用于：侧边栏文件夹导航树渲染、移动文件夹时的目标选择器、面包屑路径构建等需要完整目录结构的场景。"
        "如果只需要浏览某一层的子文件夹，请使用 GET /children 接口。"
    ),
)
async def list_folders(
    knowledge_base_id: str = Query(..., description="知识库ID"),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FolderListResponse]:
    folders = workspace_folder_repo.get_by_user_and_knowledge_base(
        session, user_id, knowledge_base_id
    )
    items = [_to_folder_info(f) for f in folders]
    return ApiResponse.success(
        data=FolderListResponse(folders=items, total=len(items))
    )


@router.get(
    "/children",
    response_model=ApiResponse[FolderListResponse],
    summary="获取当前目录的子文件夹",
    description=(
        "获取指定父文件夹下的直接子文件夹（仅一层，不递归）。"
        "适用于：逐层浏览文件夹、打开某个文件夹时加载其内容。"
        "parent_folder_id 不传则返回根目录下的文件夹。"
    ),
)
async def list_children(
    parent_folder_id: Optional[str] = Query(
        default=None, description="父文件夹ID（不传则查询根目录）"
    ),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FolderListResponse]:
    children = workspace_folder_repo.get_children(
        session, user_id, parent_folder_id
    )
    items = [_to_folder_info(f) for f in children]
    return ApiResponse.success(
        data=FolderListResponse(folders=items, total=len(items))
    )


@router.get(
    "/root-files",
    response_model=ApiResponse[FileListResponse],
    summary="获取知识库根目录文件",
    description=(
        "获取指定知识库根目录下的文件（即 folder_id 为空的文件）。"
        "这些文件不属于任何文件夹，直接挂在知识库根目录下。"
    ),
)
async def list_root_files(
    knowledge_base_id: str = Query(..., description="知识库ID"),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FileListResponse]:
    files = workspace_file_system_repo.get_by_folder_id(
        session, user_id, folder_id=None, knowledge_base_id=knowledge_base_id
    )
    items = [_to_file_info(f) for f in files]
    return ApiResponse.success(
        data=FileListResponse(files=items, total=len(items))
    )


@router.get(
    "/{folder_id}",
    response_model=ApiResponse[FolderInfo],
    summary="获取文件夹详情",
    description="根据 folder_id 获取单个文件夹的详细信息。",
)
async def get_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FolderInfo]:
    folder = session.query(WorkspaceFolder).filter(
        WorkspaceFolder.folder_id == folder_id,
        WorkspaceFolder.user_id == user_id,
        WorkspaceFolder.deleted == 0,
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在或无权限")

    return ApiResponse.success(data=_to_folder_info(folder))


@router.get(
    "/{folder_id}/files",
    response_model=ApiResponse[FileListResponse],
    summary="获取文件夹内的文件列表",
    description="获取指定文件夹下的所有文件（不含子文件夹中的文件）。",
)
async def list_folder_files(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FileListResponse]:
    folder = session.query(WorkspaceFolder).filter(
        WorkspaceFolder.folder_id == folder_id,
        WorkspaceFolder.user_id == user_id,
        WorkspaceFolder.deleted == 0,
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在或无权限")

    files = workspace_file_system_repo.get_by_folder_id(
        session, user_id, folder_id
    )
    items = [_to_file_info(f) for f in files]
    return ApiResponse.success(
        data=FileListResponse(files=items, total=len(items))
    )


# ==================== 修改 ====================


@router.put(
    "/{folder_id}/rename",
    response_model=ApiResponse[FolderInfo],
    summary="重命名文件夹",
    description="重命名文件夹，会级联更新所有后代文件夹的 full_path。默认文件夹不允许重命名。",
)
async def rename_folder(
    folder_id: str,
    request: FolderRenameRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FolderInfo]:
    folder = session.query(WorkspaceFolder).filter(
        WorkspaceFolder.folder_id == folder_id,
        WorkspaceFolder.user_id == user_id,
        WorkspaceFolder.deleted == 0,
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在或无权限")
    if folder.is_default == 1:
        raise HTTPException(status_code=400, detail="默认文件夹不允许重命名")

    try:
        updated = workspace_folder_repo.rename(
            session, user_id, folder_id, request.folder_name, updater=user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if not updated:
        raise HTTPException(status_code=500, detail="重命名失败")

    return ApiResponse.success(
        data=_to_folder_info(updated), message="重命名成功"
    )


@router.put(
    "/{folder_id}/move",
    response_model=ApiResponse[FolderInfo],
    summary="移动文件夹",
    description=(
        "将文件夹移动到新的父文件夹下，级联更新所有后代的 full_path 和 depth。"
        "默认文件夹不允许移动。不能移动到自身的子目录下。"
    ),
)
async def move_folder(
    folder_id: str,
    request: FolderMoveRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FolderInfo]:
    folder = session.query(WorkspaceFolder).filter(
        WorkspaceFolder.folder_id == folder_id,
        WorkspaceFolder.user_id == user_id,
        WorkspaceFolder.deleted == 0,
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在或无权限")
    if folder.is_default == 1:
        raise HTTPException(status_code=400, detail="默认文件夹不允许移动")

    try:
        updated = workspace_folder_repo.move(
            session,
            user_id,
            folder_id,
            request.target_parent_folder_id,
            updater=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not updated:
        raise HTTPException(status_code=500, detail="移动失败")

    return ApiResponse.success(
        data=_to_folder_info(updated), message="移动成功"
    )


# ==================== 删除 ====================


@router.delete(
    "/{folder_id}",
    response_model=ApiResponse[FolderDeleteResponse],
    summary="删除文件夹",
    description=(
        "删除文件夹及其所有后代文件夹。"
        "如果文件夹树内包含文件：移入回收站（可恢复），文件一并级联删除。"
        "如果文件夹树内没有任何文件：直接永久删除空文件夹。"
        "默认文件夹不允许删除。"
    ),
)
async def delete_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[FolderDeleteResponse]:
    folder = session.query(WorkspaceFolder).filter(
        WorkspaceFolder.folder_id == folder_id,
        WorkspaceFolder.user_id == user_id,
        WorkspaceFolder.deleted == 0,
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在或无权限")
    if folder.is_default == 1:
        raise HTTPException(status_code=400, detail="默认文件夹不允许删除")

    try:
        descendant_rows = session.query(WorkspaceFolder.folder_id).filter(
            WorkspaceFolder.user_id == user_id,
            WorkspaceFolder.full_path.like(f"{folder.full_path}%"),
            WorkspaceFolder.folder_id != folder_id,
            WorkspaceFolder.deleted == 0,
        ).all()
        all_folder_ids = [folder_id] + [r[0] for r in descendant_rows]

        file_count = session.query(WorkspaceFileSystem).filter(
            WorkspaceFileSystem.user_id == user_id,
            WorkspaceFileSystem.folder_id.in_(all_folder_ids),
            WorkspaceFileSystem.deleted == 0,
        ).count()

        if file_count > 0:
            deleted_folder_ids = (
                workspace_folder_repo.soft_delete_with_descendants(
                    session,
                    user_id=user_id,
                    folder_id=folder_id,
                    full_path_prefix=folder.full_path,
                    updater=user_id,
                )
            )
            deleted_file_count = (
                workspace_file_system_repo.cascade_soft_delete_by_folder_ids(
                    session,
                    user_id=user_id,
                    folder_ids=deleted_folder_ids,
                    updater=user_id,
                )
            )
            session.commit()

            logger.info(
                f"文件夹移入回收站: user_id={user_id}, folder_id={folder_id}, "
                f"path={folder.full_path}, folders={len(deleted_folder_ids)}, "
                f"files={deleted_file_count}"
            )
            return ApiResponse.success(
                data=FolderDeleteResponse(
                    folder_id=folder_id,
                    deleted_folder_count=len(deleted_folder_ids),
                    deleted_file_count=deleted_file_count,
                ),
                message=(
                    f"已移入回收站：{len(deleted_folder_ids)} 个文件夹，"
                    f"{deleted_file_count} 个文件"
                ),
            )
        else:
            folder_count = session.query(WorkspaceFolder).filter(
                WorkspaceFolder.folder_id.in_(all_folder_ids),
            ).delete(synchronize_session='fetch')
            session.commit()

            logger.info(
                f"永久删除空文件夹: user_id={user_id}, folder_id={folder_id}, "
                f"path={folder.full_path}, count={folder_count}"
            )
            return ApiResponse.success(
                data=FolderDeleteResponse(
                    folder_id=folder_id,
                    deleted_folder_count=folder_count,
                    deleted_file_count=0,
                ),
                message=f"已删除 {folder_count} 个空文件夹",
            )

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"删除文件夹失败: {e}")
        raise HTTPException(status_code=500, detail="删除失败")
