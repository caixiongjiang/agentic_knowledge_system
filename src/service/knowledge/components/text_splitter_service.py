#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : text_splitter_service.py
@Author  : caixiongjiang
@Date    : 2026/02/07
@Function: 
    TextSplitter Service - 文本切分服务
    
    核心职责:
    - 从数据库加载 ParseResult
    - 执行文本切分
    - 生成 SplitResult
    
    架构说明:
    TextSplitterService (本类) → 完整流程编排
      1. 从 MySQL/MongoDB 加载 ParseResult
      2. 调用切分器处理文本、表格、图片、代码
      3. 生成 Section 和 Chunk
      4. 返回 SplitResult
    
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import List, Optional, Dict, Any, Tuple
from loguru import logger
from sqlalchemy.orm import Session

from src.types.models.parse_result import ParseResult, ElementInfo, ElementType
from src.types.models.split_result import (
    SplitResult,
    SplitStatus,
    SectionInfo,
    ChunkInfo
)
from src.utils.component_config_manager import get_component_config_manager
from src.index.common_file_extract.splitter.models import SplitConfig
from src.index.common_file_extract.splitter.text_splitter import TextSplitter
from src.index.common_file_extract.splitter.table_splitter import TableSplitter
from src.index.common_file_extract.splitter.element_processor import ElementProcessor
from src.index.common_file_extract.splitter.text_cleaner import TextCleaner

# 数据库导入
from src.db.mysql.repositories.base.element_meta_info_repo import element_meta_info_repo
from src.db.mongodb.repositories.element_data_repository import element_data_repository


class TextSplitterService:
    """
    文本切分服务
    
    核心功能：
    - 从数据库加载 ParseResult
    - 执行文本切分
    - 生成 SplitResult
    """
    
    def __init__(self, config: Optional[SplitConfig] = None):
        """
        初始化切分服务
        
        Args:
            config: 切分配置（如果为 None，则从 config/components.json 加载）
        """
        if config is None:
            config_manager = get_component_config_manager()
            config_dict = config_manager.get_text_splitter_config()
            # 过滤掉不属于 SplitConfig 的字段（如 enabled, comment）
            valid_fields = SplitConfig.model_fields.keys()
            filtered_config = {k: v for k, v in config_dict.items() if k in valid_fields}
            config = SplitConfig(**filtered_config)
        
        self.config = config
        self.text_splitter = TextSplitter(self.config)
        self.table_splitter = TableSplitter()
        self.element_processor = ElementProcessor()
        self.text_cleaner = TextCleaner()
    
    async def load_parse_result_from_db(
        self,
        user_id: str,
        file_id: str,
        document_id: str,
        mysql_session: Session,
        knowledge_base_id: Optional[str] = None
    ) -> ParseResult:
        """
        从数据库加载 ParseResult
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
            document_id: Document ID（格式: document-{uuid}，基于file_sha256的后台唯一标识）
            mysql_session: MySQL会话
            knowledge_base_id: 知识库ID
        
        Returns:
            ParseResult
        """
        logger.info(f"从数据库加载ParseResult: user_id={user_id}, document_id={document_id}")
        
        # 1. 从 MySQL 通过 document_id 获取所有 ElementMetaInfo
        elements_meta = element_meta_info_repo.get_by_document_id(mysql_session, document_id)
        
        logger.debug(f"从MySQL加载了 {len(elements_meta)} 个元素元信息")
        
        if not elements_meta:
            logger.warning(f"未找到任何元素元信息: document_id={document_id}")
            return ParseResult(
                user_id=user_id,
                file_id=file_id,
                document_id=document_id,
                filename="unknown",
                status="failed",
                error_message="未找到解析数据",
                elements=[],
                knowledge_base_id=knowledge_base_id
            )
        
        # 2. 提取所有 element_id
        element_ids = [elem.element_id for elem in elements_meta]
        
        # 3. 从 MongoDB 批量获取内容
        elements_data = await element_data_repository.get_by_ids(element_ids)
        logger.debug(f"从MongoDB加载了 {len(elements_data)} 个元素内容")
        
        # 4. 构建 element_id -> content 的映射
        content_map = {elem.id: elem for elem in elements_data}
        
        # 5. 合并元信息和内容，构建 ElementInfo 列表
        elements = []
        for elem_meta in elements_meta:
            elem_content = content_map.get(elem_meta.element_id)
            
            # 辅助函数：将列表转换为字符串（MongoDB 存储为列表，ElementInfo 需要字符串）
            def list_to_str(value):
                """将列表转换为字符串，如果是列表则取第一个元素"""
                if isinstance(value, list) and len(value) > 0:
                    return value[0]
                return value if isinstance(value, str) else None
            
            # 构建 ElementInfo
            element_info = ElementInfo(
                element_id=elem_meta.element_id,
                document_id=elem_meta.document_id,
                element_index=elem_meta.element_index,
                element_type=ElementType(elem_meta.element_type),
                page_index=elem_meta.page_index,
                page_position=eval(elem_meta.page_position) if elem_meta.page_position else None,
                # 文本特定字段
                text=elem_content.content.get("text") if elem_content else None,
                text_level=elem_meta.text_level,
                # 图片特定字段
                bucket_name=elem_meta.bucket_name,
                image_file_path=elem_meta.image_file_path,
                image_file_name=elem_meta.image_file_name,
                image_file_type=elem_meta.image_file_type,
                image_file_format=elem_meta.image_file_format,
                image_file_suffix=elem_meta.image_file_suffix,
                image_caption=list_to_str(elem_content.content.get("image_caption")) if elem_content else None,
                image_footnote=list_to_str(elem_content.content.get("image_footnote")) if elem_content else None,
                # 表格特定字段
                table_body=elem_content.content.get("table_body") if elem_content else None,
                table_caption=list_to_str(elem_content.content.get("table_caption")) if elem_content else None,
                table_footnote=list_to_str(elem_content.content.get("table_footnote")) if elem_content else None,
            )
            elements.append(element_info)
        
        # 6. 构建 ParseResult
        parse_result = ParseResult(
            user_id=user_id,
            file_id=file_id,
            document_id=document_id,
            filename="unknown",  # TODO: 从 workspace_file_system 表获取
            status="success",
            elements=elements,
            total_pages=max((e.page_index or 0) for e in elements) + 1 if elements else 0,
            knowledge_base_id=knowledge_base_id
        )
        
        logger.info(f"ParseResult加载完成: {len(elements)} 个元素, {parse_result.total_pages} 页")
        return parse_result
    
    def _map_chunks_to_elements(
        self,
        merged_text: str,
        split_texts: List[str],
        element_char_ranges: List[Tuple[int, int, str]],
    ) -> List[List[str]]:
        """将每个分块精确映射到其实际包含的 element_id 列表

        通过字符位置匹配：先确定每个 split_text 在 merged_text 中的位置，
        再找出与该位置范围有交集的 element。

        Args:
            merged_text: 由 text_buffer 拼接的完整文本
            split_texts: text_splitter 切分后的文本列表
            element_char_ranges: 每个 element 在 merged_text 中的字符范围
                [(start, end, element_id), ...]

        Returns:
            per_chunk_element_ids: 每个 chunk 对应的 element_id 列表
        """
        all_element_ids = [r[2] for r in element_char_ranges]
        result: List[List[str]] = []
        cursor = 0

        for split_text in split_texts:
            search_start = max(0, cursor - self.config.chunk_overlap - 50)
            idx = merged_text.find(split_text, search_start)

            if idx == -1:
                idx = merged_text.find(split_text)

            if idx >= 0:
                chunk_start = idx
                chunk_end = idx + len(split_text)
                cursor = idx + 1

                chunk_element_ids: List[str] = []
                for elem_start, elem_end, elem_id in element_char_ranges:
                    if elem_start < chunk_end and elem_end > chunk_start:
                        chunk_element_ids.append(elem_id)

                result.append(chunk_element_ids if chunk_element_ids else list(all_element_ids))
            else:
                logger.warning(
                    f"无法在 merged_text 中定位分块文本(len={len(split_text)})，"
                    f"回退至关联所有 {len(all_element_ids)} 个 element"
                )
                result.append(list(all_element_ids))

        return result

    def _flush_text_buffer(
        self,
        text_buffer: List[str],
        buffer_element_ids: List[str],
        buffer_page_index: Optional[int],
        section_id: Optional[str],
        document_id: str,
        language: str
    ) -> List[ChunkInfo]:
        """
        将累积的文本 buffer 合并、切分并生成 Chunk

        精确溯源策略：
        1. 计算每个 element 在 merged_text 中的字符范围
        2. 切分后，根据每个 chunk 文本在 merged_text 中的位置
           匹配与之有交集的 element，得到精确的 per-chunk element_ids

        Args:
            text_buffer: 累积的已清洗文本列表
            buffer_element_ids: 累积的 Element ID 列表
            buffer_page_index: 首个文本元素的页码
            section_id: 当前 Section ID
            document_id: 文档 ID
            language: 文档语言

        Returns:
            生成的 ChunkInfo 列表（buffer 为空时返回空列表）
        """
        if not text_buffer:
            return []

        separator = "\n\n"

        element_char_ranges: List[Tuple[int, int, str]] = []
        offset = 0
        for i, text in enumerate(text_buffer):
            start = offset
            end = offset + len(text)
            element_char_ranges.append((start, end, buffer_element_ids[i]))
            offset = end + len(separator)

        merged_text = separator.join(text_buffer)
        split_texts = self.text_splitter.split_text(merged_text)

        per_chunk_element_ids = self._map_chunks_to_elements(
            merged_text, split_texts, element_char_ranges,
        )

        text_chunks = self.element_processor.create_text_chunks(
            per_chunk_element_ids=per_chunk_element_ids,
            page_index=buffer_page_index,
            section_id=section_id,
            split_texts=split_texts,
            document_id=document_id,
            language=language
        )

        logger.debug(
            f"flush文本buffer: {len(buffer_element_ids)}个元素, "
            f"合并{len(merged_text)}字符, 切分为{len(text_chunks)}个chunk"
        )

        return text_chunks
    
    async def split_document(
        self,
        parse_result: ParseResult,
        document_id: str
    ) -> SplitResult:
        """
        执行文档切分
        
        采用"文本累积 buffer"策略：连续的文本 Element 先累积到 buffer 中，
        遇到非文本元素（图片/表格/标题）或循环结束时再统一 flush（合并 + 切分）。
        这避免了连续短文本 Element 各自产生碎片 chunk 的问题。
        
        Args:
            parse_result: 解析结果
            document_id: 文档ID
        
        Returns:
            切分结果
        """
        logger.info(f"开始文档切分: file_id={parse_result.file_id}, 元素数={len(parse_result.elements)}")
        
        sections: List[SectionInfo] = []
        chunks: List[ChunkInfo] = []
        current_section_id: Optional[str] = None
        
        # ===== 文本累积 buffer 状态 =====
        text_buffer: List[str] = []
        buffer_element_ids: List[str] = []
        buffer_page_index: Optional[int] = None
        
        # ===== 遍历所有元素 =====
        for element in parse_result.elements:
            # 处理 Section（标题）—— 先 flush buffer，再创建 Section
            if element.is_text() and element.text_level and element.text_level > 0:
                chunks.extend(self._flush_text_buffer(
                    text_buffer, buffer_element_ids, buffer_page_index,
                    current_section_id, document_id, parse_result.document_language
                ))
                text_buffer.clear()
                buffer_element_ids.clear()
                buffer_page_index = None
                
                section = self.element_processor.create_section_from_element(
                    element=element,
                    document_id=document_id
                )
                sections.append(section)
                current_section_id = section.section_id
                logger.debug(f"创建Section: level={section.level}, content={section.content[:50]}...")
            
            # 处理普通文本 —— 清洗后追加到 buffer
            elif element.is_text() and element.text:
                text = element.text
                if self.config.enable_text_clean:
                    text = self.text_cleaner.clean_all(text)
                
                if not text:
                    continue
                
                text_buffer.append(text)
                buffer_element_ids.append(element.element_id)
                if buffer_page_index is None:
                    buffer_page_index = element.page_index
            
            # 处理图片 —— 先 flush buffer，再创建 Image Chunk
            elif element.is_image():
                chunks.extend(self._flush_text_buffer(
                    text_buffer, buffer_element_ids, buffer_page_index,
                    current_section_id, document_id, parse_result.document_language
                ))
                text_buffer.clear()
                buffer_element_ids.clear()
                buffer_page_index = None
                
                image_chunk = self.element_processor.create_image_chunk(
                    element=element,
                    section_id=current_section_id,
                    document_id=document_id
                )
                chunks.append(image_chunk)
                
                logger.debug(f"创建图片Chunk: image_file_name={element.image_file_name}")
            
            # 处理表格 —— 先 flush buffer，再处理表格
            elif element.is_table():
                chunks.extend(self._flush_text_buffer(
                    text_buffer, buffer_element_ids, buffer_page_index,
                    current_section_id, document_id, parse_result.document_language
                ))
                text_buffer.clear()
                buffer_element_ids.clear()
                buffer_page_index = None
                
                table_texts = self.table_splitter.assemble_and_split_table(
                    table_body=element.table_body or "",
                    table_caption=element.table_caption,
                    table_footnote=element.table_footnote,
                    chunk_size=4000
                )
                
                table_chunks = self.element_processor.create_table_chunks(
                    element=element,
                    section_id=current_section_id,
                    assembled_table_texts=table_texts,
                    document_id=document_id,
                    language=parse_result.document_language
                )
                chunks.extend(table_chunks)
                
                logger.debug(f"切分表格: 切分后={len(table_chunks)}个chunk")
        
        # ===== 循环结束，flush 剩余 buffer =====
        chunks.extend(self._flush_text_buffer(
            text_buffer, buffer_element_ids, buffer_page_index,
            current_section_id, document_id, parse_result.document_language
        ))
        
        # 更新 Section 的 chunk_id_list
        for section in sections:
            section.chunk_id_list = [
                chunk.chunk_id
                for chunk in chunks
                if chunk.section_id == section.section_id
            ]
        
        # 填充 enhanced_vector_text（Section标题 + Chunk文本 → enhanced_chunk_store）
        section_content_map = {s.section_id: s.content for s in sections}
        enhanced_count = 0
        for chunk in chunks:
            if not chunk.section_id or chunk.section_id not in section_content_map:
                continue
            chunk_text = chunk.get_text_content()
            if not chunk_text:
                continue
            section_title = section_content_map[chunk.section_id]
            chunk.enhanced_vector_text = f"{section_title}\n{chunk_text}"
            enhanced_count += 1
        
        if enhanced_count > 0:
            logger.debug(f"填充 enhanced_vector_text: {enhanced_count}/{len(chunks)} 个Chunk")
        
        # 计算总字符数
        total_chars = sum(
            len(chunk.get_text_content() or "")
            for chunk in chunks
            if chunk.is_text() or chunk.is_table()
        )
        
        # 构建 SplitResult
        split_result = SplitResult(
            user_id=parse_result.user_id,
            file_id=parse_result.file_id,
            filename=parse_result.filename,
            status=SplitStatus.SUCCESS,
            sections=sections,
            chunks=chunks,
            split_method=self.config.split_method,
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            total_sections=len(sections),
            total_chunks=len(chunks),
            total_chars=total_chars,
            document_language=parse_result.document_language,
            knowledge_base_id=parse_result.knowledge_base_id,
            knowledge_base_name=parse_result.knowledge_base_name
        )
        
        logger.info(
            f"文档切分完成: sections={len(sections)}, chunks={len(chunks)}, "
            f"text={len(split_result.text_chunks)}, image={len(split_result.image_chunks)}, "
            f"table={len(split_result.table_chunks)}"
        )
        
        return split_result
