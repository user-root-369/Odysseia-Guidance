# -*- coding: utf-8 -*-
"""统一图像生成工具。"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from src.chat.features.image_generation.config.image_generation_config import (
    IMAGE_GENERATION_CONFIG,
)
from src.chat.features.image_generation.providers.base import ImageGenerationRequest
from src.chat.features.image_generation.services.image_generation_service import (
    image_generation_service,
)
from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)

ASPECT_RATIO_ALIASES = {
    "square": "1:1",
    "portrait": "3:4",
    "landscape": "4:3",
    "vertical": "3:4",
    "horizontal": "4:3",
    "tall": "9:16",
    "wide": "16:9",
}


def _normalize_aspect_ratio(aspect_ratio: Optional[str]) -> str:
    """将模型常见的宽高比别名归一化为系统允许的比例。"""
    if not aspect_ratio:
        return IMAGE_GENERATION_CONFIG["DEFAULT_ASPECT_RATIO"]

    normalized = aspect_ratio.strip().lower()
    return ASPECT_RATIO_ALIASES.get(normalized, aspect_ratio.strip())


class GenerateImageParams(BaseModel):
    """图像生成参数。"""

    prompt: str = Field(description="用于生成图片的详细描述。")
    aspect_ratio: str = Field(
        default=IMAGE_GENERATION_CONFIG["DEFAULT_ASPECT_RATIO"],
        description="画面宽高比，可选值包括 1:1、3:4、4:3、9:16、16:9。",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="不希望出现在图片中的内容描述。",
    )
    style_preset: Optional[str] = Field(
        default=None,
        description="可选的风格提示，例如 anime、cinematic、oil painting。",
    )
    provider: Optional[str] = Field(
        default=None,
        description="可选的图像生成后端名称，例如 prodia 或 gemini_multimodal。若不提供，则使用默认 Provider。",
    )


@tool_metadata(
    name="图像生成",
    description="根据用户明确的绘图请求生成一张图片。仅在用户明确要求画图、做头像、做立绘或生成图片时调用。",
    emoji="🎨",
    category="创作",
)
async def generate_image(
    params: GenerateImageParams | str | None = None,
    prompt: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    style_preset: Optional[str] = None,
    provider: Optional[str] = None,
    **kwargs,
) -> dict:
    """根据提示词生成图片，并以多模态结果返回。"""
    if isinstance(params, GenerateImageParams):
        normalized_params = params
    elif isinstance(params, str):
        normalized_params = GenerateImageParams(
            prompt=params,
            aspect_ratio=_normalize_aspect_ratio(aspect_ratio),
            negative_prompt=negative_prompt,
            style_preset=style_preset,
            provider=provider,
        )
    else:
        effective_prompt = prompt or kwargs.get("params")
        if not isinstance(effective_prompt, str):
            return {
                "success": False,
                "error_code": "missing_prompt",
                "error_message": "缺少用于生成图片的提示词。",
            }

        normalized_params = GenerateImageParams(
            prompt=effective_prompt,
            aspect_ratio=_normalize_aspect_ratio(aspect_ratio),
            negative_prompt=negative_prompt,
            style_preset=style_preset,
            provider=provider,
        )

    normalized_aspect_ratio = _normalize_aspect_ratio(normalized_params.aspect_ratio)
    prompt = normalized_params.prompt.strip()
    negative_prompt = (
        normalized_params.negative_prompt.strip()
        if normalized_params.negative_prompt
        else None
    )

    if not prompt:
        return {
            "success": False,
            "error_code": "empty_prompt",
            "error_message": "提示词不能为空。",
        }

    if len(prompt) > IMAGE_GENERATION_CONFIG["MAX_PROMPT_LENGTH"]:
        return {
            "success": False,
            "error_code": "prompt_too_long",
            "error_message": "提示词过长，请缩短后重试。",
        }

    if (
        negative_prompt
        and len(negative_prompt)
        > IMAGE_GENERATION_CONFIG["MAX_NEGATIVE_PROMPT_LENGTH"]
    ):
        return {
            "success": False,
            "error_code": "negative_prompt_too_long",
            "error_message": "负面提示词过长，请缩短后重试。",
        }

    if normalized_aspect_ratio not in IMAGE_GENERATION_CONFIG["ALLOWED_ASPECT_RATIOS"]:
        return {
            "success": False,
            "error_code": "invalid_aspect_ratio",
            "error_message": "不支持的宽高比，请使用系统允许的比例。",
            "metadata": {
                "received_aspect_ratio": normalized_params.aspect_ratio,
                "allowed_aspect_ratios": IMAGE_GENERATION_CONFIG["ALLOWED_ASPECT_RATIOS"],
            },
        }

    request = ImageGenerationRequest(
        prompt=prompt,
        negative_prompt=negative_prompt,
        aspect_ratio=normalized_aspect_ratio,
        style_preset=normalized_params.style_preset,
        provider=normalized_params.provider,
    )

    result = await image_generation_service.generate(request)
    if not result.success or not result.image_bytes:
        return {
            "success": False,
            "provider": result.provider,
            "model": result.model,
            "prompt": result.prompt,
            "revised_prompt": result.revised_prompt,
            "error_code": result.error_code or "generation_failed",
            "error_message": result.error_message or "图像生成失败。",
        }

    log.info("图像生成成功，provider=%s, model=%s", result.provider, result.model)
    return {
        "success": True,
        "provider": result.provider,
        "model": result.model,
        "prompt": result.prompt,
        "revised_prompt": result.revised_prompt,
        "metadata": result.metadata,
        "image_data": {
            "data": result.image_bytes,
            "mime_type": result.mime_type,
        },
        "message": "已根据请求生成图片。",
    }
