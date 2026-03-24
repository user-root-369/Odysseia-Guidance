# -*- coding: utf-8 -*-
"""
AI 模型配置模块

定义支持的模型及其配置
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

log = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """
    模型配置数据类

    Attributes:
        display_name: 显示名称
        provider: 所属 Provider 名称
        actual_model: 实际调用的模型名（可能与显示名不同）
        generation_config: 生成配置参数
        supports_vision: 是否支持视觉/图片
        supports_tools: 是否支持工具调用
        supports_thinking: 是否支持思考链
        max_output_tokens: 最大输出 token 数
        description: 模型描述
    """

    display_name: str
    provider: str
    actual_model: str
    generation_config: Dict[str, Any] = field(default_factory=dict)
    supports_vision: bool = False
    supports_tools: bool = True
    supports_thinking: bool = False
    max_output_tokens: int = 6000
    description: str = ""


# 默认模型配置
DEFAULT_MODEL_CONFIGS: Dict[str, ModelConfig] = {
    # === Gemini 官方模型 ===
    "gemini-2.5-flash": ModelConfig(
        display_name="Gemini 2.5 Flash",
        provider="gemini_official",
        actual_model="gemini-2.5-flash",
        supports_vision=True,
        supports_tools=True,
        supports_thinking=False,
        max_output_tokens=6000,
        description="Google 最新的快速模型，平衡性能和速度",
    ),
    "gemini-flash-latest": ModelConfig(
        display_name="Gemini Flash (Latest)",
        provider="gemini_official",
        actual_model="gemini-2.5-flash",
        supports_vision=True,
        supports_tools=True,
        supports_thinking=False,
        max_output_tokens=6000,
        description="Gemini Flash 最新版本别名",
    ),
    # === DeepSeek 模型 ===
    "deepseek-chat": ModelConfig(
        display_name="DeepSeek Chat",
        provider="deepseek",
        actual_model="deepseek-chat",
        supports_vision=False,
        supports_tools=True,
        supports_thinking=False,
        max_output_tokens=6000,
        description="DeepSeek 对话模型，擅长中文对话",
    ),
    "deepseek-reasoner": ModelConfig(
        display_name="DeepSeek R1",
        provider="deepseek",
        actual_model="deepseek-reasoner",
        supports_vision=False,
        supports_tools=False,  # R1 不支持工具调用
        supports_thinking=True,
        max_output_tokens=8000,
        description="DeepSeek 推理模型，擅长复杂推理任务",
    ),
    # === OpenAI 兼容模型 ===
    "gpt-4": ModelConfig(
        display_name="GPT-4",
        provider="openai_compatible",
        actual_model="gpt-4",
        supports_vision=False,
        supports_tools=True,
        supports_thinking=False,
        max_output_tokens=4000,
        description="OpenAI GPT-4 模型",
    ),
    "gpt-4o": ModelConfig(
        display_name="GPT-4o",
        provider="openai_compatible",
        actual_model="gpt-4o",
        supports_vision=True,
        supports_tools=True,
        supports_thinking=False,
        max_output_tokens=4000,
        description="OpenAI GPT-4o 多模态模型",
    ),
    "claude-3-opus": ModelConfig(
        display_name="Claude 3 Opus",
        provider="openai_compatible",
        actual_model="claude-3-opus",
        supports_vision=True,
        supports_tools=True,
        supports_thinking=False,
        max_output_tokens=4000,
        description="Anthropic Claude 3 Opus 模型",
    ),
}


# 故障转移优先级配置
FALLBACK_PRIORITY: Dict[str, List[str]] = {
    # 当使用 Gemini 自定义端点失败时
    "gemini_custom": [
        "deepseek",  # 首选 DeepSeek
        "openai_compatible",  # 其次 OpenAI 兼容端点
        "gemini_official",  # 最后回退到 Gemini 官方
    ],
    # 当使用 DeepSeek 失败时
    "deepseek": [
        "gemini_custom",
        "openai_compatible",
        "gemini_official",
    ],
    # 当使用 OpenAI 兼容端点失败时
    "openai_compatible": [
        "deepseek",
        "gemini_custom",
        "gemini_official",
    ],
    # 当使用 Gemini 官方失败时
    "gemini_official": [
        "gemini_custom",
        "deepseek",
        "openai_compatible",
    ],
}


def get_model_configs() -> Dict[str, ModelConfig]:
    """
    获取所有模型配置

    Returns:
        Dict[str, ModelConfig]: 模型名称到配置的映射
    """
    configs = DEFAULT_MODEL_CONFIGS.copy()

    # 动态添加自定义 Gemini 端点模型
    for key, value in os.environ.items():
        if key.startswith("CUSTOM_GEMINI_URL_"):
            endpoint_name = key[len("CUSTOM_GEMINI_URL_") :].lower()
            model_name = f"gemini-{endpoint_name.replace('_', '-')}-custom"

            # 确定实际模型名（从环境变量或使用默认）
            actual_model = os.getenv(
                f"CUSTOM_GEMINI_MODEL_{endpoint_name.upper()}", "gemini-2.0-flash"
            )

            configs[model_name] = ModelConfig(
                display_name=f"Gemini {endpoint_name.replace('_', ' ').title()} (Custom)",
                provider=f"gemini_custom_{endpoint_name}",
                actual_model=actual_model,
                supports_vision=True,
                supports_tools=True,
                supports_thinking=True,  # 自定义端点可能支持 thinking
                max_output_tokens=8000,
                description=f"自定义 Gemini 端点: {endpoint_name}",
            )

    return configs


def get_model_config(model_name: str) -> Optional[ModelConfig]:
    """
    获取指定模型的配置

    Args:
        model_name: 模型名称

    Returns:
        Optional[ModelConfig]: 模型配置，如果不存在则返回 None
    """
    configs = get_model_configs()
    return configs.get(model_name)


def get_available_models() -> List[str]:
    """
    获取所有可用的模型名称列表

    Returns:
        List[str]: 模型名称列表
    """
    return list(get_model_configs().keys())


def get_fallback_providers(provider_type: str) -> List[str]:
    """
    获取指定 Provider 类型的故障转移优先级列表

    Args:
        provider_type: Provider 类型

    Returns:
        List[str]: 故障转移 Provider 列表
    """
    # 标准化 provider_type
    normalized = provider_type.lower()

    # 检查是否是自定义 Gemini 端点
    if normalized.startswith("gemini_custom") or "custom" in normalized:
        return FALLBACK_PRIORITY.get("gemini_custom", [])

    return FALLBACK_PRIORITY.get(normalized, [])
