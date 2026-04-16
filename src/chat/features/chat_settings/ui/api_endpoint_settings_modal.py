# -*- coding: utf-8 -*-
"""
API 端点配置 Modal

允许管理员直接在 Discord 界面填写 OpenAI 兼容端点的 URL、API Key
和可选显示名称，保存后立即热重载 Provider，无需重启 bot。

安全说明：
- Modal 交互为 ephemeral（仅触发者可见），通过 HTTPS 加密传输
- API Key 以明文存入 SQLite global_settings 表，安全级别与 .env 文件相同
- 日志中的 API Key 已做脱敏处理（仅打印前4位+****+后4位）
- 访问权限由上层 is_authorized 控制
"""

import logging
import discord
from discord import Interaction
from discord.ui import Modal, TextInput

log = logging.getLogger(__name__)

_URL_PLACEHOLDER = "例：https://openrouter.ai/api/v1  或  https://your-host.com/v1"
_KEY_PLACEHOLDER = "留空表示保留当前 Key 不变"


class ApiEndpointSettingsModal(Modal, title="🔌 OpenAI 兼容端点配置"):
    """
    三个输入字段：
    1. API 基础 URL（必填）
    2. API Key（可选，留空则保留当前值）
    3. 显示名称（可选）
    """

    api_url = TextInput(
        label="API 基础 URL",
        placeholder=_URL_PLACEHOLDER,
        required=True,
        max_length=500,
        style=discord.TextStyle.short,
    )

    api_key = TextInput(
        label="API Key（留空保留当前值）",
        placeholder=_KEY_PLACEHOLDER,
        required=False,
        max_length=500,
        style=discord.TextStyle.short,
    )

    display_name = TextInput(
        label="显示名称（可选）",
        placeholder="例：OpenRouter / Together AI / 自建代理",
        required=False,
        max_length=50,
        style=discord.TextStyle.short,
    )

    def __init__(self, current_url: str = "", current_name: str = ""):
        super().__init__()
        # 预填当前 URL 和名称（Key 不回显）
        if current_url:
            self.api_url.default = current_url
        if current_name and current_name != "OpenAI 兼容":
            self.display_name.default = current_name

    async def on_submit(self, interaction: Interaction) -> None:
        """处理表单提交：验证 → 保存 → 热重载 → 触发模型发现 → 反馈。"""
        await interaction.response.defer(ephemeral=True)

        url = self.api_url.value.strip().rstrip("/")
        raw_key = self.api_key.value.strip()
        name = self.display_name.value.strip() or "OpenAI 兼容"

        # --- URL 基本验证 ---
        if not (url.startswith("http://") or url.startswith("https://")):
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ URL 格式错误",
                    description=f"URL 必须以 `http://` 或 `https://` 开头。\n收到：`{url}`",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # --- 保存并热重载 ---
        from src.chat.features.chat_settings.services.chat_settings_service import (
            chat_settings_service,
        )

        # raw_key 为空字符串时传 None，service 层会保留当前值
        api_key_to_save = raw_key if raw_key else None

        try:
            await chat_settings_service.save_openai_compatible_config(
                url=url,
                api_key=api_key_to_save,
                name=name,
            )
        except Exception as e:
            log.error(f"保存 OpenAI 兼容端点配置失败: {e}", exc_info=True)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ 保存失败",
                    description=f"保存时发生错误：`{e}`",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # --- 触发模型发现，获取连接状态 ---
        discovery_info = await self._probe_endpoint(url)

        # --- 构建确认 Embed ---
        key_status = "已更新" if raw_key else "保留原值（未更改）"
        masked_url = url if len(url) <= 60 else url[:57] + "..."

        embed = discord.Embed(
            title="✅ API 端点配置已保存",
            color=discord.Color.green(),
        )
        embed.add_field(name="显示名称", value=f"`{name}`", inline=True)
        embed.add_field(name="API URL", value=f"`{masked_url}`", inline=False)
        embed.add_field(name="API Key", value=key_status, inline=True)
        embed.add_field(name="连接状态", value=discovery_info, inline=False)
        embed.set_footer(
            text="注意：重启 bot 后将恢复使用 .env 中的配置。"
            "如需永久生效，请同步更新 .env 文件中的 OPENAI_COMPATIBLE_URL / OPENAI_COMPATIBLE_API_KEY。"
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def on_error(self, interaction: Interaction, error: Exception) -> None:
        log.error(f"ApiEndpointSettingsModal 异常: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "表单处理时发生未知错误，请查看日志。", ephemeral=True
            )

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    async def _probe_endpoint(self, url: str) -> str:
        """
        对新配置的端点触发一次 /models 探测，返回人类可读的状态字符串。
        失败时不抛异常，只返回带说明的错误信息。
        """
        from src.chat.services.ai.model_discovery import model_discovery_service

        try:
            result = await model_discovery_service.discover_provider(
                "openai_compatible"
            )
            if result.source == "remote" and result.success:
                model_ids = [m.id for m in result.models[:5]]
                suffix = (
                    f" …共 {len(result.models)} 个" if len(result.models) > 5 else ""
                )
                return f"✅ 远端探测成功\n`{', '.join(model_ids)}{suffix}`"
            elif result.source == "unavailable":
                return f"❌ Provider 不可用：{result.error or '未知原因'}"
            else:
                reason = result.error or "端点不支持 /models 接口"
                return f"⚠️ 回退静态配置（{reason[:80]}）\n可手动在模型列表中选择模型"
        except Exception as e:
            return f"⚠️ 探测时发生错误：`{type(e).__name__}: {e}`"
