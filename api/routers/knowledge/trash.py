#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : trash.py
@Author  : caixiongjiang
@Date    : 2026/02/19
@Function: 
    回收站管理路由（原子化操作：保留文件夹层级，仅顶层条目可操作）
    提供回收站相关的 API 端点：

    查看/浏览（只读预览）：
      GET    /list                             - 查看回收站顶层列表（仅 deleted=1）
      GET    /folder/{folder_id}/children      - 浏览回收站文件夹的子文件夹（只读预览）
      GET    /folder/{folder_id}/files         - 浏览回收站文件夹的子文件（只读预览）

    恢复（仅 deleted=1 顶层条目）：
      POST   /restore/folder/{folder_id}       - 恢复文件夹（仅 deleted=1，含后代+文件）
      POST   /restore/file/{file_id}           - 恢复单个文件（仅 deleted=1）

    永久删除（仅 deleted=1 顶层条目，含级联删除索引数据）：
      DELETE /folder/{folder_id}               - 永久删除文件夹（仅 deleted=1，含后代+文件+索引数据）
      DELETE /file/{file_id}                   - 永久删除单个文件（仅 deleted=1，含索引数据）
      DELETE /empty                            - 清空回收站（含索引数据）

@Modify History:
    2026/02/19 - 升级为方案 B，支持回收站内浏览、部分恢复/删除
    2026/03/09 - 永久删除增加级联删除（清理 Milvus/MongoDB/Storage 索引数据）
    2026/03/17 - 改为原子化操作：恢复/永久删除仅限 deleted=1 顶层条目，避免幽灵文件
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from api.dependencies.auth import get_current_user_id
from api.dependencies.database import get_db_session, get_storage_manager
from api.schemas.common import ApiResponse
from src.db.storage.manager import StorageManager
from src.service.knowledge.delete_service import knowledge_delete_service
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
    summary="浏览回收站文件夹的子文件夹（只读预览）",
    description=(
        "在回收站中展开一个已删除的文件夹，查看其直接子文件夹（只读预览）。"
        "返回 parent_folder_id 匹配且 deleted=1 或 deleted=2 的文件夹。"
        "该接口仅用于预览，子项不支持独立的恢复或永久删除操作。"
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
    summary="浏览回收站文件夹的子文件（只读预览）",
    description=(
        "在回收站中查看一个已删除文件夹的直接子文件（只读预览）。"
        "返回 folder_id 匹配且 deleted=1 或 deleted=2 的文件。"
        "该接口仅用于预览，子项不支持独立的恢复或永久删除操作。"
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
        "从回收站恢复文件夹（仅 deleted=1 的顶层条目），"
        "同时恢复其所有后代文件夹和关联文件。"
        "如果父文件夹不存在或已被删除，则将该文件夹移到根目录。"
    ),
)
async def restore_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[TrashRestoreResponse]:
    try:
        restored_folder_ids = workspace_folder_repo.restore_folder_with_descendants(
            session, user_id, folder_id
        )
        restored_file_count = workspace_file_system_repo.restore_by_folder_ids(
            session, user_id, restored_folder_ids
        )
        session.commit()
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"恢复文件夹失败: {e}")
        raise HTTPException(status_code=500, detail="恢复失败")

    folder_count = len(restored_folder_ids)
    logger.info(
        f"恢复文件夹: user_id={user_id}, folder_id={folder_id}, "
        f"folders={folder_count}, files={restored_file_count}"
    )

    return ApiResponse.success(
        data=TrashRestoreResponse(
            item_type=TrashItemType.FOLDER,
            item_id=folder_id,
            restored_folder_count=folder_count,
            restored_file_count=restored_file_count,
        ),
        message=f"成功恢复 {folder_count} 个文件夹和 {restored_file_count} 个文件",
    )


@router.post(
    "/restore/file/{file_id}",
    response_model=ApiResponse[TrashRestoreResponse],
    summary="恢复单个文件",
    description=(
        "从回收站恢复单个文件（仅 deleted=1 的顶层条目）。"
        "如果文件的父文件夹不存在或已被删除，则将文件移到根目录。"
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
    if not file_obj or file_obj.deleted != 1:
        raise HTTPException(status_code=404, detail="回收站中未找到该文件（仅支持顶层条目）")

    try:
        if file_obj.folder_id:
            parent_folder = session.query(WorkspaceFolder).filter(
                WorkspaceFolder.folder_id == file_obj.folder_id,
                WorkspaceFolder.user_id == user_id,
                WorkspaceFolder.deleted == 0,
            ).first()
            if not parent_folder:
                file_obj.folder_id = None

        file_obj.deleted = 0
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"恢复文件失败: {e}")
        raise HTTPException(status_code=500, detail="恢复失败")

    logger.info(f"恢复文件: user_id={user_id}, file_id={file_id}")

    return ApiResponse.success(
        data=TrashRestoreResponse(
            item_type=TrashItemType.FILE,
            item_id=file_id,
            restored_folder_count=0,
            restored_file_count=1,
        ),
        message="文件恢复成功",
    )



# ==================== 永久删除（含级联删除索引数据） ====================


async def _cascade_delete_files(
    session: Session,
    user_id: str,
    file_ids: list[str],
    storage_manager: StorageManager,
) -> None:
    """对一组即将被硬删除的 file_id 执行级联删除（Milvus/MongoDB/Storage）

    在硬删除 workspace_file_system 记录之前调用。
    级联删除的错误只记录日志，不阻塞回收站删除流程。
    """
    for file_id in file_ids:
        try:
            result = await knowledge_delete_service.permanent_delete_file(
                session, user_id, file_id, storage_manager
            )
            if result.has_errors:
                logger.warning(
                    f"级联删除部分失败: file_id={file_id}, errors={result.errors}"
                )
        except Exception as e:
            logger.error(f"级联删除异常: file_id={file_id}, error={e}")


@router.delete(
    "/folder/{folder_id}",
    response_model=ApiResponse[TrashEmptyResponse],
    summary="永久删除文件夹",
    description=(
        "从回收站永久删除文件夹（仅 deleted=1 的顶层条目）"
        "及其所有后代文件夹和关联文件（不可恢复）。"
        "同时级联删除文件在 Milvus、MongoDB、对象存储中的索引数据。"
    ),
)
async def permanent_delete_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
    storage_manager: StorageManager = Depends(get_storage_manager),
) -> ApiResponse[TrashEmptyResponse]:
    try:
        folder_ids, folder_count = (
            workspace_folder_repo.hard_delete_subfolder(
                session, user_id, folder_id
            )
        )

        affected_files = []
        for fid in folder_ids:
            files = workspace_file_system_repo.get_deleted_files_by_folder(
                session, user_id, fid
            )
            affected_files.extend(files)
        affected_file_ids = [f.file_id for f in affected_files]

        if affected_file_ids:
            await _cascade_delete_files(
                session, user_id, affected_file_ids, storage_manager
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
    description=(
        "从回收站永久删除单个文件（仅 deleted=1 的顶层条目，不可恢复）。"
        "同时级联删除文件在 Milvus、MongoDB、对象存储中的索引数据。"
    ),
)
async def permanent_delete_file(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
    storage_manager: StorageManager = Depends(get_storage_manager),
) -> ApiResponse[TrashEmptyResponse]:
    try:
        await _cascade_delete_files(
            session, user_id, [file_id], storage_manager
        )

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
    description=(
        "永久删除回收站中的所有文件夹和文件（不可恢复）。"
        "同时级联删除所有文件在 Milvus、MongoDB、对象存储中的索引数据。"
    ),
)
async def empty_trash(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
    storage_manager: StorageManager = Depends(get_storage_manager),
) -> ApiResponse[TrashEmptyResponse]:
    try:
        all_deleted_files = workspace_file_system_repo.get_deleted_files(
            session, user_id
        )
        all_file_ids = [f.file_id for f in all_deleted_files]

        if all_file_ids:
            await _cascade_delete_files(
                session, user_id, all_file_ids, storage_manager
            )

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
