#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
切分相关数据模型

定义切分方法枚举和切分配置模型。
"""

from enum import Enum
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class SplitMethod(str, Enum):
    """切分方法枚举"""
    STRUCTURE_FIRST = "structure_first"  # 两阶段结构切分（推荐）
    RECURSIVE = "recursive"              # 递归切分
    REGULAR = "regular"                  # 常规切分
    SEMANTIC = "semantic"                # 语义切分
    TOKEN = "token"                      # Token切分


class SplitConfig(BaseModel):
    """
    切分配置模型
    
    用于配置文本切分的各项参数。
    配置从 config/components.json 的 text_splitter 部分加载。
    """
    
    # ========== 基础配置 ==========
    split_method: SplitMethod = Field(
        default=SplitMethod.STRUCTURE_FIRST,
        description="切分方法"
    )
    
    chunk_size: int = Field(
        default=1000,
        gt=0,
        description="Chunk大小（字符数或Token数）"
    )
    
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        description="Chunk重叠大小（建议为 chunk_size 的 10%-20%）"
    )
    
    # ========== 递归切分配置 ==========
    separators: List[str] = Field(
        default=["\n", "。", "，", " "],
        description="递归切分的分隔符列表（优先级从高到低）"
    )
    
    # ========== 语义切分配置 ==========
    model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="语义切分使用的模型名称"
    )
    
    # ========== Token切分配置 ==========
    encoding_name: str = Field(
        default="cl100k_base",
        description="Token编码方式（如 cl100k_base for GPT-4）"
    )
    
    # ========== 文本清洗配置 ==========
    enable_text_clean: bool = Field(
        default=True,
        description="是否启用文本清洗"
    )
    
    class Config:
        use_enum_values = True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SplitConfig":
        """从字典创建"""
        return cls(**data)
