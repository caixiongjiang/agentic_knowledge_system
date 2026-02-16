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
        default=0,
        ge=0,
        description="Chunk重叠大小"
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
    
    # ========== 表格切分配置 ==========
    enable_table_split: bool = Field(
        default=True,
        description="是否启用超长表格切分"
    )
    
    table_max_size: int = Field(
        default=2000,
        gt=0,
        description="表格最大大小，超过则切分"
    )
    
    preserve_table_header: bool = Field(
        default=True,
        description="表格切分时是否在每个切片中保留表头"
    )
    
    # ========== 代码块配置 ==========
    code_block_max_size: int = Field(
        default=1500,
        gt=0,
        description="代码块最大大小"
    )
    
    # ========== 文本清洗配置 ==========
    enable_text_clean: bool = Field(
        default=True,
        description="是否启用文本清洗"
    )
    
    remove_extra_whitespace: bool = Field(
        default=True,
        description="是否移除多余空白字符"
    )
    
    remove_control_chars: bool = Field(
        default=True,
        description="是否移除控制字符"
    )
    
    # ========== 语言检测配置 ==========
    enable_language_detection: bool = Field(
        default=True,
        description="是否启用语言检测"
    )
    
    language_detection_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="语言检测置信度阈值"
    )
    
    # ========== 其他配置 ==========
    min_chunk_size: int = Field(
        default=50,
        gt=0,
        description="最小Chunk大小（小于此大小的chunk会被忽略或合并）"
    )
    
    max_chunk_size: int = Field(
        default=5000,
        gt=0,
        description="最大Chunk大小（强制切分）"
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
