# -*- coding: utf-8 -*-
"""统一图像生成服务。"""

from __future__ import annotations

import logging
from typing import Dict

from src.chat.features.image_generation.config.image_generation_config import (
    IMAGE_GENERATION_CONFIG,
)
from src.chat.features.image_generation.providers.base import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from src.chat.features.image_generation.providers.gemini_multimodal_image_provider import (
    GeminiMultimodalImageProvider,
)
from src.chat.features.image_generation.providers.prodia_provider import ProdiaProvider

log = logging.getLogger(__name__)


class ImageGenerationService:
    """统一管理图像生成 Provider 的调度逻辑。"""

    def __init__(self) -> None:
        self.providers: Dict[str, ImageGenerationProvider] = {
            "prodia": ProdiaProvider(),
            "gemini_multimodal": GeminiMultimodalImageProvider(),
        }

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not IMAGE_GENERATION_CONFIG["ENABLED"]:
            return ImageGenerationResult(
                success=False,
                provider="disabled",
                prompt=request.prompt,
                revised_prompt=request.prompt,
                error_code="disabled",
                error_message="图像生成功能当前未启用。",
            )

        provider_name = (request.provider or IMAGE_GENERATION_CONFIG["DEFAULT_PROVIDER"]).lower()
        provider = self.providers.get(provider_name)
        if not provider:
            return ImageGenerationResult(
                success=False,
                provider=provider_name,
                prompt=request.prompt,
                revised_prompt=request.prompt,
                error_code="provider_not_found",
                error_message=f"不支持的图像生成 Provider: {provider_name}",
            )

        log.info("开始执行图像生成，请求 provider=%s aspect_ratio=%s", provider_name, request.aspect_ratio)
        return await provider.generate(request)


image_generation_service = ImageGenerationService()
