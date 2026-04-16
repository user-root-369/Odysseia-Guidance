# -*- coding: utf-8 -*-
"""通过 OpenAI 兼容 Chat Completions 接入 Gemini 多模态产图。"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, Optional

import httpx

from src.chat.features.image_generation.config.image_generation_config import (
    IMAGE_GENERATION_CONFIG,
)
from src.chat.features.image_generation.providers.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
)

log = logging.getLogger(__name__)


class GeminiMultimodalImageProvider:
    """通过 OpenAI 兼容 Chat Completions 调用 Gemini 多模态图像模型。"""

    def __init__(self) -> None:
        gemini_config = IMAGE_GENERATION_CONFIG["GEMINI_MULTIMODAL"]
        self.api_key = gemini_config.get("API_KEY")
        self.base_url = str(gemini_config.get("BASE_URL", "")).rstrip("/")
        self.model = gemini_config.get("MODEL", "google/gemini-3.1-flash-image-preview")
        self.output_format = gemini_config.get("OUTPUT_FORMAT", "png")
        self.timeout_seconds = int(IMAGE_GENERATION_CONFIG.get("TIMEOUT_SECONDS", 45))

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not self.api_key:
            return ImageGenerationResult(
                success=False,
                provider="gemini_multimodal",
                model=self.model,
                prompt=request.prompt,
                revised_prompt=request.prompt,
                error_code="missing_api_key",
                error_message="未配置 Gemini 多模态图像接口 API Key。",
            )

        revised_prompt = self._build_prompt(request)
        payload = {
            "model": self.model,
            "modalities": ["image", "text"],
            "messages": [
                {
                    "role": "user",
                    "content": revised_prompt,
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        timeout = httpx.Timeout(float(self.timeout_seconds), connect=10.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                image_bytes = self._extract_image_bytes(data)
                if not image_bytes:
                    debug_summary = self._build_debug_summary(data)
                    first_choice = (
                        data.get("choices", [None])[0]
                        if isinstance(data.get("choices"), list) and data.get("choices")
                        else None
                    )
                    first_choice_json = (
                        str(first_choice)
                        if first_choice is None
                        else __import__("json").dumps(first_choice, ensure_ascii=False, default=str)
                    )
                    log.warning(
                        "Gemini 多模态图像接口返回成功但未解析到图片，响应摘要: %s，原始首个 choice JSON: %s",
                        debug_summary,
                        first_choice_json,
                    )
                    return ImageGenerationResult(
                        success=False,
                        provider="gemini_multimodal",
                        model=self.model,
                        prompt=request.prompt,
                        revised_prompt=revised_prompt,
                        error_code="invalid_response",
                        error_message=(
                            "多模态图像接口返回成功，但未提供可解析的图片数据。"
                            f" 调试摘要: {debug_summary}"
                            f" 首个choice: {first_choice_json}"
                        ),
                        metadata={
                            "endpoint": "/chat/completions",
                            "response_keys": list(data.keys()),
                            "debug_summary": debug_summary,
                        },
                    )

                return ImageGenerationResult(
                    success=True,
                    provider="gemini_multimodal",
                    model=self.model,
                    prompt=request.prompt,
                    revised_prompt=revised_prompt,
                    image_bytes=image_bytes,
                    mime_type=self._guess_mime_type(),
                    metadata={
                        "aspect_ratio": request.aspect_ratio,
                        "style_preset": request.style_preset,
                        "endpoint": "/chat/completions",
                    },
                )
        except httpx.TimeoutException:
            log.warning("Gemini 多模态图像接口请求超时。")
            return ImageGenerationResult(
                success=False,
                provider="gemini_multimodal",
                model=self.model,
                prompt=request.prompt,
                revised_prompt=revised_prompt,
                error_code="timeout",
                error_message="多模态图像生成请求超时，请稍后再试。",
            )
        except httpx.HTTPStatusError as exc:
            error_text = exc.response.text if exc.response is not None else str(exc)
            log.error("Gemini 多模态图像接口返回 HTTP 错误: %s", error_text)
            return ImageGenerationResult(
                success=False,
                provider="gemini_multimodal",
                model=self.model,
                prompt=request.prompt,
                revised_prompt=revised_prompt,
                error_code="http_error",
                error_message=f"多模态图像接口请求失败: {error_text}",
            )
        except httpx.HTTPError as exc:
            log.error("Gemini 多模态图像接口 HTTP 请求失败: %s", exc)
            return ImageGenerationResult(
                success=False,
                provider="gemini_multimodal",
                model=self.model,
                prompt=request.prompt,
                revised_prompt=revised_prompt,
                error_code="http_error",
                error_message=f"多模态图像接口请求失败: {exc}",
            )
        except Exception as exc:
            log.error("Gemini 多模态图像生成发生未知错误。", exc_info=True)
            return ImageGenerationResult(
                success=False,
                provider="gemini_multimodal",
                model=self.model,
                prompt=request.prompt,
                revised_prompt=revised_prompt,
                error_code="unknown_error",
                error_message=f"多模态图像生成失败: {exc}",
            )

    def _build_prompt(self, request: ImageGenerationRequest) -> str:
        prompt_parts = [request.prompt.strip()]

        aspect_ratio_hint = self._map_aspect_ratio_hint(request.aspect_ratio)
        if aspect_ratio_hint:
            prompt_parts.append(aspect_ratio_hint)

        if request.style_preset:
            prompt_parts.append(f"Style: {request.style_preset.strip()}")

        if request.negative_prompt:
            prompt_parts.append(f"Avoid: {request.negative_prompt.strip()}")

        return " ".join(part for part in prompt_parts if part)

    def _extract_image_bytes(self, data: Dict[str, Any]) -> Optional[bytes]:
        files = data.get("files")
        image_bytes = self._extract_from_files(files)
        if image_bytes:
            return image_bytes

        choices = data.get("choices")
        if not isinstance(choices, list):
            return None

        for choice in choices:
            if not isinstance(choice, dict):
                continue

            image_bytes = self._extract_from_choice(choice)
            if image_bytes:
                return image_bytes

        return None

    def _extract_from_choice(self, choice: Dict[str, Any]) -> Optional[bytes]:
        message = choice.get("message")
        if isinstance(message, dict):
            image_bytes = self._extract_from_message(message)
            if image_bytes:
                return image_bytes

        for key in ("files", "attachments"):
            image_bytes = self._extract_from_files(choice.get(key))
            if image_bytes:
                return image_bytes

        return None

    def _extract_from_files(self, files: Any) -> Optional[bytes]:
        if not isinstance(files, list):
            return None

        for file in files:
            if not isinstance(file, dict):
                continue

            media_type = file.get("mediaType") or file.get("media_type")
            if isinstance(media_type, str) and not media_type.startswith("image/"):
                continue

            image_value = file.get("image")
            image_bytes = self._decode_image_value(image_value)
            if image_bytes:
                return image_bytes

            for key in ("base64", "b64_json", "data", "image_base64"):
                value = file.get(key)
                image_bytes = self._decode_image_value(value)
                if image_bytes:
                    return image_bytes

        return None

    def _extract_from_message(self, message: Dict[str, Any]) -> Optional[bytes]:
        files = message.get("files") or message.get("attachments")
        image_bytes = self._extract_from_files(files)
        if image_bytes:
            return image_bytes

        images = message.get("images")
        image_bytes = self._extract_from_images(images)
        if image_bytes:
            return image_bytes

        content = message.get("content")
        if isinstance(content, str):
            return None
        if not isinstance(content, list):
            return None

        for part in content:
            if not isinstance(part, dict):
                continue

            part_type = part.get("type")
            if part_type == "image":
                image_bytes = self._decode_image_value(part.get("image"))
                if image_bytes:
                    return image_bytes

            image_url = part.get("image_url")
            if isinstance(image_url, dict):
                image_bytes = self._decode_image_value(image_url.get("url"))
                if image_bytes:
                    return image_bytes

            for key in ("image", "base64", "b64_json", "data", "image_base64"):
                image_bytes = self._decode_image_value(part.get(key))
                if image_bytes:
                    return image_bytes

            file_data = part.get("file") or part.get("file_data") or part.get("inline_data")
            if isinstance(file_data, dict):
                for key in ("image", "base64", "b64_json", "data"):
                    image_bytes = self._decode_image_value(file_data.get(key))
                    if image_bytes:
                        return image_bytes

        return None

    def _extract_from_images(self, images: Any) -> Optional[bytes]:
        if not isinstance(images, list):
            return None

        for image_item in images:
            if not isinstance(image_item, dict):
                continue

            image_url = image_item.get("image_url")
            if isinstance(image_url, dict):
                image_bytes = self._decode_image_value(image_url.get("url"))
                if image_bytes:
                    return image_bytes

            image_bytes = self._decode_image_value(image_item.get("image"))
            if image_bytes:
                return image_bytes

            for key in ("url", "base64", "b64_json", "data", "image_base64"):
                image_bytes = self._decode_image_value(image_item.get(key))
                if image_bytes:
                    return image_bytes

        return None

    def _decode_image_value(self, value: Any) -> Optional[bytes]:
        if isinstance(value, str) and value:
            if value.startswith("http://") or value.startswith("https://"):
                log.info("检测到远程图片 URL，当前暂未自动下载: %s", value)
                return None
            try:
                return self._decode_possible_data_url(value)
            except Exception:
                log.debug("图片字符串解析失败，已跳过当前字段。")
                return None

        if isinstance(value, (bytes, bytearray)) and value:
            return bytes(value)

        return None

    def _decode_possible_data_url(self, value: str) -> bytes:
        if value.startswith("data:") and "," in value:
            _, encoded = value.split(",", 1)
            return base64.b64decode(encoded)
        return base64.b64decode(value)

    def _build_debug_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "top_level_keys": list(data.keys()),
        }

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return summary

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            summary["first_choice_type"] = type(first_choice).__name__
            return summary

        summary["first_choice_keys"] = list(first_choice.keys())

        message = first_choice.get("message")
        if not isinstance(message, dict):
            summary["message_type"] = type(message).__name__
            return summary

        summary["message_keys"] = list(message.keys())
        content = message.get("content")
        if isinstance(content, list):
            summary["content_length"] = len(content)
            summary["content_part_summaries"] = []
            for part in content[:5]:
                if isinstance(part, dict):
                    summary["content_part_summaries"].append(
                        {
                            "keys": list(part.keys()),
                            "type": part.get("type"),
                        }
                    )
                else:
                    summary["content_part_summaries"].append(
                        {"python_type": type(part).__name__}
                    )
        else:
            summary["content_type"] = type(content).__name__

        return summary

    def _map_aspect_ratio_hint(self, aspect_ratio: str) -> Optional[str]:
        mapping = {
            "1:1": "Square composition.",
            "3:4": "Portrait composition.",
            "4:3": "Landscape composition.",
            "9:16": "Tall vertical composition.",
            "16:9": "Wide cinematic composition.",
        }
        return mapping.get(aspect_ratio)

    def _guess_mime_type(self) -> str:
        if self.output_format.lower() == "webp":
            return "image/webp"
        if self.output_format.lower() in {"jpg", "jpeg"}:
            return "image/jpeg"
        return "image/png"
