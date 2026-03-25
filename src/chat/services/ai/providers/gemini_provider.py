# -*- coding: utf-8 -*-
"""
Gemini Provider - 支持 Gemini 官方 API 和自定义端点

实现两种模式：
1. 官方 API 模式：使用密钥轮换服务
2. 自定义端点模式：直接使用指定的 API 端点
"""

import logging
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types as genai_types
from google.genai import errors as genai_errors

from .base import (
    BaseProvider,
    GenerationConfig,
    GenerationResult,
    FinishReason,
    ProviderNotAvailableError,
    GenerationError,
)
from ..utils.tool_converter import ToolConverter
from src.chat.services.key_rotation_service import (
    KeyRotationService,
    NoAvailableKeyError,
)

log = logging.getLogger(__name__)


class GeminiProvider(BaseProvider):
    """
    Gemini API Provider

    支持：
    - Gemini 官方 API（带密钥轮换）
    - 自定义 Gemini 端点（公益站等）
    - 工具调用
    - 思考链（Thinking）
    - 视觉（图片理解）
    """

    provider_type = "gemini"
    supported_models = [
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
    ]
    supports_vision = True
    supports_tools = True
    supports_thinking = True

    # 安全惩罚映射
    SAFETY_PENALTY_MAP: Dict[str, int] = {
        "HARM_PROBABILITY_UNSPECIFIED": 0,
        "NEGLIGIBLE": 0,
        "LOW": 5,
        "MEDIUM": 15,
        "HIGH": 30,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        use_key_rotation: bool = True,
        api_keys_list: Optional[List[str]] = None,
        provider_name: str = "gemini_official",
    ):
        """
        初始化 Gemini Provider

        Args:
            api_key: API 密钥（单密钥模式）
            base_url: API 基础 URL（可选，用于代理或自定义端点）
            use_key_rotation: 是否使用密钥轮换
            api_keys_list: API 密钥列表（用于密钥轮换）
            provider_name: Provider 名称标识
        """
        self.provider_name = provider_name
        self.base_url = base_url
        self.use_key_rotation = use_key_rotation

        # 初始化密钥轮换服务
        self.key_rotation_service: Optional[KeyRotationService] = None
        self._single_api_key: Optional[str] = None

        if use_key_rotation and api_keys_list:
            self.key_rotation_service = KeyRotationService(api_keys_list)
            log.info(
                f"GeminiProvider '{provider_name}' 启用密钥轮换，共 {len(api_keys_list)} 个密钥"
            )
        elif api_key:
            self._single_api_key = api_key
            log.info(f"GeminiProvider '{provider_name}' 使用单密钥模式")
        else:
            log.warning(f"GeminiProvider '{provider_name}' 未配置 API 密钥")

        # 安全设置
        self.safety_settings = [
            genai_types.SafetySetting(
                category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
            ),
            genai_types.SafetySetting(
                category=genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
            ),
            genai_types.SafetySetting(
                category=genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
            ),
            genai_types.SafetySetting(
                category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ]

        # 客户端缓存
        self._client_cache: Dict[str, genai.Client] = {}

    def _create_client(self, api_key: str) -> genai.Client:
        """
        创建 Gemini 客户端

        Args:
            api_key: API 密钥

        Returns:
            genai.Client: Gemini 客户端
        """
        if self.base_url:
            http_options = genai_types.HttpOptions(base_url=self.base_url)
            return genai.Client(api_key=api_key, http_options=http_options)
        else:
            return genai.Client(api_key=api_key)

    def get_client(self) -> Any:
        """
        获取底层客户端对象

        如果使用密钥轮换，需要先调用 acquire_client

        Returns:
            genai.Client 或 None
        """
        if self._single_api_key:
            if self._single_api_key not in self._client_cache:
                self._client_cache[self._single_api_key] = self._create_client(
                    self._single_api_key
                )
            return self._client_cache[self._single_api_key]
        return None

    async def acquire_client(self) -> tuple[Any, Optional[str]]:
        """
        获取可用的客户端（支持密钥轮换）

        Returns:
            Tuple[genai.Client, Optional[str]]: (客户端, 密钥标识)

        Raises:
            ProviderNotAvailableError: 没有可用的密钥
        """
        if self.key_rotation_service:
            key_obj = await self.key_rotation_service.acquire_key()
            client = self._create_client(key_obj.key)
            return client, key_obj.key
        elif self._single_api_key:
            client = self.get_client()
            return client, self._single_api_key[-4:] if self._single_api_key else None
        else:
            raise ProviderNotAvailableError("未配置 API 密钥")

    async def release_client(
        self,
        api_key: Optional[str],
        success: bool = True,
        failure_penalty: int = 0,
        safety_penalty: int = 0,
    ):
        """
        释放客户端（更新密钥状态）

        Args:
            api_key: API 密钥
            success: 是否成功
            failure_penalty: 失败惩罚分数
            safety_penalty: 安全惩罚分数
        """
        if self.key_rotation_service and api_key:
            await self.key_rotation_service.release_key(
                api_key,
                success=success,
                failure_penalty=failure_penalty + safety_penalty,
            )

    async def is_available(self) -> bool:
        """检查服务是否可用"""
        if self.key_rotation_service:
            return True
        return bool(self._single_api_key)

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        tools: Optional[List[Any]] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        生成 AI 回复

        Args:
            messages: 对话消息列表
            config: 生成配置
            tools: 工具列表（ToolDeclaration 列表）
            model: 模型名称
            **kwargs: 其他参数

        Returns:
            GenerationResult: 生成结果
        """
        config = config or GenerationConfig()
        model_name = model or self.supported_models[0]

        client, api_key = await self.acquire_client()
        failure_penalty = 0
        safety_penalty = 0

        try:
            # 构建生成配置
            gen_config = self._build_generation_config(config)

            # 转换工具格式
            gemini_tools = None
            if tools:
                gemini_tools = ToolConverter.to_gemini_tools(tools)
                gen_config.tools = gemini_tools
                gen_config.automatic_function_calling = (
                    genai_types.AutomaticFunctionCallingConfig(disable=True)
                )

            # 转换消息格式
            contents = self._convert_messages_to_contents(messages)

            # 调用 API
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=gen_config,
            )

            # 处理响应
            result = self._process_response(response, model_name)

            # 计算安全惩罚
            safety_penalty = self._calculate_safety_penalty(response, api_key)

            # 释放密钥
            await self.release_client(
                api_key, success=True, safety_penalty=safety_penalty
            )

            return result

        except (genai_errors.ClientError, genai_errors.ServerError) as e:
            error_str = str(e)
            log.error(f"Gemini API 错误: {e}")

            # 判断是否可重试
            is_retryable = "429" in error_str or "503" in error_str
            if is_retryable:
                failure_penalty = 10
            elif "403" in error_str or "API_KEY_INVALID" in error_str.upper():
                failure_penalty = 101  # 毁灭性惩罚

            await self.release_client(
                api_key, success=False, failure_penalty=failure_penalty
            )
            raise GenerationError(
                f"Gemini API 错误: {e}",
                provider_type=self.provider_type,
                original_error=e,
            )

        except Exception as e:
            log.error(f"Gemini 生成错误: {e}", exc_info=True)
            await self.release_client(api_key, success=False, failure_penalty=10)
            raise GenerationError(
                f"Gemini 生成错误: {e}",
                provider_type=self.provider_type,
                original_error=e,
            )

    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        tools: Optional[List[Any]] = None,
        tool_executor: Optional[Any] = None,
        max_iterations: int = 5,
        model: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        带工具调用支持的生成方法

        Args:
            messages: 对话消息列表
            config: 生成配置
            tools: 工具列表
            tool_executor: 工具执行函数
            max_iterations: 最大迭代次数
            model: 模型名称
            **kwargs: 其他参数

        Returns:
            GenerationResult: 最终生成结果
        """
        config = config or GenerationConfig()
        model_name = model or self.supported_models[0]

        client, api_key = await self.acquire_client()

        try:
            # 构建生成配置
            gen_config = self._build_generation_config(config)

            # 转换工具格式
            if tools:
                gemini_tools = ToolConverter.to_gemini_tools(tools)
                gen_config.tools = gemini_tools
                gen_config.automatic_function_calling = (
                    genai_types.AutomaticFunctionCallingConfig(disable=True)
                )

            # 转换消息格式
            conversation_history = self._convert_messages_to_contents(messages)

            # 工具调用循环
            thinking_content = None

            for iteration in range(max_iterations):
                log.info(f"工具调用循环: 第 {iteration + 1}/{max_iterations} 次")

                # 调用 API
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=conversation_history,
                    config=gen_config,
                )

                # 检查思考链
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, "thought") and part.thought:
                            thinking_content = part.text
                            log.info(f"模型思考过程: {thinking_content[:100]}...")

                # 解析函数调用
                function_calls = ToolConverter.parse_gemini_function_calls(response)

                if not function_calls:
                    # 没有工具调用，返回最终结果
                    result = self._process_response(response, model_name)
                    if thinking_content:
                        result.thinking_content = thinking_content
                    await self.release_client(api_key, success=True)
                    return result

                # 有工具调用，执行工具
                log.info(f"模型请求调用 {len(function_calls)} 个工具")

                # 将模型响应添加到对话历史
                if response.candidates and response.candidates[0].content:
                    conversation_history.append(response.candidates[0].content)

                # 执行工具调用
                if tool_executor:
                    tool_results = []
                    for call in function_calls:
                        try:
                            result = await tool_executor(call, **kwargs)
                            tool_results.append(
                                ToolConverter.tool_result_to_gemini_part(
                                    call["name"],
                                    result,
                                    is_error=isinstance(result, dict)
                                    and "error" in result,
                                )
                            )
                        except Exception as e:
                            log.error(f"执行工具 {call['name']} 失败: {e}")
                            tool_results.append(
                                ToolConverter.tool_result_to_gemini_part(
                                    call["name"], {"error": str(e)}, is_error=True
                                )
                            )

                    # 将工具结果添加到对话历史
                    conversation_history.append(
                        genai_types.Content(parts=tool_results, role="user")
                    )
                else:
                    # 没有工具执行器，直接返回
                    result = self._process_response(response, model_name)
                    result.finish_reason = FinishReason.TOOL_CALL
                    result.tool_calls = function_calls
                    await self.release_client(api_key, success=True)
                    return result

            # 达到最大迭代次数
            log.warning(f"达到最大工具调用迭代次数 {max_iterations}")
            await self.release_client(api_key, success=True)
            return GenerationResult(
                content="抱歉，我在处理这个请求时遇到了一些复杂的情况，请换个方式问我。",
                model_used=model_name,
                finish_reason=FinishReason.MAX_ITERATIONS,
            )

        except Exception as e:
            log.error(f"Gemini 工具调用生成错误: {e}", exc_info=True)
            await self.release_client(api_key, success=False, failure_penalty=10)
            raise GenerationError(
                f"Gemini 工具调用生成错误: {e}",
                provider_type=self.provider_type,
                original_error=e,
            )

    async def generate_embedding(
        self, text: str, model: str = "text-embedding-004", **kwargs
    ) -> Optional[List[float]]:
        """
        生成文本的向量嵌入

        Args:
            text: 要嵌入的文本
            model: 嵌入模型名称
            **kwargs: 其他参数

        Returns:
            Optional[List[float]]: 嵌入向量
        """
        try:
            client, api_key = await self.acquire_client()

            try:
                result = await client.aio.models.embed_content(
                    model=model,
                    contents=text,
                )

                await self.release_client(api_key, success=True)

                if result.embeddings:
                    return result.embeddings[0].values
                return None

            except Exception as e:
                log.error(f"生成嵌入失败: {e}")
                await self.release_client(api_key, success=False, failure_penalty=10)
                return None

        except NoAvailableKeyError:
            log.warning("没有可用的 API 密钥用于生成嵌入")
            return None

    def _build_generation_config(
        self, config: GenerationConfig
    ) -> genai_types.GenerateContentConfig:
        """
        构建 Gemini 生成配置

        Args:
            config: 通用生成配置

        Returns:
            genai_types.GenerateContentConfig: Gemini 生成配置
        """
        gen_config_params: Dict[str, Any] = {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_output_tokens": config.max_output_tokens,
            "safety_settings": self.safety_settings,
        }

        # top_k 仅在设置时添加（Gemini 支持）
        if config.top_k is not None:
            gen_config_params["top_k"] = config.top_k

        if config.stop_sequences:
            gen_config_params["stop_sequences"] = config.stop_sequences

        gen_config = genai_types.GenerateContentConfig(**gen_config_params)

        # 添加思考链配置
        if config.thinking_budget_tokens:
            gen_config.thinking_config = genai_types.ThinkingConfig(
                thinking_budget=config.thinking_budget_tokens
            )

        return gen_config

    def _convert_messages_to_contents(
        self, messages: List[Dict[str, Any]]
    ) -> List[genai_types.Content]:
        """
        将通用消息格式转换为 Gemini Contents 格式

        Args:
            messages: 通用消息列表

        Returns:
            List[genai_types.Content]: Gemini Contents
        """
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # 转换角色
            gemini_role = "user" if role == "user" else "model"

            # 构建 Parts
            parts = []

            # 处理文本内容
            if isinstance(content, str):
                parts.append(genai_types.Part(text=content))
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        parts.append(genai_types.Part(text=item))
                    elif isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append(genai_types.Part(text=item.get("text", "")))
                        elif item.get("type") == "image_url":
                            # 处理图片
                            image_data = item.get("image_url", {})
                            if isinstance(image_data, dict):
                                url = image_data.get("url", "")
                                if url.startswith("data:"):
                                    # Base64 编码的图片
                                    import base64

                                    mime_match = (
                                        url.split(";")[0].split(":")[1]
                                        if ":" in url
                                        else "image/png"
                                    )
                                    base64_data = (
                                        url.split(",")[1] if "," in url else ""
                                    )
                                    try:
                                        image_bytes = base64.b64decode(base64_data)
                                        parts.append(
                                            genai_types.Part(
                                                inline_data=genai_types.Blob(
                                                    mime_type=mime_match,
                                                    data=image_bytes,
                                                )
                                            )
                                        )
                                    except Exception as e:
                                        log.error(f"解析 Base64 图片失败: {e}")

            if parts:
                contents.append(genai_types.Content(parts=parts, role=gemini_role))

        return contents

    def _process_response(
        self, response: genai_types.GenerateContentResponse, model_name: str
    ) -> GenerationResult:
        """
        处理 Gemini 响应

        Args:
            response: Gemini 响应对象
            model_name: 模型名称

        Returns:
            GenerationResult: 生成结果
        """
        # 提取文本内容
        content = ""
        if response.candidates and response.candidates[0].content:
            parts = response.candidates[0].content.parts or []
            for part in parts:
                if hasattr(part, "text") and part.text:
                    content += part.text

        # 确定结束原因
        finish_reason = FinishReason.STOP
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.finish_reason:
                reason_map = {
                    "STOP": FinishReason.STOP,
                    "MAX_TOKENS": FinishReason.MAX_TOKENS,
                    "SAFETY": FinishReason.SAFETY,
                }
                finish_reason = reason_map.get(
                    str(candidate.finish_reason).upper(), FinishReason.UNKNOWN
                )

        # 提取 token 使用量
        tokens_used = None
        input_tokens = None
        output_tokens = None
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count
            output_tokens = response.usage_metadata.candidates_token_count
            tokens_used = (input_tokens or 0) + (output_tokens or 0)

        return GenerationResult(
            content=content,
            model_used=model_name,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=finish_reason,
            raw_response=response,
        )

    def _calculate_safety_penalty(
        self, response: genai_types.GenerateContentResponse, api_key: Optional[str]
    ) -> int:
        """
        计算安全惩罚分数

        Args:
            response: Gemini 响应
            api_key: API 密钥（用于日志）

        Returns:
            int: 惩罚分数
        """
        total_penalty = 0

        if not response.candidates:
            return total_penalty

        candidate = response.candidates[0]
        if not hasattr(candidate, "safety_ratings") or not candidate.safety_ratings:
            return total_penalty

        for rating in candidate.safety_ratings:
            category_name = rating.category.name if rating.category else "UNKNOWN"
            severity_name = rating.probability.name if rating.probability else "UNKNOWN"

            penalty = self.SAFETY_PENALTY_MAP.get(severity_name, 0)
            if penalty > 0:
                log.warning(
                    f"密钥 ...{api_key[-4:] if api_key else '????'} 收到安全警告。"
                    f"类别: {category_name}, 严重性: {severity_name}, 惩罚: {penalty}"
                )
                total_penalty += penalty

        return total_penalty


class GeminiCustomProvider(GeminiProvider):
    """
    自定义 Gemini 端点 Provider

    用于连接自定义的 Gemini 兼容端点（如公益站）
    """

    provider_type = "gemini_custom"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        provider_name: str = "gemini_custom",
        models: Optional[List[str]] = None,
    ):
        """
        初始化自定义 Gemini Provider

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            provider_name: Provider 名称
            models: 支持的模型列表
        """
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            use_key_rotation=False,
            provider_name=provider_name,
        )

        if models:
            self.supported_models = models
