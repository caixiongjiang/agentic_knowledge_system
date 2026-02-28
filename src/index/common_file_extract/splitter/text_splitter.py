#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
文本切分器

提供多种文本切分算法，支持结构优先、递归、语义等多种切分方式。
"""

import re
from typing import List, Optional
from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
    SentenceTransformersTokenTextSplitter
)
from langchain_core.documents import Document

from src.index.common_file_extract.splitter.models import SplitConfig, SplitMethod


class TextSplitter:
    """
    文本切分器
    
    支持多种切分方法：
    - structure_first: 两阶段结构切分（推荐）
    - recursive: 递归切分
    - regular: 常规切分
    - semantic: 语义切分
    - token: Token切分
    """
    
    def __init__(self, config: Optional[SplitConfig] = None):
        """
        初始化文本切分器
        
        Args:
            config: 切分配置
        """
        self.config = config or SplitConfig()
    
    def split_text(self, text: str) -> List[str]:
        """
        根据配置的方法切分文本
        
        Args:
            text: 待切分的文本
        
        Returns:
            切分后的文本列表
        """
        if not text:
            return []
        
        method = self.config.split_method
        
        if method == SplitMethod.STRUCTURE_FIRST:
            return self.split_text_structure_first(
                text,
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap
            )
        elif method == SplitMethod.RECURSIVE:
            return self.split_text_recursive(
                text,
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                separators=self.config.separators
            )
        elif method == SplitMethod.REGULAR:
            return self.split_text_regular(
                text,
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap
            )
        elif method == SplitMethod.SEMANTIC:
            return self.split_text_semantic(
                text,
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                model_name=self.config.model_name
            )
        elif method == SplitMethod.TOKEN:
            return self.split_text_token(
                text,
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                encoding_name=self.config.encoding_name
            )
        else:
            raise ValueError(f"不支持的切分方法: {method}")
    
    def split_text_structure_first(
        self,
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[str]:
        """
        两阶段结构切分（推荐）⭐
        
        特点：
        - 第一阶段：按段落边界（\\n\\n）拆分
        - 第二阶段：根据段落大小决定合并或再切分
        - 优先保证段落完整性
        - 超大段落递归切分时使用 overlap 保持上下文连贯
        
        Args:
            text: 待切分的文本
            chunk_size: 目标chunk大小
            chunk_overlap: chunk重叠大小（建议为 chunk_size 的 10%-20%）
        
        Returns:
            切分后的文本列表
        """
        # 1. 定义微观切分器（只用于处理超大段落）
        sub_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self.config.separators,
            length_function=len
        )
        
        # 2. 宏观拆分：按两个或以上换行符拆分段落
        paragraphs = re.split(r'\n{2,}', text)
        
        final_chunks = []
        current_buffer = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 情况 A: 超大段落（超过 chunk_size）
            if len(para) > chunk_size:
                # 先提交当前 buffer
                if current_buffer:
                    final_chunks.append(current_buffer)
                    current_buffer = ""
                
                # 使用递归切分器切碎超大段落
                sub_docs = sub_splitter.split_text(para)
                final_chunks.extend(sub_docs)
            
            # 情况 B: 普通段落（小于等于 chunk_size）
            else:
                # 判断是否可以合并到 buffer
                if current_buffer and (len(current_buffer) + len(para) + 2 <= chunk_size):
                    # 可以合并
                    current_buffer += "\n\n" + para
                else:
                    # 不能合并，提交 buffer，段落成为新 buffer
                    if current_buffer:
                        final_chunks.append(current_buffer)
                    current_buffer = para
        
        # 提交最后剩余的 buffer
        if current_buffer:
            final_chunks.append(current_buffer)
        
        return final_chunks
    
    def split_text_recursive(
        self,
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None
    ) -> List[str]:
        """
        递归切分
        
        特点：
        - 多级分隔符递归切分
        - 优先保持段落完整性
        
        Args:
            text: 待切分的文本
            chunk_size: 目标chunk大小
            chunk_overlap: chunk重叠大小
            separators: 分隔符列表（优先级从高到低）
        
        Returns:
            切分后的文本列表
        """
        if separators is None:
            separators = ["\n\n", "\n", " ", ""]
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len
        )
        
        docs = splitter.create_documents([text])
        return [doc.page_content for doc in docs]
    
    def split_text_regular(
        self,
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separator: str = "\n"
    ) -> List[str]:
        """
        常规切分
        
        特点：
        - 固定分隔符切分
        - 适用于格式规整的文档
        
        Args:
            text: 待切分的文本
            chunk_size: 目标chunk大小
            chunk_overlap: chunk重叠大小
            separator: 分隔符
        
        Returns:
            切分后的文本列表
        """
        splitter = CharacterTextSplitter(
            separator=separator,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )
        
        docs = splitter.create_documents([text])
        return [doc.page_content for doc in docs]
    
    def split_text_semantic(
        self,
        text: str,
        chunk_size: int = 100,
        chunk_overlap: int = 20,
        model_name: str = "all-MiniLM-L6-v2"
    ) -> List[str]:
        """
        语义切分
        
        特点：
        - 基于语义嵌入的切分
        - 保持语义上相关的内容在一起
        - chunk_size 单位是 token 数，不是字符数
        
        Args:
            text: 待切分的文本
            chunk_size: 每个块的最大token数
            chunk_overlap: 块之间的重叠token数
            model_name: 使用的嵌入模型名称
        
        Returns:
            切分后的文本列表
        """
        splitter = SentenceTransformersTokenTextSplitter(
            model_name=model_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        docs = splitter.create_documents([text])
        return [doc.page_content for doc in docs]
    
    def split_text_token(
        self,
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base"
    ) -> List[str]:
        """
        基于token的切分
        
        特点：
        - 适用于针对特定模型的token限制
        - chunk_size 单位是 token 数
        
        Args:
            text: 待切分的文本
            chunk_size: 每个块的最大token数
            chunk_overlap: 块之间的重叠token数
            encoding_name: 使用的编码名称（如 cl100k_base for GPT-4）
        
        Returns:
            切分后的文本列表
        """
        splitter = TokenTextSplitter(
            encoding_name=encoding_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        docs = splitter.create_documents([text])
        return [doc.page_content for doc in docs]
