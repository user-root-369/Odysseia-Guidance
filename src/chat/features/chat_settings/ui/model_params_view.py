# -*- coding: utf-8 -*-
"""
模型参数设置视图
用于在 Discord 中配置不同 AI 模型的生成参数
"""

import discord
from discord.ui import View, Button, Select, Modal, TextInput
from discord import (
    ButtonStyle,
    SelectOption,
    Interaction,
)
from typing import Optional, Dict, Any, List, Callable, Awaitable

from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)
from src.chat.config.model_params import (
    ModelParams,
    SupportedParam,
    PROVIDER_SUPPORTED_PARAMS,
)


class ModelParamsModal(Modal):
    """模型参数编辑模态框 - 根据模型提供商动态显示支持的参数"""

    def __init__(
        self,
        model_name: str,
        current_params: ModelParams,
        on_save_callback: Callable[[Interaction, str, Dict[str, Any]], Awaitable[None]],
    ):
        self.model_name = model_name
        self.current_params = current_params
        self.on_save_callback = on_save_callback
        self.supported_params = current_params.get_supported_params()

        super().__init__(title=f"编辑 {model_name} 参数")

        # 温度参数 - 所有模型都支持
        self.temperature_input = TextInput(
            label="Temperature (0.0-2.0)",
            placeholder="控制随机性，越高越有创意",
            default=str(current_params.temperature),
            custom_id="temperature",
            required=True,
            min_length=1,
            max_length=5,
        )
        self.add_item(self.temperature_input)

        # Top-p 参数 - 所有模型都支持
        self.top_p_input = TextInput(
            label="Top-p (0.0-1.0)",
            placeholder="核采样参数",
            default=str(current_params.top_p),
            custom_id="top_p",
            required=True,
            min_length=1,
            max_length=5,
        )
        self.add_item(self.top_p_input)

        # Top-k 参数 - 仅 Gemini/Anthropic 支持
        if SupportedParam.TOP_K in self.supported_params:
            top_k_value = (
                current_params.top_k if current_params.top_k is not None else 40
            )
            self.top_k_input = TextInput(
                label="Top-k (整数，Gemini/Anthropic)",
                placeholder="Top-k 采样参数",
                default=str(top_k_value),
                custom_id="top_k",
                required=False,
                min_length=1,
                max_length=5,
            )
            self.add_item(self.top_k_input)
        else:
            self.top_k_input = None

        # 存在惩罚 - 仅 DeepSeek/OpenAI 支持
        if SupportedParam.PRESENCE_PENALTY in self.supported_params:
            presence_value = (
                current_params.presence_penalty
                if current_params.presence_penalty is not None
                else 0.0
            )
            self.presence_penalty_input = TextInput(
                label="Presence Penalty (-2.0 to 2.0)",
                placeholder="存在惩罚，减少重复内容",
                default=str(presence_value),
                custom_id="presence_penalty",
                required=False,
                min_length=1,
                max_length=5,
            )
            self.add_item(self.presence_penalty_input)
        else:
            self.presence_penalty_input = None

        # 频率惩罚 - 仅 DeepSeek/OpenAI 支持
        if SupportedParam.FREQUENCY_PENALTY in self.supported_params:
            frequency_value = (
                current_params.frequency_penalty
                if current_params.frequency_penalty is not None
                else 0.0
            )
            self.frequency_penalty_input = TextInput(
                label="Frequency Penalty (-2.0 to 2.0)",
                placeholder="频率惩罚，减少重复用词",
                default=str(frequency_value),
                custom_id="frequency_penalty",
                required=False,
                min_length=1,
                max_length=5,
            )
            self.add_item(self.frequency_penalty_input)
        else:
            self.frequency_penalty_input = None

        # 最大输出 token - 所有模型都支持
        self.max_tokens_input = TextInput(
            label="Max Output Tokens",
            placeholder="最大输出 token 数",
            default=str(current_params.max_output_tokens),
            custom_id="max_output_tokens",
            required=True,
            min_length=1,
            max_length=6,
        )
        self.add_item(self.max_tokens_input)

    async def on_submit(self, interaction: Interaction):
        """提交时解析参数并回调"""
        try:
            params: Dict[str, Any] = {
                "provider": self.current_params.provider,
            }

            # 解析基础参数
            params["temperature"] = float(self.temperature_input.value)
            params["top_p"] = float(self.top_p_input.value)
            params["max_output_tokens"] = int(self.max_tokens_input.value)

            # 解析可选参数
            if self.top_k_input is not None and self.top_k_input.value:
                params["top_k"] = int(self.top_k_input.value)

            if (
                self.presence_penalty_input is not None
                and self.presence_penalty_input.value
            ):
                params["presence_penalty"] = float(self.presence_penalty_input.value)

            if (
                self.frequency_penalty_input is not None
                and self.frequency_penalty_input.value
            ):
                params["frequency_penalty"] = float(self.frequency_penalty_input.value)

            # 验证参数范围
            if not (0.0 <= params["temperature"] <= 2.0):
                await interaction.response.send_message(
                    "❌ Temperature 必须在 0.0 到 2.0 之间", ephemeral=True
                )
                return

            if not (0.0 <= params["top_p"] <= 1.0):
                await interaction.response.send_message(
                    "❌ Top-p 必须在 0.0 到 1.0 之间", ephemeral=True
                )
                return

            if "top_k" in params and params["top_k"] < 1:
                await interaction.response.send_message(
                    "❌ Top-k 必须是正整数", ephemeral=True
                )
                return

            if "presence_penalty" in params and not (
                -2.0 <= params["presence_penalty"] <= 2.0
            ):
                await interaction.response.send_message(
                    "❌ Presence Penalty 必须在 -2.0 到 2.0 之间", ephemeral=True
                )
                return

            if "frequency_penalty" in params and not (
                -2.0 <= params["frequency_penalty"] <= 2.0
            ):
                await interaction.response.send_message(
                    "❌ Frequency Penalty 必须在 -2.0 到 2.0 之间", ephemeral=True
                )
                return

            if params["max_output_tokens"] < 1:
                await interaction.response.send_message(
                    "❌ Max Output Tokens 必须是正整数", ephemeral=True
                )
                return

            await self.on_save_callback(interaction, self.model_name, params)

        except ValueError as e:
            await interaction.response.send_message(
                f"❌ 参数格式错误: {e}", ephemeral=True
            )


class ModelParamsView(View):
    """模型参数设置视图"""

    def __init__(self, on_back_callback: Callable[[Interaction], Awaitable[None]]):
        super().__init__(timeout=300)
        self.on_back_callback = on_back_callback
        self.selected_model: Optional[str] = None
        self.model_params: Dict[str, ModelParams] = {}
        self.available_models: List[str] = []
        self.message: Optional[discord.Message] = None

    async def _initialize(self):
        """异步初始化"""
        # 获取可用模型列表
        self.available_models = chat_settings_service.get_available_ai_models()
        # 获取所有模型参数
        self.model_params = await chat_settings_service.get_all_model_params()
        self._create_view_items()

    @classmethod
    async def create(
        cls, on_back_callback: Callable[[Interaction], Awaitable[None]]
    ) -> "ModelParamsView":
        """工厂方法，用于异步创建和初始化 View"""
        view = cls(on_back_callback)
        await view._initialize()
        return view

    def _create_view_items(self):
        """创建视图组件"""
        self.clear_items()

        # 模型选择器
        model_options = []
        for model in self.available_models[:25]:  # Discord 最多 25 个选项
            is_selected = self.selected_model == model
            model_options.append(
                SelectOption(
                    label=model,
                    value=model,
                    default=is_selected,
                )
            )

        if model_options:
            model_select = Select(
                placeholder="选择要配置的模型...",
                options=model_options,
                custom_id="model_select",
                row=0,
            )
            model_select.callback = self._on_model_select
            self.add_item(model_select)

        # 如果选中了模型，显示当前参数和编辑按钮
        if self.selected_model:
            # 编辑参数按钮
            edit_button = Button(
                label=f"📝 编辑 {self.selected_model} 参数",
                style=ButtonStyle.primary,
                custom_id="edit_params",
                row=1,
            )
            edit_button.callback = self._on_edit_params
            self.add_item(edit_button)

            # 重置参数按钮
            reset_button = Button(
                label="🔄 重置为默认",
                style=ButtonStyle.danger,
                custom_id="reset_params",
                row=1,
            )
            reset_button.callback = self._on_reset_params
            self.add_item(reset_button)

        # 返回按钮
        back_button = Button(
            label="🔙 返回",
            style=ButtonStyle.secondary,
            custom_id="back",
            row=4,
        )
        back_button.callback = self._on_back
        self.add_item(back_button)

    def _get_params_display(self, params: ModelParams) -> str:
        """根据模型提供商生成参数显示文本"""
        lines = [
            f"**Temperature:** {params.temperature}",
            f"**Top-p:** {params.top_p}",
            f"**Max Tokens:** {params.max_output_tokens}",
        ]

        supported = params.get_supported_params()

        if SupportedParam.TOP_K in supported:
            top_k = params.top_k if params.top_k is not None else "未设置"
            lines.append(f"**Top-k:** {top_k}")

        if SupportedParam.PRESENCE_PENALTY in supported:
            presence = (
                params.presence_penalty
                if params.presence_penalty is not None
                else "未设置"
            )
            lines.append(f"**Presence Penalty:** {presence}")

        if SupportedParam.FREQUENCY_PENALTY in supported:
            frequency = (
                params.frequency_penalty
                if params.frequency_penalty is not None
                else "未设置"
            )
            lines.append(f"**Frequency Penalty:** {frequency}")

        return "\n".join(lines)

    def _get_provider_display(self, provider: str) -> str:
        """获取提供商显示名称和支持的参数说明"""
        provider_info = {
            "deepseek": "DeepSeek (支持: temp, top_p, presence_penalty, frequency_penalty)",
            "gemini": "Gemini (支持: temp, top_p, top_k)",
            "openai": "OpenAI (支持: temp, top_p, presence_penalty, frequency_penalty)",
            "anthropic": "Anthropic (支持: temp, top_p, top_k)",
            "default": "默认 (支持: temp, top_p)",
        }
        return provider_info.get(provider, provider)

    def _get_params_embed(self) -> discord.Embed:
        """创建参数显示嵌入"""
        embed = discord.Embed(
            title="🎛️ 模型参数设置",
            description="选择一个模型来配置其生成参数\n\n**注意：不同模型提供商支持的参数不同**",
            color=discord.Color.blue(),
        )

        if self.selected_model:
            params = self.model_params.get(self.selected_model)
            if params is None:
                params = ModelParams(provider="default")

            embed.add_field(
                name=f"📊 当前模型: {self.selected_model}",
                value=self._get_params_display(params),
                inline=False,
            )

            embed.add_field(
                name="提供商",
                value=self._get_provider_display(params.provider),
                inline=False,
            )

        # 显示所有模型的参数概览
        params_overview = []
        for model, params in list(self.model_params.items())[:10]:
            temp = params.temperature
            provider = params.provider
            params_overview.append(f"• **{model}**: temp={temp} ({provider})")

        if params_overview:
            embed.add_field(
                name="📋 参数概览",
                value="\n".join(params_overview),
                inline=False,
            )

        return embed

    async def _on_model_select(self, interaction: Interaction):
        """模型选择回调"""
        select = [item for item in self.children if isinstance(item, Select)][0]
        self.selected_model = select.values[0]
        self._create_view_items()
        await interaction.response.edit_message(
            embed=self._get_params_embed(), view=self
        )

    async def _on_edit_params(self, interaction: Interaction):
        """编辑参数回调"""
        if not self.selected_model:
            await interaction.response.send_message("请先选择一个模型", ephemeral=True)
            return

        current_params = self.model_params.get(self.selected_model)
        if current_params is None:
            current_params = ModelParams(provider="default")

        modal = ModelParamsModal(
            model_name=self.selected_model,
            current_params=current_params,
            on_save_callback=self._on_save_params,
        )

        await interaction.response.send_modal(modal)

    async def _on_save_params(
        self, interaction: Interaction, model_name: str, params: Dict[str, Any]
    ):
        """保存参数回调"""
        await chat_settings_service.set_model_params(
            model_name=model_name,
            temperature=params["temperature"],
            top_p=params["top_p"],
            top_k=params.get("top_k"),
            max_output_tokens=params["max_output_tokens"],
            presence_penalty=params.get("presence_penalty"),
            frequency_penalty=params.get("frequency_penalty"),
            provider=params.get("provider", "default"),
        )

        # 更新本地缓存
        self.model_params[model_name] = ModelParams.from_dict(params)

        await interaction.response.send_message(
            f"✅ 已更新 **{model_name}** 的参数配置", ephemeral=True
        )

        # 刷新视图
        self._create_view_items()
        if self.message:
            await self.message.edit(embed=self._get_params_embed(), view=self)

    async def _on_reset_params(self, interaction: Interaction):
        """重置参数回调"""
        if not self.selected_model:
            await interaction.response.send_message("请先选择一个模型", ephemeral=True)
            return

        await chat_settings_service.reset_model_params(self.selected_model)

        # 更新本地缓存
        from src.chat.config.model_params import get_model_params

        self.model_params[self.selected_model] = get_model_params(self.selected_model)

        self._create_view_items()
        await interaction.response.edit_message(
            embed=self._get_params_embed(), view=self
        )

    async def _on_back(self, interaction: Interaction):
        """返回回调"""
        await self.on_back_callback(interaction)
