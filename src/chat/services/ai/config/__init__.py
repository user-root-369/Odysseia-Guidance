# -*- coding: utf-8 -*-
"""
AI 服务配置模块
"""

from .providers import ProviderConfig, get_provider_configs
from .models import ModelConfig, get_model_configs, FALLBACK_PRIORITY

__all__ = [
    "ProviderConfig",
    "get_provider_configs",
    "ModelConfig",
    "get_model_configs",
    "FALLBACK_PRIORITY",
]
