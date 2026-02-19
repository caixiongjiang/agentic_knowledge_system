#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : trash.py
@Author  : caixiongjiang
@Date    : 2026/02/19
@Function: 
    回收站管理路由（方案 B：保留文件夹层级）
    提供回收站相关的 API 端点：

    查看/浏览：
      GET    /list                             - 查看回收站顶层列表（deleted=1）
      GET    /folder/{folder_id}/children      - 浏览回收站文件夹的子文件夹
      GET    /folder/{folder_id}/files         - 浏览回收站文件夹的子文件

    恢复：
      POST   /restore/folder/{folder_id}       - 恢复文件夹（支持 deleted=1/2，含后代+文件，自动重建祖先路径）
      POST   /restore/file/{file_id}           - 恢复单个文件（支持 deleted=1/2，自动重建祖先路径）

    永久删除：
      DELETE /folder/{folder_id}               - 永久删除文件夹（支持 deleted=1/2，含后代+文件）
      DELETE /file/{file_id}                   - 永久删除单个文件（支持 deleted=1/2）
      DELETE /empty                            - 清空回收站

@Modify History:
    2026/02/19 - 升级为方案 B，支持回收站内浏览、部分恢复/删除
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from api.dependencies.auth import get_current_user_id
from api.dependencies.database import get_db_session
from api.schemas.common import ApiResponse
from api.schemas.knowledge.trash import (
    TrashEmptyResponse,
    TrashFolderChildItem,
    TrashFolderChildrenResponse,
    TrashFolderFileItem,
    TrashFolderFilesResponse,
    TrashItem,
    TrashItemType,
    TrashListResponse,
    TrashRestoreResponse,
)
from src.db.mysql.models.business.workspace_folder import WorkspaceFolder
from src.db.mysql.repositories.business.workspace_folder_repo import (
    workspace_folder_repo,
)
from src.db.mysql.repositories.business.workspace_file_system_repo import (
    workspace_file_system_repo,
)

router = APIRouter(tags=["Trash"])


# ==================== 查看 ====================


@router.get(
    "/list",
    response_model=ApiResponse[TrashListResponse],
    summary="查看回收站顶层列表",
    description=(
        "获取当前用户回收站中的顶层条目（文件夹和文件），"
        "仅返回 deleted=1 的条目。对于文件夹条目可进一步通过"
        "浏览接口展开查看其内部子文件夹和子文件。"
        "可按 knowledge_base_id 筛选。"
    ),
)
async def list_trash(
    knowledge_base_id: Optional[str] = Query(
        default=None, description="按知识库ID筛选"
    ),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[TrashListResponse]:
    folders = workspace_folder_repo.get_deleted_folders(
        session, user_id, knowledge_base_id
    )
    files = workspace_file_system_repo.get_deleted_files(
        session, user_id, knowledge_base_id
    )

    items: list[TrashItem] = []
    for f in folders:
        items.append(TrashItem(
            item_type=TrashItemType.FOLDER,
            item_id=f.folder_id,
            item_name=f.folder_name,
            full_path=f.full_path,
            knowledge_base_id=f.knowledge_base_id or "",
            deleted_at=f.update_time.isoformat() if f.update_time else None,
        ))
    for f in files:
        items.append(TrashItem(
            item_type=TrashItemType.FILE,
            item_id=f.file_id,
            item_name=f.file_name,
            folder_id=f.folder_id,
            file_size=f.file_size,
            mime_type=f.mime_type,
            knowledge_base_id=f.knowledge_base_id or "",
            deleted_at=f.update_time.isoformat() if f.update_time else None,
        ))

    return ApiResponse.success(
        data=TrashListResponse(items=items, total=len(items))
    )


@router.get(
    "/folder/{folder_id}/children",
    response_model=ApiResponse[TrashFolderChildrenResponse],
    summary="浏览回收站文件夹的子文件夹",
    description=(
        "在回收站中展开一个已删除的文件夹，查看其直接子文件夹。"
        "返回 parent_folder_id 匹配且 deleted=1 或 deleted=2 的文件夹。"
    ),
)
async def browse_trash_folder_children(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[TrashFolderChildrenResponse]:
    folder = session.query(WorkspaceFolder).filter(
        WorkspaceFolder.folder_id == folder_id,
        WorkspaceFolder.user_id == user_id,
        WorkspaceFolder.deleted.in_([1, 2]),
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="回收站中未找到该文件夹")

    children = workspace_folder_repo.get_deleted_children(
        session, user_id, folder_id
    )

    child_items = [
        TrashFolderChildItem(
            folder_id=c.folder_id,
            folder_name=c.folder_name,
            full_path=c.full_path,
            parent_folder_id=c.parent_folder_id,
            depth=c.depth,
            knowledge_base_id=c.knowledge_base_id or "",
        )
        for c in children
    ]

    return ApiResponse.success(
        data=TrashFolderChildrenResponse(
            folder_id=folder_id,
            children=child_items,
            total=len(child_items),
        )
    )


@router.get(
    "/folder/{folder_id}/files",
    response_model=ApiResponse[TrashFolderFilesResponse],
    summary="浏览回收站文件夹的子文件",
    description=(
        "在回收站中查看一个已删除文件夹的直接子文件。"
        "返回 folder_id 匹配且 deleted=1 或 deleted=2 的文件。"
    ),
)
async def browse_trash_folder_files(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[TrashFolderFilesResponse]:
    folder = session.query(WorkspaceFolder).filter(
        WorkspaceFolder.folder_id == folder_id,
        WorkspaceFolder.user_id == user_id,
        WorkspaceFolder.deleted.in_([1, 2]),
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="回收站中未找到该文件夹")

    files = workspace_file_system_repo.get_deleted_files_by_folder(
        session, user_id, folder_id
    )

    file_items = [
        TrashFolderFileItem(
            file_id=f.file_id,
            file_name=f.file_name,
            folder_id=f.folder_id,
            file_size=f.file_size,
            mime_type=f.mime_type,
            knowledge_base_id=f.knowledge_base_id or "",
        )
        for f in files
    ]

    return ApiResponse.success(
        data=TrashFolderFilesResponse(
            folder_id=folder_id,
            files=file_items,
            total=len(file_items),
        )
    )


# ==================== 恢复 ====================


@router.post(
    "/restore/folder/{folder_id}",
    response_model=ApiResponse[TrashRestoreResponse],
    summary="恢复文件夹",
    description=(
        "从回收站恢复文件夹（支持 deleted=1 和 deleted=2），"
        "同时恢复其所有后代文件夹和关联文件。"
        "如果文件夹的祖先仍处于删除状态，会自动重建整条祖先路径。"
        "如果最顶层祖先的父文件夹不存在，则将其移到根目录。"
    ),
)
async def restore_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[TrashRestoreResponse]:
    try:
        restored_folder_ids, restored_ancestor_ids = (
            workspace_folder_repo.restore_subfolder_with_ancestors(
                session, user_id, folder_id
            )
        )
        all_affected_folder_ids = restored_folder_ids + restored_ancestor_ids
        restored_file_count = workspace_file_system_repo.restore_by_folder_ids(
            session, user_id, all_affected_folder_ids
        )
        session.commit()
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"恢复文件夹失败: {e}")
        raise HTTPException(status_code=500, detail="恢复失败")

    total_folders = len(restored_folder_ids) + len(restored_ancestor_ids)
    logger.info(
        f"恢复文件夹: user_id={user_id}, folder_id={folder_id}, "
        f"self+descendants={len(restored_folder_ids)}, "
        f"ancestors={len(restored_ancestor_ids)}, files={restored_file_count}"
    )

    return ApiResponse.success(
        data=TrashRestoreResponse(
            item_type=TrashItemType.FOLDER,
            item_id=folder_id,
            restored_folder_count=total_folders,
            restored_file_count=restored_file_count,
        ),
        message=(
            f"成功恢复 {total_folders} 个文件夹和 {restored_file_count} 个文件"
            + (f"（含 {len(restored_ancestor_ids)} 个祖先文件夹）"
               if restored_ancestor_ids else "")
        ),
    )


@router.post(
    "/restore/file/{file_id}",
    response_model=ApiResponse[TrashRestoreResponse],
    summary="恢复单个文件",
    description=(
        "从回收站恢复单个文件（支持 deleted=1 和 deleted=2）。"
        "如果文件的父文件夹仍处于删除状态，会自动重建整条祖先文件夹路径。"
        "如果祖先链的最顶层父文件夹不存在，则将其移到根目录。"
    ),
)
async def restore_file(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[TrashRestoreResponse]:
    file_obj = workspace_file_system_repo.get_by_user_and_file(
        session, user_id, file_id
    )
    if not file_obj or file_obj.deleted not in (1, 2):
        raise HTTPException(status_code=404, detail="回收站中未找到该文件")

    restored_folder_count = 0

    try:
        if file_obj.folder_id:
            parent_folder = session.query(WorkspaceFolder).filter(
                WorkspaceFolder.folder_id == file_obj.folder_id,
                WorkspaceFolder.user_id == user_id,
            ).first()

            if parent_folder and parent_folder.deleted != 0:
                parent_folder.deleted = 0
                ancestor_ids = workspace_folder_repo.restore_ancestors_chain(
                    session, user_id, parent_folder.parent_folder_id
                ) if parent_folder.parent_folder_id else []
                restored_folder_count = 1 + len(ancestor_ids)
            elif not parent_folder:
                file_obj.folder_id = None

        file_obj.deleted = 0
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"恢复文件失败: {e}")
        raise HTTPException(status_code=500, detail="恢复失败")

    logger.info(
        f"恢复文件: user_id={user_id}, file_id={file_id}, "
        f"restored_ancestors={restored_folder_count}"
    )

    return ApiResponse.success(
        data=TrashRestoreResponse(
            item_type=TrashItemType.FILE,
            item_id=file_id,
            restored_folder_count=restored_folder_count,
            restored_file_count=1,
        ),
        message=(
            f"文件恢复成功"
            + (f"，同时恢复了 {restored_folder_count} 个祖先文件夹"
               if restored_folder_count > 0 else "")
        ),
    )



# ==================== 永久删除 ====================


@router.delete(
    "/folder/{folder_id}",
    response_model=ApiResponse[TrashEmptyResponse],
    summary="永久删除文件夹",
    description=(
        "从回收站永久删除文件夹（支持 deleted=1 和 deleted=2）"
        "及其所有后代文件夹和关联文件（不可恢复）。"
    ),
)
async def permanent_delete_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[TrashEmptyResponse]:
    try:
        folder_ids, folder_count = (
            workspace_folder_repo.hard_delete_subfolder(
                session, user_id, folder_id
            )
        )
        file_count = workspace_file_system_repo.hard_delete_by_folder_ids(
            session, user_id, folder_ids
        )
        session.commit()
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"永久删除文件夹失败: {e}")
        raise HTTPException(status_code=500, detail="永久删除失败")

    logger.info(
        f"永久删除文件夹: user_id={user_id}, folder_id={folder_id}, "
        f"folders={folder_count}, files={file_count}"
    )

    return ApiResponse.success(
        data=TrashEmptyResponse(
            deleted_folder_count=folder_count,
            deleted_file_count=file_count,
        ),
        message=f"永久删除 {folder_count} 个文件夹和 {file_count} 个文件",
    )


@router.delete(
    "/file/{file_id}",
    response_model=ApiResponse[TrashEmptyResponse],
    summary="永久删除单个文件",
    description="从回收站永久删除单个文件（支持 deleted=1 和 deleted=2，不可恢复）。",
)
async def permanent_delete_file(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[TrashEmptyResponse]:
    try:
        deleted = workspace_file_system_repo.hard_delete_by_file_id(
            session, user_id, file_id
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="回收站中未找到该文件")
        session.commit()
    except HTTPException:
        session.rollback()
        raise
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"永久删除文件失败: {e}")
        raise HTTPException(status_code=500, detail="永久删除失败")

    return ApiResponse.success(
        data=TrashEmptyResponse(
            deleted_folder_count=0,
            deleted_file_count=1,
        ),
        message="文件已永久删除",
    )


# ==================== 清空回收站 ====================


@router.delete(
    "/empty",
    response_model=ApiResponse[TrashEmptyResponse],
    summary="清空回收站",
    description="永久删除回收站中的所有文件夹和文件（不可恢复）。",
)
async def empty_trash(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[TrashEmptyResponse]:
    try:
        folder_ids, folder_count = workspace_folder_repo.hard_delete_all_trash(
            session, user_id
        )
        file_count = workspace_file_system_repo.hard_delete_by_folder_ids(
            session, user_id, folder_ids
        )
        file_count += workspace_file_system_repo.hard_delete_all_trash(
            session, user_id
        )
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"清空回收站失败: {e}")
        raise HTTPException(status_code=500, detail="清空回收站失败")

    logger.info(
        f"清空回收站: user_id={user_id}, "
        f"folders={folder_count}, files={file_count}"
    )

    return ApiResponse.success(
        data=TrashEmptyResponse(
            deleted_folder_count=folder_count,
            deleted_file_count=file_count,
        ),
        message=f"回收站已清空：删除 {folder_count} 个文件夹和 {file_count} 个文件",
    )
