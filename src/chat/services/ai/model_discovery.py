# -*- coding: utf-8 -*-
"""
模型发现服务 - 动态查询各 Provider 的可用模型列表

对每个已注册的 Provider：
  1. 若 Provider 实现了 list_models()，则优先向远端 API 查询真实可用模型。
  2. 若远端查询失败或超时，则回退到 models_config.json + provider.supported_models 的静态列表。
  3. 若 Provider 未初始化或不可用，则返回 "unavailable" 状态。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# 每个 Provider 远端查询的超时时间（秒）
_DISCOVERY_TIMEOUT = 10.0


@dataclass
class DiscoveredModel:
    """单个发现的模型信息"""

    id: str
    """模型 ID（传给 API 的名称）"""
    display_name: str
    """展示名称（优先用 models_config.json 中的 display_name）"""
    provider_name: str
    """所属 Provider 名称"""
    source: str
    """来源：'remote'（远端实时）| 'static'（本地配置）"""
    supports_tools: bool = True
    supports_vision: bool = False
    description: str = ""


@dataclass
class ProviderDiscoveryResult:
    """单个 Provider 的模型发现结果"""

    provider_name: str
    success: bool
    """远端查询是否成功"""
    source: str
    """'remote' | 'static' | 'unavailable'"""
    models: List[DiscoveredModel] = field(default_factory=list)
    error: Optional[str] = None
    """失败原因（仅在 success=False 时非空）"""


class ModelDiscoveryService:
    """
    模型发现服务（单例）

    用法：
        results = await model_discovery_service.discover_all()
        result = await model_discovery_service.discover_provider("openai_compatible")
    """

    async def discover_all(self) -> Dict[str, ProviderDiscoveryResult]:
        """
        对所有已注册 Provider 并发执行模型发现。

        Returns:
            dict: provider_name → ProviderDiscoveryResult
        """
        from src.chat.services.ai import ai_service

        if not ai_service._providers:
            return {}

        provider_names = list(ai_service._providers.keys())
        providers = [ai_service._providers[n] for n in provider_names]

        coros = [
            self._discover_one(name, provider)
            for name, provider in zip(provider_names, providers)
        ]
        gathered = await asyncio.gather(*coros, return_exceptions=True)

        results: Dict[str, ProviderDiscoveryResult] = {}
        for name, outcome in zip(provider_names, gathered):
            if isinstance(outcome, Exception):
                results[name] = ProviderDiscoveryResult(
                    provider_name=name,
                    success=False,
                    source="static",
                    error=f"未预期错误: {outcome}",
                    models=self._static_models_for(name),
                )
            else:
                results[name] = outcome

        return results

    async def discover_provider(self, provider_name: str) -> ProviderDiscoveryResult:
        """对单个 Provider 执行模型发现。"""
        from src.chat.services.ai import ai_service

        provider = ai_service.get_provider(provider_name)
        if provider is None:
            return ProviderDiscoveryResult(
                provider_name=provider_name,
                success=False,
                source="unavailable",
                error="Provider 未初始化（可能未配置 API 密钥）",
                models=self._static_models_for(provider_name),
            )
        return await self._discover_one(provider_name, provider)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _discover_one(
        self, provider_name: str, provider: Any
    ) -> ProviderDiscoveryResult:
        """对单个 Provider 执行发现，包含可用性检查 + 远端查询 + 静态回退。"""
        # 1. 检查 provider 是否可用
        try:
            available = await provider.is_available()
        except Exception as e:
            available = False
            log.debug(f"[模型发现] {provider_name} is_available() 异常: {e}")

        if not available:
            return ProviderDiscoveryResult(
                provider_name=provider_name,
                success=False,
                source="unavailable",
                error="Provider 未配置或不可用（缺少 API 密钥 / URL）",
                models=self._static_models_for(provider_name),
            )

        # 2. 若 Provider 实现了 list_models()，尝试远端拉取
        if hasattr(provider, "list_models") and callable(provider.list_models):
            try:
                raw_models: List[Dict] = await asyncio.wait_for(
                    provider.list_models(), timeout=_DISCOVERY_TIMEOUT
                )
                models = self._enrich_remote_models(raw_models, provider_name)
                log.info(
                    f"[模型发现] {provider_name}: 远端拉取成功，共 {len(models)} 个模型"
                )
                return ProviderDiscoveryResult(
                    provider_name=provider_name,
                    success=True,
                    source="remote",
                    models=models,
                )
            except asyncio.TimeoutError:
                error = f"远端 /models 接口超时（>{_DISCOVERY_TIMEOUT}s）"
                log.warning(f"[模型发现] {provider_name}: {error}，回退静态配置")
            except Exception as e:
                # repr(e) 同时打出异常类型和消息，避免 str(e) 为空时什么都看不到
                error = repr(e)
                log.warning(
                    f"[模型发现] {provider_name}: 远端拉取失败 ({error})，回退静态配置",
                    exc_info=True,
                )

            return ProviderDiscoveryResult(
                provider_name=provider_name,
                success=False,
                source="static",
                error=error,
                models=self._static_models_for(provider_name),
            )

        # 3. 没有 list_models()，直接使用静态配置（不算失败）
        return ProviderDiscoveryResult(
            provider_name=provider_name,
            success=True,
            source="static",
            models=self._static_models_for(provider_name),
        )

    def _static_models_for(self, provider_name: str) -> List[DiscoveredModel]:
        """
        从 models_config.json 和 provider.supported_models 合并静态模型列表。
        优先使用 models_config.json 中的完整元数据。
        """
        from src.chat.services.ai import ai_service
        from src.chat.services.ai.config.models import get_model_configs

        static_models: List[DiscoveredModel] = []
        seen: set = set()

        # 先从 models_config.json 读取有完整元数据的模型
        try:
            model_configs = get_model_configs()
            for model_id, cfg in model_configs.items():
                if cfg.provider == provider_name:
                    static_models.append(
                        DiscoveredModel(
                            id=model_id,
                            display_name=cfg.display_name or model_id,
                            provider_name=provider_name,
                            source="static",
                            supports_tools=cfg.supports_tools,
                            supports_vision=cfg.supports_vision,
                            description=cfg.description or "",
                        )
                    )
                    seen.add(model_id)
        except Exception as e:
            log.warning(f"[模型发现] 读取 models_config.json 失败: {e}")

        # 再从 provider.supported_models 补充没有详细配置的模型
        p = ai_service.get_provider(provider_name)
        if p and hasattr(p, "supported_models"):
            for model_id in p.supported_models:
                if model_id not in seen:
                    static_models.append(
                        DiscoveredModel(
                            id=model_id,
                            display_name=model_id,
                            provider_name=provider_name,
                            source="static",
                        )
                    )
                    seen.add(model_id)

        return static_models

    def _enrich_remote_models(
        self, raw_models: List[Dict], provider_name: str
    ) -> List[DiscoveredModel]:
        """
        将远端 /models 返回的原始列表解析并用本地 models_config.json 增强元数据。
        """
        from src.chat.services.ai.config.models import get_model_configs

        try:
            model_configs = get_model_configs()
        except Exception:
            model_configs = {}

        models: List[DiscoveredModel] = []
        for raw in raw_models:
            model_id = raw.get("id") or raw.get("name") or ""
            if not model_id:
                continue
            local_cfg = model_configs.get(model_id)
            models.append(
                DiscoveredModel(
                    id=model_id,
                    display_name=local_cfg.display_name if local_cfg else model_id,
                    provider_name=provider_name,
                    source="remote",
                    supports_tools=local_cfg.supports_tools if local_cfg else True,
                    supports_vision=local_cfg.supports_vision if local_cfg else False,
                    description=(
                        local_cfg.description
                        if local_cfg
                        else raw.get("description", "")
                    ),
                )
            )
        return models


# 全局单例
model_discovery_service = ModelDiscoveryService()
