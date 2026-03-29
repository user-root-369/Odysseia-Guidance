# -*- coding: utf-8 -*-
"""
AI 服务配置模块
"""

from .providers import ProviderConfig, get_provider_configs
from .models import (
    ModelConfig,
    PromptConfig,
    GenerationConfigParams,
    SupportedParam,
    PROVIDER_SUPPORTED_PARAMS,
    get_model_configs,
    get_model_config,
    get_generation_config,
    get_prompt_config,
    get_supported_params_for_provider,
    save_model_config,
    save_all_model_configs,
    reload_model_configs,
    reset_model_to_original,
    update_model_generation_config,
    update_model_prompt_config,
    FALLBACK_PRIORITY,
)

__all__ = [
    "ProviderConfig",
    "get_provider_configs",
    "ModelConfig",
    "PromptConfig",
    "GenerationConfigParams",
    "SupportedParam",
    "PROVIDER_SUPPORTED_PARAMS",
    "get_model_configs",
    "get_model_config",
    "get_generation_config",
    "get_prompt_config",
    "get_supported_params_for_provider",
    "save_model_config",
    "save_all_model_configs",
    "reload_model_configs",
    "reset_model_to_original",
    "update_model_generation_config",
    "update_model_prompt_config",
    "FALLBACK_PRIORITY",
]
