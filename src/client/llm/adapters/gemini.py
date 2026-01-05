#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : gemini.py
@Author  : caixiongjiang
@Date    : 2026/1/5 10:52
@Function: 
    Gemini Adapter 实现
    处理 Google Gemini 的特殊格式转换
@Modify History:
    2026/1/5 - 初始实现，支持多模态和复杂格式转换
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""

from typing import Dict, Any, List, Union
import base64
import httpx

from src.client.llm.adapters.base import BaseAdapter
from src.client.llm.types import LLMResponse, TokenUsage


class GeminiAdapter(BaseAdapter):
    """
    Gemini Adapter
    
    支持的模型：
    - gemini-1.5-pro
    - gemini-2.0-flash-thinking-exp-1219
    - gemini-1.5-flash
    
    特性：
    - 复杂的消息格式转换（messages → contents + parts）
    - 参数映射（max_tokens → maxOutputTokens）
    - System message 单独处理（systemInstruction）
    - 支持多模态内容（图片、文本混合）
    """
    
    def build_request(self, messages: List[Dict[str, Any]], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建 Gemini 请求
        
        Gemini 格式特点：
        1. messages → contents (role: "user"/"model")
        2. content → parts (array of {text: "..."} or {inlineData: ...})
        3. system message → systemInstruction
        4. 参数嵌套在 generationConfig 中
        
        Args:
            messages: 标准消息列表
            params: 生成参数
        
        Returns:
            Gemini API 请求体
        """
        # 1. 提取 system message
        system_messages = [m for m in messages if m["role"] == "system"]
        other_messages = [m for m in messages if m["role"] != "system"]
        
        # 2. 转换消息格式（messages → contents）
        contents = []
        for msg in other_messages:
            # 映射角色：user → user, assistant → model
            role = "user" if msg["role"] == "user" else "model"
            
            # 处理内容（可能是字符串或多模态列表）
            if isinstance(msg["content"], str):
                # 纯文本
                parts = [{"text": msg["content"]}]
            else:
                # 多模态内容
                parts = self._convert_content_parts(msg["content"])
            
            contents.append({
                "role": role,
                "parts": parts
            })
        
        # 3. 构建请求
        request = {
            "contents": contents,
            "generationConfig": {}
        }
        
        # 4. 添加生成配置（参数映射）
        if "temperature" in params:
            request["generationConfig"]["temperature"] = params["temperature"]
        
        if "max_tokens" in params:
            # 注意：Gemini 使用 maxOutputTokens
            request["generationConfig"]["maxOutputTokens"] = params["max_tokens"]
        
        if "top_p" in params:
            request["generationConfig"]["topP"] = params["top_p"]
        
        if "top_k" in params:
            request["generationConfig"]["topK"] = params["top_k"]
        
        if "stop_sequences" in params:
            request["generationConfig"]["stopSequences"] = params["stop_sequences"]
        
        # 5. System instruction（如果有）
        if system_messages:
            request["systemInstruction"] = {
                "parts": [{"text": system_messages[0]["content"]}]
            }
        
        # 6. Safety settings（如果有）
        if "safety_settings" in params:
            request["safetySettings"] = params["safety_settings"]
        
        return request
    
    def _convert_content_parts(self, content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        转换多模态内容
        
        标准格式 → Gemini 格式：
        - {"type": "text", "text": "..."} → {"text": "..."}
        - {"type": "image_url", "image_url": "..."} → {"inlineData": {"mimeType": "image/jpeg", "data": "..."}}
        - {"type": "image_base64", "image_data": "..."} → {"inlineData": {"mimeType": "image/jpeg", "data": "..."}}
        
        Args:
            content: 标准多模态内容列表
        
        Returns:
            Gemini parts 格式
        """
        parts = []
        
        for item in content:
            if item["type"] == "text":
                parts.append({"text": item["text"]})
            
            elif item["type"] == "image_url":
                # 下载 URL 图片并转换为 base64
                image_url = item["image_url"]
                image_base64 = self._download_and_encode_image(image_url)
                
                parts.append({
                    "inlineData": {
                        "mimeType": self._get_mime_type_from_url(image_url),
                        "data": image_base64
                    }
                })
            
            elif item["type"] == "image_base64":
                parts.append({
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": item["image_data"]
                    }
                })
        
        return parts
    
    def _download_and_encode_image(self, url: str) -> str:
        """
        下载图片并转换为 base64
        
        Args:
            url: 图片 URL
        
        Returns:
            base64 编码的图片数据
        """
        try:
            response = httpx.get(url, timeout=30.0)
            response.raise_for_status()
            return base64.b64encode(response.content).decode("utf-8")
        except Exception as e:
            raise ValueError(f"无法下载图片 {url}: {e}")
    
    def _get_mime_type_from_url(self, url: str) -> str:
        """
        从 URL 推断 MIME 类型
        
        Args:
            url: 图片 URL
        
        Returns:
            MIME 类型
        """
        url_lower = url.lower()
        if url_lower.endswith(".png"):
            return "image/png"
        elif url_lower.endswith(".jpg") or url_lower.endswith(".jpeg"):
            return "image/jpeg"
        elif url_lower.endswith(".gif"):
            return "image/gif"
        elif url_lower.endswith(".webp"):
            return "image/webp"
        else:
            # 默认使用 jpeg
            return "image/jpeg"
    
    def parse_response(self, raw_response: Dict[str, Any]) -> LLMResponse:
        """
        解析 Gemini 响应
        
        Gemini 响应格式：
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "回答内容"}
                        ],
                        "role": "model"
                    },
                    "finishReason": "STOP",
                    "index": 0
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 20,
                "totalTokenCount": 30
            },
            "modelVersion": "gemini-1.5-pro"
        }
        
        Args:
            raw_response: Gemini 原始响应
        
        Returns:
            统一的 LLMResponse
        """
        # 提取第一个候选
        candidate = raw_response["candidates"][0]
        content_parts = candidate["content"]["parts"]
        
        # 提取文本内容（可能有多个 parts）
        text_parts = [p["text"] for p in content_parts if "text" in p]
        content = "\n".join(text_parts)
        
        # 提取 finish_reason，映射到统一格式
        finish_reason_map = {
            "STOP": "stop",
            "MAX_TOKENS": "length",
            "SAFETY": "content_filter",
            "RECITATION": "content_filter",
            "OTHER": "error",
        }
        gemini_finish_reason = candidate.get("finishReason", "STOP")
        finish_reason = finish_reason_map.get(gemini_finish_reason, "stop")
        
        # 构建 Token 使用统计
        usage_metadata = raw_response.get("usageMetadata", {})
        usage = TokenUsage(
            prompt_tokens=usage_metadata.get("promptTokenCount", 0),
            completion_tokens=usage_metadata.get("candidatesTokenCount", 0),
            thinking_tokens=None,  # Gemini 当前不单独统计 thinking tokens
            total_tokens=usage_metadata.get("totalTokenCount", 0)
        )
        
        # 返回统一响应
        return LLMResponse(
            content=content,
            thinking=None,  # Gemini 暂不支持 thinking 内容提取
            usage=usage,
            model=raw_response.get("modelVersion", "gemini"),
            finish_reason=finish_reason,
            raw_response=raw_response
        )
    
    def get_endpoint(self) -> str:
        """
        Gemini API 端点（普通请求）
        
        注意：Gemini 端点需要模型名称，使用占位符
        
        Returns:
            "/models/{model}:generateContent"
        """
        return "/models/{model}:generateContent"
    
    def get_stream_endpoint(self) -> str:
        """
        Gemini 流式 API 端点
        
        Gemini 流式请求使用不同的端点：streamGenerateContent
        
        Returns:
            "/models/{model}:streamGenerateContent?alt=sse"
        """
        return "/models/{model}:streamGenerateContent?alt=sse"
    
    def validate_params(self, params: Dict[str, Any]) -> None:
        """
        参数校验（Gemini 特殊要求）
        
        Args:
            params: 生成参数
        
        Raises:
            ValueError: 参数不合法
        """
        # temperature 范围校验
        if "temperature" in params:
            temp = params["temperature"]
            if not (0 <= temp <= 2):
                raise ValueError(f"temperature 必须在 [0, 2] 范围内，当前值: {temp}")
        
        # top_p 范围校验
        if "top_p" in params:
            top_p = params["top_p"]
            if not (0 <= top_p <= 1):
                raise ValueError(f"top_p 必须在 [0, 1] 范围内，当前值: {top_p}")
        
        # top_k 范围校验
        if "top_k" in params:
            top_k = params["top_k"]
            if not isinstance(top_k, int) or top_k <= 0:
                raise ValueError(f"top_k 必须为正整数，当前值: {top_k}")
    
    def build_headers(self, api_key: str) -> Dict[str, str]:
        """
        构建 Gemini 请求头
        
        Gemini 使用特殊的请求头：x-goog-api-key
        
        Args:
            api_key: API 密钥
        
        Returns:
            请求头字典
        """
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
    
    def parse_stream_chunk(self, chunk_data: Dict[str, Any]) -> Union[str, None]:
        """
        解析 Gemini 流式响应块
        
        Gemini SSE 响应格式：
        {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "文本内容"}],
                        "role": "model"
                    },
                    "finishReason": "STOP",  # 可能为空
                    "index": 0
                }
            ]
        }
        
        Args:
            chunk_data: 解析后的 JSON 数据
        
        Returns:
            文本增量内容，如果没有内容则返回 None
        """
        if "candidates" not in chunk_data or not chunk_data["candidates"]:
            return None
        
        candidate = chunk_data["candidates"][0]
        
        # 提取 content.parts
        if "content" not in candidate:
            return None
        
        content = candidate["content"]
        if "parts" not in content or not content["parts"]:
            return None
        
        # 提取文本内容
        text_parts = [p.get("text", "") for p in content["parts"] if "text" in p]
        
        if not text_parts:
            return None
        
        return "".join(text_parts)
