#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : __init__.py
@Author  : caixiongjiang
@Date    : 2026/02/28
@Function: 
    Agentic 知识库检索模块
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
"""
Agentic 知识库检索模块

分层架构：
- types/          公共类型定义（枚举、查询参数、结果模型）
- capabilities/   原子能力层（按能力类型组织：semantic、lexical、structured、graph、navigation）
- skills/         技能组合层（对原子能力的编排组合）
- engine/         引擎编排层（查询分析、多技能调度、结果合并）
- tools/          Agent 工具注册层（MCP / Function Calling）
"""
