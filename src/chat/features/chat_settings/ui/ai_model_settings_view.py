# -*- coding: utf-8 -*-
"""
AI 模型设置视图

提供 Provider + Model 双下拉选择界面
"""

import discord
from discord.ui import View, Select, Button
from discord import ButtonStyle, Interaction, SelectOption
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.chat.services.ai.config.models import ModelConfig


class AIModelSettingsView(View):
    """
    AI 模型设置视图

    通过两个级联下拉框选择模型：
    1. Provider 下拉框 - 选择供应商
    2. Model 下拉框 - 选择该供应商下的模型
    """

    def __init__(
        self,
        current_provider: Optional[str] = None,
        current_model: Optional[str] = None,
    ):
        super().__init__(timeout=300)
        self.selected_provider: Optional[str] = current_provider
        self.selected_model: Optional[str] = current_model
        self.confirmed = False

        # 获取按 Provider 分组的模型
        self._models_by_provider = self._get_models_by_provider()

        # 构建 UI
        self._create_provider_select()
        self._create_model_select()
        self._create_buttons()

    def _get_models_by_provider(self) -> Dict[str, Dict[str, "ModelConfig"]]:
        """
        获取按 Provider 分组的模型配置

        Returns:
            {"provider_name": {"model_name": ModelConfig, ...}, ...}
        """
        from src.chat.services.ai.config.models import get_model_configs

        model_configs = get_model_configs()
        grouped: Dict[str, Dict[str, "ModelConfig"]] = {}

        for model_name, config in model_configs.items():
            provider = config.provider or "unknown"
            if provider not in grouped:
                grouped[provider] = {}
            grouped[provider][model_name] = config

        return grouped

    def _get_provider_display_name(self, provider_name: str) -> str:
        """获取 Provider 的显示名称"""
        provider_names = {
            "gemini_official": "📦 Gemini 官方",
            "deepseek": "📦 DeepSeek",
            "openai_compatible": "📦 OpenAI 兼容",
            "unknown": "📦 未知",
        }

        # 自定义 Gemini 端点
        if provider_name.startswith("gemini_custom_"):
            endpoint_name = provider_name.replace("gemini_custom_", "")
            return f"📦 Gemini 自定义 ({endpoint_name})"

        return provider_names.get(provider_name, f"📦 {provider_name}")

    def _create_provider_select(self):
        """创建 Provider 选择下拉框"""
        options = []

        for provider_name in sorted(self._models_by_provider.keys()):
            display_name = self._get_provider_display_name(provider_name)
            is_default = provider_name == self.selected_provider
            options.append(
                SelectOption(
                    label=display_name[:100],  # Discord 限制 100 字符
                    value=provider_name,
                    default=is_default,
                )
            )

        if not options:
            options.append(
                SelectOption(label="无可用 Provider", value="none", default=True)
            )

        self.provider_select = Select(
            placeholder="选择供应商...",
            options=options[:25],  # Discord 限制最多 25 个选项
            custom_id="provider_select",
            row=0,
        )
        self.provider_select.callback = self._on_provider_select
        self.add_item(self.provider_select)

    def _create_model_select(self, provider_name: Optional[str] = None):
        """创建或更新 Model 选择下拉框"""
        # 移除旧的 model_select（如果存在）
        for item in self.children:
            if isinstance(item, Select) and item.custom_id == "model_select":
                self.remove_item(item)
                break

        options = []
        provider = provider_name or self.selected_provider

        if provider and provider in self._models_by_provider:
            models = self._models_by_provider[provider]
            for model_name, config in models.items():
                display_name = config.display_name or model_name
                is_default = model_name == self.selected_model
                options.append(
                    SelectOption(
                        label=display_name[:100],
                        value=model_name,
                        description=config.description[:100]
                        if config.description
                        else None,
                        default=is_default,
                    )
                )

        if not options:
            options.append(
                SelectOption(label="请先选择供应商", value="none", default=True)
            )

        self.model_select = Select(
            placeholder="选择模型...",
            options=options[:25],
            custom_id="model_select",
            row=1,
        )
        self.model_select.callback = self._on_model_select
        self.add_item(self.model_select)

    def _create_buttons(self):
        """创建确认和取消按钮"""
        self.confirm_button = Button(
            label="✅ 确认",
            style=ButtonStyle.green,
            custom_id="confirm",
            row=2,
            disabled=True,  # 初始禁用，选择模型后启用
        )
        self.confirm_button.callback = self._on_confirm
        self.add_item(self.confirm_button)

        self.cancel_button = Button(
            label="❌ 取消",
            style=ButtonStyle.red,
            custom_id="cancel",
            row=2,
        )
        self.cancel_button.callback = self._on_cancel
        self.add_item(self.cancel_button)

    async def _on_provider_select(self, interaction: Interaction):
        """Provider 选择回调"""
        self.selected_provider = self.provider_select.values[0]

        # 重置模型选择
        self.selected_model = None

        # 更新模型下拉框
        self._create_model_select(self.selected_provider)

        # 禁用确认按钮
        self.confirm_button.disabled = True

        await interaction.response.edit_message(view=self)

    async def _on_model_select(self, interaction: Interaction):
        """Model 选择回调"""
        self.selected_model = self.model_select.values[0]

        # 启用确认按钮
        self.confirm_button.disabled = False

        await interaction.response.edit_message(view=self)

    async def _on_confirm(self, interaction: Interaction):
        """确认按钮回调"""
        self.confirmed = True
        self.stop()

        # 获取模型显示名称
        display_name = self.selected_model or ""
        if (
            self.selected_provider
            and self.selected_provider in self._models_by_provider
        ):
            if (
                self.selected_model
                and self.selected_model
                in self._models_by_provider[self.selected_provider]
            ):
                config = self._models_by_provider[self.selected_provider][
                    self.selected_model
                ]
                display_name = config.display_name or self.selected_model

        provider_display = self._get_provider_display_name(
            self.selected_provider or "unknown"
        )

        embed = discord.Embed(
            title="✅ 模型已更新",
            description=f"供应商: **{provider_display}**\n模型: **{display_name}**",
            color=discord.Color.green(),
        )

        await interaction.response.edit_message(embed=embed, view=None)

    async def _on_cancel(self, interaction: Interaction):
        """取消按钮回调"""
        self.stop()

        embed = discord.Embed(
            title="❌ 已取消",
            description="模型设置未更改",
            color=discord.Color.red(),
        )

        await interaction.response.edit_message(embed=embed, view=None)

    def get_selected_full_model_id(self) -> Optional[str]:
        """
        获取选中的完整模型 ID

        Returns:
            "provider_name:model_name" 或 None
        """
        if self.confirmed and self.selected_provider and self.selected_model:
            return f"{self.selected_provider}:{self.selected_model}"
        return None

    @classmethod
    def parse_full_model_id(
        cls, full_model_id: str
    ) -> tuple[Optional[str], Optional[str]]:
        """
        解析完整模型 ID

        Args:
            full_model_id: "provider_name:model_name" 格式的字符串

        Returns:
            (provider_name, model_name) 元组
        """
        if not full_model_id:
            return None, None

        if ":" in full_model_id:
            parts = full_model_id.split(":", 1)
            return parts[0], parts[1]

        # 旧格式兼容：只有模型名，尝试从配置查找 provider
        from src.chat.services.ai.config.models import get_model_configs

        model_configs = get_model_configs()

        if full_model_id in model_configs:
            return model_configs[full_model_id].provider, full_model_id

        return None, full_model_id
