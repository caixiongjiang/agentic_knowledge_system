#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
文本清洗工具

提供文本清洗和规范化功能。
"""

import re


class TextCleaner:
    """
    文本清洗工具类
    
    提供多种文本清洗方法，用于在切分前对文本进行预处理。
    """
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        基础文本清洗（保留段落结构）
        
        只做行内水平空白归一化，不破坏换行符和段落边界（\\n\\n）。
        控制字符的移除由 clean_special_chars() 负责。
        
        Args:
            text: 原始文本
        
        Returns:
            清洗后的文本
        """
        if not text:
            return ""
        
        # 行内多余水平空白 → 单空格（不影响换行符 \n）
        # [^\S\n]+ 匹配"非(\n 或 非空白字符)"= 水平空白字符（空格、制表符等）
        text = re.sub(r'[^\S\n]+', ' ', text)
        
        # 移除重复的标点符号
        text = re.sub(r'([!?,.:;])\1+', r'\1', text)
        
        # 规范化段落边界：3个以上连续换行 → 2个换行（保留段落间隔）
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    @staticmethod
    def clean_special_chars(text: str) -> str:
        """
        清理特殊字符
        
        Args:
            text: 原始文本
        
        Returns:
            清洗后的文本
        """
        if not text:
            return ""
        
        # 移除不可见的控制字符和零宽度字符
        text = re.sub(
            r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F\u200B-\u200F\u2028-\u202F\u2060-\u206F]',
            '',
            text
        )
        
        # 规范化换行符
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)
        
        return text
    
    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """
        规范化空白字符（保留段落结构）
        
        处理每行内的多余空格，同时保留空行作为段落边界标记（\\n\\n）。
        连续多个空行会被合并为单个空行。
        
        Args:
            text: 原始文本
        
        Returns:
            规范化后的文本
        """
        if not text:
            return ""
        
        # 处理每一行：去除行首尾空格
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        
        # 合并连续空行为单个空行（保留段落边界的 \n\n）
        result_lines: list[str] = []
        prev_empty = False
        for line in lines:
            if not line:
                if not prev_empty:
                    result_lines.append('')
                    prev_empty = True
            else:
                result_lines.append(line)
                prev_empty = False
        
        # 去除首尾空行
        while result_lines and not result_lines[0]:
            result_lines.pop(0)
        while result_lines and not result_lines[-1]:
            result_lines.pop()
        
        return '\n'.join(result_lines)
    
    @staticmethod
    def remove_extra_newlines(text: str, max_consecutive: int = 2) -> str:
        """
        移除多余的换行符
        
        Args:
            text: 原始文本
            max_consecutive: 最多允许连续的换行符数量
        
        Returns:
            处理后的文本
        """
        if not text:
            return ""
        
        # 将超过 max_consecutive 的连续换行符替换为 max_consecutive 个
        pattern = r'\n{' + str(max_consecutive + 1) + r',}'
        replacement = '\n' * max_consecutive
        
        return re.sub(pattern, replacement, text)
    
    @staticmethod
    def clean_all(
        text: str,
        remove_control_chars: bool = True,
        normalize_ws: bool = True,
        remove_extra_newlines: bool = True
    ) -> str:
        """
        执行所有清洗操作（保留段落结构）
        
        处理流水线（顺序不可随意调整）：
        1. clean_special_chars: 规范化换行符（\\r\\n→\\n），移除零宽/不可见字符
        2. clean_text: 行内水平空白归一化，移除重复标点，段落边界规范化
        3. normalize_whitespace: 逐行修剪空格，合并连续空行为单个空行
        4. remove_extra_newlines: 限制最大连续换行数
        
        Args:
            text: 原始文本
            remove_control_chars: 是否移除控制字符
            normalize_ws: 是否规范化空白字符
            remove_extra_newlines: 是否移除多余换行符
        
        Returns:
            清洗后的文本
        """
        if not text:
            return ""
        
        # 1. 先规范化换行符和清理不可见字符（为后续步骤提供干净的输入）
        if remove_control_chars:
            text = TextCleaner.clean_special_chars(text)
        
        # 2. 基础清洗（保留段落结构）
        text = TextCleaner.clean_text(text)
        
        # 3. 规范化空白字符（保留段落边界）
        if normalize_ws:
            text = TextCleaner.normalize_whitespace(text)
        
        # 4. 限制连续换行符数量
        if remove_extra_newlines:
            text = TextCleaner.remove_extra_newlines(text)
        
        return text
