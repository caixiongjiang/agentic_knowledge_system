#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : mineru.py
@Author  : caixiongjiang
@Date    : 2025/12/29 15:42
@Function: 
    MinerU 请求客户端
@Modify History:
         
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import Dict, List, Optional
import uuid
import base64
import requests
import asyncio
import time
import copy

from loguru import logger



class MineruClient:
    """
    Mineru服务请求客户端，用于处理文档解析请求
    支持单文件请求和分页并行请求
    """
    
    def __init__(self, mineru_config: Dict):
        """
        初始化客户端
        
        """
        self._mineru_config = mineru_config
        self._endpoint = mineru_config.get("endpoint")
        self._per_request_file_pages = mineru_config.get("per_request_file_pages")
        self._concurrency = mineru_config.get("concurrency", {})
        self._retry_config = mineru_config.get("retry_config", {})
        self._params = mineru_config.get("params", {})
        self._total_pages = 0
        self.logger = logger
    
    @staticmethod
    def _to_b64(file_bytes: bytes) -> str:
        """
        将文件转换为base64编码
        
        :param file_bytes: 文件字节内容

        :return: base64编码的文件内容

        :raises Exception: 文件读取失败时抛出异常
        """
        try:
            return base64.b64encode(file_bytes).decode('utf-8')
        except Exception as e:
            raise Exception(f'Error: {e}')
    
    async def parse_file(
        self, 
        file_bytes: bytes, 
        file_name: str, 
        pages_number: Optional[int] = None
    ) -> Dict:
        """
        解析单个文件
        
        :param file_bytes: 文件字节内容
        :param file_name: 文件名
        :param pages_number: 文件的页数

        :return: 解析结果

        :raises Exception: 请求失败时抛出异常
        """
        self._params["file_name"] = file_name.lower()
        self._total_pages = pages_number

        if pages_number is None:
            # 如果未传入文件的页数，则直接使用整个文件进行请求
            result = self._send_request(file_bytes, **self._params)
            result = self._transform_mineru_data(result)
            return result
        else:
            # 如果传入了文件的页数，则使用分页请求
            total_pages = pages_number
            result = await self._parse_file_parallel(file_bytes=file_bytes, total_pages=total_pages)
            result = self._transform_mineru_data(result)
            return result
        

    def parse_files(self,):
        """
        批量解析多个文件
        """
        pass


    
    async def _parse_file_parallel(
        self, 
        file_bytes: bytes, 
        total_pages: int
    ) -> Dict:
        """
        异步并行解析文件，将文件按页码范围分块处理，然后合并结果
        
        :param file_bytes: 文件字节内容
        :param total_pages: 文件总页数
            
        :return: 合并后的解析结果
        """
        
        # 创建页面范围列表
        page_ranges = [(i, min(i + self._per_request_file_pages - 1, total_pages - 1)) 
                       for i in range(0, total_pages, self._per_request_file_pages)]
        self.logger.debug(f"文件 {self._params['file_name']} 分页请求的页码范围: {page_ranges}")

        # 设置最大并发数
        concurrency = self._concurrency
        max_concurrent = min(len(page_ranges), concurrency.get("max_concurrency", 12))
        
        # 创建信号量控制并发请求数
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_range(start_page, end_page, index):
            async with semaphore:
                result = await self._send_request_async(
                    file_bytes, 
                    **self._params,
                    start_page_id=str(start_page),
                    end_page_id=str(end_page),
                )
                return index, result
        
        # 创建任务列表，并保存原始索引
        tasks = [
            process_range(start_page, end_page, i) 
            for i, (start_page, end_page) in enumerate(page_ranges)
        ]
        
        # 等待所有任务完成
        results_with_index = await asyncio.gather(*tasks)
        
        # 按原始顺序排序结果
        sorted_results = [result for _, result in sorted(results_with_index, key=lambda x: x[0])]
        
        # 合并结果
        return self.merge_results(sorted_results)
        
    async def _send_request_async(self, file_bytes, **kwargs):
        """
        异步发送请求的包装方法，支持重试机制
        
        :param file_bytes: 文件字节内容
        :param kwargs: 其他参数
        :return: 解析结果
        """
        # 获取重试配置
        retry_config = self._retry_config
        max_retries = retry_config.get("max_retries", 3)
        retry_delay = retry_config.get("retry_delay", 1.0)
        retry_strategy = retry_config.get("retry_strategy", "fixed")
        
        # 实现重试逻辑
        attempt = 0
        last_exception = None
        
        while attempt <= max_retries:
            try:
                # 执行请求
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: self._send_request(file_bytes, **kwargs)
                )
                return result
            except Exception as e:
                attempt += 1
                last_exception = e
                
                # 如果已达到最大重试次数，则抛出最后一个异常
                if attempt > max_retries:
                    break
                
                # 根据重试策略计算延迟时间
                delay = retry_delay
                if retry_strategy == "exponential":
                    delay = retry_delay * (2 ** (attempt - 1))
                elif retry_strategy == "linear":
                    delay = retry_delay * attempt
                elif retry_strategy == "fixed":
                    delay = retry_delay
                else:
                    raise Exception(f"Invalid retry strategy: {retry_strategy}")
                
                # 等待后重试
                await asyncio.sleep(delay)
        
        # 所有重试都失败，抛出最后捕获的异常
        raise last_exception

    def _send_request(self, file_bytes: bytes, **kwargs):
        try:
            response = requests.post(self._endpoint, json={
                'file': self._to_b64(file_bytes),
                'kwargs': kwargs
            })

            if response.status_code == 200:
                output = response.json()
                return output
            else:
                raise Exception(response.text)
        except Exception as e:
            raise Exception(f'Error: {e}')

    def merge_results(self, results):
        """
        合并多个解析结果
        
        :param results: 解析结果列表

        :return: 合并后的解析结果
        """
        if not results:
            return {}
        
        # 获取第一个结果作为基础
        merged_result = results[0].copy()
        
        # 如果有md_content字段，合并
        if "md_content" in merged_result:
            md_contents = [r.get("md_content", "") for r in results]
            merged_result["md_content"] = "\n\n".join(filter(None, md_contents))
        
        # 合并layout信息
        if "layout" in merged_result:
            layout = []
            for i, r in enumerate(results):
                if "layout" in r:
                    # layout中的page_idx已经自动处理正确
                    current_layout = r.get("layout", [])
                    layout.extend(current_layout)
            
            merged_result["layout"] = layout

        # 合并content_list信息
        if "content_list" in merged_result:
            content_list = []
            for r in results:
                if "content_list" in r:
                    # content_list中的page_idx已经自动处理正确
                    current_content_list = r.get("content_list", [])
                    content_list.extend(current_content_list)
            merged_result["content_list"] = content_list
        
        # 合并info信息，按照请求的页码范围顺序合并
        if "info" in merged_result:
            info = {"pdf_info": []}
            
            last_max_page_idx = 0

            for i, r in enumerate(results):
                if "info" in r and "pdf_info" in r["info"]:
                    
                    # 获取当前结果中的pdf_info列表
                    pdf_info_list = r["info"]["pdf_info"]
                    start_idx = last_max_page_idx
                    end_idx= min(last_max_page_idx + self._per_request_file_pages, self._total_pages)
                    pages_pdf_info = pdf_info_list[start_idx: end_idx]
                    info["pdf_info"].extend(pages_pdf_info)
                    # 更新已处理的总页数
                    last_max_page_idx += self._per_request_file_pages
            merged_result["info"] = info
        else:
            # 如果没有info字段，创建一个空的
            merged_result["info"] = {"pdf_info": []}

        # 合并images信息
        if "images" in merged_result:
            images = {}
            for r in results:
                if "images" in r:
                    images.update(r["images"])
            merged_result["images"] = images
        
        return merged_result
    
    def _transform_mineru_data(self, data: Dict) -> Dict:
        """
        将Mineru返回的数据转换为标准格式
        :param data: Mineru返回的原始数据
        :return: 标准化的结构化数据
        """
        # 这里需要根据Mineru的实际返回格式进行转换

        info = data.get("info", {})
        content_list = data.get("content_list", [])
        md_content = data.get("md_content", "")
        images_base64 = data.get("images", {})

        try:
            struct_content = self.nest_content_by_level(info, content_list, images_base64)
        except Exception as e:
            raise Exception(f"Mineru数据格式转换失败: {str(e)}")

        try:
            return {
                "status": "success",
                "struct_content": struct_content,
                "content": md_content,
                "pages": len(struct_content.get("root", []))
            }
        except Exception as e:
            raise Exception(f"Mineru数据转换失败: {str(e)}")

    @staticmethod
    def nest_content_by_level(info: Dict, content_list: List, images_base64: Dict):

        nest_data = []

        pdf_info = info.get("pdf_info", [])
        total_preproc_blocks = sum([len(page_info.get("preproc_blocks", [])) for page_info in pdf_info])
        assert total_preproc_blocks == len(content_list), \
            "preproc_blocks数量与content数量不匹配, preproc_blocks数量: {}, content数量: {}".format(total_preproc_blocks, len(content_list))

        content_list_idx = 0  # 追踪content_list的索引
        for page_idx, page_info in enumerate(pdf_info):
            page_info_item = {
                "page_idx": page_idx,
                "page_size": {
                    "width": page_info["page_size"][0],
                    "height": page_info["page_size"][1]
                },
                "page_info": []
            }
            preproc_blocks = page_info.get("preproc_blocks", [])
            for block_idx, block_info in enumerate(preproc_blocks):
                content_item = content_list[content_list_idx]
                type = block_info.get("type")
                match type:
                    case "image":
                        content_item["id"] = str(uuid.uuid4())
                        content_item["bbox"] = block_info.get("bbox")
                        image_name = content_item.get("img_path").split("/")[-1]
                        content_item["image_base64"] = images_base64.get(image_name)
                    case _:
                        content_item["id"] = str(uuid.uuid4())
                        content_item["bbox"] = block_info.get("bbox")

                page_info_item["page_info"].append(content_item)
                content_list_idx += 1

            nest_data.append(page_info_item)

        for page_item in nest_data:
            for index, element in enumerate(page_item["page_info"]):
                element["element_index"] = index

        nested = {"root": nest_data}

        return nested
    
    def print_config(self):
        """
        打印当前客户端的配置信息（用于debug）
        """
        import json
        print("\n" + "="*80)
        print("MineruClient 当前配置")
        print("="*80)
        print(json.dumps(self._mineru_config, indent=2, ensure_ascii=False))
        print("="*80 + "\n")




class Mineru2Client:
    """
    Mineru服务请求客户端（新版本 - 异步任务队列模式）
    
    新版本特性：
    - 异步任务提交，立即返回 task_id
    - 轮询等待任务完成
    - 支持分页请求（可指定页码范围）
    - 支持获取完整结构化数据
    """
    
    def __init__(self, mineru_config: Dict):
        """
        初始化客户端
        
        Args:
            mineru_config: 配置字典，需包含以下字段：
                - endpoint: API 基础地址，如 "http://localhost:18000"
                - timeout: 超时时间（秒），默认 600
                - params: 任务参数，如 backend, lang, method 等
        """
        self._mineru_config = mineru_config
        self._api_base_url = mineru_config.get("endpoint")
        self._timeout = mineru_config.get("timeout", 600)
        self._params = mineru_config.get("params", {})
        self.logger = logger
    
    def parse_file(
        self, 
        file_bytes: bytes, 
        file_name: str, 
        start_page_id: Optional[int] = None,
        end_page_id: Optional[int] = None
    ) -> Dict:
        """
        解析单个文件（新版本：异步任务模式）
        
        支持分页请求：
        - 不传参数：处理整个文件
        - 传 start_page_id 和 end_page_id：处理指定页码范围
        - 只传 start_page_id：从指定页码处理到最后一页
        
        :param file_bytes: 文件字节内容
        :param file_name: 文件名
        :param start_page_id: 起始页码（从0开始），None 表示从第0页开始
        :param end_page_id: 结束页码（包含），None 表示处理到最后一页
        
        :return: 解析结果（与旧版本格式兼容）
        
        :raises Exception: 请求失败时抛出异常
        
        示例：
            # 处理整个文件
            parse_file(file_bytes, "doc.pdf")
            
            # 处理前10页（0-9）
            parse_file(file_bytes, "doc.pdf", start_page_id=0, end_page_id=9)
            
            # 处理第5-10页
            parse_file(file_bytes, "doc.pdf", start_page_id=5, end_page_id=10)
            
            # 从第20页到最后
            parse_file(file_bytes, "doc.pdf", start_page_id=20)
        """
        # 构建日志信息
        if start_page_id is not None or end_page_id is not None:
            page_range = f"{start_page_id or 0}-{end_page_id or 'end'}"
            self.logger.info(f"📤 提交文档解析任务: {file_name}，页码范围: {page_range}")
        else:
            self.logger.info(f"📤 提交文档解析任务: {file_name}（完整文件）")
        
        try:
            # 步骤1: 提交任务
            task_id = self._submit_task(
                file_bytes, 
                file_name,
                start_page_id=start_page_id,
                end_page_id=end_page_id
            )
            
            # 步骤2: 等待任务完成
            self._wait_for_completion(task_id)
            
            # 步骤3: 获取完整数据
            full_data = self._get_task_data(task_id)
            
            # 步骤4: 提取并映射为旧格式
            mineru_format_data = self._extract_mineru_format(full_data)
            
            # 步骤5: 使用现有的转换逻辑
            result = self._transform_mineru_data(mineru_format_data)
            
            self.logger.info(f"✅ 文档解析完成: {file_name}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 文档解析失败: {file_name}, 错误: {e}")
            raise

    def parse_files(self, file_list: List[tuple], max_concurrent: int = 5) -> List[Dict]:
        """
        批量解析多个文件（并发提交，顺序等待）
        
        :param file_list: 文件列表，每个元素为 (file_bytes, file_name) 元组
        :param max_concurrent: 最大并发提交数，默认5（避免服务器过载）
        
        :return: 解析结果列表
        
        :raises Exception: 如果任何文件解析失败
        """
        self.logger.info(f"📦 开始批量解析 {len(file_list)} 个文件")
        self.logger.info(f"⚙️  最大并发提交数: {max_concurrent}")
        
        results = []
        task_ids = []
        
        # 第一阶段：批量提交任务（控制并发数）
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"第1阶段: 批量提交任务")
        self.logger.info(f"{'='*60}")
        
        for idx in range(0, len(file_list), max_concurrent):
            batch = file_list[idx:idx + max_concurrent]
            batch_size = len(batch)
            
            self.logger.info(f"\n📤 提交批次 {idx//max_concurrent + 1}: {batch_size} 个文件")
            
            for file_bytes, file_name in batch:
                try:
                    task_id = self._submit_task(file_bytes, file_name)
                    task_ids.append({
                        "task_id": task_id,
                        "file_name": file_name,
                        "file_bytes": file_bytes
                    })
                except Exception as e:
                    self.logger.error(f"❌ 提交失败: {file_name}, 错误: {e}")
                    task_ids.append({
                        "task_id": None,
                        "file_name": file_name,
                        "error": str(e)
                    })
            
            # 短暂等待，避免瞬间提交过多任务
            if idx + max_concurrent < len(file_list):
                time.sleep(0.5)
        
        self.logger.info(f"\n✅ 已提交 {len([t for t in task_ids if t.get('task_id')])} 个任务")
        
        # 第二阶段：等待所有任务完成
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"第2阶段: 等待任务完成")
        self.logger.info(f"{'='*60}\n")
        
        success_count = 0
        failed_count = 0
        
        for idx, task_info in enumerate(task_ids, 1):
            file_name = task_info["file_name"]
            task_id = task_info.get("task_id")
            
            self.logger.info(f"[{idx}/{len(task_ids)}] 处理: {file_name}")
            
            if task_id is None:
                # 提交阶段就失败了
                results.append({
                    "file_name": file_name,
                    "status": "failed",
                    "error": task_info.get("error", "任务提交失败")
                })
                failed_count += 1
                continue
            
            try:
                # 等待任务完成
                self._wait_for_completion(task_id)
                
                # 获取结果
                full_data = self._get_task_data(task_id)
                mineru_format_data = self._extract_mineru_format(full_data)
                result = self._transform_mineru_data(mineru_format_data)
                
                results.append({
                    "file_name": file_name,
                    "status": "success",
                    "result": result
                })
                success_count += 1
                
            except Exception as e:
                self.logger.error(f"❌ 任务失败: {file_name}, 错误: {e}")
                results.append({
                    "file_name": file_name,
                    "status": "failed",
                    "error": str(e),
                    "task_id": task_id
                })
                failed_count += 1
        
        # 总结
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"📊 批量解析完成")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"✅ 成功: {success_count}")
        self.logger.info(f"❌ 失败: {failed_count}")
        self.logger.info(f"📝 总计: {len(file_list)}")
        
        return results

    def _submit_task(
        self, 
        file_bytes: bytes, 
        file_name: str,
        start_page_id: Optional[int] = None,
        end_page_id: Optional[int] = None
    ) -> str:
        """
        提交任务到新版本 API
        
        :param file_bytes: 文件字节内容
        :param file_name: 文件名
        :param start_page_id: 起始页码（可选）
        :param end_page_id: 结束页码（可选）
        
        :return: task_id
        
        :raises Exception: 提交失败时抛出异常
        """
        try:
            # 准备文件和参数
            files = {'file': (file_name, file_bytes)}
            data = {
                'backend': self._params.get('backend', 'pipeline'),
                'lang': self._params.get('lang', 'ch'),
                'method': self._params.get('method', 'auto'),
                'formula_enable': str(self._params.get('formula_enable', True)).lower(),
                'table_enable': str(self._params.get('table_enable', True)).lower(),
                'priority': str(self._params.get('priority', 0))
            }
            
            # 添加分页参数（如果提供）
            if start_page_id is not None:
                data['start_page_id'] = str(start_page_id)
            if end_page_id is not None:
                data['end_page_id'] = str(end_page_id)
            
            # 提交任务
            response = requests.post(
                f'{self._api_base_url}/api/v1/tasks/submit',
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                task_id = result['task_id']
                page_info = ""
                if start_page_id is not None or end_page_id is not None:
                    page_info = f"（页码: {start_page_id or 0}-{end_page_id or 'end'}）"
                self.logger.info(f"✅ 任务已提交: {task_id} {page_info}")
                return task_id
            else:
                raise Exception(f"提交任务失败: {response.text}")
                
        except Exception as e:
            raise Exception(f"提交任务错误: {e}")

    def _wait_for_completion(self, task_id: str):
        """
        等待任务完成
        
        :param task_id: 任务ID
        
        :raises Exception: 任务失败或超时时抛出异常
        """
        start_time = time.time()
        
        self.logger.info(f"⏳ 等待任务完成: {task_id}")
        
        while True:
            # 查询任务状态
            try:
                response = requests.get(
                    f'{self._api_base_url}/api/v1/tasks/{task_id}',
                    timeout=10
                )
                
                if response.status_code != 200:
                    raise Exception(f"查询任务状态失败: {response.text}")
                
                result = response.json()
                status = result.get('status')
                
                if status == 'completed':
                    self.logger.info(f"✅ 任务完成: {task_id}")
                    return
                elif status == 'failed':
                    error_msg = result.get('error_message', 'Unknown error')
                    raise Exception(f"任务失败: {error_msg}")
                elif status == 'cancelled':
                    raise Exception("任务已被取消")
                
                # 检查超时
                elapsed_time = time.time() - start_time
                if elapsed_time > self._timeout:
                    raise Exception(f"任务超时（{self._timeout}秒）")
                
            except requests.exceptions.RequestException as e:
                raise Exception(f"网络请求错误: {e}")

    def _get_task_data(self, task_id: str) -> Dict:
        """
        获取任务的完整数据
        
        :param task_id: 任务ID
        
        :return: 完整的任务数据
        
        :raises Exception: 获取数据失败时抛出异常
        """
        try:
            response = requests.get(
                f'{self._api_base_url}/api/v1/tasks/{task_id}/data',
                params={
                    'include_fields': 'md,content_list,middle_json,images',
                    'upload_images': False,
                    'include_image_base64': True,  # 获取图片的 base64
                    'include_metadata': False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'completed':
                    return result
                else:
                    raise Exception(f"任务未完成，状态: {result.get('status')}")
            else:
                raise Exception(f"获取任务数据失败: {response.text}")
                
        except Exception as e:
            raise Exception(f"获取任务数据错误: {e}")

    def _extract_mineru_format(self, full_data: Dict) -> Dict:
        """
        将新版本 API 数据提取并映射为旧版本格式
        
        这样可以复用现有的 _transform_mineru_data 方法
        
        :param full_data: 新版本 API 返回的完整数据
        
        :return: 旧版本格式的数据字典
        """
        data_content = full_data.get('data', {})
        
        # 1. 提取 markdown 内容
        md_content = data_content.get('markdown', {}).get('content', '')
        
        # 2. 提取 content_list，并过滤掉 type="discarded" 的元素
        content_list_raw = data_content.get('content_list', {}).get('content', [])
        content_list = [item for item in content_list_raw if item.get('type') != 'discarded']
        
        # 3. 从 middle_json 提取 pdf_info
        middle_json = data_content.get('middle_json', {}).get('content', {})
        pdf_info = middle_json.get('pdf_info', [])
        
        # 4. 转换图片格式：从列表转换为字典 {filename: base64}
        images_list = data_content.get('images', {}).get('list', [])
        images_dict = {}
        for img in images_list:
            img_name = img.get('name')
            img_base64 = img.get('base64')
            if img_name and img_base64:
                images_dict[img_name] = img_base64
        
        # 构建旧版本格式
        return {
            "md_content": md_content,
            "content_list": content_list,
            "info": {"pdf_info": pdf_info},
            "images": images_dict
        }

    def _transform_mineru_data(self, data: Dict) -> Dict:
        """
        将Mineru返回的数据转换为标准格式
        
        :param data: Mineru返回的原始数据
        :return: 标准化的结构化数据
        """
        info = data.get("info", {})
        content_list = data.get("content_list", [])
        md_content = data.get("md_content", "")
        images_base64 = data.get("images", {})

        try:
            struct_content = self.nest_content_by_level(info, content_list, images_base64)
        except Exception as e:
            raise Exception(f"Mineru数据格式转换失败: {str(e)}")

        try:
            return {
                "status": "success",
                "struct_content": struct_content,
                "content": md_content,
                "pages": len(struct_content.get("root", []))
            }
        except Exception as e:
            raise Exception(f"Mineru数据转换失败: {str(e)}")

    @staticmethod
    def nest_content_by_level(info: Dict, content_list: List, images_base64: Dict):
        """
        将内容按页面结构嵌套
        
        :param info: 包含 pdf_info 的信息字典
        :param content_list: 内容列表
        :param images_base64: 图片 base64 字典
        
        :return: 嵌套结构的数据
        """
        nest_data = []

        pdf_info = info.get("pdf_info", [])
        total_preproc_blocks = sum([len(page_info.get("preproc_blocks", [])) for page_info in pdf_info])
        assert total_preproc_blocks == len(content_list), \
            f"preproc_blocks数量与content数量不匹配, preproc_blocks数量: {total_preproc_blocks}, content数量: {len(content_list)}"

        content_list_idx = 0  # 追踪content_list的索引
        for page_idx, page_info in enumerate(pdf_info):
            page_info_item = {
                "page_idx": page_idx,
                "page_size": {
                    "width": page_info["page_size"][0],
                    "height": page_info["page_size"][1]
                },
                "page_info": []
            }
            preproc_blocks = page_info.get("preproc_blocks", [])
            for block_idx, block_info in enumerate(preproc_blocks):
                # 使用深拷贝避免修改原始数据
                content_item = copy.deepcopy(content_list[content_list_idx])
                type = block_info.get("type")
                match type:
                    case "image":
                        content_item["id"] = str(uuid.uuid4())
                        content_item["bbox"] = block_info.get("bbox")
                        # 从 content_item 中获取图片路径
                        img_path = content_item.get("img_path", "")
                        if img_path:
                            image_name = img_path.split("/")[-1]
                            content_item["image_base64"] = images_base64.get(image_name)
                    case _:
                        content_item["id"] = str(uuid.uuid4())
                        content_item["bbox"] = block_info.get("bbox")

                page_info_item["page_info"].append(content_item)
                content_list_idx += 1

            nest_data.append(page_info_item)

        for page_item in nest_data:
            for index, element in enumerate(page_item["page_info"]):
                element["element_index"] = index

        nested = {"root": nest_data}

        return nested
    
    def print_config(self):
        """
        打印当前客户端的配置信息（用于debug）
        """
        import json
        print("\n" + "="*80)
        print("Mineru2Client 当前配置")
        print("="*80)
        print(json.dumps(self._mineru_config, indent=2, ensure_ascii=False))
        print("="*80 + "\n")