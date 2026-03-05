#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Milvus Repository 抽象基类
提供通用的CRUD操作，封装数据访问逻辑
"""

from abc import ABC
from typing import List, Dict, Any, Optional
import os
from loguru import logger

from pymilvus import Collection, FieldSchema, CollectionSchema, DataType, utility
from pymilvus.exceptions import MilvusException

from src.db.milvus import get_milvus_manager, BaseMilvusManager
from src.db.milvus.models.base_schema import BaseSchema, FieldType


class BaseRepository(ABC):
    """Milvus仓储基类
    
    职责：
    1. 数据访问逻辑封装（CRUD操作）
    2. Collection生命周期管理（创建、加载、删除）
    3. 与Schema层解耦（通过BaseSchema注入）
    4. 与连接层解耦（通过BaseMilvusManager注入）
    
    设计模式：
    - 仓储模式（Repository Pattern）
    - 依赖注入（Dependency Injection）
    
    使用示例：
        >>> from src.db.milvus.models import ChunkSchemaZh
        >>> from src.db.milvus import get_milvus_manager
        >>> 
        >>> # 自动使用工厂函数获取Manager
        >>> repo = ChunkRepository()
        >>> 
        >>> # 或者手动注入Manager
        >>> manager = get_milvus_manager()
        >>> repo = ChunkRepository(manager=manager)
        >>> 
        >>> # 插入数据
        >>> ids = repo.insert([{"id": "123", "vector": [...], ...}])
        >>> 
        >>> # 向量搜索
        >>> results = repo.search(vectors=[[...]], vector_field="vector", top_k=10)
    """
    
    def __init__(
        self, 
        schema: BaseSchema,
        manager: Optional[BaseMilvusManager] = None
    ):
        """初始化Repository
        
        Args:
            schema: 表Schema实例（必须）
            manager: Milvus连接管理器（可选，默认使用工厂函数）
        """
        self.schema = schema
        self.manager = manager or get_milvus_manager()
        self.collection_name = schema.get_collection_name()
        self.logger = logger
        
        # Collection对象（延迟初始化）
        self._collection: Optional[Collection] = None
        
        # 确保集合存在
        self._ensure_collection()
    
    def _ensure_collection(self) -> None:
        """确保集合存在
        
        行为说明：
        - 如果集合存在：直接加载
        - 如果集合不存在：
          * 开发/测试环境（MILVUS_AUTO_CREATE_COLLECTION=true）：自动创建
          * 生产环境（默认）：抛出异常，要求人工创建
        
        环境变量：
            MILVUS_AUTO_CREATE_COLLECTION: 是否允许自动创建集合
                - "true"/"1"/"yes": 允许（开发/测试环境）
                - 其他值: 不允许（生产环境，默认）
        
        Raises:
            RuntimeError: 生产环境中集合不存在时
            ConnectionError: 无法连接到Milvus时
        """
        try:
            if not self.manager._ensure_connected():
                raise ConnectionError("无法连接到Milvus")
            
            alias = self.manager.get_connection_alias()
            
            if utility.has_collection(self.collection_name, using=alias):
                # 集合已存在，加载
                self._collection = Collection(self.collection_name, using=alias)
                
                # 检查并确保索引存在（修复旧集合可能没有索引的问题）
                self._ensure_indexes()
                
                self._collection.load()
                self.logger.debug(f"已加载集合: {self.collection_name}")
            else:
                # 集合不存在，检查是否允许自动创建
                auto_create = os.getenv("MILVUS_AUTO_CREATE_COLLECTION", "false").lower()
                allow_auto_create = auto_create in ("true", "1", "yes")
                
                if allow_auto_create:
                    # 开发/测试环境：自动创建
                    self.logger.warning(
                        f"⚠️  自动创建集合: {self.collection_name} "
                        f"(MILVUS_AUTO_CREATE_COLLECTION={auto_create})"
                    )
                    self._create_collection()
                else:
                    # 生产环境：禁止自动创建，抛出异常
                    error_msg = (
                        f"❌ 集合 '{self.collection_name}' 不存在！\n"
                        f"\n"
                        f"🔒 生产环境安全策略：不允许自动创建集合。\n"
                        f"\n"
                        f"📝 请按以下步骤操作：\n"
                        f"1. 使用 Schema 导出工具生成创建脚本：\n"
                        f"   python scripts/export_milvus_schema.py --collection {self.collection_name}\n"
                        f"\n"
                        f"2. 由 DBA 审核生成的脚本\n"
                        f"\n"
                        f"3. 在数据库中手动执行脚本创建集合\n"
                        f"\n"
                        f"💡 如果是开发/测试环境，可以设置环境变量允许自动创建：\n"
                        f"   export MILVUS_AUTO_CREATE_COLLECTION=true\n"
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)
        
        except RuntimeError:
            # 直接抛出 RuntimeError（集合不存在的错误）
            raise
        except Exception as e:
            self.logger.error(f"确保集合存在失败: {e}", exc_info=True)
            raise
    
    def _create_collection(self) -> None:
        """创建集合"""
        try:
            alias = self.manager.get_connection_alias()
            
            # 从Schema获取字段定义
            fields = self._build_fields()
            
            # 创建集合Schema
            collection_schema = CollectionSchema(
                fields=fields,
                description=self.schema.get_description(),
                enable_dynamic_field=self.schema.ENABLE_DYNAMIC_FIELD
            )
            
            # 创建集合
            self._collection = Collection(
                name=self.collection_name,
                schema=collection_schema,
                using=alias
            )
            
            # 创建索引
            self._create_indexes()
            
            # 加载集合
            self._collection.load()
            
            self.logger.info(f"集合创建成功: {self.collection_name}")
        
        except Exception as e:
            self.logger.error(f"创建集合失败: {e}", exc_info=True)
            raise
    
    def _build_fields(self) -> List[FieldSchema]:
        """根据Schema构建Milvus字段
        
        将我们的FieldDefinition转换为Milvus的FieldSchema
        """
        milvus_fields = []
        
        for field_def in self.schema.get_fields():
            # 构建字段参数
            field_dict = {
                "name": field_def.name,
                "dtype": getattr(DataType, field_def.dtype.value),
            }
            
            # 添加可选参数
            if field_def.is_primary:
                field_dict["is_primary"] = True
            if field_def.auto_id:
                field_dict["auto_id"] = True
            if field_def.max_length:
                field_dict["max_length"] = field_def.max_length
            if field_def.dim:
                field_dict["dim"] = field_def.dim
            if field_def.nullable:
                field_dict["nullable"] = True
            if field_def.default_value is not None:
                field_dict["default_value"] = field_def.default_value
            
            # 创建FieldSchema
            milvus_fields.append(FieldSchema(**field_dict))
        
        return milvus_fields
    
    _VECTOR_FIELD_TYPES = {
        FieldType.FLOAT_VECTOR,
        FieldType.SPARSE_FLOAT_VECTOR,
    }

    def _ensure_indexes(self) -> None:
        """确保索引存在
        
        检查所有向量字段（包括稀疏向量）的索引，如果不存在则创建。
        用于加载已存在的集合时，确保索引完整性。
        """
        existing_indexes = {}
        try:
            for index in self._collection.indexes:
                existing_indexes[index.field_name] = index
        except Exception as e:
            self.logger.warning(f"获取索引信息失败: {e}")
        
        vector_fields = [
            field_def for field_def in self.schema.get_fields()
            if field_def.dtype in self._VECTOR_FIELD_TYPES
        ]
        
        for field_def in vector_fields:
            if field_def.name not in existing_indexes:
                self.logger.warning(
                    f"⚠️  字段 {field_def.name} 缺少索引，正在创建..."
                )
                self._create_index_for_field(field_def.name)
            else:
                self.logger.debug(
                    f"字段 {field_def.name} 索引已存在: {existing_indexes[field_def.name].params}"
                )
    
    def _create_indexes(self) -> None:
        """创建索引（新集合创建时调用）
        
        为所有向量字段（包括稀疏向量）创建索引。
        
        Note:
            自动处理 Milvus Lite 的索引类型限制：
            - Lite 只支持: FLAT, IVF_FLAT, AUTOINDEX
            - Server 支持: 所有索引类型
            - 如果在 Lite 下使用不支持的索引，自动降级到 AUTOINDEX
            - 稀疏向量索引(SPARSE_INVERTED_INDEX) 在 Lite 下不支持
        """
        for field_def in self.schema.get_fields():
            if field_def.dtype in self._VECTOR_FIELD_TYPES:
                self._create_index_for_field(field_def.name)
    
    def _is_sparse_vector_field(self, field_name: str) -> bool:
        """判断字段是否为稀疏向量类型"""
        for field_def in self.schema.get_fields():
            if field_def.name == field_name:
                return field_def.dtype == FieldType.SPARSE_FLOAT_VECTOR
        return False

    def _create_index_for_field(self, field_name: str) -> None:
        """为指定字段创建索引
        
        Args:
            field_name: 字段名称
        """
        is_lite_mode = self._is_lite_mode()

        if self._is_sparse_vector_field(field_name):
            sparse_params = self.schema.get_sparse_index_params()
            if sparse_params is None:
                self.logger.warning(
                    f"字段 {field_name} 是稀疏向量类型，"
                    f"但 Schema 未定义 get_sparse_index_params()，跳过索引创建"
                )
                return

            if is_lite_mode:
                self.logger.warning(
                    f"⚠️  Milvus Lite 不支持 SPARSE_INVERTED_INDEX 索引，"
                    f"跳过稀疏向量字段 {field_name} 的索引创建"
                )
                return

            self._collection.create_index(
                field_name=field_name,
                index_params=sparse_params,
            )
            self.logger.debug(
                f"已为稀疏向量字段 {field_name} 创建索引: "
                f"{sparse_params.get('index_type')}"
            )
            return

        index_params = self.schema.get_index_params().copy()

        LITE_SUPPORTED_INDEXES = {"FLAT", "IVF_FLAT", "AUTOINDEX"}

        if is_lite_mode and index_params.get("index_type") not in LITE_SUPPORTED_INDEXES:
            original_index = index_params["index_type"]
            index_params["index_type"] = "AUTOINDEX"
            index_params["params"] = {}
            self.logger.warning(
                f"⚠️  Milvus Lite 不支持 {original_index} 索引，"
                f"自动降级为 AUTOINDEX"
            )
        
        self._collection.create_index(
            field_name=field_name,
            index_params=index_params
        )
        self.logger.debug(
            f"已为字段 {field_name} 创建索引: {index_params['index_type']}"
        )
    
    def _is_lite_mode(self) -> bool:
        """检测是否为 Milvus Lite 模式
        
        Returns:
            bool: True 表示 Lite 模式，False 表示 Server 模式
        """
        from src.db.milvus import MilvusLiteManager
        return isinstance(self.manager, MilvusLiteManager)
    
    # ========== CRUD操作 ==========
    
    def insert(self, data: List[Dict[str, Any]]) -> List[Any]:
        """插入数据
        
        Args:
            data: 数据列表，每个元素是一个字典，字段名对应Schema定义
            
        Returns:
            插入的记录ID列表
            
        Example:
            >>> repo.insert([
            ...     {"id": "123", "vector": [0.1, 0.2, ...], "text": "Hello"},
            ...     {"id": "456", "vector": [0.3, 0.4, ...], "text": "World"},
            ... ])
            ['123', '456']
        """
        try:
            if not self._collection:
                raise RuntimeError("Collection未初始化")
            
            result = self._collection.insert(data)
            self._collection.flush()
            
            self.logger.debug(f"插入 {len(data)} 条数据到 {self.collection_name}")
            return result.primary_keys
        
        except Exception as e:
            self.logger.error(f"插入数据失败: {e}", exc_info=True)
            raise
    
    def upsert(self, data: List[Dict[str, Any]]) -> List[Any]:
        """更新或插入数据（存在则更新，不存在则插入）
        
        Args:
            data: 数据列表
            
        Returns:
            upsert的记录ID列表
            
        Note:
            需要Milvus 2.3+版本支持
        """
        try:
            if not self._collection:
                raise RuntimeError("Collection未初始化")
            
            result = self._collection.upsert(data)
            self._collection.flush()
            
            self.logger.debug(f"Upsert {len(data)} 条数据到 {self.collection_name}")
            return result.primary_keys
        
        except Exception as e:
            self.logger.error(f"Upsert数据失败: {e}", exc_info=True)
            raise
    
    def delete(self, expr: str) -> None:
        """根据表达式删除数据
        
        Args:
            expr: 删除表达式，如 "id in ['123', '456']" 或 "age > 30"
            
        Example:
            >>> # 删除指定ID
            >>> repo.delete("id in ['123', '456']")
            >>> 
            >>> # 删除满足条件的记录
            >>> repo.delete("timestamp < 1609459200")
        """
        try:
            if not self._collection:
                raise RuntimeError("Collection未初始化")
            
            self._collection.delete(expr)
            self._collection.flush()
            
            self.logger.debug(f"删除数据从 {self.collection_name}，表达式: {expr}")
        
        except Exception as e:
            self.logger.error(f"删除数据失败: {e}", exc_info=True)
            raise
    
    def delete_by_ids(self, ids: List[Any]) -> None:
        """根据ID列表删除数据
        
        Args:
            ids: ID列表
            
        Example:
            >>> repo.delete_by_ids(['123', '456', '789'])
        """
        if not ids:
            return
        
        # 构建删除表达式
        expr = f"id in {ids}"
        self.delete(expr)
    
    def query(
        self, 
        expr: str,
        output_fields: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        consistency_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """查询数据
        
        Args:
            expr: 查询表达式，如 "id in ['123']" 或 "age > 30 and city == 'Beijing'"
            output_fields: 要返回的字段列表，None表示返回所有字段
            limit: 返回结果数量限制
            offset: 偏移量（分页）
            consistency_level: 一致性级别，可选值 "Strong"/"Bounded"/"Session"/"Eventually"，
                              None 时使用 Collection 创建时的默认级别
            
        Returns:
            查询结果列表
            
        Example:
            >>> # 查询指定ID
            >>> results = repo.query("id in ['123', '456']")
            >>> 
            >>> # 查询并指定返回字段
            >>> results = repo.query(
            ...     "user_id == '001'",
            ...     output_fields=["id", "text", "timestamp"],
            ...     limit=50
            ... )
        """
        try:
            if not self._collection:
                raise RuntimeError("Collection未初始化")
            
            kwargs: Dict[str, Any] = {}
            if consistency_level is not None:
                kwargs["consistency_level"] = consistency_level
            
            results = self._collection.query(
                expr=expr,
                output_fields=output_fields or ["*"],
                limit=limit,
                offset=offset,
                **kwargs
            )
            
            return results
        
        except Exception as e:
            self.logger.error(f"查询数据失败: {e}", exc_info=True)
            raise
    
    def query_by_ids(
        self,
        ids: List[Any],
        output_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """根据ID列表查询数据
        
        Args:
            ids: ID列表
            output_fields: 要返回的字段列表
            
        Returns:
            查询结果列表
        """
        if not ids:
            return []
        
        expr = f"id in {ids}"
        return self.query(expr, output_fields=output_fields, limit=len(ids))
    
    def search(
        self,
        vectors: List[List[float]],
        vector_field: str,
        top_k: int = 10,
        search_params: Optional[Dict[str, Any]] = None,
        output_fields: Optional[List[str]] = None,
        filter_expr: Optional[str] = None,
        consistency_level: Optional[str] = None
    ) -> List[List[Dict[str, Any]]]:
        """向量搜索
        
        Args:
            vectors: 查询向量列表（可以一次搜索多个向量）
            vector_field: 向量字段名
            top_k: 返回Top-K结果
            search_params: 搜索参数（如果为None，使用默认参数）
            output_fields: 返回字段列表
            filter_expr: 过滤表达式（在搜索前过滤）
            consistency_level: 一致性级别，可选值 "Strong"/"Bounded"/"Session"/"Eventually"，
                              None 时使用 Collection 创建时的默认级别
            
        Returns:
            搜索结果列表，第一层是每个查询向量的结果，第二层是每个结果的详情
            
        Example:
            >>> # 单个向量搜索
            >>> results = repo.search(
            ...     vectors=[[0.1, 0.2, 0.3, ...]],
            ...     vector_field="vector",
            ...     top_k=10
            ... )
            >>> 
            >>> # 带过滤条件的搜索
            >>> results = repo.search(
            ...     vectors=[[0.1, 0.2, ...]],
            ...     vector_field="vector",
            ...     top_k=5,
            ...     filter_expr="user_id == '001'"
            ... )
            >>> 
            >>> # 指定一致性级别搜索
            >>> results = repo.search(
            ...     vectors=[[0.1, 0.2, ...]],
            ...     vector_field="vector",
            ...     top_k=10,
            ...     consistency_level="Strong"
            ... )
        """
        try:
            if not self._collection:
                raise RuntimeError("Collection未初始化")
            
            # 默认搜索参数
            if search_params is None:
                index_params = self.schema.get_index_params()
                search_params = {
                    "metric_type": index_params["metric_type"],
                    "params": {"ef": 128}  # HNSW搜索参数
                }
            
            kwargs: Dict[str, Any] = {}
            if consistency_level is not None:
                kwargs["consistency_level"] = consistency_level
            
            results = self._collection.search(
                data=vectors,
                anns_field=vector_field,
                param=search_params,
                limit=top_k,
                output_fields=output_fields or ["*"],
                expr=filter_expr,
                **kwargs
            )
            
            return self._format_search_results(results, output_fields)
        
        except Exception as e:
            self.logger.error(f"向量搜索失败: {e}", exc_info=True)
            raise
    
    def search_sparse(
        self,
        sparse_vectors: List[Dict[int, float]],
        sparse_field: str = "sparse_vector",
        top_k: int = 10,
        output_fields: Optional[List[str]] = None,
        filter_expr: Optional[str] = None,
        consistency_level: Optional[str] = None,
    ) -> List[List[Dict[str, Any]]]:
        """稀疏向量搜索（BM25 关键词检索）

        使用 IP（内积）度量对稀疏向量字段进行 ANN 搜索，
        等价于 BM25 评分排序。

        Args:
            sparse_vectors: 查询稀疏向量列表，格式 [{dim_idx: weight, ...}]
            sparse_field: 稀疏向量字段名
            top_k: 返回 Top-K 结果
            output_fields: 返回字段列表
            filter_expr: 标量过滤表达式
            consistency_level: 一致性级别

        Returns:
            搜索结果列表（与 search() 格式一致）
        """
        try:
            if not self._collection:
                raise RuntimeError("Collection未初始化")

            search_params = {"metric_type": "IP"}

            kwargs: Dict[str, Any] = {}
            if consistency_level is not None:
                kwargs["consistency_level"] = consistency_level

            results = self._collection.search(
                data=sparse_vectors,
                anns_field=sparse_field,
                param=search_params,
                limit=top_k,
                output_fields=output_fields or ["*"],
                expr=filter_expr,
                **kwargs,
            )

            return self._format_search_results(results, output_fields)

        except Exception as e:
            self.logger.error(f"稀疏向量搜索失败: {e}", exc_info=True)
            raise

    def _format_search_results(
        self,
        results: Any,
        output_fields: Optional[List[str]] = None,
    ) -> List[List[Dict[str, Any]]]:
        """将 Milvus 原始搜索结果格式化为统一字典列表"""
        formatted_results: List[List[Dict[str, Any]]] = []
        for hits in results:
            hit_list: List[Dict[str, Any]] = []
            for hit in hits:
                hit_dict: Dict[str, Any] = {
                    "id": hit.id,
                    "distance": hit.distance,
                    "score": hit.score,
                    "entity": {},
                }
                if hasattr(hit, "entity"):
                    try:
                        entity_dict = (
                            hit.entity.to_dict()
                            if hasattr(hit.entity, "to_dict")
                            else {}
                        )
                        hit_dict["entity"] = entity_dict
                    except Exception:
                        if output_fields and output_fields != ["*"]:
                            for field in output_fields:
                                if hasattr(hit.entity, field):
                                    hit_dict["entity"][field] = getattr(
                                        hit.entity, field
                                    )
                hit_list.append(hit_dict)
            formatted_results.append(hit_list)
        return formatted_results

    def count(self) -> int:
        """获取集合中的记录数
        
        Returns:
            记录总数
        """
        try:
            if not self._collection:
                raise RuntimeError("Collection未初始化")
            
            return self._collection.num_entities
        
        except Exception as e:
            self.logger.error(f"获取记录数失败: {e}", exc_info=True)
            raise
    
    # ========== 表结构管理（生产安全策略） ==========
    # 
    # 🔒 安全原则：表的创建、修改、删除必须由DBA人工执行，不能通过应用代码自动完成
    # 
    # ❌ 已移除的危险方法：
    #    - drop_collection(): 删除集合
    #    - alter_schema(): 修改表结构
    #    - drop_index(): 删除索引
    # 
    # ✅ 正确的操作流程：
    #    1. 使用 Schema 导出工具生成 SQL/脚本
    #    2. 由 DBA 审核脚本
    #    3. 在数据库管理工具中手动执行
    # 
    # 💡 如需删除集合，请：
    #    1. 使用 Milvus 官方管理工具（Attu）
    #    2. 或使用 pymilvus 的独立脚本（不集成在应用代码中）
    #    3. 确保有完整的备份和审批流程
    
    # ========== 资源管理 ==========
    
    def __enter__(self):
        """上下文管理器入口
        
        Example:
            >>> with ChunkRepository() as repo:
            ...     repo.insert([...])
        """
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出
        
        Collection对象由Milvus管理，不需要手动释放
        """
        # Collection对象由Milvus SDK管理，这里不需要特殊处理
        pass
    
    def __del__(self):
        """析构函数
        
        确保资源释放
        """
        try:
            # 清理Collection引用
            self._collection = None
        except Exception:
            pass
