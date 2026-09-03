#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
清理相关消息模型

定义删除文件后的异步清理消息：
- CleanupMessage: 清理某个文件的全部关联数据
"""

from typing import Optional
from pydantic import Field

from src.types.messages.base import BaseMessage


class CleanupMessage(BaseMessage):
    """
    清理消息

    用户删除文件后，MySQL 只写墓碑（deleted=1）就立即返回，
    真正的关联数据清理（Milvus / MongoDB / MySQL 元数据 / 对象存储）由本消息触发。
    发送到: knowledge_base.cleanup.start
    消费者: CleanupWorker

    document_id 与 storage_path 在投递时就带上，避免 worker 再查一次 MySQL；
    墓碑行被清掉后消息重投也仍然能定位到要清理的数据。
    """

    # Document ID（内容级唯一标识，多个同内容文件共享）
    document_id: Optional[str] = Field(
        default=None,
        description="Document ID，为空表示该文件没有索引数据需要清理"
    )

    # 存储路径（MinIO/S3 路径）
    storage_path: Optional[str] = Field(
        default=None,
        description="文件在对象存储中的路径，为空表示无需清理对象存储"
    )

    # 知识库ID
    knowledge_base_id: Optional[str] = Field(
        default=None,
        description="知识库ID，仅用于日志与排查"
    )
