# -*- coding: utf-8 -*-
"""
AI 模型配置模块

定义支持的模型及其配置
所有模型配置从 JSON 配置文件动态加载，不在代码中硬编码任何模型
"""

import json
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path

log = logging.getLogger(__name__)

# JSON 配置文件路径
MODELS_CONFIG_PATH = Path(__file__).parent / "models_config.json"


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfig":
        """
        从字典创建 ModelConfig 实例

        Args:
            data: 包含模型配置的字典

        Returns:
            ModelConfig 实例
        """
        return cls(
            display_name=data.get("display_name", ""),
            provider=data.get("provider", ""),
            actual_model=data.get("actual_model", ""),
            generation_config=data.get("generation_config", {}),
            supports_vision=data.get("supports_vision", False),
            supports_tools=data.get("supports_tools", True),
            supports_thinking=data.get("supports_thinking", False),
            max_output_tokens=data.get("max_output_tokens", 6000),
            description=data.get("description", ""),
        )


# 模型配置缓存
_model_configs_cache: Optional[Dict[str, ModelConfig]] = None


def _load_models_from_json() -> Dict[str, ModelConfig]:
    """
    从 JSON 配置文件加载模型配置

    Returns:
        Dict[str, ModelConfig]: 模型名称到配置的映射
    """
    configs = {}

    if not MODELS_CONFIG_PATH.exists():
        log.warning(f"模型配置文件不存在: {MODELS_CONFIG_PATH}，将只使用环境变量配置")
        return configs

    try:
        with open(MODELS_CONFIG_PATH, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        for model_name, model_data in config_data.items():
            configs[model_name] = ModelConfig.from_dict(model_data)

        log.info(f"已从 {MODELS_CONFIG_PATH} 加载 {len(configs)} 个模型配置")

    except Exception as e:
        log.error(f"加载模型配置文件失败: {e}")

    return configs


def get_model_configs() -> Dict[str, ModelConfig]:
    """
    获取所有模型配置

    配置只从 JSON 配置文件加载 (models_config.json)
    自定义端点的 URL 和 API 密钥在 providers.py 中从环境变量读取

    Returns:
        Dict[str, ModelConfig]: 模型名称到配置的映射
    """
    global _model_configs_cache

    if _model_configs_cache is not None:
        return _model_configs_cache

    # 从 JSON 配置文件加载
    configs = _load_models_from_json()

    # 缓存配置
    _model_configs_cache = configs

    return configs


def reload_model_configs() -> Dict[str, ModelConfig]:
    """
    重新加载模型配置（清除缓存）

    Returns:
        Dict[str, ModelConfig]: 模型名称到配置的映射
    """
    global _model_configs_cache
    _model_configs_cache = None
    return get_model_configs()


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


# 故障转移优先级配置
# 这个配置保留在代码中，因为它是系统行为配置，不是模型定义
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
