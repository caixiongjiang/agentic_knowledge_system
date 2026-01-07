#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : base_model.py
@Author  : caixiongjiang
@Date    : 2026/1/7 16:43
@Function: 
    MongoDB文档公共基类
    提供通用字段和软删除支持
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime
from beanie import Document
from pydantic import Field


class BaseDocument(Document):
    """
    MongoDB文档的公共基类
    
    提供通用字段：
    - status: 状态标识
    - creator: 创建者
    - create_time: 创建时间
    - updater: 更新者
    - update_time: 更新时间
    - deleted: 软删除标记
    
    所有业务文档都应继承此类。
    """
    
    # ========== 审计字段 ==========
    status: int = Field(
        default=0,
        description="状态标识：0=正常，1=停用，2=回滚"
    )
    
    creator: str = Field(
        default="",
        max_length=64,
        description="创建者用户名或ID"
    )
    
    create_time: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )
    
    updater: str = Field(
        default="",
        max_length=64,
        description="最后更新者用户名或ID"
    )
    
    update_time: datetime = Field(
        default_factory=datetime.now,
        description="最后更新时间"
    )
    
    # ========== 软删除标记 ==========
    deleted: int = Field(
        default=0,
        description="软删除标记：0=未删除，1=已删除"
    )
    
    class Settings:
        """Beanie 设置"""
        # 标记为抽象类，不创建集合
        # 子类必须设置 name 才会创建集合
        name = None  # 不设置集合名称，阻止为基类创建集合
        use_state_management = True  # 启用状态管理
        validate_on_save = True  # 保存时验证
    
    # ========== 软删除方法 ==========
    
    async def soft_delete(self, updater: str = "") -> None:
        """
        软删除文档
        
        Args:
            updater: 执行删除的用户名或ID
        """
        self.deleted = 1
        self.updater = updater
        self.update_time = datetime.now()
        await self.save()
    
    async def restore(self, updater: str = "") -> None:
        """
        恢复已软删除的文档
        
        Args:
            updater: 执行恢复的用户名或ID
        """
        self.deleted = 0
        self.updater = updater
        self.update_time = datetime.now()
        await self.save()
    
    def is_deleted(self) -> bool:
        """检查文档是否已被软删除"""
        return self.deleted == 1
    
    # ========== 通用查询方法 ==========
    
    @classmethod
    async def find_active(cls, *args, **kwargs):
        """
        查询所有未删除的文档
        
        Args:
            *args: 查询条件
            **kwargs: 额外查询参数
            
        Returns:
            查询构造器
        """
        return cls.find({"deleted": 0, **kwargs})
    
    @classmethod
    async def count_active(cls) -> int:
        """统计未删除的文档数量"""
        return await cls.find({"deleted": 0}).count()
