#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
表格切分器

提供表格组装和智能切分功能。
"""

import re
from typing import List, Optional


class TableSplitter:
    """
    表格切分器
    
    功能：
    - 组装表格文本（caption + body + footnote）
    - 超长表格智能切分（按行切分，保留完整标题和脚注）
    """
    
    @staticmethod
    def assemble_table(
        table_body: str,
        table_caption: Optional[str] = None,
        table_footnote: Optional[str] = None
    ) -> str:
        """
        组装表格文本
        
        Args:
            table_body: 表格主体内容
            table_caption: 表格标题
            table_footnote: 表格脚注
        
        Returns:
            组装后的表格文本
        """
        parts = []
        
        # 添加标题
        if table_caption:
            parts.append(f"table_caption: {table_caption}")
        
        # 添加主体
        if table_body:
            parts.append(f"table_body: {table_body}")
        
        # 添加脚注
        if table_footnote:
            parts.append(f"table_footnote: {table_footnote}")
        
        return "\n".join(parts)
    
    @staticmethod
    def split_large_table(
        table_body: str,
        table_caption: Optional[str] = None,
        table_footnote: Optional[str] = None,
        chunk_size: int = 2000
    ) -> List[str]:
        """
        超长表格智能切分
        
        核心原则：
        1. 按行切分表格主体（table_body）
        2. 每个切片都保留完整的 caption 和 footnote
        3. 保证每个切片不超过 chunk_size
        
        Args:
            table_body: 表格主体内容
            table_caption: 表格标题
            table_footnote: 表格脚注
            chunk_size: 最大块大小
        
        Returns:
            切分后的表格文本列表，每个元素是完整的表格格式
        """
        # 1. 解析表格主体，按行分割
        table_rows = TableSplitter._parse_table_rows(table_body)
        
        if not table_rows:
            # 如果无法解析行，返回整个表格
            return [TableSplitter.assemble_table(table_body, table_caption, table_footnote)]
        
        # 2. 计算固定开销（caption + footnote + 表头）
        caption_text = table_caption or ""
        footnote_text = table_footnote or ""
        header_row = table_rows[0] if table_rows else ""
        
        fixed_overhead = len(caption_text) + len(footnote_text) + len(header_row) + 50  # 50为格式字符
        
        # 3. 计算每个切片最多能容纳多少行
        available_size = chunk_size - fixed_overhead
        if available_size <= 0:
            # chunk_size 太小，无法切分，返回整个表格
            return [TableSplitter.assemble_table(table_body, table_caption, table_footnote)]
        
        # 4. 分批切分表格行
        chunks = []
        current_batch = [header_row]  # 每个批次都包含表头
        current_size = len(header_row)
        
        for row in table_rows[1:]:  # 跳过表头
            row_size = len(row)
            
            if current_size + row_size > available_size:
                # 当前批次已满，组装成完整表格
                chunk_table = TableSplitter._assemble_table_chunk(
                    caption=caption_text,
                    rows=current_batch,
                    footnote=footnote_text
                )
                chunks.append(chunk_table)
                
                # 开启新批次
                current_batch = [header_row, row]
                current_size = len(header_row) + row_size
            else:
                current_batch.append(row)
                current_size += row_size
        
        # 5. 处理最后一批
        if len(current_batch) > 1:  # 不只有表头
            chunk_table = TableSplitter._assemble_table_chunk(
                caption=caption_text,
                rows=current_batch,
                footnote=footnote_text
            )
            chunks.append(chunk_table)
        
        return chunks if chunks else [TableSplitter.assemble_table(table_body, table_caption, table_footnote)]
    
    @staticmethod
    def _parse_table_rows(table_body: str) -> List[str]:
        """
        解析表格主体，按行分割
        
        Args:
            table_body: 表格主体内容
        
        Returns:
            表格行列表
        """
        if not table_body:
            return []
        
        # 尝试多种分割策略
        
        # 策略1: 如果是HTML表格，按 <tr> 标签分割
        if "<tr>" in table_body.lower():
            rows = re.findall(r'<tr[^>]*>.*?</tr>', table_body, re.IGNORECASE | re.DOTALL)
            if rows:
                return rows
        
        # 策略2: 如果是Markdown表格，按行分割
        if "|" in table_body:
            rows = [line.strip() for line in table_body.split('\n') if line.strip() and '|' in line]
            if rows:
                return rows
        
        # 策略3: 按换行符分割
        rows = [line.strip() for line in table_body.split('\n') if line.strip()]
        return rows
    
    @staticmethod
    def _assemble_table_chunk(
        caption: str,
        rows: List[str],
        footnote: str
    ) -> str:
        """
        组装单个表格切片
        
        格式:
        table_caption: [Caption]
        table_body: [表格内容]
        table_footnote: [Footnote]
        
        Args:
            caption: 表格标题
            rows: 表格行列表
            footnote: 表格脚注
        
        Returns:
            组装后的表格文本
        """
        parts = []
        
        # 添加标题
        if caption:
            parts.append(f"table_caption: {caption}")
        
        # 添加表格主体
        if rows:
            table_body = "\n".join(rows)
            parts.append(f"table_body: {table_body}")
        
        # 添加脚注
        if footnote:
            parts.append(f"table_footnote: {footnote}")
        
        return "\n".join(parts)
    
    @staticmethod
    def assemble_and_split_table(
        table_body: str,
        table_caption: Optional[str] = None,
        table_footnote: Optional[str] = None,
        chunk_size: int = 2000
    ) -> List[str]:
        """
        组装并根据大小决定是否切分表格
        
        Args:
            table_body: 表格主体内容
            table_caption: 表格标题
            table_footnote: 表格脚注
            chunk_size: 最大块大小
        
        Returns:
            表格文本列表（如果需要切分则返回多个，否则返回单个）
        """
        # 先组装完整表格
        full_table = TableSplitter.assemble_table(table_body, table_caption, table_footnote)
        
        # 判断是否需要切分
        if len(full_table) <= chunk_size:
            return [full_table]
        else:
            return TableSplitter.split_large_table(
                table_body,
                table_caption,
                table_footnote,
                chunk_size
            )
