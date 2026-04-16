# -*- coding: utf-8 -*-
"""图像生成 Provider 抽象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol


@dataclass(slots=True)
class ImageGenerationRequest:
    prompt: str
    negative_prompt: Optional[str] = None
    aspect_ratio: str = "1:1"
    style_preset: Optional[str] = None
    provider: Optional[str] = None


@dataclass(slots=True)
class ImageGenerationResult:
    success: bool
    provider: str
    model: Optional[str] = None
    prompt: Optional[str] = None
    revised_prompt: Optional[str] = None
    image_bytes: Optional[bytes] = None
    mime_type: str = "image/png"
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class ImageGenerationProvider(Protocol):
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """执行一次图像生成请求。"""
