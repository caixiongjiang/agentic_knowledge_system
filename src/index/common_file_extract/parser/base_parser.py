#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : base_parser.py
@Author  : caixiongjiang
@Date    : 2026/07/30
@Function:
    通用文档解析器基类。

    - BaseParser：统一 parse 接口 + MinerU schema 构造辅助方法
    - OfficeToPdfParser：Word/PPT 等 Office 文档共用的
      「LibreOffice 转 PDF → PDFParser(MinerU)」链路
@Modify History:

@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import asyncio
import shutil
import tempfile
import uuid

from loguru import logger

from src.client.mineru import Mineru2Client


class BaseParser(ABC):
    """
    通用文档解析器基类。

    所有格式解析器继承此类，统一输出 MinerU schema 形状的 Dict，
    使下游 FileSplitterService / ElementInfo / DB 写入链路零改动。

    说明：
    - parse 采用实例方法，便于 PDF/Office 解析器注入 Mineru2Client 等依赖
    - _build_element / _build_page / _wrap_result 供 TXT/Markdown/Excel 等
      自建结构的解析器复用
    """

    @abstractmethod
    async def parse(
        self,
        file_path: Union[str, Path],
        file_name: Optional[str] = None,
    ) -> Dict:
        """解析文档，返回 MinerU schema 形状的 Dict。"""
        ...

    @staticmethod
    def _build_element(
        element_type: str,
        page_idx: int,
        element_index: int,
        bbox: Optional[List[float]] = None,
        **kwargs: Any,
    ) -> Dict:
        """构造单个元素，自动填充 id / page_idx / element_index / bbox。"""
        return {
            "id": str(uuid.uuid4()),
            "type": element_type,
            "page_idx": page_idx,
            "element_index": element_index,
            "bbox": bbox or [0, 0, 0, 0],
            **kwargs,
        }

    @staticmethod
    def _build_page(
        page_idx: int,
        page_info: List[Dict],
        page_size: Optional[Dict[str, float]] = None,
    ) -> Dict:
        """构造单页结构。"""
        return {
            "page_idx": page_idx,
            "page_size": page_size or {"width": 0, "height": 0},
            "page_info": page_info,
        }

    @staticmethod
    def _wrap_result(
        root: List[Dict],
        content: str = "",
        total_pages: Optional[int] = None,
    ) -> Dict:
        """包装最终返回结构。"""
        return {
            "status": "success",
            "total_pages": total_pages if total_pages is not None else len(root),
            "struct_content": {"root": root},
            "content": content,
        }


class OfficeToPdfParser(BaseParser):
    """
    Office 文档 → LibreOffice headless 转 PDF → MinerU 解析的共用基类。

    Word / PPT 等格式复用此链路，获得与 PDF 一致的真实像素 bbox。
    子类通过 source_file_type / display_name 区分原始格式与日志文案。
    """

    def __init__(
        self,
        mineru_client: Mineru2Client,
        source_file_type: str,
        display_name: Optional[str] = None,
        max_pages_per_request: int = 4,
        max_concurrent_requests: int = 5,
        soffice_path: str = "soffice",
        convert_timeout: int = 120,
    ):
        """
        初始化 Office → PDF 解析器

        :param mineru_client: Mineru2Client 客户端实例（用于解析转换后的 PDF）
        :param source_file_type: 原始文件类型标记（如 "ppt" / "word"）
        :param display_name: 日志展示名（如 "PPT" / "Word"），默认取 source_file_type 大写
        :param max_pages_per_request: 单次 MinerU 请求最大页数
        :param max_concurrent_requests: MinerU 最大并发请求数
        :param soffice_path: LibreOffice soffice 可执行文件路径
            - macOS: /Applications/LibreOffice.app/Contents/MacOS/soffice
            - Linux: soffice（PATH 中）或 /usr/bin/soffice
        :param convert_timeout: LibreOffice 转换超时时间（秒）
        """
        self.mineru_client = mineru_client
        self.source_file_type = source_file_type
        self.display_name = display_name or source_file_type.upper()
        self.max_pages_per_request = max_pages_per_request
        self.max_concurrent_requests = max_concurrent_requests
        self.soffice_path = soffice_path
        self.convert_timeout = convert_timeout
        self.logger = logger

    async def parse(
        self,
        file_path: Union[str, Path],
        file_name: Optional[str] = None,
    ) -> Dict:
        """
        解析 Office 文档

        流程：
        1. LibreOffice headless 转换为 PDF（临时文件）
        2. 复用 PDFParser + MinerU 解析转换后的 PDF
        3. 标记原始 file_type
        4. 将转换 PDF 临时路径交给上层持久化（失败时本层清理）

        成功时结果额外包含：
        - converted_pdf_temp_path: 转换后 PDF 本地临时路径
          （由 FileParserService 上传 MinIO 后负责清理）
        """
        # 延迟导入，避免 base_parser ↔ pdf_parser 循环依赖
        from src.index.common_file_extract.parser.pdf_parser import PDFParser

        file_path = Path(file_path)

        if file_name is None:
            file_name = file_path.name

        label = self.display_name
        self.logger.info(f"🖥️ 开始解析 {label}: {file_name}")

        pdf_path: Optional[Path] = None
        try:
            self.logger.debug(
                f"🔄 调用 LibreOffice 转换 {label} → PDF: {file_name}"
            )
            pdf_path = await self._convert_to_pdf(file_path)
            self.logger.debug(f"✅ PDF 转换完成: {pdf_path}")

            pdf_parser = PDFParser(
                mineru_client=self.mineru_client,
                max_pages_per_request=self.max_pages_per_request,
                max_concurrent_requests=self.max_concurrent_requests,
            )
            # MinerU 按扩展名选择解析器：必须传 .pdf。
            # 若仍传原始 .doc/.docx/.ppt，会得到 markdown 但 content_list 为空 → 0 页。
            mineru_file_name = f"{Path(file_name).stem}.pdf"
            result = await pdf_parser.parse(pdf_path, mineru_file_name)

            # 显式标记原始格式，便于下游区分
            result["file_type"] = self.source_file_type
            # 所有权转移给上层：用于溯源预览的转换 PDF 持久化
            result["converted_pdf_temp_path"] = str(pdf_path)
            pdf_path = None

            self.logger.info(
                f"✅ {label} 解析完成: {file_name}, "
                f"{result.get('total_pages', 0)} 页"
            )
            return result

        except Exception as e:
            self.logger.error(f"❌ {label} 解析失败: {file_name}, 错误: {e}")
            raise Exception(f"{label} 解析失败: {e}")

        finally:
            if pdf_path is not None:
                self._cleanup_temp_pdf(pdf_path)

    async def _convert_to_pdf(self, file_path: Path) -> Path:
        """调用 LibreOffice headless 将 Office 文档转换为 PDF。"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._convert_to_pdf_sync, file_path
        )

    def _convert_to_pdf_sync(self, file_path: Path) -> Path:
        """
        同步执行 LibreOffice headless 转换。

        使用独立的 UserInstallation 目录避免多实例并发时的 profile 锁冲突
        （LibreOffice headless 默认共享同一用户配置目录，并发会互相阻塞）。
        """
        import subprocess

        out_dir = Path(tempfile.mkdtemp(prefix=f"{self.source_file_type}_convert_"))
        profile_dir = Path(tempfile.mkdtemp(prefix="lo_profile_"))
        profile_url = f"file://{profile_dir}"

        try:
            cmd = [
                self.soffice_path,
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                f"-env:UserInstallation={profile_url}",
                "--convert-to", "pdf",
                "--outdir", str(out_dir),
                str(file_path),
            ]

            self.logger.debug(f"LibreOffice 命令: {' '.join(cmd)}")

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.convert_timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                raise Exception(
                    f"LibreOffice 转换超时（{self.convert_timeout}s）: {file_path.name}"
                )

            if proc.returncode != 0:
                stderr = (proc.stderr or "").strip()
                raise Exception(
                    f"LibreOffice 转换失败（returncode={proc.returncode}）: {stderr}"
                )

            pdf_name = file_path.stem + ".pdf"
            pdf_path = out_dir / pdf_name

            if not pdf_path.exists():
                pdfs = list(out_dir.glob("*.pdf"))
                if not pdfs:
                    raise Exception(
                        f"LibreOffice 转换未生成 PDF 产物: {file_path.name}"
                    )
                pdf_path = pdfs[0]

            return pdf_path

        finally:
            try:
                shutil.rmtree(profile_dir, ignore_errors=True)
            except Exception:
                pass

    def _cleanup_temp_pdf(self, pdf_path: Path):
        """清理临时 PDF 文件及其所在临时目录。"""
        try:
            out_dir = pdf_path.parent
            if pdf_path.exists():
                pdf_path.unlink()
            if out_dir.exists() and not any(out_dir.iterdir()):
                shutil.rmtree(out_dir, ignore_errors=True)
        except Exception as e:
            self.logger.debug(f"清理临时 PDF 失败（可忽略）: {e}")
