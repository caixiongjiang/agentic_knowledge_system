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
import requests
import time

from loguru import logger


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
                - api_url: API 基础地址，如 "http://localhost:18000"
                - timeout: 超时时间（秒），默认 600
        """
        self._mineru_config = mineru_config
        self._api_base_url = mineru_config.get("api_url")
        self._timeout = mineru_config.get("timeout", 600)
        self.logger = logger

    def parse_file(
            self,
            file_bytes: bytes,
            file_name: str,
            start_page_id: Optional[int] = None,
            end_page_id: Optional[int] = None,
            backend: str = 'pipeline',
            lang: str = 'ch',
            method: str = 'auto',
            formula_enable: bool = True,
            table_enable: bool = True,
            priority: int = 0
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
        :param backend: 处理后端，'pipeline' 或 'magic-pdf'，默认 'pipeline'
        :param lang: 文档语言，'ch'（中文）或 'en'（英文），默认 'ch'
        :param method: 解析方法，'auto'、'ocr'、'txt'，默认 'auto'
        :param formula_enable: 是否启用公式识别，默认 True
        :param table_enable: 是否启用表格识别，默认 True
        :param priority: 任务优先级，0-9，数字越大优先级越高，默认 0

        :return: 解析结果（与旧版本格式兼容）

        :raises Exception: 请求失败时抛出异常

        示例：
            # 处理整个文件
            parse_file(file_bytes, "doc.pdf")

            # 处理前10页（0-9）
            parse_file(file_bytes, "doc.pdf", start_page_id=0, end_page_id=9)

            # 处理第5-10页，启用 OCR
            parse_file(file_bytes, "doc.pdf", start_page_id=5, end_page_id=10, method='ocr')

            # 从第20页到最后，禁用公式识别
            parse_file(file_bytes, "doc.pdf", start_page_id=20, formula_enable=False)
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
                end_page_id=end_page_id,
                backend=backend,
                lang=lang,
                method=method,
                formula_enable=formula_enable,
                table_enable=table_enable,
                priority=priority
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

    def parse_files(
            self,
            file_list: List[tuple],
            max_concurrent: int = 5,
            backend: str = 'pipeline',
            lang: str = 'ch',
            method: str = 'auto',
            formula_enable: bool = True,
            table_enable: bool = True,
            priority: int = 0
    ) -> List[Dict]:
        """
        批量解析多个文件（并发提交，顺序等待）

        :param file_list: 文件列表，每个元素为 (file_bytes, file_name) 元组
        :param max_concurrent: 最大并发提交数，默认5（避免服务器过载）
        :param backend: 处理后端，'pipeline' 或 'magic-pdf'，默认 'pipeline'
        :param lang: 文档语言，'ch'（中文）或 'en'（英文），默认 'ch'
        :param method: 解析方法，'auto'、'ocr'、'txt'，默认 'auto'
        :param formula_enable: 是否启用公式识别，默认 True
        :param table_enable: 是否启用表格识别，默认 True
        :param priority: 任务优先级，0-9，数字越大优先级越高，默认 0

        :return: 解析结果列表

        :raises Exception: 如果任何文件解析失败
        """
        self.logger.info(f"📦 开始批量解析 {len(file_list)} 个文件")
        self.logger.info(f"⚙️  最大并发提交数: {max_concurrent}")

        results = []
        task_ids = []

        # 第一阶段：批量提交任务（控制并发数）
        self.logger.info(f"\n{'=' * 60}")
        self.logger.info(f"第1阶段: 批量提交任务")
        self.logger.info(f"{'=' * 60}")

        for idx in range(0, len(file_list), max_concurrent):
            batch = file_list[idx:idx + max_concurrent]
            batch_size = len(batch)

            self.logger.info(f"\n📤 提交批次 {idx // max_concurrent + 1}: {batch_size} 个文件")

            for file_bytes, file_name in batch:
                try:
                    task_id = self._submit_task(
                        file_bytes,
                        file_name,
                        backend=backend,
                        lang=lang,
                        method=method,
                        formula_enable=formula_enable,
                        table_enable=table_enable,
                        priority=priority
                    )
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
        self.logger.info(f"\n{'=' * 60}")
        self.logger.info(f"第2阶段: 等待任务完成")
        self.logger.info(f"{'=' * 60}\n")

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
        self.logger.info(f"\n{'=' * 60}")
        self.logger.info(f"📊 批量解析完成")
        self.logger.info(f"{'=' * 60}")
        self.logger.info(f"✅ 成功: {success_count}")
        self.logger.info(f"❌ 失败: {failed_count}")
        self.logger.info(f"📝 总计: {len(file_list)}")

        return results

    def _submit_task(
            self,
            file_bytes: bytes,
            file_name: str,
            start_page_id: Optional[int] = None,
            end_page_id: Optional[int] = None,
            backend: str = 'pipeline',
            lang: str = 'ch',
            method: str = 'auto',
            formula_enable: bool = True,
            table_enable: bool = True,
            priority: int = 0
    ) -> str:
        """
        提交任务到新版本 API

        :param file_bytes: 文件字节内容
        :param file_name: 文件名
        :param start_page_id: 起始页码（可选）
        :param end_page_id: 结束页码（可选）
        :param backend: 处理后端，'pipeline' 或 'magic-pdf'
        :param lang: 文档语言，'ch'（中文）或 'en'（英文）
        :param method: 解析方法，'auto'、'ocr'、'txt'
        :param formula_enable: 是否启用公式识别
        :param table_enable: 是否启用表格识别
        :param priority: 任务优先级，0-9

        :return: task_id

        :raises Exception: 提交失败时抛出异常
        """
        try:
            # 准备文件和参数
            files = {'file': (file_name, file_bytes)}
            data = {
                'backend': backend,
                'lang': lang,
                'method': method,
                'formula_enable': str(formula_enable).lower(),
                'table_enable': str(table_enable).lower(),
                'priority': str(priority)
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

                # 添加轮询间隔，避免频繁请求
                time.sleep(1)  # 每秒查询一次

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
        从 MinerU API 返回数据中提取并清洗内容

        :param full_data: MinerU API 返回的完整数据

        :return: 清洗后的数据字典
        """
        data_content = full_data.get('data', {})

        md_content = data_content.get('markdown', {}).get('content', '')

        content_list_raw = data_content.get('content_list', {}).get('content', [])
        valid_types = {'text', 'image', 'table', 'equation'}
        content_list = []
        for item in content_list_raw:
            if item.get('type') not in valid_types:
                continue
            if item.get('type') == 'text' and not item.get('text', '').strip():
                continue
            content_list.append(item)

        middle_json = data_content.get('middle_json', {}).get('content', {})
        pdf_info = middle_json.get('pdf_info', [])
        page_sizes: Dict[int, Dict] = {}
        for idx, page_info in enumerate(pdf_info):
            size = page_info.get('page_size', [0, 0])
            page_sizes[idx] = {"width": size[0], "height": size[1]}

        images_list = data_content.get('images', {}).get('list', [])
        images_dict: Dict[str, str] = {}
        for img in images_list:
            img_name = img.get('name')
            img_base64 = img.get('base64')
            if img_name and img_base64:
                images_dict[img_name] = img_base64

        return {
            "md_content": md_content,
            "content_list": content_list,
            "page_sizes": page_sizes,
            "images": images_dict
        }

    def _transform_mineru_data(self, data: Dict) -> Dict:
        """
        将清洗后的数据按 page_idx 分组，构建按页嵌套的结构化数据

        :param data: _extract_mineru_format 返回的数据
        :return: 标准化的结构化数据
        """
        content_list = data.get("content_list", [])
        md_content = data.get("md_content", "")
        images_base64 = data.get("images", {})
        page_sizes = data.get("page_sizes", {})

        pages: Dict[int, List] = {}
        for item in content_list:
            page_idx = item.get('page_idx', 0)
            if page_idx not in pages:
                pages[page_idx] = []
            pages[page_idx].append(item)

        root = []
        for page_idx in sorted(pages.keys()):
            page_items = pages[page_idx]
            page_data = {
                "page_idx": page_idx,
                "page_size": page_sizes.get(page_idx, {"width": 0, "height": 0}),
                "page_info": []
            }

            for element_index, item in enumerate(page_items):
                element = dict(item)
                element["id"] = str(uuid.uuid4())
                element["element_index"] = element_index

                if element.get("type") == "image":
                    img_path = element.get("img_path", "")
                    if img_path:
                        image_name = img_path.split("/")[-1]
                        element["image_base64"] = images_base64.get(image_name)

                page_data["page_info"].append(element)

            root.append(page_data)

        return {
            "status": "success",
            "struct_content": {"root": root},
            "content": md_content,
            "pages": len(root)
        }

    def print_config(self):
        """
        打印当前客户端的配置信息（用于debug）
        """
        import json
        print("\n" + "=" * 80)
        print("Mineru2Client 当前配置")
        print("=" * 80)
        print(json.dumps(self._mineru_config, indent=2, ensure_ascii=False))
        print("=" * 80 + "\n")