#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : file_parser.py
@Author  : caixiongjiang
@Date    : 2025/12/31 14:27
@Function: 
    文件解析器 - 统一的文件解析入口
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Dict, Optional, Union, Any
from pathlib import Path
import json
import uuid

from loguru import logger
from sqlalchemy.orm import Session

from src.index.common_file_extract.parser.pdf_parser import PDFParser
from src.db.mysql.models.base.element_meta_info import ElementMetaInfo
from src.db.mongodb.models.element_data import ElementData


class FileParser:
    """
    文件解析器 - 统一的文件解析和存储入口
    
    功能：
    1. 根据文件类型路由到不同的解析器
    2. 解析文件内容
    3. 存储元信息到 MySQL
    4. 存储内容数据到 MongoDB
    5. 存储图片到存储服务（可选，支持 MinIO/S3/OSS/COS 等）
    """
    
    SUPPORTED_EXTENSIONS = {
        '.pdf': 'pdf',
        '.PDF': 'pdf',
        # 未来扩展：
        # '.docx': 'docx',
        # '.txt': 'txt',
        # '.md': 'markdown',
    }
    
    def __init__(
        self,
        pdf_parser: PDFParser,
        mysql_session: Session,
        storage_client: Optional[Any] = None
    ):
        """
        初始化文件解析器
        
        :param pdf_parser: PDF 解析器实例
        :param mysql_session: MySQL 数据库会话
        :param storage_client: 存储客户端（可选，支持 MinIO、S3、OSS 等）
        """
        self.pdf_parser = pdf_parser
        self.mysql_session = mysql_session
        self.storage_client = storage_client
        self.logger = logger
    
    def detect_file_type(self, file_path: Union[str, Path]) -> str:
        """
        检测文件类型
        
        :param file_path: 文件路径
        :return: 文件类型（pdf, docx, txt等）
        :raises ValueError: 不支持的文件类型
        """
        file_path = Path(file_path)
        suffix = file_path.suffix
        
        if suffix not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件类型: {suffix}")
        
        return self.SUPPORTED_EXTENSIONS[suffix]
    
    async def _route_to_parser(self, file_type: str, file_path: Path) -> Dict:
        """
        根据文件类型路由到对应的解析器
        
        :param file_type: 文件类型
        :param file_path: 文件路径
        :return: 解析结果
        :raises ValueError: 不支持的文件类型
        """
        if file_type == 'pdf':
            return await self.pdf_parser.parse(file_path)
        elif file_type == 'docx':
            # 未来实现
            # return await self.docx_parser.parse(file_path)
            raise ValueError(f"文件类型 {file_type} 暂未实现")
        elif file_type == 'txt':
            # 未来实现
            # return await self.txt_parser.parse(file_path)
            raise ValueError(f"文件类型 {file_type} 暂未实现")
        elif file_type == 'markdown':
            # 未来实现
            # return await self.markdown_parser.parse(file_path)
            raise ValueError(f"文件类型 {file_type} 暂未实现")
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")
    
    async def parse_and_store(
        self,
        file_path: Union[str, Path],
        knowledge_base_info: Dict[str, Any],
        creator: str = "system",
        store_images: bool = False
    ) -> Dict[str, Any]:
        """
        解析文件并存储到数据库
        
        :param file_path: 文件路径
        :param knowledge_base_info: 知识库信息字典，包含：
            - knowledge_base_id: 知识库ID
            - knowledge_base_name: 知识库名称
            - parent_knowledge_base_id: 父知识库ID（可选）
            - parent_knowledge_base_name: 父知识库名称（可选）
            - knowledge_type: 知识类型（可选）
        :param creator: 创建者
        :param store_images: 是否存储图片到存储服务
        
        :return: 存储结果统计
        {
            "status": "success",
            "file_name": "example.pdf",
            "file_type": "pdf",
            "total_pages": 10,
            "total_elements": 50,
            "elements_by_type": {
                "text": 30,
                "image": 10,
                "table": 5,
                "discarded": 5
            },
            "stored_mysql": 50,
            "stored_mongodb": 50,
            "stored_minio": 10
        }
        
        :raises Exception: 解析或存储失败时抛出异常
        """
        file_path = Path(file_path)
        file_name = file_path.name
        
        self.logger.info(f"🚀 开始解析文件: {file_name}")
        
        try:
            # 1. 检测文件类型
            file_type = self.detect_file_type(file_path)
            self.logger.info(f"📂 文件类型: {file_type}")
            
            # 2. 路由到对应的解析器
            parse_result = await self._route_to_parser(file_type, file_path)
            
            # 3. 提取解析结果
            struct_content = parse_result.get("struct_content", {})
            total_pages = parse_result.get("pages", 0)
            
            # 4. 存储到数据库
            storage_stats = await self._store_to_databases(
                struct_content=struct_content,
                knowledge_base_info=knowledge_base_info,
                creator=creator,
                store_images=store_images
            )
            
            # 5. 构建返回结果
            result = {
                "status": "success",
                "file_name": file_name,
                "file_type": file_type,
                "total_pages": total_pages,
                **storage_stats
            }
            
            self.logger.info(
                f"✅ 文件解析完成: {file_name}, "
                f"总计 {storage_stats['total_elements']} 个元素"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 文件解析失败: {file_name}, 错误: {e}")
            raise Exception(f"文件解析失败: {e}")
    
    async def _store_to_databases(
        self,
        struct_content: Dict,
        knowledge_base_info: Dict[str, Any],
        creator: str,
        store_images: bool
    ) -> Dict[str, Any]:
        """
        将解析结果存储到数据库
        
        注意：element_id 使用 UUID4 随机生成，确保全局唯一性
        
        :param struct_content: 结构化内容
        :param knowledge_base_info: 知识库信息
        :param creator: 创建者
        :param store_images: 是否存储图片
        
        :return: 存储统计信息
        """
        root_pages = struct_content.get("root", [])
        
        # 统计信息
        stats = {
            "total_elements": 0,
            "elements_by_type": {
                "text": 0,
                "image": 0,
                "table": 0,
                "discarded": 0
            },
            "stored_mysql": 0,
            "stored_mongodb": 0,
            "stored_minio": 0
        }
        
        # 批量存储列表
        mysql_records = []
        mongodb_records = []
        
        # 遍历每一页
        for page_data in root_pages:
            page_idx = page_data.get("page_idx")
            page_size = page_data.get("page_size", {})
            page_info_list = page_data.get("page_info", [])
            
            # 遍历每个元素
            for element in page_info_list:
                # 使用 UUID4 生成唯一的 element_id
                element_id = "element_" + str(uuid.uuid4())
                element_type = element.get("type")
                bbox = element.get("bbox", [])
                element_index = element.get("element_index", 0)
                
                # 更新统计
                stats["total_elements"] += 1
                stats["elements_by_type"][element_type] = \
                    stats["elements_by_type"].get(element_type, 0) + 1
                
                # 构建 MySQL 记录
                mysql_record = self._build_mysql_record(
                    element_id=element_id,
                    element_type=element_type,
                    page_idx=page_idx,
                    bbox=bbox,
                    element=element,
                    knowledge_base_info=knowledge_base_info,
                    creator=creator
                )
                mysql_records.append(mysql_record)
                
                # 构建 MongoDB 记录
                mongodb_record = self._build_mongodb_record(
                    element_id=element_id,
                    element_type=element_type,
                    element=element
                )
                mongodb_records.append(mongodb_record)
                
                # 处理图片存储（如果需要）
                if store_images and element_type == "image":
                    await self._store_image_to_storage(element, element_id)
                    stats["stored_minio"] += 1
        
        # 批量写入 MySQL
        try:
            self.mysql_session.bulk_save_objects(mysql_records)
            self.mysql_session.commit()
            stats["stored_mysql"] = len(mysql_records)
            self.logger.info(f"✅ MySQL 存储完成: {stats['stored_mysql']} 条记录")
        except Exception as e:
            self.mysql_session.rollback()
            raise Exception(f"MySQL 存储失败: {e}")
        
        # 批量写入 MongoDB
        try:
            if mongodb_records:
                await ElementData.insert_many(mongodb_records)
            stats["stored_mongodb"] = len(mongodb_records)
            self.logger.info(f"✅ MongoDB 存储完成: {stats['stored_mongodb']} 条记录")
        except Exception as e:
            raise Exception(f"MongoDB 存储失败: {e}")
        
        return stats
    
    def _build_mysql_record(
        self,
        element_id: str,
        element_type: str,
        page_idx: int,
        bbox: list,
        element: Dict,
        knowledge_base_info: Dict,
        creator: str
    ) -> ElementMetaInfo:
        """
        构建 MySQL 记录
        
        注意：审计字段（status, create_time, update_time, deleted）由数据库自动填充，
        应用层只需提供业务必需的字段（creator, updater）
        
        :param element_id: 元素ID
        :param element_type: 元素类型
        :param page_idx: 页码
        :param bbox: 边界框 [x, y, width, height]
        :param element: 元素完整数据
        :param knowledge_base_info: 知识库信息
        :param creator: 创建者
        
        :return: ElementMetaInfo 实例
        """
        # 构建位置信息（直接使用 bbox 数组格式：[x, y, width, height]）
        page_position = None
        if bbox and len(bbox) == 4:
            page_position = json.dumps(bbox)
        
        # 提取 text_level（仅 text 类型）
        # 注意：并非所有 text 类型都有 text_level，只有标题等有层级结构的文本才有
        text_level = element.get("text_level") if element_type == "text" else None
        
        # 提取图片相关字段（仅 image 类型）
        bucket_name = None
        image_file_path = None
        image_file_name = None
        image_file_type = None
        image_file_format = None
        image_file_suffix = None
        
        if element_type == "image":
            img_path = element.get("img_path", "")
            if img_path:
                # 从路径提取文件信息
                path_obj = Path(img_path)
                image_file_name = path_obj.name
                image_file_suffix = path_obj.suffix
                image_file_type = path_obj.suffix.lstrip('.')
        
        # 构建记录
        record = ElementMetaInfo(
            element_id=element_id,
            page_index=page_idx,
            element_type=element_type,
            page_position=page_position,
            text_level=text_level,
            bucket_name=bucket_name,
            image_file_path=image_file_path,
            image_file_name=image_file_name,
            image_file_type=image_file_type,
            image_file_format=image_file_format,
            image_file_suffix=image_file_suffix,
            # KnowledgeMixin 字段
            knowledge_base_id=knowledge_base_info.get("knowledge_base_id"),
            knowledge_base_name=knowledge_base_info.get("knowledge_base_name"),
            parent_knowledge_base_id=knowledge_base_info.get("parent_knowledge_base_id"),
            parent_knowledge_base_name=knowledge_base_info.get("parent_knowledge_base_name"),
            knowledge_type=knowledge_base_info.get("knowledge_type"),
            # BaseModel 字段（仅设置必须由应用层提供的字段）
            creator=creator,
            updater=creator
            # status, create_time, update_time, deleted 由数据库默认值自动设置
        )
        
        return record
    
    def _build_mongodb_record(
        self,
        element_id: str,
        element_type: str,
        element: Dict
    ) -> ElementData:
        """
        构建 MongoDB 记录
        
        :param element_id: 元素ID（作为 _id）
        :param element_type: 元素类型
        :param element: 元素完整数据
        
        :return: ElementData 实例
        """
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
        elif element_type == "discarded":
            content = {
                "text": element.get("text", "")
            }
        
        # 构建记录
        record = ElementData(
            id=element_id,  # Beanie 会将 id 映射为 _id
            type=element_type,
            content=content
        )
        
        return record
    
    async def _store_image_to_storage(
        self,
        element: Dict,
        element_id: str
    ) -> Optional[str]:
        """
        存储图片到存储服务
        
        :param element: 元素数据
        :param element_id: 元素ID
        
        :return: 存储路径（如果成功）
        
        注意：此功能暂未实现，预留接口
        支持的存储类型：MinIO, S3, OSS, COS 等
        """
        # TODO: 实现图片存储到存储服务
        # 1. 从 element 中提取 image_base64
        # 2. 解码 base64 为字节
        # 3. 根据 storage_client 类型上传到对应存储
        # 4. 返回存储路径
        pass
    
    async def parse_multiple_and_store(
        self,
        file_paths: list[Union[str, Path]],
        knowledge_base_info: Dict[str, Any],
        creator: str = "system",
        store_images: bool = False
    ) -> list[Dict[str, Any]]:
        """
        批量解析多个文件并存储
        
        :param file_paths: 文件路径列表
        :param knowledge_base_info: 知识库信息
        :param creator: 创建者
        :param store_images: 是否存储图片
        
        :return: 每个文件的处理结果列表
        """
        results = []
        
        for file_path in file_paths:
            try:
                result = await self.parse_and_store(
                    file_path=file_path,
                    knowledge_base_info=knowledge_base_info,
                    creator=creator,
                    store_images=store_images
                )
                results.append(result)
            except Exception as e:
                results.append({
                    "status": "failed",
                    "file_name": Path(file_path).name,
                    "error": str(e)
                })
        
        return results
