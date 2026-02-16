#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : file_parser_service.py
@Author  : caixiongjiang
@Date    : 2026/02/04
@Function: 
    FileParser Service - 文件解析服务（完整流程）
    
    核心职责:
    - 从对象存储下载文件
    - 调用 FileParser 进行解析（纯解析）
    - 上传图片到 MinIO
    - 向 Kafka 发送数据库写入消息
    - 清理临时文件
    - 返回标准化的 ParseResult
    
    架构说明:
    FileParserService (本类) → 完整流程编排
      1. 下载文件
      2. 保存临时文件
      3. 调用 FileParser.parse() → 纯解析，返回解析结果
      4. 上传图片到 MinIO
      5. 构建 MySQL/MongoDB 数据
      6. 向 Kafka 发送消息（不直接插入数据库）
      7. 清理临时文件
      8. 返回 ParseResult
    
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

import tempfile
import uuid
import json
import base64
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from loguru import logger

from src.db.storage.manager import StorageManager
from src.index.common_file_extract.parser.file_parser import FileParser
from src.types.models.parse_result import ParseResult, ParseStatus


class FileParserService:
    """
    文件解析服务（完整流程）
    
    核心功能:
    1. 从对象存储下载文件
    2. 保存到临时文件
    3. 调用 FileParser.parse() 进行解析（纯解析，不存储）
    4. 上传图片到 MinIO
    5. 构建 MySQL/MongoDB 数据
    6. 向 Kafka 发送数据库写入消息
    7. 清理临时文件
    8. 返回标准化的 ParseResult
    
    使用方式:
        ```python
        async with StorageManager() as storage:
            service = FileParserService(storage_manager=storage)
            result = await service.parse_file(
                user_id="user1",
                file_id="file1",
                filename="doc.pdf",
                storage_path="bucket/path/to/file.pdf",
                knowledge_base_id="kb1",
                knowledge_base_name="我的知识库"
            )
            
            # 获取构建好的数据库消息
            mysql_data = result.mysql_messages
            mongodb_data = result.mongodb_messages
        ```
    """
    
    def __init__(self, storage_manager: StorageManager):
        """
        初始化文件解析服务
        
        Args:
            storage_manager: 对象存储管理器(必须)
        """
        self.storage_manager = storage_manager
        logger.info("FileParserService 初始化完成")
    
    # ========== 核心接口 ==========
    
    async def parse_file(
        self,
        user_id: str,
        file_id: str,
        filename: str,
        storage_path: str,
        knowledge_base_id: str,
        knowledge_base_name: str,
        session_id: Optional[str] = None,
        parent_knowledge_base_id: Optional[str] = None,
        parent_knowledge_base_name: Optional[str] = None,
        knowledge_type: Optional[str] = None,
        creator: str = "system",
        store_images: bool = True
    ) -> Tuple[ParseResult, List[Dict], List[Dict]]:
        """
        解析文件(核心方法)
        
        完整流程:
        1. 从对象存储下载文件
        2. 保存到临时文件
        3. 调用 FileParser.parse() 进行解析
        4. 上传图片到 MinIO
        5. 构建 MySQL/MongoDB 数据
        6. 清理临时文件
        7. 返回 ParseResult 和数据库消息
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
            filename: 文件名
            storage_path: 文件在对象存储中的路径(格式: bucket/path/to/file)
            knowledge_base_id: 知识库ID
            knowledge_base_name: 知识库名称
            session_id: 会话ID(可选,用于图片上传路径)
            parent_knowledge_base_id: 父知识库ID(可选)
            parent_knowledge_base_name: 父知识库名称(可选)
            knowledge_type: 知识类型(可选)
            creator: 创建者
            store_images: 是否上传图片到 MinIO
            
        Returns:
            Tuple[ParseResult, List[Dict], List[Dict]]: 
                - ParseResult: 解析结果
                - MySQL消息列表
                - MongoDB消息列表
            
        Raises:
            Exception: 下载、解析或处理失败
        """
        logger.info(f"开始解析文件: user_id={user_id}, file_id={file_id}, filename={filename}")
        
        # 初始化结果对象
        result = ParseResult(
            user_id=user_id,
            file_id=file_id,
            filename=filename,
            status=ParseStatus.PENDING,
            storage_path=storage_path,
            knowledge_base_id=knowledge_base_id,
            knowledge_base_name=knowledge_base_name
        )
        
        temp_file_path = None
        mysql_messages = []
        mongodb_messages = []
        
        try:
            # 1. 下载文件
            logger.info(f"下载文件: {storage_path}")
            file_bytes = await self._download_file(storage_path)
            logger.info(f"文件下载成功: {len(file_bytes)} bytes")
            
            # 2. 保存到临时文件
            temp_file_path = self._save_to_temp_file(file_bytes, filename)
            logger.info(f"临时文件创建: {temp_file_path}")
            
            # 3. 调用 FileParser 进行解析（纯解析，不存储）
            logger.info("开始解析文件...")
            parse_result = await FileParser.parse(
                file_path=temp_file_path,
                file_name=filename
            )
            logger.info("文件解析完成")
            
            # 4. 构建知识库信息
            knowledge_base_info = {
                "knowledge_base_id": knowledge_base_id,
                "knowledge_base_name": knowledge_base_name,
                "parent_knowledge_base_id": parent_knowledge_base_id,
                "parent_knowledge_base_name": parent_knowledge_base_name,
                "knowledge_type": knowledge_type
            }
            
            # 5. 处理解析结果：上传图片 + 构建数据库消息
            logger.info("处理解析结果...")
            mysql_messages, mongodb_messages = await self._process_parse_result(
                parse_result=parse_result,
                user_id=user_id,
                file_id=file_id,
                session_id=session_id,
                knowledge_base_info=knowledge_base_info,
                creator=creator,
                store_images=store_images
            )
            logger.info(f"消息构建完成: MySQL={len(mysql_messages)}, MongoDB={len(mongodb_messages)}")
            
            # 6. 转换为标准 ParseResult
            result = self._convert_to_parse_result(
                parse_result=parse_result,
                mysql_count=len(mysql_messages),
                mongodb_count=len(mongodb_messages),
                user_id=user_id,
                file_id=file_id,
                filename=filename,
                storage_path=storage_path,
                knowledge_base_id=knowledge_base_id,
                knowledge_base_name=knowledge_base_name
            )
            
            logger.info(f"文件解析成功: {result.get_summary()}")
            return result, mysql_messages, mongodb_messages
            
        except Exception as e:
            # 错误处理
            error_msg = f"解析文件失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.status = ParseStatus.FAILED
            result.error_message = error_msg
            return result, mysql_messages, mongodb_messages
            
        finally:
            # 7. 清理临时文件
            if temp_file_path:
                self._cleanup_temp_file(temp_file_path)
    
    # ========== 私有方法: 文件下载 ==========
    
    async def _download_file(self, storage_path: str) -> bytes:
        """
        从对象存储下载文件
        
        Args:
            storage_path: 存储路径(格式: bucket/path/to/file)
            
        Returns:
            bytes: 文件字节内容
            
        Raises:
            Exception: 下载失败
        """
        try:
            return await self.storage_manager.download_file(storage_path)
        except Exception as e:
            raise Exception(f"下载文件失败: {e}")
    
    def _save_to_temp_file(self, file_bytes: bytes, filename: str) -> str:
        """
        保存字节内容到临时文件
        
        Args:
            file_bytes: 文件字节内容
            filename: 原始文件名(用于保留扩展名)
            
        Returns:
            str: 临时文件路径
            
        Raises:
            Exception: 保存失败
        """
        try:
            # 获取文件扩展名
            suffix = Path(filename).suffix
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
                prefix="file_parser_"
            ) as tmp_file:
                tmp_file.write(file_bytes)
                temp_path = tmp_file.name
            
            return temp_path
            
        except Exception as e:
            raise Exception(f"保存临时文件失败: {e}")
    
    def _cleanup_temp_file(self, temp_file_path: str):
        """
        清理临时文件
        
        Args:
            temp_file_path: 临时文件路径
        """
        try:
            Path(temp_file_path).unlink(missing_ok=True)
            logger.debug(f"临时文件已清理: {temp_file_path}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")
    
    # ========== 私有方法: 处理解析结果 ==========
    
    async def _process_parse_result(
        self,
        parse_result: Dict,
        user_id: str,
        file_id: str,
        session_id: Optional[str],
        knowledge_base_info: Dict[str, Any],
        creator: str,
        store_images: bool
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        处理解析结果：上传图片 + 构建数据库消息
        
        Args:
            parse_result: FileParser.parse() 的返回结果
            user_id: 用户ID
            file_id: 文件ID
            session_id: 会话ID
            knowledge_base_info: 知识库信息
            creator: 创建者
            store_images: 是否上传图片
            
        Returns:
            Tuple[List[Dict], List[Dict]]: MySQL消息列表, MongoDB消息列表
        """
        struct_content = parse_result.get("struct_content", {})
        root_pages = struct_content.get("root", [])
        
        mysql_messages = []
        mongodb_messages = []
        
        # 遍历每一页
        for page_data in root_pages:
            page_idx = page_data.get("page_idx")
            page_info_list = page_data.get("page_info", [])
            
            # 遍历每个元素
            for element in page_info_list:
                # 使用 UUID4 生成唯一的 element_id
                element_id = "element_" + str(uuid.uuid4())
                element_type = element.get("type")
                bbox = element.get("bbox", [])
                element_index = element.get("element_index", 0)
                
                # 处理图片上传（如果需要）
                bucket_name = None
                image_file_path = None
                if store_images and element_type == "image" and session_id:
                    bucket_name, image_file_path = await self._upload_image(
                        element=element,
                        user_id=user_id,
                        file_id=file_id,
                        session_id=session_id,
                        element_id=element_id
                    )
                
                # 构建 MySQL 消息
                mysql_message = self._build_mysql_message(
                    element_id=element_id,
                    element_type=element_type,
                    element_index=element_index,
                    page_idx=page_idx,
                    bbox=bbox,
                    element=element,
                    knowledge_base_info=knowledge_base_info,
                    creator=creator,
                    bucket_name=bucket_name,
                    image_file_path=image_file_path
                )
                mysql_messages.append(mysql_message)
                
                # 构建 MongoDB 消息
                mongodb_message = self._build_mongodb_message(
                    element_id=element_id,
                    element_type=element_type,
                    element=element
                )
                mongodb_messages.append(mongodb_message)
        
        return mysql_messages, mongodb_messages
    
    async def _upload_image(
        self,
        element: Dict,
        user_id: str,
        file_id: str,
        session_id: str,
        element_id: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        上传图片到 MinIO
        
        Args:
            element: 元素数据
            user_id: 用户ID
            file_id: 文件ID
            session_id: 会话ID
            element_id: 元素ID
            
        Returns:
            Tuple[bucket_name, image_path]: 桶名称和图片路径
        """
        try:
            # 从 element 中提取图片数据
            image_base64 = element.get("image_base64")
            if not image_base64:
                return None, None
            
            # 解码 base64
            image_bytes = base64.b64decode(image_base64)
            
            # 生成图片文件名
            img_path = element.get("img_path", "")
            if img_path:
                image_name = Path(img_path).name
            else:
                image_name = f"{element_id}.png"
            
            # 上传到 MinIO
            storage_path = await self.storage_manager.upload_image(
                image_bytes=image_bytes,
                user_id=user_id,
                session_id=session_id,
                file_id=file_id,
                image_name=image_name
            )
            
            # 解析 storage_path: bucket/path/to/image
            parts = storage_path.split("/", 1)
            bucket_name = parts[0] if len(parts) > 1 else "knowledge-files"
            image_path = parts[1] if len(parts) > 1 else storage_path
            
            logger.debug(f"图片上传成功: {storage_path}")
            return bucket_name, image_path
            
        except Exception as e:
            logger.error(f"图片上传失败: {e}")
            return None, None
    
    def _build_mysql_message(
        self,
        element_id: str,
        element_type: str,
        element_index: int,
        page_idx: int,
        bbox: list,
        element: Dict,
        knowledge_base_info: Dict,
        creator: str,
        bucket_name: Optional[str] = None,
        image_file_path: Optional[str] = None
    ) -> Dict:
        """构建 MySQL 插入消息"""
        # 构建位置信息
        page_position = None
        if bbox and len(bbox) == 4:
            page_position = json.dumps(bbox)
        
        # 提取 text_level（仅 text 类型）
        text_level = element.get("text_level") if element_type == "text" else None
        
        # 提取图片相关字段（仅 image 类型）
        image_file_name = None
        image_file_type = None
        image_file_format = None
        image_file_suffix = None
        
        if element_type == "image":
            img_path = element.get("img_path", "")
            if img_path:
                path_obj = Path(img_path)
                image_file_name = path_obj.name
                image_file_suffix = path_obj.suffix
                image_file_type = path_obj.suffix.lstrip('.')
        
        # 构建消息
        message = {
            "element_id": element_id,
            "element_index": element_index,
            "page_index": page_idx,
            "element_type": element_type,
            "page_position": page_position,
            "text_level": text_level,
            "bucket_name": bucket_name,
            "image_file_path": image_file_path,
            "image_file_name": image_file_name,
            "image_file_type": image_file_type,
            "image_file_format": image_file_format,
            "image_file_suffix": image_file_suffix,
            # KnowledgeMixin 字段
            "knowledge_base_id": knowledge_base_info.get("knowledge_base_id"),
            "knowledge_base_name": knowledge_base_info.get("knowledge_base_name"),
            "parent_knowledge_base_id": knowledge_base_info.get("parent_knowledge_base_id"),
            "parent_knowledge_base_name": knowledge_base_info.get("parent_knowledge_base_name"),
            "knowledge_type": knowledge_base_info.get("knowledge_type"),
            # BaseModel 字段
            "creator": creator,
            "updater": creator
        }
        
        return message
    
    def _build_mongodb_message(
        self,
        element_id: str,
        element_type: str,
        element: Dict
    ) -> Dict:
        """构建 MongoDB 插入消息"""
        # 根据类型提取内容
        content = {}
        
        if element_type == "text":
            content = {
                "text": element.get("text", "")
            }
        elif element_type == "image":
            content = {
                "image_caption": element.get("image_caption", []),
                "image_footnote": element.get("image_footnote", [])
            }
        elif element_type == "table":
            content = {
                "table_caption": element.get("table_caption", []),
                "table_footnote": element.get("table_footnote", []),
                "table_body": element.get("table_body", "")
            }
        elif element_type == "equation":
            content = {
                "text": element.get("text", ""),
                "text_format": element.get("text_format", "")
            }
        elif element_type == "discarded":
            content = {
                "text": element.get("text", "")
            }
        else:
            content = {
                "text": element.get("text", "")
            }
        
        # 构建消息
        message = {
            "_id": element_id,
            "type": element_type,
            "content": content
        }
        
        return message
    
    # ========== 私有方法: 数据转换 ==========
    
    def _convert_to_parse_result(
        self,
        parse_result: Dict,
        mysql_count: int,
        mongodb_count: int,
        user_id: str,
        file_id: str,
        filename: str,
        storage_path: str,
        knowledge_base_id: str,
        knowledge_base_name: str
    ) -> ParseResult:
        """
        将解析结果转换为标准 ParseResult
        
        Args:
            parse_result: FileParser.parse() 的返回结果
            mysql_count: MySQL 消息数量
            mongodb_count: MongoDB 消息数量
            user_id: 用户ID
            file_id: 文件ID
            filename: 文件名
            storage_path: 存储路径
            knowledge_base_id: 知识库ID
            knowledge_base_name: 知识库名称
            
        Returns:
            ParseResult: 标准解析结果
        """
        # 解析状态
        status = ParseStatus.SUCCESS if parse_result.get("status") == "success" else ParseStatus.FAILED
        
        # 提取统计信息
        total_pages = parse_result.get("total_pages", 0)
        
        # 构建 ParseResult
        result = ParseResult(
            user_id=user_id,
            file_id=file_id,
            filename=filename,
            status=status,
            elements=[],  # 数据将通过 Kafka 异步写入数据库
            parse_tool="mineru",
            total_pages=total_pages,
            total_chars=0,  # 可以从 MongoDB 异步统计
            storage_path=storage_path,
            knowledge_base_id=knowledge_base_id,
            knowledge_base_name=knowledge_base_name
        )
        
        logger.debug(
            f"解析结果转换完成: status={status}, "
            f"mysql_messages={mysql_count}, "
            f"mongodb_messages={mongodb_count}"
        )
        
        return result
