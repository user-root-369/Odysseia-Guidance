# -*- coding: utf-8 -*-
"""
Adobe Firefly Web Provider

通过复用网页版 Token 调用 Firefly 内部 API，支持图片生成和视频生成。

Token 由开发者手动注入（通过 /firefly enable 命令），无需自动登录。
视频生成使用 asyncio.Lock 保证同一时间只有一个任务在执行。
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import aiohttp

from src.chat.features.firefly.config.firefly_config import FIREFLY_CONFIG
from src.chat.features.image_generation.providers.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 视频生成请求/结果数据类
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class VideoGenerationRequest:
    prompt: str
    negative_prompt: Optional[str] = None
    width: int = FIREFLY_CONFIG["VIDEO_DEFAULT_WIDTH"]
    height: int = FIREFLY_CONFIG["VIDEO_DEFAULT_HEIGHT"]
    duration: int = FIREFLY_CONFIG["VIDEO_DEFAULT_DURATION"]
    model_id: str = FIREFLY_CONFIG["VIDEO_DEFAULT_MODEL_ID"]
    model_version: str = FIREFLY_CONFIG["VIDEO_DEFAULT_MODEL_VERSION"]
    generate_audio: bool = True
    # 图生视频时使用，存储图片字节（提交前需先上传为 blob 取得 blob_id）
    image_bytes: Optional[bytes] = None
    image_mime_type: str = "image/jpeg"
    # 图生视频时使用，图片上传后返回的 blob ID（用于 referenceBlobs 字段）
    image_blob_id: Optional[str] = None


@dataclass
class VideoGenerationResult:
    success: bool
    provider: str = "firefly_web"
    video_bytes: Optional[bytes] = None
    video_url: Optional[str] = None
    mime_type: str = "video/mp4"
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------


class FireflyTokenExpiredError(Exception):
    """Token 已失效（HTTP 401）"""


class FireflyBusyError(Exception):
    """视频生成锁被占用"""


# ---------------------------------------------------------------------------
# 核心 Provider
# ---------------------------------------------------------------------------


class FireflyWebProvider:
    """
    Adobe Firefly 网页版 Provider。

    生命周期：
    - 开发者执行 /firefly enable <token> → activate()
    - Token 401 失效 → 自动 deactivate()
    - 开发者执行 /firefly disable → deactivate()
    """

    # Adobe IMS Token 验证端点
    _IMS_VALIDATE_URL = "https://ims-na1.adobelogin.com/ims/validate_token/v1"

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._enabled: bool = False
        self._activated_at: Optional[float] = None
        # Token 的精确过期时间（Unix 秒），从验证接口获取
        self._token_expires_at: Optional[float] = None

        # 视频生成互斥锁，同一时间只允许一个视频任务
        self._video_lock: asyncio.Lock = asyncio.Lock()
        # 当前视频任务的提示词摘要（用于 status 命令展示）
        self._current_video_prompt: Optional[str] = None
        # 当前视频任务的开始时间
        self._video_started_at: Optional[float] = None

    # ------------------------------------------------------------------
    # Token 管理
    # ------------------------------------------------------------------

    async def activate(self, token: str) -> Dict[str, Any]:
        """
        注入 Token 并调用 IMS 验证接口确认有效性。

        返回验证结果字典，包含：
          success: bool
          expires_at: float  (Unix 秒)
          remaining_seconds: int
          error: str (仅失败时)
        """
        self._token = token.strip()
        self._enabled = True
        self._activated_at = time.monotonic()
        self._token_expires_at = None

        # 调用 IMS 验证接口获取精确过期时间
        result = await self._validate_token()
        if result["success"]:
            self._token_expires_at = result["expires_at"]
            remaining = result["remaining_seconds"]
            log.info(
                "Firefly Web Provider 已激活，Token 有效，剩余 %d 秒（%.1f 小时）。",
                remaining,
                remaining / 3600,
            )
        else:
            # 验证失败：Token 本身可能已经无效，但仍允许尝试使用
            # （验证接口失败不代表生成请求一定失败，保持 enabled）
            log.warning(
                "Firefly Token 验证失败：%s，仍尝试保持激活。", result.get("error")
            )

        return result

    def activate_sync(self, token: str) -> None:
        """同步版本的激活，仅设置 Token 不调用验证接口，供内部使用。"""
        self._token = token.strip()
        self._enabled = True
        self._activated_at = time.monotonic()

    def deactivate(self, reason: str = "手动禁用") -> None:
        """清除 Token，禁用功能。"""
        self._token = None
        self._enabled = False
        self._activated_at = None
        self._token_expires_at = None
        log.info("Firefly Web Provider 已禁用，原因：%s", reason)

    @property
    def is_active(self) -> bool:
        if not self._enabled or not self._token:
            return False
        # 若已知过期时间且已过期，主动禁用，避免发出必定 401 的请求
        if self._token_expires_at and time.time() >= self._token_expires_at:
            log.warning("Firefly Token 已到期，自动禁用。")
            self.deactivate(reason="Token 到期")
            return False
        return True

    @property
    def is_video_generating(self) -> bool:
        return self._video_lock.locked()

    async def _validate_token(self) -> Dict[str, Any]:
        """
        调用 Adobe IMS 验证接口，返回 Token 的有效性和精确过期时间。

        POST https://ims-na1.adobelogin.com/ims/validate_token/v1
        Content-Type: application/x-www-form-urlencoded
        Body: token=<token>&client_id=clio-playground-web
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._IMS_VALIDATE_URL,
                    data={
                        "type": "access_token",
                        "client_id": FIREFLY_CONFIG["WEB_API_KEY"],
                        "token": self._token,
                    },
                    headers={
                        "Origin": "https://firefly.adobe.com",
                        "Referer": "https://firefly.adobe.com/",
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) "
                            "Gecko/20100101 Firefox/149.0"
                        ),
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return {
                            "success": False,
                            "error": f"验证接口返回 HTTP {resp.status}",
                        }

                    data = await resp.json(content_type=None)

                    if not data.get("valid"):
                        return {"success": False, "error": "Token 无效（valid=false）"}

                    # expires_at 是毫秒时间戳，转换为 Unix 秒
                    expires_at_ms = data.get("expires_at")
                    if expires_at_ms:
                        expires_at = expires_at_ms / 1000
                    else:
                        # 备用：从 token.expires_in（毫秒）+ token.created_at（毫秒）推算
                        token_info = data.get("token", {})
                        created_ms = float(token_info.get("created_at", 0))
                        expires_in_ms = float(token_info.get("expires_in", 86400000))
                        expires_at = (created_ms + expires_in_ms) / 1000

                    remaining = max(0, int(expires_at - time.time()))
                    return {
                        "success": True,
                        "expires_at": expires_at,
                        "remaining_seconds": remaining,
                    }

        except asyncio.TimeoutError:
            return {"success": False, "error": "验证接口超时"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def get_status(self) -> Dict[str, Any]:
        """返回当前状态信息，供 /firefly status 命令使用。"""
        status: Dict[str, Any] = {
            "active": self.is_active,
            "video_generating": self.is_video_generating,
        }
        if self._token_expires_at:
            remaining = max(0, int(self._token_expires_at - time.time()))
            status["token_remaining_seconds"] = remaining
        elif self.is_active and self._activated_at:
            # 没有精确过期时间时，fallback 显示激活时长
            elapsed = int(time.monotonic() - self._activated_at)
            status["token_age_seconds"] = elapsed
        if self.is_video_generating and self._video_started_at:
            elapsed = int(time.monotonic() - self._video_started_at)
            status["video_elapsed_seconds"] = elapsed
            status["video_prompt_preview"] = self._current_video_prompt
        return status

    # ------------------------------------------------------------------
    # 通用请求头构建
    # ------------------------------------------------------------------

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "x-api-key": FIREFLY_CONFIG["WEB_API_KEY"],
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": "https://firefly.adobe.com",
            "Referer": "https://firefly.adobe.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) "
                "Gecko/20100101 Firefox/149.0"
            ),
        }

    # ------------------------------------------------------------------
    # ImageGenerationProvider Protocol 兼容接口
    # ------------------------------------------------------------------

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """实现 ImageGenerationProvider Protocol，代理到 generate_image。"""
        return await self.generate_image(request)

    # ------------------------------------------------------------------
    # 轮询逻辑（图片和视频通用）
    # ------------------------------------------------------------------

    async def _poll_until_done(
        self,
        session: aiohttp.ClientSession,
        poll_url: str,
        max_wait: int,
        task_label: str,
    ) -> Dict[str, Any]:
        """
        轮询任务状态直到完成或超时。

        响应头 x-task-status 的取值：
          ACCEPTED    → 已排队
          IN_PROGRESS → 生成中
          SUCCEEDED   → 成功
          FAILED      → 失败

        响应头 retry-after 给出建议的下次轮询间隔（秒）。
        """
        deadline = time.monotonic() + max_wait
        interval = FIREFLY_CONFIG["POLL_INTERVAL"]

        while time.monotonic() < deadline:
            await asyncio.sleep(interval)

            try:
                async with session.get(
                    poll_url,
                    headers=self._build_headers(),
                    timeout=aiohttp.ClientTimeout(total=FIREFLY_CONFIG["POLL_TIMEOUT"]),
                ) as resp:
                    if resp.status == 401:
                        self.deactivate(reason="Token 已失效（轮询 401）")
                        raise FireflyTokenExpiredError()

                    task_status = resp.headers.get("x-task-status", "UNKNOWN").upper()
                    # 使用服务端建议的下次轮询间隔
                    try:
                        interval = max(
                            2, int(resp.headers.get("retry-after", interval))
                        )
                    except (ValueError, TypeError):
                        pass

                    log.info(
                        "%s 轮询状态: %s，下次间隔: %ds",
                        task_label,
                        task_status,
                        interval,
                    )

                    if task_status in ("SUCCEEDED", "COMPLETED"):
                        data = await resp.json(content_type=None)
                        log.info("%s 任务完成，响应体：%s", task_label, str(data)[:800])
                        return data

                    if task_status in ("FAILED", "ERROR"):
                        data = await resp.json(content_type=None)
                        error_msg = (
                            data.get("message") or data.get("error") or "任务失败"
                        )
                        raise RuntimeError(f"{task_label} 任务失败：{error_msg}")

                    # ACCEPTED / IN_PROGRESS → 继续等待

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                log.warning(
                    "%s 轮询请求异常：%s，将在 %ds 后重试", task_label, exc, interval
                )

        raise TimeoutError(f"{task_label} 等待超时（超过 {max_wait} 秒）")

    # ------------------------------------------------------------------
    # 图片生成
    # ------------------------------------------------------------------

    async def generate_image(
        self, request: ImageGenerationRequest
    ) -> ImageGenerationResult:
        """
        调用 Firefly 图片生成 API。
        结果为预签名 URL，下载后以字节返回，与现有 Provider 格式一致。
        """
        if not self.is_active:
            return ImageGenerationResult(
                success=False,
                provider="firefly_web",
                prompt=request.prompt,
                error_code="disabled",
                error_message="Firefly 功能当前未启用，请联系管理员激活。",
            )

        width, height = self._map_aspect_ratio(request.aspect_ratio)
        payload: Dict[str, Any] = {
            "generationMetadata": {"module": "text2image"},
            "modelId": FIREFLY_CONFIG["IMAGE_DEFAULT_MODEL_ID"],
            "modelSpecificPayload": {},
            "modelVersion": FIREFLY_CONFIG["IMAGE_DEFAULT_MODEL_VERSION"],
            "n": 1,
            "output": {"storeInputs": True},
            "prompt": request.prompt,
            "size": {"height": height, "width": width},
        }

        submit_timeout = aiohttp.ClientTimeout(total=FIREFLY_CONFIG["SUBMIT_TIMEOUT"])

        try:
            async with aiohttp.ClientSession() as session:
                # 1. 提交图片生成任务
                async with session.post(
                    FIREFLY_CONFIG["IMAGE_SUBMIT_URL"],
                    headers=self._build_headers(),
                    json=payload,
                    timeout=submit_timeout,
                ) as resp:
                    if resp.status == 401:
                        self.deactivate(reason="Token 已失效（图片提交 401）")
                        return ImageGenerationResult(
                            success=False,
                            provider="firefly_web",
                            prompt=request.prompt,
                            error_code="token_expired",
                            error_message="Firefly Token 已失效，功能已自动关闭，请管理员重新激活。",
                        )
                    resp.raise_for_status()

                    body_text = await resp.text()
                    log.info(
                        "图片提交响应 status=%d body=%s",
                        resp.status,
                        body_text[:500],
                    )

                    import json as _json

                    try:
                        body = _json.loads(body_text)
                    except Exception:
                        body = {}

                    poll_url = resp.headers.get("x-override-status-link")
                    if not poll_url:
                        poll_url = (
                            body.get("links", {}).get("result", {}).get("href")
                            or body.get("statusUrl")
                            or body.get("jobUrl")
                            or body.get("status_url")
                        )

                    if not poll_url:
                        log.error("图片提交响应中找不到轮询地址，响应体：%s", body)
                        return ImageGenerationResult(
                            success=False,
                            provider="firefly_web",
                            prompt=request.prompt,
                            error_code="no_poll_url",
                            error_message="Firefly 未返回任务轮询地址，请稍后再试。",
                        )

                    log.info("图片任务已提交，轮询地址：%s", poll_url)

                # 2. 轮询直到完成
                result_data = await self._poll_until_done(
                    session,
                    poll_url,
                    max_wait=FIREFLY_CONFIG["IMAGE_MAX_WAIT"],
                    task_label="图片生成",
                )

                # 3. 提取图片 URL 并下载
                image_url = self._extract_image_url(result_data)
                if not image_url:
                    return ImageGenerationResult(
                        success=False,
                        provider="firefly_web",
                        prompt=request.prompt,
                        error_code="no_image_url",
                        error_message="Firefly 任务完成但未找到图片 URL。",
                    )

                image_bytes = await self._download_bytes(session, image_url, "图片")

                return ImageGenerationResult(
                    success=True,
                    provider="firefly_web",
                    prompt=request.prompt,
                    image_bytes=image_bytes,
                    mime_type="image/png",
                )

        except FireflyTokenExpiredError:
            return ImageGenerationResult(
                success=False,
                provider="firefly_web",
                prompt=request.prompt,
                error_code="token_expired",
                error_message="Firefly Token 已失效，功能已自动关闭，请管理员重新激活。",
            )
        except TimeoutError as exc:
            log.warning("Firefly 图片生成超时：%s", exc)
            return ImageGenerationResult(
                success=False,
                provider="firefly_web",
                prompt=request.prompt,
                error_code="timeout",
                error_message=str(exc),
            )
        except Exception as exc:
            log.error("Firefly 图片生成发生未知错误", exc_info=True)
            return ImageGenerationResult(
                success=False,
                provider="firefly_web",
                prompt=request.prompt,
                error_code="unknown_error",
                error_message=f"图片生成失败：{exc}",
            )

    # ------------------------------------------------------------------
    # 视频生成（公开入口，带互斥锁）
    # ------------------------------------------------------------------

    async def generate_video(
        self, request: VideoGenerationRequest
    ) -> VideoGenerationResult:
        """
        视频生成公开入口。使用 asyncio.Lock 保证同时只有一个任务执行。
        若已有任务在运行，立即返回 busy 错误。
        """
        if not self.is_active:
            return VideoGenerationResult(
                success=False,
                error_code="disabled",
                error_message="Firefly 功能当前未启用，请联系管理员激活。",
            )

        if self._video_lock.locked():
            return VideoGenerationResult(
                success=False,
                error_code="busy",
                error_message="当前已有视频生成任务在运行，请等待完成后再试。",
            )

        async with self._video_lock:
            self._current_video_prompt = request.prompt[:80]
            self._video_started_at = time.monotonic()
            try:
                return await self._do_generate_video(request)
            finally:
                self._current_video_prompt = None
                self._video_started_at = None

    # ------------------------------------------------------------------
    # 视频生成（内部实现）
    # ------------------------------------------------------------------

    async def _do_generate_video(
        self, request: VideoGenerationRequest
    ) -> VideoGenerationResult:
        """视频生成的实际 HTTP 逻辑，由 generate_video 在锁内调用。"""

        negative_prompt = (
            request.negative_prompt or FIREFLY_CONFIG["VIDEO_DEFAULT_NEGATIVE_PROMPT"]
        )

        # 根据是否有图片字节决定模式
        is_image2video = bool(request.image_bytes)
        module = (
            FIREFLY_CONFIG["VIDEO_IMAGE2VIDEO_MODULE"]
            if is_image2video
            else FIREFLY_CONFIG["VIDEO_TEXT2VIDEO_MODULE"]
        )

        submit_timeout = aiohttp.ClientTimeout(total=FIREFLY_CONFIG["SUBMIT_TIMEOUT"])

        try:
            async with aiohttp.ClientSession() as session:
                # 0. 图生视频：先上传图片取得 blob ID
                blob_id: Optional[str] = request.image_blob_id
                if is_image2video and request.image_bytes and not blob_id:
                    log.info("图生视频：开始上传参考图片...")
                    blob_id = await self._upload_image_blob(
                        session,
                        request.image_bytes,
                        mime_type=request.image_mime_type,
                    )

                # 1. 构建提交 payload
                # Veo 3.1-fast-generate 仅支持 [4, 6, 8] 秒，就近校正
                _VALID_DURATIONS = [4, 6, 8]
                _duration = min(
                    _VALID_DURATIONS, key=lambda d: abs(d - request.duration)
                )
                if _duration != request.duration:
                    log.warning(
                        "duration=%d 不在合法范围 %s，已自动校正为 %d",
                        request.duration,
                        _VALID_DURATIONS,
                        _duration,
                    )

                payload: Dict[str, Any] = {
                    "duration": _duration,
                    "generateAudio": request.generate_audio,
                    "generationMetadata": {"module": module},
                    "modelId": request.model_id,
                    "modelVersion": request.model_version,
                    "negativePrompt": negative_prompt,
                    "output": {"storeInputs": True},
                    "prompt": request.prompt,
                    "size": {"height": request.height, "width": request.width},
                }

                # 图生视频：通过 referenceBlobs 引用已上传图片的 blob ID
                if blob_id:
                    payload["referenceBlobs"] = [
                        {
                            "id": blob_id,
                            "promptReference": 1,
                            "usage": "general",
                        }
                    ]

                # 2. 提交视频生成任务
                async with session.post(
                    FIREFLY_CONFIG["VIDEO_SUBMIT_URL"],
                    headers=self._build_headers(),
                    json=payload,
                    timeout=submit_timeout,
                ) as resp:
                    if resp.status == 401:
                        self.deactivate(reason="Token 已失效（视频提交 401）")
                        return VideoGenerationResult(
                            success=False,
                            error_code="token_expired",
                            error_message="Firefly Token 已失效，功能已自动关闭，请管理员重新激活。",
                        )
                    if not resp.ok:
                        err_body = await resp.text()
                        log.error(
                            "视频提交失败 status=%d body=%s payload=%s",
                            resp.status,
                            err_body[:800],
                            str(payload)[:500],
                        )
                    resp.raise_for_status()

                    body_text = await resp.text()
                    log.info(
                        "视频提交响应 status=%d headers=%s body=%s",
                        resp.status,
                        dict(resp.headers),
                        body_text[:500],
                    )

                    import json as _json

                    try:
                        body = _json.loads(body_text)
                    except Exception:
                        body = {}

                    # 优先从响应头取，再从响应体 links.result.href 取
                    poll_url = resp.headers.get("x-override-status-link")
                    if not poll_url:
                        poll_url = (
                            body.get("links", {}).get("result", {}).get("href")
                            or body.get("statusUrl")
                            or body.get("jobUrl")
                            or body.get("status_url")
                        )

                    if not poll_url:
                        log.error("视频提交响应中找不到轮询地址，响应体：%s", body)
                        return VideoGenerationResult(
                            success=False,
                            error_code="no_poll_url",
                            error_message="Firefly 未返回任务轮询地址，请稍后再试。",
                        )

                    log.info("视频任务已提交，轮询地址：%s", poll_url)

                # 3. 轮询直到完成
                result_data = await self._poll_until_done(
                    session,
                    poll_url,
                    max_wait=FIREFLY_CONFIG["VIDEO_MAX_WAIT"],
                    task_label="视频生成",
                )

                # 4. 提取视频 URL
                video_url = self._extract_video_url(result_data)
                if not video_url:
                    return VideoGenerationResult(
                        success=False,
                        error_code="no_video_url",
                        error_message="Firefly 任务完成但未找到视频 URL。",
                    )

                # 5. 下载视频字节
                video_bytes = await self._download_bytes(session, video_url, "视频")

                elapsed = (
                    int(time.monotonic() - self._video_started_at)
                    if self._video_started_at
                    else 0
                )
                log.info(
                    "Firefly 视频生成成功，耗时约 %ds，大小：%s bytes",
                    elapsed,
                    len(video_bytes) if video_bytes else "未知（仅 URL）",
                )

                return VideoGenerationResult(
                    success=True,
                    video_bytes=video_bytes,
                    video_url=video_url,  # 始终保留预签名 URL，供文件过大时降级发送
                    mime_type="video/mp4",
                    metadata={
                        "width": request.width,
                        "height": request.height,
                        "duration": request.duration,
                        "model": f"{request.model_id}-{request.model_version}",
                        "elapsed_seconds": elapsed,
                    },
                )

        except FireflyTokenExpiredError:
            return VideoGenerationResult(
                success=False,
                error_code="token_expired",
                error_message="Firefly Token 已失效，功能已自动关闭，请管理员重新激活。",
            )
        except TimeoutError as exc:
            log.warning("Firefly 视频生成超时：%s", exc)
            return VideoGenerationResult(
                success=False,
                error_code="timeout",
                error_message=str(exc),
            )
        except RuntimeError as exc:
            log.error("Firefly 视频任务服务端失败：%s", exc)
            return VideoGenerationResult(
                success=False,
                error_code="generation_failed",
                error_message=str(exc),
            )
        except Exception as exc:
            log.error("Firefly 视频生成发生未知错误", exc_info=True)
            return VideoGenerationResult(
                success=False,
                error_code="unknown_error",
                error_message=f"视频生成失败：{exc}",
            )

    # ------------------------------------------------------------------
    # 图片上传（图生视频前置步骤）
    # ------------------------------------------------------------------

    async def _upload_image_blob(
        self,
        session: aiohttp.ClientSession,
        image_bytes: bytes,
        mime_type: str = "image/png",
    ) -> str:
        """
        将图片字节上传到 Firefly 存储，返回服务器分配的 blob UUID。

        端点：POST https://firefly-3p.ff.adobe.io/v2/storage/image
        请求体：原始图片二进制，Content-Type 与图片格式一致。
        响应体：{"images":[{"id":"<uuid>"}]}
        """
        headers = self._build_headers()
        headers["Content-Type"] = mime_type  # 覆盖默认的 application/json

        upload_timeout = aiohttp.ClientTimeout(total=FIREFLY_CONFIG["SUBMIT_TIMEOUT"])

        async with session.post(
            FIREFLY_CONFIG["IMAGE_UPLOAD_URL"],
            headers=headers,
            data=image_bytes,
            timeout=upload_timeout,
        ) as resp:
            if resp.status == 401:
                self.deactivate(reason="Token 已失效（图片上传 401）")
                raise FireflyTokenExpiredError()
            resp.raise_for_status()

            body = await resp.json(content_type=None)
            log.info("图片上传响应：%s", body)

            try:
                blob_id: str = body["images"][0]["id"]
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(
                    f"图片上传成功但响应格式异常，无法提取 blob ID：{body}"
                ) from exc

            log.info("图片上传成功，blob_id=%s", blob_id)
            return blob_id

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _map_aspect_ratio(self, aspect_ratio: str) -> tuple[int, int]:
        """将宽高比字符串映射为像素尺寸（图片生成用）。"""
        mapping = {
            "1:1": (1024, 1024),
            "3:4": (768, 1024),
            "4:3": (1024, 768),
            "9:16": (720, 1280),
            "16:9": (1280, 720),
        }
        return mapping.get(aspect_ratio, (1024, 1024))

    def _extract_image_url(self, data: Dict[str, Any]) -> Optional[str]:
        """从轮询成功响应中提取图片 URL，兼容多种可能的响应结构。"""
        try:
            outputs = data.get("outputs") or data.get("result", {}).get("outputs", [])
            if isinstance(outputs, list) and outputs:
                first = outputs[0]
                image_obj = first.get("image", {})
                return (
                    image_obj.get("presignedUrl")
                    or image_obj.get("url")
                    or first.get("presignedUrl")
                    or first.get("url")
                )
        except Exception:
            pass
        return data.get("presignedUrl") or data.get("url") or data.get("imageUrl")

    def _extract_video_url(self, data: Dict[str, Any]) -> Optional[str]:
        """从轮询成功响应中提取视频 URL，兼容多种可能的响应结构。"""
        try:
            outputs = data.get("outputs") or data.get("result", {}).get("outputs", [])
            if isinstance(outputs, list) and outputs:
                first = outputs[0]
                video_obj = first.get("video", {})
                return (
                    video_obj.get("presignedUrl")
                    or video_obj.get("url")
                    or first.get("presignedUrl")
                    or first.get("url")
                )
        except Exception:
            pass
        return data.get("presignedUrl") or data.get("url") or data.get("videoUrl")

    async def _download_bytes(
        self,
        session: aiohttp.ClientSession,
        url: str,
        label: str,
    ) -> Optional[bytes]:
        """下载 URL 内容为字节，失败时返回 None。"""
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=FIREFLY_CONFIG["DOWNLOAD_TIMEOUT"]),
            ) as resp:
                resp.raise_for_status()
                data = await resp.read()
                log.debug("%s 下载完成，大小：%d bytes", label, len(data))
                return data
        except Exception as exc:
            log.warning("%s 下载失败：%s", label, exc)
            return None


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

firefly_web_provider = FireflyWebProvider()
