# -*- coding: utf-8 -*-
"""
Firefly Discord Cog

提供以下斜杠命令：
  /firefly enable <token>  — 仅开发者，注入 Token 并启用功能
  /firefly disable         — 仅开发者，手动关闭功能
  /firefly status          — 仅开发者，查看当前状态
  /draw_ff <prompt> [...]  — 仅开发者，触发 Firefly 图片生成
  /video_ff <prompt> [...] — 仅开发者，触发 Firefly 视频生成
"""

from __future__ import annotations

import io
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src import config
from src.chat.features.firefly.config.firefly_config import FIREFLY_CONFIG
from src.chat.features.firefly.providers.firefly_web_provider import (
    VideoGenerationRequest,
    firefly_web_provider,
)
from src.chat.features.image_generation.providers.base import ImageGenerationRequest

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 权限检查
# ---------------------------------------------------------------------------


def _is_developer(user_id: int) -> bool:
    return user_id in config.DEVELOPER_USER_IDS


async def _check_developer(interaction: discord.Interaction) -> bool:
    if _is_developer(interaction.user.id):
        return True
    await interaction.response.send_message("此命令仅限开发者使用。", ephemeral=True)
    return False


# ---------------------------------------------------------------------------
# /firefly 命令组（独立 Group 子类，discord.py 推荐写法）
# ---------------------------------------------------------------------------


class FireflyGroup(app_commands.Group):
    """管理 Adobe Firefly 功能（仅开发者）"""

    def __init__(self) -> None:
        super().__init__(
            name="firefly", description="管理 Adobe Firefly 功能（仅开发者）"
        )

    @app_commands.command(name="enable", description="注入 Token 并启用 Firefly 功能")
    @app_commands.describe(
        token="从浏览器 DevTools 抓取的 Bearer Token（不含 'Bearer ' 前缀）"
    )
    async def enable(self, interaction: discord.Interaction, token: str) -> None:
        if not await _check_developer(interaction):
            return

        if not FIREFLY_CONFIG["ENABLED"]:
            await interaction.response.send_message(
                "Firefly 功能已在配置中全局禁用。", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        result = await firefly_web_provider.activate(token)

        if result["success"]:
            remaining = result["remaining_seconds"]
            hours, remainder = divmod(remaining, 3600)
            minutes = remainder // 60
            time_str = (
                f"{hours} 小时 {minutes} 分钟" if hours > 0 else f"{minutes} 分钟"
            )
            await interaction.followup.send(
                f"✅ Firefly 已激活。\nToken 验证成功，剩余有效期：**{time_str}**。",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"⚠️ Firefly 已注入 Token，但验证接口返回错误：{result.get('error')}\n"
                "Token 可能已失效，请确认后重新抓包。",
                ephemeral=True,
            )

    @app_commands.command(name="disable", description="手动关闭 Firefly 功能")
    async def disable(self, interaction: discord.Interaction) -> None:
        if not await _check_developer(interaction):
            return

        if firefly_web_provider.is_video_generating:
            await interaction.response.send_message(
                "⚠️ 当前有视频任务正在生成，无法关闭。请等待视频完成后再禁用。",
                ephemeral=True,
            )
            return

        firefly_web_provider.deactivate(reason="开发者手动禁用")
        await interaction.response.send_message("🔴 Firefly 已关闭。", ephemeral=True)

    @app_commands.command(name="status", description="查看 Firefly 当前状态")
    async def status(self, interaction: discord.Interaction) -> None:
        if not await _check_developer(interaction):
            return

        status = firefly_web_provider.get_status()
        active_str = "✅ 已激活" if status["active"] else "🔴 未激活"
        lines = ["**Firefly 状态**", f"Token 状态：{active_str}"]

        if status["active"]:
            remaining = status.get("token_remaining_seconds")
            if remaining is not None:
                hours, remainder = divmod(remaining, 3600)
                minutes = remainder // 60
                time_str = (
                    f"{hours} 小时 {minutes} 分钟" if hours > 0 else f"{minutes} 分钟"
                )
                warn = " ⚠️ 即将过期，请准备重新抓包！" if remaining < 1800 else ""
                lines.append(f"Token 剩余有效期：**{time_str}**{warn}")
            else:
                age = status.get("token_age_seconds", 0)
                m, s = divmod(age, 60)
                lines.append(f"Token 已使用：{m} 分 {s} 秒（过期时间未知）")

        if status["video_generating"]:
            elapsed = status.get("video_elapsed_seconds", 0)
            preview = status.get("video_prompt_preview", "")
            lines.append(f'视频生成：🔄 进行中（"{preview}"，已用时 {elapsed} 秒）')
        else:
            lines.append("视频生成：⚡ 空闲")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------


class FireflyCog(commands.Cog):
    """Adobe Firefly Web 功能命令组。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # 把命令组挂到 Cog 上
        self.firefly_group = FireflyGroup()

    # ------------------------------------------------------------------
    # /draw_ff — 图片生成命令（仅开发者）
    # ------------------------------------------------------------------

    @app_commands.command(
        name="draw_ff", description="使用 Firefly 生成图片（仅开发者）"
    )
    @app_commands.describe(
        prompt="图片内容描述",
        aspect_ratio="宽高比，可选：1:1 / 4:3 / 3:4 / 16:9 / 9:16",
    )
    async def draw_ff(
        self,
        interaction: discord.Interaction,
        prompt: str,
        aspect_ratio: str = "1:1",
    ) -> None:
        if not await _check_developer(interaction):
            return

        if not firefly_web_provider.is_active:
            await interaction.response.send_message(
                "Firefly 功能未激活，请先执行 `/firefly enable <token>`。",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        request = ImageGenerationRequest(prompt=prompt, aspect_ratio=aspect_ratio)
        result = await firefly_web_provider.generate_image(request)

        if not result.success or not result.image_bytes:
            await interaction.followup.send(
                f"图片生成失败：{result.error_message}", ephemeral=True
            )
            return

        file = discord.File(
            io.BytesIO(result.image_bytes), filename="firefly_image.png"
        )
        await interaction.followup.send(
            f"✅ 图片生成成功！提示词：{prompt[:80]}",
            file=file,
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # /video_ff — 视频生成命令（仅开发者）
    # ------------------------------------------------------------------

    @app_commands.command(
        name="video_ff", description="使用 Firefly 生成视频（仅开发者）"
    )
    @app_commands.describe(
        prompt="视频内容描述",
        image="上传参考图片以进行图生视频（可选）",
        width="视频宽度像素（默认 1280）",
        height="视频高度像素（默认 720）",
        duration="视频时长秒数（默认 10）",
        negative_prompt="不希望出现的内容（可选）",
    )
    async def video_ff(
        self,
        interaction: discord.Interaction,
        prompt: str,
        image: Optional[discord.Attachment] = None,
        width: int = FIREFLY_CONFIG["VIDEO_DEFAULT_WIDTH"],
        height: int = FIREFLY_CONFIG["VIDEO_DEFAULT_HEIGHT"],
        duration: int = FIREFLY_CONFIG["VIDEO_DEFAULT_DURATION"],
        negative_prompt: Optional[str] = None,
    ) -> None:
        if not await _check_developer(interaction):
            return

        if not firefly_web_provider.is_active:
            await interaction.response.send_message(
                "Firefly 功能未激活，请先执行 `/firefly enable <token>`。",
                ephemeral=True,
            )
            return

        if firefly_web_provider.is_video_generating:
            s = firefly_web_provider.get_status()
            preview = s.get("video_prompt_preview", "")
            elapsed = s.get("video_elapsed_seconds", 0)
            await interaction.response.send_message(
                f'⚠️ 当前视频任务正在生成（"{preview}"，已用时 {elapsed} 秒），请等待完成后再试。',
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        image_bytes: Optional[bytes] = None
        image_mime: str = "image/jpeg"
        if image is not None:
            if not (image.content_type and image.content_type.startswith("image/")):
                await interaction.followup.send("附件必须是图片文件。", ephemeral=True)
                return
            try:
                image_bytes = await image.read()
                image_mime = image.content_type
                log.info(
                    "图生视频：已下载图片 %s，大小 %d bytes",
                    image.filename,
                    len(image_bytes),
                )
            except Exception as exc:
                log.error("下载图片附件失败：%s", exc)
                await interaction.followup.send(f"图片下载失败：{exc}", ephemeral=True)
                return

        mode_str = "图生视频" if image_bytes else "文生视频"
        await interaction.followup.send(
            f"🎬 {mode_str}任务已开始，正在生成中，预计需要 1-3 分钟……",
            ephemeral=True,
        )

        request = VideoGenerationRequest(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            duration=duration,
            image_bytes=image_bytes,
            image_mime_type=image_mime,
        )
        result = await firefly_web_provider.generate_video(request)

        if not result.success:
            await interaction.followup.send(
                f"视频生成失败：{result.error_message}", ephemeral=True
            )
            return

        if result.video_bytes:
            if len(result.video_bytes) <= 8 * 1024 * 1024:
                file = discord.File(
                    io.BytesIO(result.video_bytes), filename="firefly_video.mp4"
                )
                await interaction.followup.send(
                    f"✅ 视频生成成功！提示词：{prompt[:60]}",
                    file=file,
                    ephemeral=True,
                )
            else:
                url = result.video_url or "（无法提供链接）"
                size_mb = len(result.video_bytes) / 1024 / 1024
                await interaction.followup.send(
                    f"✅ 视频生成成功，但文件较大（{size_mb:.1f} MB），无法直接上传。\n"
                    f"视频链接（有效期有限）：{url}",
                    ephemeral=True,
                )
        elif result.video_url:
            await interaction.followup.send(
                f"✅ 视频生成成功！提示词：{prompt[:60]}\n"
                f"视频链接（有效期有限）：{result.video_url}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "视频生成完成，但无法获取视频内容，请稍后重试。", ephemeral=True
            )


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------


async def setup(bot: commands.Bot) -> None:
    cog = FireflyCog(bot)
    await bot.add_cog(cog)
    # 手动把命令组注册到命令树
    bot.tree.add_command(cog.firefly_group)
    log.info("FireflyCog 已加载，/firefly 命令组已注册。")
