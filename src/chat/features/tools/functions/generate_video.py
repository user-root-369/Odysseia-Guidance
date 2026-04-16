# -*- coding: utf-8 -*-
"""
视频生成工具函数。

LLM 可在以下场景调用此工具：
  1. 用户明确要求生成视频（文生视频）
  2. 用户发送图片并要求将其变成视频（图生视频）
     — LLM 从消息上下文中提取图片的 Discord 附件 URL 并传入 image_url 参数

视频生成使用 asyncio.Lock 互斥，锁被占用时立即返回 busy 错误供 LLM 告知用户。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aiohttp
from pydantic import BaseModel, Field

from src.chat.features.firefly.config.firefly_config import FIREFLY_CONFIG
from src.chat.features.firefly.providers.firefly_web_provider import (
    VideoGenerationRequest,
    firefly_web_provider,
)
from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 参数模型
# ---------------------------------------------------------------------------


class GenerateVideoParams(BaseModel):
    """视频生成参数。"""

    prompt: str = Field(
        description="视频内容的详细文字描述，尽量具体描述画面、动作、氛围。"
    )
    image_url: Optional[str] = Field(
        default=None,
        description=(
            "图生视频时，用户上传的图片的 URL 或 base64 data URL。"
            "若消息上下文中图片以 data URL 形式出现（格式：data:image/png;base64,...），"
            "请优先直接传入该完整字符串，无需转换。"
            "若只有 Discord CDN URL 则传该 URL。"
            "仅在用户明确提供了图片并希望将图片变成视频时传入此参数，文生视频时留空。"
        ),
    )
    aspect_ratio: str = Field(
        default="16:9",
        description="视频宽高比，可选：16:9（横版）、9:16（竖版）、1:1（方形）。默认 16:9。",
    )
    duration: int = Field(
        default=FIREFLY_CONFIG["VIDEO_DEFAULT_DURATION"],
        description="视频时长（秒），仅支持 4、6、8 三个值，默认 8 秒。不要使用其他数值。",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="不希望出现在视频中的内容描述（可选）。",
    )


# ---------------------------------------------------------------------------
# 宽高比映射
# ---------------------------------------------------------------------------

_ASPECT_RATIO_MAP = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "1:1": (720, 720),
    # 允许别名
    "wide": (1280, 720),
    "landscape": (1280, 720),
    "vertical": (720, 1280),
    "portrait": (720, 1280),
    "square": (720, 720),
}


def _parse_size(aspect_ratio: str) -> tuple[int, int]:
    return _ASPECT_RATIO_MAP.get(aspect_ratio.lower().strip(), (1280, 720))


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


@tool_metadata(
    name="视频生成",
    description=(
        "根据文字描述生成一段视频，或将用户上传的图片变成视频。"
        "仅在用户明确要求生成视频，或明确要求将图片变成视频时调用。"
        "视频生成耗时约 1-3 分钟，生成期间无法接受新的视频请求。"
    ),
    emoji="🎬",
    category="创作",
)
async def generate_video(
    params: GenerateVideoParams | str | None = None,
    prompt: Optional[str] = None,
    image_url: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    duration: Optional[int] = None,
    negative_prompt: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    视频生成工具入口。

    支持两种调用方式：
    1. params 为 GenerateVideoParams 实例（Pydantic 自动转换）
    2. 关键字参数形式（兼容旧调用方式）
    """
    # --- 参数归一化 ---
    if isinstance(params, GenerateVideoParams):
        p = params
    elif isinstance(params, str):
        # LLM 直接传了字符串作为 prompt
        p = GenerateVideoParams(
            prompt=params,
            image_url=image_url,
            aspect_ratio=aspect_ratio or "16:9",
            duration=duration or FIREFLY_CONFIG["VIDEO_DEFAULT_DURATION"],
            negative_prompt=negative_prompt,
        )
    else:
        effective_prompt = prompt or kwargs.get("params")
        if not isinstance(effective_prompt, str) or not effective_prompt.strip():
            return {
                "success": False,
                "error_code": "missing_prompt",
                "error_message": "缺少视频描述，请告诉我想要生成什么样的视频。",
            }
        p = GenerateVideoParams(
            prompt=effective_prompt,
            image_url=image_url,
            aspect_ratio=aspect_ratio or "16:9",
            duration=duration or FIREFLY_CONFIG["VIDEO_DEFAULT_DURATION"],
            negative_prompt=negative_prompt,
        )

    # --- 基本校验 ---
    if not p.prompt.strip():
        return {
            "success": False,
            "error_code": "empty_prompt",
            "error_message": "视频描述不能为空。",
        }

    # --- 功能可用性检查 ---
    if not FIREFLY_CONFIG["ENABLED"]:
        return {
            "success": False,
            "error_code": "disabled",
            "error_message": "视频生成功能当前未启用。",
        }

    log.info(
        "Firefly 状态检查: enabled=%s, token=%s, expires_at=%s, is_active=%s",
        firefly_web_provider._enabled,
        bool(firefly_web_provider._token),
        firefly_web_provider._token_expires_at,
        firefly_web_provider.is_active,
    )
    if not firefly_web_provider.is_active:
        return {
            "success": False,
            "error_code": "not_active",
            "error_message": "视频生成功能当前未激活，请稍后再试或联系管理员。",
        }

    # --- 视频锁检查：占用则立即拒绝，不等待 ---
    if firefly_web_provider.is_video_generating:
        status = firefly_web_provider.get_status()
        preview = status.get("video_prompt_preview", "")
        elapsed = status.get("video_elapsed_seconds", 0)
        return {
            "success": False,
            "error_code": "busy",
            "error_message": (
                f'视频生成功能当前正忙（正在生成："{preview}"，已用时 {elapsed} 秒），'
                "请等待当前任务完成后再试。"
            ),
        }

    # --- 图生视频：获取用户图片字节 ---
    image_bytes: Optional[bytes] = None
    image_mime: str = "image/jpeg"

    # 优先使用 tool_service 注入的附件字节（消息处理阶段已下载，不受 CDN URL 过期影响）
    _injected_bytes: Optional[bytes] = kwargs.get("_injected_image_bytes")
    _injected_mime: str = kwargs.get("_injected_image_mime", "image/png")

    if _injected_bytes and p.image_url:
        image_bytes = _injected_bytes
        image_mime = _injected_mime
        log.info(
            "图生视频：使用注入的附件字节（%d bytes, %s），跳过 URL 下载",
            len(image_bytes),
            image_mime,
        )
    elif p.image_url:
        if p.image_url.startswith("data:"):
            # base64 data URL，直接解码，无需 HTTP 请求，不受 Discord CDN 过期影响
            import base64 as _b64

            try:
                header, b64_data = p.image_url.split(",", 1)
                # header 格式: "data:image/png;base64"
                image_mime = header.split(":")[1].split(";")[0]
                image_bytes = _b64.b64decode(b64_data)
                log.info(
                    "图生视频：从 base64 data URL 解码图片，大小：%d bytes，类型：%s",
                    len(image_bytes),
                    image_mime,
                )
            except Exception as exc:
                log.error("base64 图片解码失败：%s", exc)
                return {
                    "success": False,
                    "error_code": "image_decode_error",
                    "error_message": f"图片解码失败：{exc}",
                }
        else:
            # 普通 HTTP URL，发起下载请求
            log.info("图生视频：开始下载图片 %s", p.image_url)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        p.image_url,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                        },
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status != 200:
                            return {
                                "success": False,
                                "error_code": "image_download_failed",
                                "error_message": f"图片下载失败（HTTP {resp.status}），请确认图片链接是否有效。",
                            }
                        image_bytes = await resp.read()
                        image_mime = resp.content_type or "image/jpeg"
                        log.info(
                            "图片下载成功，大小：%d bytes，类型：%s",
                            len(image_bytes) if image_bytes else 0,
                            image_mime,
                        )
            except asyncio.TimeoutError:
                return {
                    "success": False,
                    "error_code": "image_download_timeout",
                    "error_message": "图片下载超时，请稍后再试。",
                }
            except Exception as exc:
                log.error("图片下载异常：%s", exc)
                return {
                    "success": False,
                    "error_code": "image_download_error",
                    "error_message": f"图片下载失败：{exc}",
                }

    # --- 构建请求并调用 Provider ---
    width, height = _parse_size(p.aspect_ratio)

    request = VideoGenerationRequest(
        prompt=p.prompt.strip(),
        negative_prompt=p.negative_prompt,
        width=width,
        height=height,
        duration=p.duration,
        image_bytes=image_bytes,
        image_mime_type=image_mime,
    )

    log.info(
        "调用 Firefly 视频生成，模式：%s，prompt：%s",
        "图生视频" if image_bytes else "文生视频",
        p.prompt[:60],
    )

    result = await firefly_web_provider.generate_video(request)

    if not result.success:
        return {
            "success": False,
            "error_code": result.error_code or "generation_failed",
            "error_message": result.error_message or "视频生成失败，请稍后再试。",
        }

    # --- 构造成功返回值 ---
    response: dict = {
        "success": True,
        "provider": result.provider,
        "metadata": result.metadata,
        "message": "视频已生成成功，将直接发送给用户。",
    }

    if result.video_bytes:
        response["video_data"] = {
            "data": result.video_bytes,
            "mime_type": result.mime_type,
            "url": result.video_url,  # 保留 URL 供文件过大时降级使用
        }
    elif result.video_url:
        response["video_data"] = {
            "data": None,
            "mime_type": result.mime_type,
            "url": result.video_url,
        }

    return response
