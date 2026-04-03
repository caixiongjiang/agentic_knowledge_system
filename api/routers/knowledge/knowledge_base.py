#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : knowledge_base.py
@Author  : caixiongjiang
@Date    : 2026/02/19
@Function: 
    知识库管理路由
    提供知识库相关的 API 端点：
      POST   /create               - 创建知识库
      GET    /list                  - 获取用户的知识库列表
      GET    /children              - 获取子知识库列表
      GET    /{knowledge_base_id}   - 获取知识库详情
      PUT    /{knowledge_base_id}   - 更新知识库
      DELETE /{knowledge_base_id}   - 删除知识库（物理删除，需无文件）
@Modify History:

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
from api.schemas.knowledge.knowledge_base import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDeleteResponse,
    KnowledgeBaseInfo,
    KnowledgeBaseListResponse,
    KnowledgeBaseUpdateRequest,
)
from src.db.mysql.models.business.knowledge_base import KnowledgeBase
from src.db.mysql.repositories.business.knowledge_base_repo import (
    knowledge_base_repo,
)

router = APIRouter(tags=["KnowledgeBase"])


def _to_kb_info(kb: KnowledgeBase) -> KnowledgeBaseInfo:
    return KnowledgeBaseInfo(
        knowledge_base_id=kb.knowledge_base_id,
        knowledge_base_name=kb.knowledge_base_name,
        parent_knowledge_base_id=kb.parent_knowledge_base_id,
        knowledge_type=kb.knowledge_type,
        description=kb.description,
    )


# ==================== 创建 ====================


@router.post(
    "/create",
    response_model=ApiResponse[KnowledgeBaseInfo],
    summary="创建知识库",
    description="创建一个新的知识库。同一用户下知识库名称不能重复。",
)
async def create_knowledge_base(
    request: KnowledgeBaseCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[KnowledgeBaseInfo]:
    if knowledge_base_repo.name_exists(
        session, user_id, request.knowledge_base_name
    ):
        raise HTTPException(
            status_code=409,
            detail=f"知识库名称已存在: {request.knowledge_base_name}",
        )

    if request.parent_knowledge_base_id:
        parent = knowledge_base_repo.get_by_id_and_user(
            session, request.parent_knowledge_base_id, user_id
        )
        if not parent:
            raise HTTPException(
                status_code=404, detail="父知识库不存在或无权限"
            )

    kb_id = f"kb-{uuid.uuid4()}"
    kb = knowledge_base_repo.create(
        session,
        knowledge_base_id=kb_id,
        user_id=user_id,
        knowledge_base_name=request.knowledge_base_name,
        parent_knowledge_base_id=request.parent_knowledge_base_id,
        knowledge_type=request.knowledge_type,
        description=request.description,
        creator=user_id,
    )
    if not kb:
        raise HTTPException(status_code=500, detail="创建知识库失败")

    logger.info(
        f"创建知识库: user_id={user_id}, kb_id={kb_id}, "
        f"name={request.knowledge_base_name}"
    )
    return ApiResponse.success(data=_to_kb_info(kb), message="知识库创建成功")


# ==================== 查询 ====================


@router.get(
    "/list",
    response_model=ApiResponse[KnowledgeBaseListResponse],
    summary="获取知识库列表",
    description="获取当前用户的所有知识库，按创建时间倒序排列。",
)
async def list_knowledge_bases(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[KnowledgeBaseListResponse]:
    kbs = knowledge_base_repo.get_by_user_id(session, user_id)
    items = [_to_kb_info(kb) for kb in kbs]
    return ApiResponse.success(
        data=KnowledgeBaseListResponse(
            knowledge_bases=items, total=len(items)
        )
    )


@router.get(
    "/children",
    response_model=ApiResponse[KnowledgeBaseListResponse],
    summary="获取子知识库列表",
    description=(
        "获取指定父知识库下的直接子知识库。"
        "parent_knowledge_base_id 不传则返回顶级知识库。"
    ),
)
async def list_children(
    parent_knowledge_base_id: Optional[str] = Query(
        default=None, description="父知识库ID（不传则查询顶级）"
    ),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[KnowledgeBaseListResponse]:
    kbs = knowledge_base_repo.get_children(
        session, user_id, parent_knowledge_base_id
    )
    items = [_to_kb_info(kb) for kb in kbs]
    return ApiResponse.success(
        data=KnowledgeBaseListResponse(
            knowledge_bases=items, total=len(items)
        )
    )


@router.get(
    "/{knowledge_base_id}",
    response_model=ApiResponse[KnowledgeBaseInfo],
    summary="获取知识库详情",
    description="根据知识库ID获取详细信息。",
)
async def get_knowledge_base(
    knowledge_base_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[KnowledgeBaseInfo]:
    kb = knowledge_base_repo.get_by_id_and_user(
        session, knowledge_base_id, user_id
    )
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在或无权限")
    return ApiResponse.success(data=_to_kb_info(kb))


# ==================== 更新 ====================


@router.put(
    "/{knowledge_base_id}",
    response_model=ApiResponse[KnowledgeBaseInfo],
    summary="更新知识库",
    description="更新知识库的名称或描述。名称不能与同用户下的其他知识库重复。",
)
async def update_knowledge_base(
    knowledge_base_id: str,
    request: KnowledgeBaseUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[KnowledgeBaseInfo]:
    kb = knowledge_base_repo.get_by_id_and_user(
        session, knowledge_base_id, user_id
    )
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在或无权限")

    if request.knowledge_base_name and request.knowledge_base_name != kb.knowledge_base_name:
        if knowledge_base_repo.name_exists(
            session, user_id, request.knowledge_base_name, exclude_id=knowledge_base_id
        ):
            raise HTTPException(
                status_code=409,
                detail=f"知识库名称已存在: {request.knowledge_base_name}",
            )

    update_fields: dict = {}
    if request.knowledge_base_name is not None:
        update_fields["knowledge_base_name"] = request.knowledge_base_name
    if request.description is not None:
        update_fields["description"] = request.description

    if not update_fields:
        return ApiResponse.success(data=_to_kb_info(kb))

    updated = knowledge_base_repo.update(
        session, knowledge_base_id, updater=user_id, **update_fields
    )
    if not updated:
        raise HTTPException(status_code=500, detail="更新失败")

    return ApiResponse.success(
        data=_to_kb_info(updated), message="知识库更新成功"
    )


# ==================== 删除 ====================


@router.delete(
    "/{knowledge_base_id}",
    response_model=ApiResponse[KnowledgeBaseDeleteResponse],
    summary="删除知识库（级联删除子知识库）",
    description=(
        "物理删除知识库及其所有子知识库，同时清理其下的所有空文件夹。"
        "前置条件：该知识库及所有子知识库下（包括回收站中）不存在任何文件。"
        "如有文件，请先手动删除文件并清空回收站后重试。"
    ),
)
async def delete_knowledge_base(
    knowledge_base_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> ApiResponse[KnowledgeBaseDeleteResponse]:
    kb = knowledge_base_repo.get_by_id_and_user(
        session, knowledge_base_id, user_id
    )
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在或无权限")

    descendant_ids = knowledge_base_repo.get_all_descendants(
        session, user_id, knowledge_base_id
    )
    all_kb_ids = [knowledge_base_id] + descendant_ids

    file_count = knowledge_base_repo.check_tree_has_files(
        session, user_id, all_kb_ids
    )
    if file_count < 0:
        raise HTTPException(status_code=500, detail="检查文件数量失败")
    if file_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"知识库树下仍有 {file_count} 个文件（含回收站），"
                "请先删除所有文件并清空回收站后重试"
            ),
        )

    try:
        total_folder_count = 0
        for kb_id in reversed(all_kb_ids):
            total_folder_count += knowledge_base_repo.hard_delete(
                session, user_id, kb_id
            )
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"删除知识库失败: {e}")
        raise HTTPException(status_code=500, detail="删除失败")

    logger.info(
        f"删除知识库: user_id={user_id}, kb_id={knowledge_base_id}, "
        f"name={kb.knowledge_base_name}, "
        f"kb_count={len(all_kb_ids)}, folders={total_folder_count}"
    )

    return ApiResponse.success(
        data=KnowledgeBaseDeleteResponse(
            knowledge_base_id=knowledge_base_id,
            deleted_folder_count=total_folder_count,
            deleted_kb_count=len(all_kb_ids),
        ),
        message=f"已删除 {len(all_kb_ids)} 个知识库，清理 {total_folder_count} 个文件夹",
    )
