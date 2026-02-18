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
      POST /create  - 创建文件夹
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from api.dependencies.auth import get_current_user_id
from api.dependencies.database import get_db_session
from api.schemas.common import ApiResponse
from api.schemas.knowledge.folder import FolderCreateRequest, FolderCreateResponse
from src.db.mysql.models.business.workspace_folder import WorkspaceFolder
from src.db.mysql.repositories.business.workspace_folder_repo import (
    workspace_folder_repo,
)

router = APIRouter(tags=["Folder"])


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
    """创建文件夹，自动计算 full_path 和 depth"""

    parent_folder: Optional[WorkspaceFolder] = None
    parent_path = "/"
    depth = 0

    if request.parent_folder_id:
        parent_folder = session.query(WorkspaceFolder).filter(
            WorkspaceFolder.folder_id == request.parent_folder_id,
            WorkspaceFolder.user_id == user_id,
            WorkspaceFolder.deleted == 0,
        ).first()

        if not parent_folder:
            raise HTTPException(
                status_code=404, detail="父文件夹不存在或无权限"
            )
        parent_path = parent_folder.full_path
        depth = parent_folder.depth + 1

    full_path = f"{parent_path}{request.folder_name}/"

    existing = workspace_folder_repo.get_by_full_path(
        session, user_id, full_path
    )
    if existing and existing.knowledge_base_id == request.knowledge_base_id:
        raise HTTPException(
            status_code=409, detail=f"同路径文件夹已存在: {full_path}"
        )

    folder_id = str(uuid.uuid4())
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
        knowledge_base_name=request.knowledge_base_name,
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
