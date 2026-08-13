#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : ppt_parser.py
@Author  : caixiongjiang
@Date    : 2025/12/31 14:30
@Function:
    PowerPoint 文件解析器 - 转 PDF 后复用 MinerU 解析链路

    策略：PPT → LibreOffice headless 转 PDF → PDFParser(MinerU) 解析。
    这样 PPT 获得与 PDF 一致的真实像素 bbox，溯源能力与 PDF 完全一致，
    无需自行处理 EMU 坐标归一化、shape 类型识别等复杂逻辑。

    跨平台：soffice 路径通过 config 注入（macOS / Linux 不同路径）。
    共用转换链路见 OfficeToPdfParser。
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from src.client.mineru import Mineru2Client
from src.index.common_file_extract.parser.base_parser import OfficeToPdfParser


class PPTParser(OfficeToPdfParser):
    """
    PowerPoint 解析器

    功能：
    - 通过 LibreOffice headless 将 PPT/PPTX 转换为 PDF
    - 复用 PDFParser + Mineru2Client 解析转换后的 PDF
    - 输出结构与 PDF 解析完全一致（真实像素 bbox）

    职责：
    - 仅负责单文件解析
    - 转换产物为临时文件，解析后自动清理

    注意：
    - 运行环境需安装 LibreOffice（macOS: brew install --cask libreoffice；
      Ubuntu/Docker: apt-get install -y libreoffice）
    - soffice 路径通过构造参数注入，默认 "soffice"（Linux PATH 中可用时）
    - 提交 MinerU 时文件名强制改为 .pdf（OfficeToPdfParser），避免 content_list 为空
    - 转换 PDF 上传 MinIO 路径与原生 PDF 一致：{user}/{session}/{folder}/{file_id}.pdf
    """

    def __init__(
        self,
        mineru_client: Mineru2Client,
        max_pages_per_request: int = 4,
        max_concurrent_requests: int = 5,
        soffice_path: str = "soffice",
        convert_timeout: int = 120,
    ):
        """
        初始化 PPT 解析器

        :param mineru_client: Mineru2Client 客户端实例（用于解析转换后的 PDF）
        :param max_pages_per_request: 单次 MinerU 请求最大页数
        :param max_concurrent_requests: MinerU 最大并发请求数
        :param soffice_path: LibreOffice soffice 可执行文件路径
            - macOS: /Applications/LibreOffice.app/Contents/MacOS/soffice
            - Linux: soffice（PATH 中）或 /usr/bin/soffice
        :param convert_timeout: LibreOffice 转换超时时间（秒）
        """
        super().__init__(
            mineru_client=mineru_client,
            source_file_type="ppt",
            display_name="PPT",
            max_pages_per_request=max_pages_per_request,
            max_concurrent_requests=max_concurrent_requests,
            soffice_path=soffice_path,
            convert_timeout=convert_timeout,
        )
