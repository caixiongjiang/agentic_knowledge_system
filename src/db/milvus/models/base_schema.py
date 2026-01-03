#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Milvus Schema 抽象基类
所有知识库表Schema的基类，定义统一的表结构接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class FieldType(Enum):
    """字段类型枚举 - Milvus支持的数据类型"""
    INT64 = "INT64"                  # 64位整型
    FLOAT = "FLOAT"                  # 单精度浮点型
    DOUBLE = "DOUBLE"                # 双精度浮点型
    VARCHAR = "VARCHAR"              # 变长字符串
    JSON = "JSON"                    # JSON对象
    BOOL = "BOOL"                    # 布尔型
    FLOAT_VECTOR = "FLOAT_VECTOR"    # 浮点向量（用于语义搜索）
    BINARY_VECTOR = "BINARY_VECTOR"  # 二进制向量


class MetricType(Enum):
    """距离度量类型 - 向量相似度计算方法"""
    L2 = "L2"              # 欧氏距离（L2范数）
    IP = "IP"              # 内积（点乘）
    COSINE = "COSINE"      # 余弦相似度


class IndexType(Enum):
    """索引类型 - 向量索引算法"""
    FLAT = "FLAT"              # 暴力搜索（精确但慢）
    IVF_FLAT = "IVF_FLAT"      # 倒排文件索引
    IVF_SQ8 = "IVF_SQ8"        # 标量量化索引
    IVF_PQ = "IVF_PQ"          # 乘积量化索引
    HNSW = "HNSW"              # 层次可导航小世界图（高性能）
    ANNOY = "ANNOY"            # Approximate Nearest Neighbors Oh Yeah


@dataclass
class FieldDefinition:
    """字段定义 - 描述表中的单个字段"""
    name: str                           # 字段名称
    dtype: FieldType                    # 字段类型
    description: str = ""               # 字段描述（重要：用于模型理解表结构）
    is_primary: bool = False            # 是否为主键
    auto_id: bool = False               # 是否自动生成ID
    max_length: Optional[int] = None    # VARCHAR类型的最大长度
    dim: Optional[int] = None           # VECTOR类型的维度


class BaseSchema(ABC):
    """Milvus Schema 抽象基类
    
    所有知识库表Schema必须继承此类，定义表的结构和索引配置。
    
    设计原则：
    1. 单一职责：只负责定义表结构，不包含业务逻辑
    2. 声明式：使用类变量声明配置，清晰明了
    3. 可复用：提供公共字段生成方法，避免重复代码
    4. 类型安全：使用枚举和数据类保证类型正确
    
    Attributes:
        COLLECTION_NAME: 集合名称（必须在子类中定义）
        DESCRIPTION: 集合描述（用于文档和模型理解）
        VECTOR_DIM: 向量维度（如果表包含向量字段）
        ENABLE_DYNAMIC_FIELD: 是否启用动态字段（允许插入未定义的字段）
    """
    
    # 子类必须定义
    COLLECTION_NAME: str = ""
    DESCRIPTION: str = ""
    
    # 可选配置
    VECTOR_DIM: int = 1024              # 向量维度（根据embedding模型调整）
    ENABLE_DYNAMIC_FIELD: bool = True   # 启用动态字段支持
    
    @abstractmethod
    def get_fields(self) -> List[FieldDefinition]:
        """返回字段定义列表
        
        子类必须实现此方法，定义表的所有字段。
        
        Returns:
            List[FieldDefinition]: 字段定义列表
        """
        pass
    
    @abstractmethod
    def get_index_params(self) -> Dict[str, Any]:
        """返回索引参数
        
        子类必须实现此方法，定义向量索引配置。
        
        Returns:
            Dict[str, Any]: 索引配置字典，包含：
                - metric_type: 距离度量类型
                - index_type: 索引类型
                - params: 索引参数（如HNSW的M和efConstruction）
        """
        pass
    
    def get_collection_name(self) -> str:
        """获取集合名称
        
        Returns:
            str: 集合名称
            
        Raises:
            ValueError: 如果子类未定义COLLECTION_NAME
        """
        if not self.COLLECTION_NAME:
            raise ValueError(f"{self.__class__.__name__} 必须定义 COLLECTION_NAME")
        return self.COLLECTION_NAME
    
    def get_description(self) -> str:
        """获取集合描述
        
        Returns:
            str: 集合描述
        """
        return self.DESCRIPTION or f"{self.COLLECTION_NAME} 知识库表"
    
    def get_schema_dict(self) -> Dict[str, Any]:
        """获取完整的Schema配置字典
        
        用于导出Schema定义，便于文档生成和调试。
        
        Returns:
            Dict[str, Any]: 包含所有Schema信息的字典
        """
        return {
            "collection_name": self.get_collection_name(),
            "description": self.get_description(),
            "fields": [self._field_to_dict(f) for f in self.get_fields()],
            "index_params": self.get_index_params(),
            "enable_dynamic_field": self.ENABLE_DYNAMIC_FIELD,
        }
    
    @staticmethod
    def _field_to_dict(field: FieldDefinition) -> Dict[str, Any]:
        """将FieldDefinition转换为字典
        
        Args:
            field: 字段定义对象
            
        Returns:
            Dict[str, Any]: 字段定义字典
        """
        field_dict = {
            "name": field.name,
            "dtype": field.dtype.value,
            "description": field.description,
        }
        
        if field.is_primary:
            field_dict["is_primary"] = True
        if field.auto_id:
            field_dict["auto_id"] = True
        if field.max_length is not None:
            field_dict["max_length"] = field.max_length
        if field.dim is not None:
            field_dict["dim"] = field.dim
        
        return field_dict
    
    # ========== 公共字段生成方法 ==========
    # 这些方法提供常用字段的标准定义，确保一致性
    
    @staticmethod
    def create_id_field(auto_id: bool = True) -> FieldDefinition:
        """创建ID字段（主键）
        
        Args:
            auto_id: 是否自动生成ID
            
        Returns:
            FieldDefinition: ID字段定义
        """
        return FieldDefinition(
            name="id",
            dtype=FieldType.INT64,
            is_primary=True,
            auto_id=auto_id,
            description="主键ID，全局唯一标识符"
        )
    
    @staticmethod
    def create_varchar_id_field(max_length: int = 64) -> FieldDefinition:
        """创建VARCHAR类型的ID字段（主键）
        
        用于需要字符串ID的场景（如UUID）
        
        Args:
            max_length: 最大长度
            
        Returns:
            FieldDefinition: VARCHAR ID字段定义
        """
        return FieldDefinition(
            name="id",
            dtype=FieldType.VARCHAR,
            max_length=max_length,
            is_primary=True,
            auto_id=False,
            description="主键ID，字符串类型的唯一标识符"
        )
    
    @staticmethod
    def create_vector_field(name: str = "vector", dim: int = 1024, description: str = "") -> FieldDefinition:
        """创建向量字段
        
        Args:
            name: 字段名称
            dim: 向量维度
            description: 字段描述
            
        Returns:
            FieldDefinition: 向量字段定义
        """
        return FieldDefinition(
            name=name,
            dtype=FieldType.FLOAT_VECTOR,
            dim=dim,
            description=description or f"{dim}维语义向量，用于相似度搜索"
        )
    
    @staticmethod
    def create_text_field(
        name: str, 
        max_length: int = 65535,
        description: str = ""
    ) -> FieldDefinition:
        """创建文本字段（VARCHAR）
        
        Args:
            name: 字段名称
            max_length: 最大长度
            description: 字段描述
            
        Returns:
            FieldDefinition: 文本字段定义
        """
        return FieldDefinition(
            name=name,
            dtype=FieldType.VARCHAR,
            max_length=max_length,
            description=description or f"{name}文本字段"
        )
    
    @staticmethod
    def create_metadata_field(name: str = "metadata") -> FieldDefinition:
        """创建元数据字段（JSON）
        
        用于存储结构化的扩展信息
        
        Args:
            name: 字段名称
            
        Returns:
            FieldDefinition: JSON字段定义
        """
        return FieldDefinition(
            name=name,
            dtype=FieldType.JSON,
            description="元数据字段（JSON格式），存储扩展信息和动态属性"
        )
    
    @staticmethod
    def create_json_field(name: str, description: str = "") -> FieldDefinition:
        """创建JSON字段
        
        用于存储结构化的JSON数据
        
        Args:
            name: 字段名称
            description: 字段描述
            
        Returns:
            FieldDefinition: JSON字段定义
        """
        return FieldDefinition(
            name=name,
            dtype=FieldType.JSON,
            description=description or f"{name}字段（JSON格式）"
        )
    
    @staticmethod
    def create_timestamp_field(name: str = "created_at") -> FieldDefinition:
        """创建时间戳字段
        
        Args:
            name: 字段名称
            
        Returns:
            FieldDefinition: 时间戳字段定义
        """
        return FieldDefinition(
            name=name,
            dtype=FieldType.INT64,
            description=f"时间戳字段（Unix时间戳），记录{name.replace('_', ' ')}"
        )
    
    @staticmethod
    def create_int_field(name: str, description: str = "") -> FieldDefinition:
        """创建整型字段
        
        Args:
            name: 字段名称
            description: 字段描述
            
        Returns:
            FieldDefinition: 整型字段定义
        """
        return FieldDefinition(
            name=name,
            dtype=FieldType.INT64,
            description=description or f"{name}整型字段"
        )
    
    @staticmethod
    def create_float_field(name: str, description: str = "") -> FieldDefinition:
        """创建浮点型字段
        
        Args:
            name: 字段名称
            description: 字段描述
            
        Returns:
            FieldDefinition: 浮点型字段定义
        """
        return FieldDefinition(
            name=name,
            dtype=FieldType.FLOAT,
            description=description or f"{name}浮点型字段"
        )
    
    @staticmethod
    def create_bool_field(name: str, description: str = "") -> FieldDefinition:
        """创建布尔型字段
        
        Args:
            name: 字段名称
            description: 字段描述
            
        Returns:
            FieldDefinition: 布尔型字段定义
        """
        return FieldDefinition(
            name=name,
            dtype=FieldType.BOOL,
            description=description or f"{name}布尔型字段"
        )
