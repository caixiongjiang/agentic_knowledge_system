#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
元素处理器

负责将 ParseResult 的 ElementInfo 转换为 SplitResult 的 ChunkInfo。
处理不同类型的元素（text/image/table）。
"""

from typing import List, Dict, Optional
from src.types.models.parse_result import ElementInfo, ElementType
from src.types.models.split_result import ChunkInfo, ChunkType, SectionInfo


class ElementProcessor:
    """
    元素处理器
    
    负责将解析后的元素转换为切分后的Chunk。
    """
    
    @staticmethod
    def create_section_from_element(
        element: ElementInfo,
        document_id: Optional[str] = None
    ) -> SectionInfo:
        """
        从元素创建Section
        
        Args:
            element: 原始元素（text类型，text_level > 0）
            document_id: 文档ID
        
        Returns:
            SectionInfo
        """
        return SectionInfo(
            level=element.text_level or 1,
            content=element.text or "",
            page_index=element.page_index,
            page_position=element.page_position,
            chunk_id_list=[],
            metadata={},
            document_id=document_id,  # 文档级关联
            element_id=element.element_id  # 传递 element_id 用于文档溯源
        )
    
    @staticmethod
    def create_text_chunks(
        per_chunk_element_ids: List[List[str]],
        page_index: Optional[int],
        section_id: Optional[str],
        split_texts: List[str],
        document_id: Optional[str] = None,
        language: str = "unknown"
    ) -> List[ChunkInfo]:
        """
        从切分后的文本列表创建Chunk列表

        Args:
            per_chunk_element_ids: 每个 chunk 精确关联的 Element ID 列表，
                长度与 split_texts 一致
            page_index: 页码（合并场景取首个元素的页码）
            section_id: 所属Section ID
            split_texts: 切分后的文本列表
            document_id: 文档ID
            language: 语言

        Returns:
            ChunkInfo列表
        """
        chunks = []

        for i, text in enumerate(split_texts):
            element_ids = per_chunk_element_ids[i] if i < len(per_chunk_element_ids) else []
            chunk = ChunkInfo(
                chunk_type=ChunkType.TEXT,
                section_id=section_id,
                document_id=document_id,
                content={
                    "original": {"content": text},
                    "translations": []
                },
                page_index=page_index,
                language=language,
                metadata={},
                element_ids=element_ids,
                split_seq=i,
            )
            chunks.append(chunk)

        return chunks
    
    @staticmethod
    def create_image_chunk(
        element: ElementInfo,
        section_id: Optional[str],
        document_id: Optional[str] = None,
        language: str = "unknown"
    ) -> ChunkInfo:
        """
        从图片元素创建Chunk

        注意：图片已经在 FileParser 阶段上传到对象存储

        Args:
            element: 原始图片元素
            section_id: 所属Section ID
            document_id: 文档ID
            language: 文档语言（作为 chunk 级语言初值，split 阶段后续会按
                caption/footnote 实测覆盖）

        Returns:
            ChunkInfo
        """
        return ChunkInfo(
            chunk_type=ChunkType.IMAGE,
            section_id=section_id,
            document_id=document_id,  # 文档级关联
            content={
                "original": {"content": ""},
                "translations": []
            },
            page_index=element.page_index,
            language=language,
            # 图片存储信息（从 ElementInfo 继承）
            bucket_name=element.bucket_name,
            image_file_path=element.image_file_path,
            image_file_name=element.image_file_name,
            image_file_type=element.image_file_type,
            image_file_format=element.image_file_format,
            image_file_suffix=element.image_file_suffix,
            image_caption=element.image_caption,
            image_footnote=element.image_footnote,
            metadata={},
            element_ids=[element.element_id]  # 传递 element_id 用于文档溯源
        )
    
    @staticmethod
    def create_table_chunks(
        element: ElementInfo,
        section_id: Optional[str],
        assembled_table_texts: List[str],
        document_id: Optional[str] = None,
        language: str = "unknown"
    ) -> List[ChunkInfo]:
        """
        从表格元素创建Chunk列表（可能切分成多个）
        
        Args:
            element: 原始表格元素
            section_id: 所属Section ID
            assembled_table_texts: 组装后的表格文本列表（如果超长切分）
            document_id: 文档ID
            language: 语言
        
        Returns:
            ChunkInfo列表
        """
        chunks = []
        
        for i, table_text in enumerate(assembled_table_texts):
            chunk = ChunkInfo(
                chunk_type=ChunkType.TABLE,
                section_id=section_id,
                document_id=document_id,
                content={
                    "original": {"content": table_text},
                    "translations": []
                },
                page_index=element.page_index,
                language=language,
                table_body=element.table_body,
                table_caption=element.table_caption,
                table_footnote=element.table_footnote,
                metadata={},
                element_ids=[element.element_id],
                split_seq=i,
            )
            chunks.append(chunk)
        
        return chunks
    
    @staticmethod
    def create_code_chunk(
        code_content: str,
        code_language: str,
        section_id: Optional[str],
        document_id: Optional[str] = None,
        page_index: Optional[int] = None,
        language: str = "unknown"
    ) -> ChunkInfo:
        """
        创建代码块Chunk
        
        Args:
            code_content: 代码内容
            code_language: 代码语言
            section_id: 所属Section ID
            document_id: 文档ID
            page_index: 页码
            language: 文档语言
        
        Returns:
            ChunkInfo
        """
        # 组装标准Markdown代码块格式
        code_text = f"```{code_language}\n{code_content}\n```"
        
        return ChunkInfo(
            chunk_type=ChunkType.CODE_BLOCK,
            section_id=section_id,
            document_id=document_id,  # 文档级关联
            content={
                "original": {"content": code_text},
                "translations": []
            },
            page_index=page_index,
            language=language,
            metadata={"code_language": code_language}
        )
