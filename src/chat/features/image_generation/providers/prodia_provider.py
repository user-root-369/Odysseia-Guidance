# -*- coding: utf-8 -*-
"""通过 OpenAI 兼容接口调用图像生成模型。"""

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


class ProdiaProvider:
    """通过 OpenAI 兼容 Images API 调用真正的图片模型。"""

    def __init__(self) -> None:
        prodia_config = IMAGE_GENERATION_CONFIG["PRODIA"]
        self.api_key = prodia_config.get("API_KEY")
        self.base_url = str(prodia_config.get("BASE_URL", "")).rstrip("/")
        self.model = prodia_config.get("MODEL", "prodia/flux-fast-schnell")
        self.output_format = prodia_config.get("OUTPUT_FORMAT", "png")
        self.timeout_seconds = int(IMAGE_GENERATION_CONFIG.get("TIMEOUT_SECONDS", 45))

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not self.api_key:
            return ImageGenerationResult(
                success=False,
                provider="prodia",
                model=self.model,
                prompt=request.prompt,
                revised_prompt=request.prompt,
                error_code="missing_api_key",
                error_message="未配置图像接口 API Key。",
            )

        revised_prompt = self._build_prompt(request)
        payload = {
            "model": self.model,
            "prompt": revised_prompt,
            "size": self._map_aspect_ratio_to_size(request.aspect_ratio),
            "response_format": "b64_json",
        }
        if request.negative_prompt:
            payload["extra_body"] = {"negative_prompt": request.negative_prompt}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        timeout = httpx.Timeout(float(self.timeout_seconds), connect=10.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/images/generations",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                image_bytes = self._extract_image_bytes(data)
                if not image_bytes:
                    return ImageGenerationResult(
                        success=False,
                        provider="prodia",
                        model=self.model,
                        prompt=request.prompt,
                        revised_prompt=revised_prompt,
                        error_code="invalid_response",
                        error_message="图像接口返回成功，但未提供可解析的图片数据。",
                    )

                return ImageGenerationResult(
                    success=True,
                    provider="prodia",
                    model=self.model,
                    prompt=request.prompt,
                    revised_prompt=revised_prompt,
                    image_bytes=image_bytes,
                    mime_type=self._guess_mime_type(),
                    metadata={
                        "aspect_ratio": request.aspect_ratio,
                        "size": payload["size"],
                        "style_preset": request.style_preset,
                        "endpoint": "/images/generations",
                    },
                )
        except httpx.TimeoutException:
            log.warning("OpenAI 兼容图像接口请求超时。")
            return ImageGenerationResult(
                success=False,
                provider="prodia",
                model=self.model,
                prompt=request.prompt,
                revised_prompt=revised_prompt,
                error_code="timeout",
                error_message="图像生成请求超时，请稍后再试。",
            )
        except httpx.HTTPStatusError as exc:
            error_text = exc.response.text if exc.response is not None else str(exc)
            log.error("图像接口返回 HTTP 错误: %s", error_text)
            return ImageGenerationResult(
                success=False,
                provider="prodia",
                model=self.model,
                prompt=request.prompt,
                revised_prompt=revised_prompt,
                error_code="http_error",
                error_message=f"图像接口请求失败: {error_text}",
            )
        except httpx.HTTPError as exc:
            log.error("图像接口 HTTP 请求失败: %s", exc)
            return ImageGenerationResult(
                success=False,
                provider="prodia",
                model=self.model,
                prompt=request.prompt,
                revised_prompt=revised_prompt,
                error_code="http_error",
                error_message=f"图像接口请求失败: {exc}",
            )
        except Exception as exc:
            log.error("图像生成发生未知错误。", exc_info=True)
            return ImageGenerationResult(
                success=False,
                provider="prodia",
                model=self.model,
                prompt=request.prompt,
                revised_prompt=revised_prompt,
                error_code="unknown_error",
                error_message=f"图像生成失败: {exc}",
            )

    def _build_prompt(self, request: ImageGenerationRequest) -> str:
        prompt = request.prompt.strip()
        if request.style_preset:
            return f"{prompt}, style: {request.style_preset}"
        return prompt

    def _map_aspect_ratio_to_size(self, aspect_ratio: str) -> str:
        mapping = {
            "1:1": "1024x1024",
            "3:4": "768x1024",
            "4:3": "1024x768",
            "9:16": "720x1280",
            "16:9": "1280x720",
        }
        return mapping.get(
            aspect_ratio,
            mapping[IMAGE_GENERATION_CONFIG["DEFAULT_ASPECT_RATIO"]],
        )

    def _extract_image_bytes(self, data: Dict[str, Any]) -> Optional[bytes]:
        items = data.get("data")
        if not isinstance(items, list) or not items:
            return None

        first_item = items[0]
        if not isinstance(first_item, dict):
            return None

        b64_data = first_item.get("b64_json") or first_item.get("image_base64")
        if isinstance(b64_data, str) and b64_data:
            return base64.b64decode(b64_data)

        return None

    def _guess_mime_type(self) -> str:
        if self.output_format.lower() == "webp":
            return "image/webp"
        if self.output_format.lower() in {"jpg", "jpeg"}:
            return "image/jpeg"
        return "image/png"
