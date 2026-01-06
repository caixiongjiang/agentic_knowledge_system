#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : base_model.py
@Author  : caixiongjiang
@Date    : 2026/01/06
@Function: 
    MySQL 数据库表的公共基类和 Mixin 类
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime
from sqlalchemy import Column, Integer, String, BigInteger, DateTime
from sqlalchemy.ext.declarative import declarative_base

# 创建基类
Base = declarative_base()


class BaseModel(Base):
    """
    所有表的公共基类
    
    提供通用字段：
    - status: 状态标识
    - creator: 创建者
    - create_time: 创建时间
    - updater: 更新者
    - update_time: 更新时间
    - deleted: 软删除标记
    """
    __abstract__ = True  # 标记为抽象类，不创建实际表
    
    status = Column(
        Integer, 
        default=0, 
        nullable=False,
        comment="状态标识：0=正常，其他值根据业务定义"
    )
    
    creator = Column(
        String(64), 
        default="", 
        nullable=False,
        comment="创建者用户名或ID"
    )
    
    create_time = Column(
        DateTime, 
        default=datetime.now, 
        nullable=False,
        comment="创建时间"
    )
    
    updater = Column(
        String(64), 
        default="", 
        nullable=False,
        comment="最后更新者用户名或ID"
    )
    
    update_time = Column(
        DateTime, 
        default=datetime.now, 
        onupdate=datetime.now, 
        nullable=False,
        comment="最后更新时间"
    )
    
    deleted = Column(
        Integer, 
        default=0, 
        nullable=False,
        comment="软删除标记：0=未删除，1=已删除"
    )
    
    def to_dict(self) -> dict:
        """
        将模型转换为字典
        
        Returns:
            dict: 包含所有字段的字典
        """
        return {
            c.name: getattr(self, c.name) 
            for c in self.__table__.columns
        }


class KnowledgeMixin:
    """
    知识库相关字段 Mixin
    
    提供知识库相关的通用字段：
    - role: 角色标识
    - knowledge_type: 知识库类型
    - knowledge_id: 知识库ID
    - parent_knowledge_id: 父知识库ID
    """
    
    role = Column(
        String(64), 
        default="",
        nullable=False,
        comment="角色标识"
    )
    
    knowledge_type = Column(
        String(255), 
        default="common_file",
        nullable=False,
        comment="知识库类型：common_file=普通文件"
    )
    
    knowledge_id = Column(
        String(255), 
        nullable=True,
        comment="知识库ID"
    )
    
    parent_knowledge_id = Column(
        String(255), 
        nullable=True,
        comment="父知识库ID"
    )


class AgentMixin:
    """
    Agent 相关字段 Mixin
    
    提供 Agent 相关的通用字段：
    - user_id: 用户ID
    - session_id: 会话ID
    - task_id: 任务ID
    - agent_id: Agent配置ID
    - agent_instance_id: Agent实例ID
    - component_id: 组件ID
    - parent_agent_instance_id: 父Agent实例ID
    - event_id: 事件ID
    """
    
    user_id = Column(
        String(64), 
        index=True, 
        default="-1",
        nullable=False,
        comment="用户ID"
    )
    
    session_id = Column(
        BigInteger, 
        index=True,
        nullable=True,
        comment="会话ID"
    )
    
    task_id = Column(
        BigInteger, 
        index=True,
        nullable=True,
        comment="任务ID"
    )
    
    agent_id = Column(
        String(255), 
        index=True,
        nullable=True,
        comment="Agent配置ID"
    )
    
    agent_instance_id = Column(
        BigInteger, 
        index=True,
        nullable=True,
        comment="Agent实例ID"
    )
    
    component_id = Column(
        String(255), 
        nullable=True,
        comment="组件ID"
    )
    
    parent_agent_instance_id = Column(
        BigInteger, 
        nullable=True,
        comment="父Agent实例ID"
    )
    
    event_id = Column(
        BigInteger, 
        nullable=True,
        comment="事件ID"
    )
