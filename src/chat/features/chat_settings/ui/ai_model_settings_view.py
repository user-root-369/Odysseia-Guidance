# -*- coding: utf-8 -*-
"""
AI 模型设置视图

提供 Provider + Model 双下拉选择界面，支持模型列表分页（每页 25 个）。
"""

import discord
from discord.ui import View, Select, Button
from discord import ButtonStyle, Interaction, SelectOption
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.chat.services.ai.config.models import ModelConfig

_PAGE_SIZE = 25  # Discord Select 单页上限


class AIModelSettingsView(View):
    """
    AI 模型设置视图

    通过两个级联下拉框选择模型：
    1. Provider 下拉框 - 选择供应商
    2. Model 下拉框 - 选择该供应商下的模型（分页，每页 25 个）

    推荐使用异步工厂方法 `create()` 创建，可获得远端动态拉取的完整模型列表。
    """

    def __init__(
        self,
        current_provider: Optional[str] = None,
        current_model: Optional[str] = None,
        discovered_models: Optional[Dict] = None,
    ):
        super().__init__(timeout=300)
        self.selected_provider: Optional[str] = current_provider
        self.selected_model: Optional[str] = current_model
        self.confirmed = False
        self._model_page: int = 0

        if discovered_models is not None:
            self._models_by_provider = discovered_models
        else:
            self._models_by_provider = self._get_models_by_provider()

        self._rebuild_ui()

    # ------------------------------------------------------------------
    # 异步工厂
    # ------------------------------------------------------------------

    @classmethod
    async def create(
        cls,
        current_provider: Optional[str] = None,
        current_model: Optional[str] = None,
    ) -> "AIModelSettingsView":
        """
        异步工厂：对所有 Provider 执行模型发现（优先远端拉取，超时回退静态配置），
        确保 OpenAI 兼容等动态端点能显示完整模型列表。
        """
        from src.chat.services.ai.config.models import ModelConfig
        from src.chat.services.ai.model_discovery import model_discovery_service

        instance = cls(current_provider=current_provider, current_model=current_model)

        try:
            all_results = await model_discovery_service.discover_all()
            for provider_name, result in all_results.items():
                if not result.models:
                    continue
                provider_models: Dict[str, "ModelConfig"] = {}
                for dm in result.models:
                    provider_models[dm.id] = ModelConfig(
                        display_name=dm.display_name,
                        provider=provider_name,
                        actual_model=dm.id,
                        supports_vision=dm.supports_vision,
                        supports_tools=dm.supports_tools,
                        description=dm.description
                        or ("🌐 远端动态拉取" if dm.source == "remote" else ""),
                    )
                instance._models_by_provider[provider_name] = provider_models
            instance._rebuild_ui()
        except Exception:
            pass

        return instance

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _rebuild_ui(self):
        """清空并重建所有 UI 组件。"""
        self.clear_items()
        self._create_provider_select()  # row 0
        self._create_model_select_paged()  # row 1
        self._create_pagination_buttons()  # row 2（仅超过一页时）
        self._create_action_buttons()  # row 2 或 3

    def _get_current_model_list(self) -> List[str]:
        """返回当前 Provider 下所有模型 ID 的有序列表。"""
        if not self.selected_provider:
            return []
        return list(self._models_by_provider.get(self.selected_provider, {}).keys())

    def _total_pages(self) -> int:
        total = len(self._get_current_model_list())
        return max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)

    def _create_provider_select(self):
        options = []
        for provider_name in sorted(self._models_by_provider.keys()):
            options.append(
                SelectOption(
                    label=self._get_provider_display_name(provider_name)[:100],
                    value=provider_name,
                    default=(provider_name == self.selected_provider),
                )
            )
        if not options:
            options.append(
                SelectOption(label="无可用 Provider", value="none", default=True)
            )

        self.provider_select = Select(
            placeholder="选择供应商...",
            options=options[:25],
            custom_id="provider_select",
            row=0,
        )
        self.provider_select.callback = self._on_provider_select
        self.add_item(self.provider_select)

    def _create_model_select_paged(self):
        """根据当前页码渲染模型下拉框（每页最多 25 个）。"""
        all_models = self._get_current_model_list()
        provider_map = self._models_by_provider.get(self.selected_provider or "", {})
        start = self._model_page * _PAGE_SIZE
        page_models = all_models[start : start + _PAGE_SIZE]

        options = []
        for model_name in page_models:
            config = provider_map.get(model_name)
            display_name = (config.display_name if config else None) or model_name
            description = (
                config.description[:100] if config and config.description else None
            )
            options.append(
                SelectOption(
                    label=display_name[:100],
                    value=model_name,
                    description=description,
                    default=(model_name == self.selected_model),
                )
            )

        if not options:
            options.append(
                SelectOption(label="请先选择供应商", value="none", default=True)
            )

        total = len(all_models)
        if total <= _PAGE_SIZE:
            placeholder = "选择模型..."
        else:
            placeholder = f"选择模型... （第 {self._model_page + 1}/{self._total_pages()} 页，共 {total} 个）"

        self.model_select = Select(
            placeholder=placeholder,
            options=options,
            custom_id="model_select",
            row=1,
        )
        self.model_select.callback = self._on_model_select
        self.add_item(self.model_select)

    def _create_pagination_buttons(self):
        """当模型总数超过一页时，在 row 2 添加翻页按钮。"""
        if self._total_pages() <= 1:
            return

        self.prev_button = Button(
            label="◀ 上一页",
            style=ButtonStyle.secondary,
            custom_id="model_prev",
            row=2,
            disabled=(self._model_page == 0),
        )
        self.prev_button.callback = self._on_prev_page
        self.add_item(self.prev_button)

        self.add_item(
            Button(
                label=f"{self._model_page + 1} / {self._total_pages()}",
                style=ButtonStyle.secondary,
                custom_id="page_indicator",
                row=2,
                disabled=True,
            )
        )

        self.next_button = Button(
            label="下一页 ▶",
            style=ButtonStyle.secondary,
            custom_id="model_next",
            row=2,
            disabled=(self._model_page >= self._total_pages() - 1),
        )
        self.next_button.callback = self._on_next_page
        self.add_item(self.next_button)

    def _create_action_buttons(self):
        """确认 / 取消按钮，分页时放 row 3，否则 row 2。"""
        action_row = 3 if self._total_pages() > 1 else 2

        self.confirm_button = Button(
            label="✅ 确认",
            style=ButtonStyle.green,
            custom_id="confirm",
            row=action_row,
            disabled=(self.selected_model is None),
        )
        self.confirm_button.callback = self._on_confirm
        self.add_item(self.confirm_button)

        self.cancel_button = Button(
            label="❌ 取消",
            style=ButtonStyle.red,
            custom_id="cancel",
            row=action_row,
        )
        self.cancel_button.callback = self._on_cancel
        self.add_item(self.cancel_button)

    # ------------------------------------------------------------------
    # 回调
    # ------------------------------------------------------------------

    async def _on_provider_select(self, interaction: Interaction):
        self.selected_provider = self.provider_select.values[0]
        self.selected_model = None
        self._model_page = 0
        self._rebuild_ui()
        await interaction.response.edit_message(view=self)

    async def _on_model_select(self, interaction: Interaction):
        value = self.model_select.values[0]
        if value == "none":
            await interaction.response.defer()
            return
        self.selected_model = value
        self._rebuild_ui()
        await interaction.response.edit_message(view=self)

    async def _on_prev_page(self, interaction: Interaction):
        self._model_page = max(0, self._model_page - 1)
        self._rebuild_ui()
        await interaction.response.edit_message(view=self)

    async def _on_next_page(self, interaction: Interaction):
        self._model_page = min(self._total_pages() - 1, self._model_page + 1)
        self._rebuild_ui()
        await interaction.response.edit_message(view=self)

    async def _on_confirm(self, interaction: Interaction):
        self.confirmed = True
        self.stop()
        provider_map = self._models_by_provider.get(self.selected_provider or "", {})
        config = provider_map.get(self.selected_model or "")
        display_name = (
            (config.display_name if config else None) or self.selected_model or ""
        )
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
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="❌ 已取消",
                description="模型设置未更改",
                color=discord.Color.red(),
            ),
            view=None,
        )

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _get_models_by_provider(self) -> Dict[str, Dict[str, "ModelConfig"]]:
        from src.chat.services.ai.config.models import get_model_configs, ModelConfig

        grouped: Dict[str, Dict[str, "ModelConfig"]] = {}
        for model_name, config in get_model_configs().items():
            provider = config.provider or "unknown"
            if provider not in grouped:
                grouped[provider] = {}
            grouped[provider][model_name] = config

        try:
            from src.chat.services.ai.config.providers import get_provider_configs

            for provider_name, pconfig in get_provider_configs().items():
                if not pconfig.is_available() or provider_name in grouped:
                    continue
                grouped[provider_name] = {}
                for model_id in pconfig.models:
                    grouped[provider_name][model_id] = ModelConfig(
                        display_name=model_id,
                        provider=provider_name,
                        actual_model=model_id,
                        supports_vision=True,
                        supports_tools=True,
                        description="动态端点模型",
                    )
        except Exception:
            pass

        return grouped

    def _get_provider_display_name(self, provider_name: str) -> str:
        names = {
            "gemini_official": "📦 Gemini 官方",
            "deepseek": "📦 DeepSeek",
            "openai_compatible": "📦 OpenAI 兼容",
            "unknown": "📦 未知",
        }
        if provider_name.startswith("gemini_custom_"):
            return f"📦 Gemini 自定义 ({provider_name.replace('gemini_custom_', '')})"
        return names.get(provider_name, f"📦 {provider_name}")

    def get_selected_full_model_id(self) -> Optional[str]:
        if self.confirmed and self.selected_provider and self.selected_model:
            return f"{self.selected_provider}:{self.selected_model}"
        return None

    @classmethod
    def parse_full_model_id(
        cls, full_model_id: str
    ) -> tuple[Optional[str], Optional[str]]:
        if not full_model_id:
            return None, None
        if ":" in full_model_id:
            parts = full_model_id.split(":", 1)
            return parts[0], parts[1]
        from src.chat.services.ai.config.models import get_model_configs

        model_configs = get_model_configs()
        if full_model_id in model_configs:
            return model_configs[full_model_id].provider, full_model_id
        return None, full_model_id
