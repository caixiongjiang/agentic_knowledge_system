#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Chat Agent ``read_image_chunks`` 核心逻辑。

策略（工具内 VLM 旁路理解，主对话模型只看文字）：
- **无 question**：一图一描述（background 阶段同口径）。
- **有 question**：多图共答，**一次 VLM 调用**综合回答。

持久化说明（当前 **不做**）：
- 本模块仅在 tool 消息中返回结果，**不写** MongoDB ``vlm_description`` / ``text``，**不** upsert Milvus。
- 后续 ``image_understand`` Background Worker 会批量理解并持久化 + 重嵌入（见开发清单 §2.4）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from loguru import logger

if TYPE_CHECKING:
    from src.service.chat.tools.kit import KnowledgeNavToolKit

from src.db.mongodb.repositories.chunk_data_repository import ChunkDataRepository
from src.db.mysql.connection.factory import get_mysql_manager
from src.db.mysql.models.base.chunk_meta_info import ChunkMetaInfo
from src.db.storage.manager import StorageManager
from src.prompts.background.multimodal_image_understanding import (
    BACKGROUND_IMAGE_UNDERSTANDING_SYSTEM,
    build_background_user_prompt,
)
from src.prompts.tool.read_image_chunks import (
    READ_IMAGE_CHUNKS_QA_SYSTEM,
    ImagePromptMeta,
    build_qa_user_prompt,
)
from src.service.chat.image_processing import (
    DEFAULT_MAX_IMAGE_LONG_EDGE,
    bytes_to_data_url,
    resize_image_bytes,
)
from src.client.llm import create_llm_client_from_preset
from src.utils.config_manager import get_config_manager


@dataclass
class LoadedImageChunk:
    chunk_id: str
    page_index: Optional[int]
    image_caption: Optional[str]
    image_footnote: Optional[str]
    section_title: Optional[str]
    vlm_description: Optional[str]
    storage_path: str
    data_url: Optional[str] = None  # 延迟加载：仅 VLM 处理时填充


def _extract_section_title(enhanced_text: Optional[str]) -> Optional[str]:
    if not enhanced_text:
        return None
    first_line = enhanced_text.split("\n", 1)[0].strip()
    if not first_line or first_line.startswith("[图片]"):
        return None
    return first_line


class ImageChunkReaderService:
    """按需加载图片 chunk 并执行 VLM 理解或直接返回压缩图 URL。"""

    def __init__(
        self,
        *,
        max_long_edge: int = DEFAULT_MAX_IMAGE_LONG_EDGE,
        kit: Optional["KnowledgeNavToolKit"] = None,
    ) -> None:
        self._max_long_edge = max_long_edge
        self._kit = kit
        self._llm_client = None

    def _get_llm_client(self):
        if self._llm_client is None:
            chat_cfg = get_config_manager().get_section("chat") or {}
            preset = str(chat_cfg.get("multimodal_model_preset", "multimodal"))
            self._llm_client = create_llm_client_from_preset(preset)
        return self._llm_client

    async def _load_chunks(
        self,
        chunk_ids: List[str],
    ) -> Tuple[Dict[str, LoadedImageChunk], List[str], List[str], List[str]]:
        """
        Returns:
            (loaded_map, missing_ids, non_image_ids, load_error_ids)
        """
        chunk_data_list = await ChunkDataRepository().get_by_ids(chunk_ids)
        chunk_data_map = {str(cd.id): cd for cd in chunk_data_list}

        meta_map: Dict[str, ChunkMetaInfo] = {}
        manager = get_mysql_manager()
        with manager.get_session() as session:
            rows = (
                session.query(ChunkMetaInfo)
                .filter(
                    ChunkMetaInfo.chunk_id.in_(chunk_ids),
                    ChunkMetaInfo.deleted == 0,
                )
                .all()
            )
            for row in rows:
                meta_map[row.chunk_id] = row

        loaded: Dict[str, LoadedImageChunk] = {}
        missing: List[str] = []
        non_image: List[str] = []
        load_errors: List[str] = []

        async with StorageManager() as storage:
            for cid in chunk_ids:
                meta = meta_map.get(cid)
                cd = chunk_data_map.get(cid)
                if meta is None:
                    missing.append(cid)
                    continue

                chunk_type = meta.chunk_type or (cd.chunk_type if cd else None)
                if chunk_type != "image":
                    non_image.append(cid)
                    continue

                if not meta.bucket_name or not meta.image_file_path:
                    load_errors.append(cid)
                    continue

                storage_path = f"{meta.bucket_name}/{meta.image_file_path}"

                # text_meta 在 ChunkData 重构后存储结构化元数据（2026/06/08）
                text_meta = cd.text_meta if cd and cd.text_meta else {}
                loaded[cid] = LoadedImageChunk(
                    chunk_id=cid,
                    page_index=meta.page_index,
                    image_caption=text_meta.get("image_caption"),
                    image_footnote=text_meta.get("image_footnote"),
                    section_title=_extract_section_title(
                        cd.enhanced_text if cd else None,
                    ),
                    vlm_description=(
                        (cd.vlm_description or "").strip() or None
                        if cd
                        else None
                    ),
                    storage_path=storage_path,
                )

        return loaded, missing, non_image, load_errors

    async def _ensure_data_url(self, chunk: LoadedImageChunk) -> str:
        """按需下载图片并生成 data_url（供 VLM 调用）。"""
        if chunk.data_url:
            return chunk.data_url
        async with StorageManager() as storage:
            raw_bytes = await storage.download_file(chunk.storage_path)
        compressed, mime = resize_image_bytes(raw_bytes, self._max_long_edge)
        chunk.data_url = bytes_to_data_url(compressed, mime)
        return chunk.data_url

    async def _call_vlm(
        self,
        *,
        data_urls: List[str],
        system_prompt: str,
        user_text: str,
    ) -> str:
        if not data_urls:
            raise RuntimeError("VLM 调用缺少图片")

        client = self._get_llm_client()
        if self._kit is not None:
            self._kit.note_execution_model(client.model)
            await self._kit.emit_progress(
                "calling_vlm",
                model=client.model,
                channel="tool",
            )
        user_content: List[dict] = [{"type": "text", "text": user_text}]
        for data_url in data_urls:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                },
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        resp = await client.agenerate(messages)
        content = (resp.content or "").strip()
        if not content:
            raise RuntimeError("VLM 返回空内容")
        return content

    async def _background_description(self, chunk: LoadedImageChunk) -> str:
        if chunk.vlm_description:
            return chunk.vlm_description

        user_text = build_background_user_prompt(
            image_caption=chunk.image_caption,
            image_footnote=chunk.image_footnote,
            section_title=chunk.section_title,
            page_index=chunk.page_index,
        )
        data_url = await self._ensure_data_url(chunk)
        return await self._call_vlm(
            data_urls=[data_url],
            system_prompt=BACKGROUND_IMAGE_UNDERSTANDING_SYSTEM,
            user_text=user_text,
        )

    async def _qa_multi_images(
        self,
        chunks: List[LoadedImageChunk],
        question: str,
    ) -> str:
        images = [
            ImagePromptMeta(
                chunk_id=chunk.chunk_id,
                image_caption=chunk.image_caption,
                image_footnote=chunk.image_footnote,
                section_title=chunk.section_title,
                page_index=chunk.page_index,
            )
            for chunk in chunks
        ]
        user_text = build_qa_user_prompt(question, images)
        data_urls = [await self._ensure_data_url(chunk) for chunk in chunks]
        return await self._call_vlm(
            data_urls=data_urls,
            system_prompt=READ_IMAGE_CHUNKS_QA_SYSTEM,
            user_text=user_text,
        )

    def _append_footer(
        self,
        lines: List[str],
        *,
        non_image: List[str],
        missing: List[str],
        load_errors: List[str],
    ) -> None:
        if non_image:
            lines.append(
                f"以下 {len(non_image)} 条不是 image 类型，已跳过："
                f"{', '.join(non_image)}",
            )
        if missing:
            lines.append(
                f"以下 {len(missing)} 条未找到元数据：{', '.join(missing)}",
            )
        if load_errors:
            lines.append(
                f"以下 {len(load_errors)} 条图片下载/压缩失败："
                f"{', '.join(load_errors)}",
            )

    async def read_image_chunks(
        self,
        chunk_ids: List[str],
        *,
        question: Optional[str] = None,
    ) -> str:
        if self._kit is not None:
            await self._kit.emit_progress("loading_images", channel="tool")

        loaded, missing, non_image, load_errors = await self._load_chunks(chunk_ids)

        lines: List[str] = [
            "read_image_chunks: "
            f"成功处理 {len(loaded)}/{len(chunk_ids)} 条图片 chunk。",
            f"图片已按长边 ≤ {self._max_long_edge}px 规则压缩（原图更小则不变）。",
            "注意：本次工具结果仅写入对话历史，不会持久化到知识库。",
        ]

        question_norm = (question or "").strip()
        ordered_loaded = [loaded[cid] for cid in chunk_ids if cid in loaded]

        if question_norm and ordered_loaded:
            chunk_id_list = ", ".join(chunk.chunk_id for chunk in ordered_loaded)
            try:
                analysis = await self._qa_multi_images(ordered_loaded, question_norm)
                lines.append(
                    f"--- vlm_qa (n={len(ordered_loaded)}, chunk_ids={chunk_id_list}) ---",
                )
                lines.append("mode: vlm_qa_multi")
                lines.append(f"question: {question_norm}")
                lines.append(f"analysis: {analysis}")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"read_image_chunks 多图 QA VLM 失败: {e}")
                lines.append(
                    f"--- vlm_qa (n={len(ordered_loaded)}) ---",
                )
                lines.append(f"error: 多图 VLM 理解失败: {e}")

            self._append_footer(
                lines,
                non_image=non_image,
                missing=missing,
                load_errors=load_errors,
            )
            return "\n".join(lines)

        for cid in chunk_ids:
            chunk = loaded.get(cid)
            if chunk is None:
                continue

            header_parts = [f"--- chunk_id={cid}"]
            if chunk.page_index is not None:
                header_parts.append(f"page={chunk.page_index + 1}")
            header = ", ".join(header_parts) + " ---"

            try:
                if chunk.vlm_description:
                    analysis = chunk.vlm_description
                    source = "background_pipeline"
                else:
                    analysis = await self._background_description(chunk)
                    source = "vlm_background_prompt"
                lines.append(header)
                lines.append("mode: vlm_background")
                lines.append(f"source: {source}")
                lines.append(f"analysis: {analysis}")
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"read_image_chunks VLM 失败 chunk_id={cid}: {e}",
                )
                lines.append(header)
                lines.append(f"error: VLM 理解失败: {e}")

        self._append_footer(
            lines,
            non_image=non_image,
            missing=missing,
            load_errors=load_errors,
        )
        return "\n".join(lines)
