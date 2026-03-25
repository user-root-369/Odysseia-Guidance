# -*- coding: utf-8 -*-
"""
模型参数配置文件
用于定义不同 AI 模型的生成参数（温度、top_p、max_tokens 等）
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class SupportedParam(Enum):
    """模型支持的参数类型"""

    TEMPERATURE = "temperature"
    TOP_P = "top_p"
    TOP_K = "top_k"
    MAX_OUTPUT_TOKENS = "max_output_tokens"
    PRESENCE_PENALTY = "presence_penalty"
    FREQUENCY_PENALTY = "frequency_penalty"


# 不同模型提供商支持的参数
# DeepSeek: temperature, top_p, presence_penalty, frequency_penalty, max_tokens
# Gemini: temperature, top_p, top_k, max_output_tokens
# OpenAI: temperature, top_p, presence_penalty, frequency_penalty, max_tokens
PROVIDER_SUPPORTED_PARAMS: Dict[str, List[SupportedParam]] = {
    "deepseek": [
        SupportedParam.TEMPERATURE,
        SupportedParam.TOP_P,
        SupportedParam.MAX_OUTPUT_TOKENS,
        SupportedParam.PRESENCE_PENALTY,
        SupportedParam.FREQUENCY_PENALTY,
    ],
    "gemini": [
        SupportedParam.TEMPERATURE,
        SupportedParam.TOP_P,
        SupportedParam.TOP_K,
        SupportedParam.MAX_OUTPUT_TOKENS,
    ],
    "openai": [
        SupportedParam.TEMPERATURE,
        SupportedParam.TOP_P,
        SupportedParam.MAX_OUTPUT_TOKENS,
        SupportedParam.PRESENCE_PENALTY,
        SupportedParam.FREQUENCY_PENALTY,
    ],
    "anthropic": [
        SupportedParam.TEMPERATURE,
        SupportedParam.TOP_P,
        SupportedParam.TOP_K,
        SupportedParam.MAX_OUTPUT_TOKENS,
    ],
    "default": [
        SupportedParam.TEMPERATURE,
        SupportedParam.TOP_P,
        SupportedParam.MAX_OUTPUT_TOKENS,
    ],
}


@dataclass
class ModelParams:
    """
    模型参数配置数据类

    Attributes:
        temperature: 温度参数，控制随机性 (0.0-2.0)
        top_p: Top-p 采样参数 (0.0-1.0)
        top_k: Top-k 采样参数 (仅 Gemini/Anthropic 支持)
        max_output_tokens: 最大输出 token 数
        presence_penalty: 存在惩罚 (-2.0 to 2.0) (仅 DeepSeek/OpenAI 支持)
        frequency_penalty: 频率惩罚 (-2.0 to 2.0) (仅 DeepSeek/OpenAI 支持)
        provider: 模型提供商，用于确定支持的参数
    """

    temperature: float = 1.0
    top_p: float = 0.95
    top_k: Optional[int] = None  # 仅 Gemini/Anthropic 支持
    max_output_tokens: int = 8192
    presence_penalty: Optional[float] = None  # 仅 DeepSeek/OpenAI 支持
    frequency_penalty: Optional[float] = None  # 仅 DeepSeek/OpenAI 支持
    provider: str = "default"  # 用于确定支持的参数

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，只包含非 None 的值"""
        result = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_output_tokens": self.max_output_tokens,
            "provider": self.provider,
        }
        if self.top_k is not None:
            result["top_k"] = self.top_k
        if self.presence_penalty is not None:
            result["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty is not None:
            result["frequency_penalty"] = self.frequency_penalty
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelParams":
        """从字典创建实例"""
        return cls(
            temperature=data.get("temperature", 1.0),
            top_p=data.get("top_p", 0.95),
            top_k=data.get("top_k"),
            max_output_tokens=data.get("max_output_tokens", 8192),
            presence_penalty=data.get("presence_penalty"),
            frequency_penalty=data.get("frequency_penalty"),
            provider=data.get("provider", "default"),
        )

    def get_supported_params(self) -> List[SupportedParam]:
        """获取该模型支持的参数列表"""
        return PROVIDER_SUPPORTED_PARAMS.get(
            self.provider, PROVIDER_SUPPORTED_PARAMS["default"]
        )

    def is_param_supported(self, param: SupportedParam) -> bool:
        """检查该模型是否支持某个参数"""
        return param in self.get_supported_params()


# 默认参数配置
DEFAULT_PARAMS = ModelParams(
    temperature=1.0,
    top_p=0.95,
    max_output_tokens=8192,
    provider="default",
)

# 各模型的参数配置
# 可以根据模型特性调整参数，例如：
# - 创意性任务可以使用较高的 temperature (1.0-1.5)
# - 精确性任务可以使用较低的 temperature (0.3-0.7)
#
# 注意：不同提供商支持的参数不同
# - DeepSeek: temperature, top_p, presence_penalty, frequency_penalty, max_output_tokens
# - Gemini: temperature, top_p, top_k, max_output_tokens
# - OpenAI: temperature, top_p, presence_penalty, frequency_penalty, max_output_tokens
MODEL_PARAMS_CONFIG: Dict[str, ModelParams] = {
    # DeepSeek 模型配置 - 支持 presence_penalty 和 frequency_penalty
    "deepseek-chat": ModelParams(
        temperature=1.0,
        top_p=0.95,
        max_output_tokens=8192,
        presence_penalty=0.0,
        frequency_penalty=0.0,
        provider="deepseek",
    ),
    "deepseek-reasoner": ModelParams(
        temperature=1.0,
        top_p=0.95,
        max_output_tokens=8192,
        presence_penalty=0.0,
        frequency_penalty=0.0,
        provider="deepseek",
    ),
    # Gemini 模型配置 - 支持 top_k
    "gemini-2.5-flash": ModelParams(
        temperature=1.0,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        provider="gemini",
    ),
    "gemini-flash-latest": ModelParams(
        temperature=1.0,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        provider="gemini",
    ),
    # 自定义 Gemini 端点
    "gemini-3-pro-preview-custom": ModelParams(
        temperature=1.0,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        provider="gemini",
    ),
    "gemini-2.5-flash-custom": ModelParams(
        temperature=1.0,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        provider="gemini",
    ),
    "gemini-3-flash-custom": ModelParams(
        temperature=1.0,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        provider="gemini",
    ),
    # OpenAI 兼容模型 - 支持 presence_penalty 和 frequency_penalty
    "gpt-4": ModelParams(
        temperature=1.0,
        top_p=0.95,
        max_output_tokens=8192,
        presence_penalty=0.0,
        frequency_penalty=0.0,
        provider="openai",
    ),
    "gpt-4o": ModelParams(
        temperature=1.0,
        top_p=0.95,
        max_output_tokens=8192,
        presence_penalty=0.0,
        frequency_penalty=0.0,
        provider="openai",
    ),
    # Anthropic 模型 - 支持 top_k
    "claude-3-opus": ModelParams(
        temperature=1.0,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        provider="anthropic",
    ),
}

# 保存原始配置的深拷贝，用于重置功能
ORIGINAL_MODEL_PARAMS: Dict[str, ModelParams] = {
    model: ModelParams(
        temperature=params.temperature,
        top_p=params.top_p,
        top_k=params.top_k,
        max_output_tokens=params.max_output_tokens,
        presence_penalty=params.presence_penalty,
        frequency_penalty=params.frequency_penalty,
        provider=params.provider,
    )
    for model, params in MODEL_PARAMS_CONFIG.items()
}


def get_model_params(model_name: str) -> ModelParams:
    """
    获取指定模型的参数配置

    Args:
        model_name: 模型名称

    Returns:
        ModelParams: 模型参数配置，如果模型未配置则返回默认配置
    """
    return MODEL_PARAMS_CONFIG.get(model_name, DEFAULT_PARAMS)


def update_model_params(model_name: str, params: ModelParams) -> None:
    """
    更新指定模型的参数配置

    Args:
        model_name: 模型名称
        params: 新的参数配置
    """
    MODEL_PARAMS_CONFIG[model_name] = params


def get_all_model_params() -> Dict[str, ModelParams]:
    """
    获取所有模型的参数配置

    Returns:
        Dict[str, ModelParams]: 模型名称到参数配置的映射
    """
    return MODEL_PARAMS_CONFIG.copy()


def get_param_value(model_name: str, param_name: str) -> Any:
    """
    获取指定模型的特定参数值

    Args:
        model_name: 模型名称
        param_name: 参数名称 (temperature, top_p, max_output_tokens 等)

    Returns:
        参数值，如果模型或参数不存在则返回默认值
    """
    params = get_model_params(model_name)
    return getattr(params, param_name, getattr(DEFAULT_PARAMS, param_name, None))


def reset_to_original(model_name: str) -> bool:
    """
    将指定模型的参数重置为原始配置

    Args:
        model_name: 模型名称

    Returns:
        bool: 是否成功重置（如果模型没有原始配置则返回 False）
    """
    if model_name in ORIGINAL_MODEL_PARAMS:
        original = ORIGINAL_MODEL_PARAMS[model_name]
        MODEL_PARAMS_CONFIG[model_name] = ModelParams(
            temperature=original.temperature,
            top_p=original.top_p,
            top_k=original.top_k,
            max_output_tokens=original.max_output_tokens,
            presence_penalty=original.presence_penalty,
            frequency_penalty=original.frequency_penalty,
            provider=original.provider,
        )
        return True
    return False
