#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : pdf_parser.py
@Author  : caixiongjiang
@Date    : 2025/12/31 14:29
@Function: 
    PDF 文件解析器 - 使用 MinerU 服务解析 PDF
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Dict, Optional, Union, List
from pathlib import Path
import asyncio

from loguru import logger
from pypdf import PdfReader

from src.client.mineru import Mineru2Client


class PDFParser:
    """
    PDF 解析器
    
    功能：
    - 自动检测 PDF 页数
    - 调用 Mineru2Client 进行解析
    - 支持自动分页解析（超过阈值则并发分页请求）
    - 返回统一的解析结果格式
    
    职责：
    - 仅负责单文件解析
    - 批量文件处理由上层线程调度器负责（一个线程处理一个文件）
    - 实现分页策略：超过阈值自动分页并发请求
    
    注意：Mineru2Client 已支持分页参数（start_page_id, end_page_id）
    """
    
    def __init__(
        self, 
        mineru_client: Mineru2Client,
        max_pages_per_request: int = 4,
        max_concurrent_requests: int = 5
    ):
        """
        初始化 PDF 解析器
        
        :param mineru_client: Mineru2Client 客户端实例
        :param max_pages_per_request: 单次请求最大页数（超过则分页）
        :param max_concurrent_requests: 最大并发请求数
        """
        self.mineru_client = mineru_client
        self.max_pages_per_request = max_pages_per_request
        self.max_concurrent_requests = max_concurrent_requests
        self.logger = logger
    
    def get_pdf_pages(self, file_path: Union[str, Path]) -> int:
        """
        获取 PDF 文件的总页数
        
        :param file_path: PDF 文件路径
        :return: 总页数
        :raises Exception: 读取失败时抛出异常
        """
        try:
            reader = PdfReader(str(file_path))
            return len(reader.pages)
        except Exception as e:
            raise Exception(f"获取 PDF 页数失败: {e}")
    
    def read_file_bytes(self, file_path: Union[str, Path]) -> bytes:
        """
        读取文件字节内容
        
        :param file_path: 文件路径
        :return: 文件字节内容
        :raises Exception: 读取失败时抛出异常
        """
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"读取文件失败: {e}")
    
    async def parse(
        self, 
        file_path: Union[str, Path],
        file_name: Optional[str] = None
    ) -> Dict:
        """
        解析 PDF 文件
        
        自动分页策略：
        - 文件页数 <= max_pages_per_request：一次性解析
        - 文件页数 > max_pages_per_request：分页并发解析
        
        :param file_path: PDF 文件路径
        :param file_name: 文件名（可选，不传则从路径提取）
        :return: 解析结果字典
        
        返回格式：
        {
            "status": "success",
            "struct_content": {
                "root": [
                    {
                        "page_idx": 0,
                        "page_size": {"width": 595, "height": 842},
                        "page_info": [
                            {
                                "id": "uuid",
                                "type": "text/image/table",
                                "bbox": [x0, y0, x1, y1],
                                "element_index": 0,
                                ...
                            }
                        ]
                    }
                ]
            },
            "content": "markdown 内容",
            "total_pages": 10
        }
        
        :raises Exception: 解析失败时抛出异常
        """
        file_path = Path(file_path)
        
        # 提取文件名
        if file_name is None:
            file_name = file_path.name
        
        self.logger.info(f"📄 开始解析 PDF: {file_name}")
        
        try:
            # 1. 读取文件字节
            file_bytes = self.read_file_bytes(file_path)
            self.logger.debug(f"✅ 文件读取成功: {len(file_bytes)} 字节")
            
            # 2. 获取总页数
            total_pages = self.get_pdf_pages(file_path)
            self.logger.info(f"📖 PDF 总页数: {total_pages}")
            
            # 3. 判断是否需要分页
            if total_pages <= self.max_pages_per_request:
                # 小文件：一次性解析
                self.logger.info(f"📝 使用单次请求（<={self.max_pages_per_request}页）")
                result = await self._parse_full_file(file_bytes, file_name)
            else:
                # 大文件：分页并发解析
                self.logger.info(
                    f"📝 使用分页并发请求（每批{self.max_pages_per_request}页，"
                    f"最大并发{self.max_concurrent_requests}个）"
                )
                result = await self._parse_with_pagination(
                    file_bytes, 
                    file_name, 
                    total_pages
                )
            
            # 4. 统一字段名：将 MinerU 返回的 "pages" 转换为 "total_pages"
            if "pages" in result and "total_pages" not in result:
                result["total_pages"] = result.pop("pages")
            
            self.logger.info(f"✅ PDF 解析完成: {file_name}, {result.get('total_pages', 0)} 页")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ PDF 解析失败: {file_name}, 错误: {e}")
            raise Exception(f"PDF 解析失败: {e}")
    
    async def _parse_full_file(
        self, 
        file_bytes: bytes, 
        file_name: str
    ) -> Dict:
        """
        一次性解析整个文件
        
        :param file_bytes: 文件字节内容
        :param file_name: 文件名
        :return: 解析结果
        """
        # Mineru2Client.parse_file 是同步方法，需要在 executor 中运行
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.mineru_client.parse_file(
                file_bytes=file_bytes,
                file_name=file_name,
                start_page_id=None,
                end_page_id=None
            )
        )
        return result
    
    async def _parse_with_pagination(
        self, 
        file_bytes: bytes, 
        file_name: str, 
        total_pages: int
    ) -> Dict:
        """
        分页并发解析文件
        
        :param file_bytes: 文件字节内容
        :param file_name: 文件名
        :param total_pages: 总页数
        :return: 合并后的解析结果
        """
        # 1. 创建页面范围列表
        page_ranges = []
        for start_page in range(0, total_pages, self.max_pages_per_request):
            end_page = min(start_page + self.max_pages_per_request - 1, total_pages - 1)
            page_ranges.append((start_page, end_page))
        
        self.logger.info(f"📋 分页方案: {len(page_ranges)} 个批次")
        for idx, (start, end) in enumerate(page_ranges, 1):
            self.logger.debug(f"   批次{idx}: 页码 {start}-{end}")
        
        # 2. 创建信号量控制并发数
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        async def process_page_range(start_page: int, end_page: int, batch_index: int):
            """处理单个页面范围"""
            async with semaphore:
                self.logger.debug(f"🔄 开始处理批次{batch_index}: 页码 {start_page}-{end_page}")
                
                # Mineru2Client.parse_file 是同步方法，需要在 executor 中运行
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.mineru_client.parse_file(
                        file_bytes=file_bytes,
                        file_name=file_name,
                        start_page_id=start_page,
                        end_page_id=end_page
                    )
                )
                
                self.logger.debug(f"✅ 批次{batch_index}完成")
                return batch_index, result
        
        # 3. 并发执行所有批次
        tasks = [
            process_page_range(start, end, idx)
            for idx, (start, end) in enumerate(page_ranges, 1)
        ]
        
        self.logger.info(f"🚀 开始并发处理（最大并发数: {self.max_concurrent_requests}）")
        results_with_index = await asyncio.gather(*tasks)
        
        # 4. 按批次索引排序
        sorted_results = [result for _, result in sorted(results_with_index, key=lambda x: x[0])]
        
        # 5. 合并结果
        self.logger.info(f"🔗 合并 {len(sorted_results)} 个批次的结果")
        merged_result = self._merge_results(sorted_results, page_ranges)
        
        return merged_result
    
    def _merge_results(
        self, 
        results: List[Dict], 
        page_ranges: List[tuple]
    ) -> Dict:
        """
        合并多个分页解析结果，修正每个批次中的 page_idx 为原文档的绝对页码
        
        MinerU 对每个分页批次返回的 page_idx 是相对于该批次的（从 0 开始），
        合并时需要根据 page_ranges 中的 start_page 偏移量进行修正。
        
        :param results: 解析结果列表（已按批次顺序排列）
        :param page_ranges: 每个批次对应的页面范围列表 [(start_page, end_page), ...]
        :return: 合并后的结果
        """
        if not results:
            return {}
        
        if len(results) == 1:
            self._fix_page_indices(results[0], page_ranges[0][0])
            return results[0]
        
        merged = {
            "status": "success",
            "struct_content": {"root": []},
            "content": "",
            "total_pages": 0
        }
        
        for result, (start_page, _) in zip(results, page_ranges):
            root_pages = result.get("struct_content", {}).get("root", [])
            for page in root_pages:
                batch_page_idx = page.get("page_idx", 0)
                actual_page_idx = start_page + batch_page_idx
                page["page_idx"] = actual_page_idx
                for element in page.get("page_info", []):
                    if "page_idx" in element:
                        element["page_idx"] = actual_page_idx
            merged["struct_content"]["root"].extend(root_pages)
        
        md_contents = [r.get("content", "") for r in results]
        merged["content"] = "\n\n".join(filter(None, md_contents))
        
        merged["total_pages"] = len(merged["struct_content"]["root"])
        
        return merged
    
    def _fix_page_indices(self, result: Dict, start_page: int) -> None:
        """
        修正单个解析结果中的 page_idx，将批次内相对索引转为原文档绝对页码
        
        :param result: 解析结果
        :param start_page: 该批次在原文档中的起始页码
        """
        if start_page == 0:
            return
        
        root_pages = result.get("struct_content", {}).get("root", [])
        for page in root_pages:
            batch_page_idx = page.get("page_idx", 0)
            actual_page_idx = start_page + batch_page_idx
            page["page_idx"] = actual_page_idx
            for element in page.get("page_info", []):
                if "page_idx" in element:
                    element["page_idx"] = actual_page_idx