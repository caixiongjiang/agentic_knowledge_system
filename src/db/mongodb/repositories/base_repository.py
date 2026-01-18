#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : base_repository.py
@Author  : caixiongjiang
@Date    : 2026/1/7 16:45
@Function: 
    MongoDB Repository 抽象基类
    提供通用的异步 CRUD 操作
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from datetime import datetime
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any, Union
from loguru import logger
from beanie import Document, PydanticObjectId
from pymongo import UpdateOne
from bson import ObjectId


# 泛型类型
DocumentType = TypeVar("DocumentType", bound=Document)


class BaseRepository(Generic[DocumentType]):
    """
    MongoDB Repository 基类
    
    提供通用的异步 CRUD 操作：
    - create: 创建单条记录
    - create_batch: 批量创建记录
    - get_by_id: 根据主键查询
    - find: 条件查询
    - update: 更新记录
    - delete: 软删除记录
    - bulk_delete_by_ids: 批量软删除
    - upsert: 插入或更新
    - upsert_batch_optimized: 批量插入或更新
    - count: 统计记录数
    
    使用泛型确保类型安全。
    """
    
    def __init__(self, model: Type[DocumentType]):
        """
        初始化 Repository
        
        Args:
            model: Beanie Document 模型类
        """
        self.model = model
        self.model_name = model.__name__
        self.logger = logger
    
    # ========== 创建操作 ==========
    
    async def create(
        self,
        creator: str = "",
        **kwargs
    ) -> DocumentType:
        """
        创建单条记录
        
        Args:
            creator: 创建者
            **kwargs: 模型字段及其值
            
        Returns:
            创建的文档实例
            
        Raises:
            Exception: 创建失败时抛出异常
            
        Examples:
            >>> repo = ChunkDataRepository()
            >>> chunk = await repo.create(
            ...     creator="user1",
            ...     text="example text",
            ...     chunk_type="text"
            ... )
        """
        try:
            # 设置审计字段（create_time 和 update_time 由 Field 的 default_factory 自动设置）
            kwargs["creator"] = creator
            kwargs["updater"] = creator
            
            # 创建文档实例
            doc = self.model(**kwargs)
            
            # 保存到数据库
            await doc.insert()
            
            self.logger.debug(f"成功创建{self.model_name}记录: {doc.id}")
            return doc
        
        except Exception as e:
            self.logger.error(f"创建{self.model_name}记录失败: {repr(e)}", exc_info=True)
            raise
    
    async def create_batch(
        self,
        data_list: List[Dict[str, Any]],
        creator: str = ""
    ) -> List[DocumentType]:
        """
        批量创建记录
        
        Args:
            data_list: 数据列表，每个元素是字典
            creator: 创建者
            
        Returns:
            创建的文档实例列表
            
        Examples:
            >>> repo = ChunkDataRepository()
            >>> chunks = await repo.create_batch([
            ...     {"text": "chunk1", "chunk_type": "text"},
            ...     {"text": "chunk2", "chunk_type": "text"}
            ... ], creator="user1")
        """
        try:
            # 为每条数据添加审计字段（create_time 和 update_time 由 Field 的 default_factory 自动设置）
            for data in data_list:
                data["creator"] = creator
                data["updater"] = creator
                data.setdefault("deleted", 0)
                data.setdefault("status", 0)
            
            # 创建文档实例
            documents = [self.model(**data) for data in data_list]
            
            # 批量插入
            # 注意：insert_many 会更新文档实例的 ID
            insert_result = await self.model.insert_many(documents)
            
            # 验证插入结果
            if insert_result and hasattr(insert_result, 'inserted_ids'):
                # 为文档实例设置 ID（如果没有自动设置）
                for doc, inserted_id in zip(documents, insert_result.inserted_ids):
                    if doc.id is None:
                        doc.id = inserted_id
            
            self.logger.debug(f"成功批量创建{len(documents)}个{self.model_name}记录")
            return documents
        
        except Exception as e:
            self.logger.error(f"批量创建{self.model_name}记录失败: {repr(e)}", exc_info=True)
            raise
    
    # ========== 查询操作 ==========
    
    async def get_by_id(
        self,
        doc_id: Union[str, ObjectId, PydanticObjectId],
        include_deleted: bool = False
    ) -> Optional[DocumentType]:
        """
        根据ID查询单条记录
        
        支持字符串 ID（如 UUID）和 ObjectId 两种格式
        
        Args:
            doc_id: 文档ID（字符串、ObjectId 或 PydanticObjectId）
            include_deleted: 是否包含已删除记录，默认False
            
        Returns:
            文档实例，未找到返回None
            
        Examples:
            >>> repo = ChunkDataRepository()
            >>> chunk = await repo.get_by_id("chunk_a1b2c3d4-...")
            >>> chunk = await repo.get_by_id("64abc123...")  # ObjectId 格式
        """
        try:
            # 直接使用 doc_id，支持字符串（UUID）或 ObjectId
            query_id = doc_id
            if isinstance(doc_id, str):
                # 尝试判断是否为 ObjectId 格式（24字符十六进制）
                if len(doc_id) == 24 and all(c in '0123456789abcdef' for c in doc_id.lower()):
                    try:
                        query_id = PydanticObjectId(doc_id)
                    except Exception:
                        # 如果转换失败，保持为字符串
                        query_id = doc_id
                # 否则直接使用字符串（支持 UUID 等自定义格式）
            elif isinstance(doc_id, (ObjectId, PydanticObjectId)):
                query_id = doc_id
            else:
                self.logger.warning(f"不支持的ID类型: {type(doc_id)}")
                return None
            
            # 构建查询
            query = {"_id": query_id}
            if not include_deleted:
                query["deleted"] = 0
            
            doc = await self.model.find_one(query)
            
            if not doc:
                self.logger.debug(f"未找到{self.model_name}记录: {doc_id}")
            
            return doc
        
        except Exception as e:
            self.logger.error(f"查询{self.model_name}记录失败: {e}", exc_info=True)
            return None
    
    async def find(
        self,
        limit: int = 100,
        skip: int = 0,
        include_deleted: bool = False,
        sort: Optional[List[tuple]] = None,
        **conditions
    ) -> List[DocumentType]:
        """
        条件查询
        
        Args:
            limit: 限制数量
            skip: 跳过数量
            include_deleted: 是否包含已删除记录
            sort: 排序规则，如 [("create_time", -1)]
            **conditions: 查询条件
            
        Returns:
            文档列表
            
        Examples:
            >>> repo = ChunkDataRepository()
            >>> chunks = await repo.find(
            ...     limit=10,
            ...     chunk_type="text",
            ...     sort=[("create_time", -1)]
            ... )
        """
        try:
            # 添加软删除过滤
            if not include_deleted:
                conditions["deleted"] = 0
            
            # 构建查询
            query = self.model.find(conditions)
            
            # 应用排序
            if sort:
                for field, direction in sort:
                    query = query.sort((field, direction))
            
            # 应用分页
            query = query.skip(skip).limit(limit)
            
            # 执行查询
            results = await query.to_list()
            
            self.logger.debug(f"查询到{len(results)}个{self.model_name}记录")
            return results
        
        except Exception as e:
            self.logger.error(f"查询{self.model_name}记录失败: {e}", exc_info=True)
            return []
    
    async def count(
        self,
        include_deleted: bool = False,
        **conditions
    ) -> int:
        """
        统计记录数
        
        Args:
            include_deleted: 是否包含已删除记录
            **conditions: 查询条件
            
        Returns:
            记录数量
        """
        try:
            if not include_deleted:
                conditions["deleted"] = 0
            
            count = await self.model.find(conditions).count()
            return count
        
        except Exception as e:
            self.logger.error(f"统计{self.model_name}记录失败: {e}", exc_info=True)
            return 0
    
    # ========== 更新操作 ==========
    
    async def update(
        self,
        doc_id: str,
        updater: str = "",
        **updates
    ) -> Optional[DocumentType]:
        """
        更新记录
        
        Args:
            doc_id: 文档ID
            updater: 更新者
            **updates: 要更新的字段
            
        Returns:
            更新后的文档实例，失败返回None
            
        Examples:
            >>> repo = ChunkDataRepository()
            >>> chunk = await repo.update(
            ...     "64abc123...",
            ...     updater="user1",
            ...     text="new text"
            ... )
        """
        try:
            doc = await self.get_by_id(doc_id)
            if not doc:
                self.logger.warning(f"{self.model_name}记录不存在: {doc_id}")
                return None
            
            # 更新字段
            for key, value in updates.items():
                if hasattr(doc, key):
                    setattr(doc, key, value)
            
            # 更新审计字段
            doc.updater = updater
            doc.update_time = datetime.now()
            
            # 保存
            await doc.save()
            
            self.logger.debug(f"成功更新{self.model_name}记录: {doc_id}")
            return doc
        
        except Exception as e:
            self.logger.error(f"更新{self.model_name}记录失败: {e}", exc_info=True)
            return None
    
    # ========== 删除操作 ==========
    
    async def delete(
        self,
        doc_id: str,
        updater: str = ""
    ) -> bool:
        """
        软删除记录
        
        Args:
            doc_id: 文档ID
            updater: 更新者
            
        Returns:
            删除成功返回True，否则返回False
            
        Examples:
            >>> repo = ChunkDataRepository()
            >>> success = await repo.delete("64abc123...", updater="user1")
        """
        try:
            doc = await self.get_by_id(doc_id)
            if not doc:
                self.logger.warning(f"未找到要删除的{self.model_name}记录: {doc_id}")
                return False
            
            # 软删除
            await doc.soft_delete(updater)
            
            self.logger.debug(f"成功删除{self.model_name}记录: {doc_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"删除{self.model_name}记录失败: {e}", exc_info=True)
            return False
    
    async def bulk_delete_by_ids(
        self,
        ids: List[Union[str, ObjectId, PydanticObjectId]],
        updater: str = ""
    ) -> int:
        """
        批量软删除记录
        
        Args:
            ids: 文档ID列表（字符串、ObjectId 或 PydanticObjectId）
            updater: 更新者
            
        Returns:
            删除的记录数量
            
        Examples:
            >>> repo = ChunkDataRepository()
            >>> count = await repo.bulk_delete_by_ids(
            ...     ["id1", "id2", "id3"],
            ...     updater="user1"
            ... )
        """
        try:
            if not ids:
                return 0
            
            # 类型转换：确保所有ID都是ObjectId类型
            object_ids = []
            for id_val in ids:
                if isinstance(id_val, str):
                    try:
                        object_ids.append(PydanticObjectId(id_val))
                    except Exception:
                        self.logger.warning(f"跳过无效的ObjectId: {id_val}")
                        continue
                elif isinstance(id_val, (ObjectId, PydanticObjectId)):
                    object_ids.append(id_val)
            
            if not object_ids:
                self.logger.warning("没有有效的ID进行批量删除")
                return 0
            
            # 使用 update_many 批量软删除
            result = await self.model.find(
                {"_id": {"$in": object_ids}, "deleted": 0}
            ).update({
                "$set": {
                    "deleted": 1,
                    "updater": updater,
                    "update_time": datetime.now()
                }
            })
            
            modified_count = result.modified_count if result else 0
            self.logger.debug(f"批量删除{self.model_name}记录: {modified_count}条")
            return modified_count
        
        except Exception as e:
            self.logger.error(f"批量删除{self.model_name}记录失败: {e}", exc_info=True)
            return 0
    
    # ========== Upsert 操作 ==========
    
    async def upsert(
        self,
        doc_id: str,
        creator: str = "",
        updater: str = "",
        **data
    ) -> DocumentType:
        """
        插入或更新（如果记录存在则更新，不存在则创建）
        
        Args:
            doc_id: 文档ID
            creator: 创建者
            updater: 更新者
            **data: 字段数据
            
        Returns:
            文档实例
            
        Examples:
            >>> repo = ChunkDataRepository()
            >>> chunk = await repo.upsert(
            ...     "64abc123...",
            ...     creator="user1",
            ...     updater="user1",
            ...     text="some text"
            ... )
        """
        try:
            # 尝试查询现有记录
            doc = await self.get_by_id(doc_id)
            
            if doc:
                # 记录已存在，更新
                self.logger.debug(f"{self.model_name} {doc_id} 已存在，更新记录")
                return await self.update(doc_id, updater, **data)
            else:
                # 记录不存在，创建
                self.logger.debug(f"{self.model_name} {doc_id} 不存在，创建新记录")
                data["_id"] = doc_id
                return await self.create(creator, **data)
        
        except Exception as e:
            self.logger.error(f"{self.model_name} upsert操作失败: {e}", exc_info=True)
            raise
    
    async def upsert_batch_optimized(
        self,
        data_list: List[Dict[str, Any]],
        id_field: str = "_id",
        creator: str = "",
        updater: str = ""
    ) -> int:
        """
        批量更新或插入（使用 bulk_write 优化）
        
        Args:
            data_list: 数据列表
            id_field: ID字段名，默认为 "_id"
            creator: 创建者
            updater: 更新者
            
        Returns:
            操作的记录数量（插入+更新）
            
        Examples:
            >>> repo = ChunkDataRepository()
            >>> count = await repo.upsert_batch_optimized([
            ...     {"_id": "id1", "text": "text1"},
            ...     {"_id": "id2", "text": "text2"}
            ... ], creator="user1")
        """
        try:
            if not data_list:
                return 0
            
            # 获取 motor 集合
            collection = self.model.get_motor_collection()
            
            # 准备批量操作
            operations = []
            current_time = datetime.now()
            
            for data in data_list:
                doc_id = data.get(id_field)
                if not doc_id:
                    self.logger.warning("数据缺少ID字段，跳过")
                    continue
                
                # 准备更新数据
                update_data = {k: v for k, v in data.items() if k != id_field}
                update_data["updater"] = updater
                update_data["update_time"] = current_time
                
                # 准备插入数据（只在文档不存在时设置）
                insert_data = {
                    "creator": creator,
                    "create_time": current_time,
                    "deleted": 0,
                    "status": 0
                }
                
                operations.append(
                    UpdateOne(
                        {"_id": doc_id},
                        {
                            "$set": update_data,
                            "$setOnInsert": insert_data
                        },
                        upsert=True
                    )
                )
            
            # 执行批量操作
            if operations:
                result = await collection.bulk_write(operations, ordered=False)
                total = result.modified_count + result.upserted_count
                self.logger.debug(
                    f"成功批量upsert {self.model_name}记录: "
                    f"插入{result.upserted_count}条, 更新{result.modified_count}条"
                )
                return total
            
            return 0
        
        except Exception as e:
            self.logger.error(f"批量upsert {self.model_name}记录失败: {e}", exc_info=True)
            raise
