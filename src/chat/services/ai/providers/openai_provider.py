# -*- coding: utf-8 -*-
"""
OpenAI Compatible Provider - 支持所有 OpenAI 兼容端点

支持各种第三方 OpenAI 兼容服务：
- OpenRouter
- Together AI
- Azure OpenAI
- 其他自定义端点
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List

import httpx

from .base import (
    BaseProvider,
    GenerationConfig,
    GenerationResult,
    FinishReason,
    ProviderNotAvailableError,
    GenerationError,
)
from ..utils.tool_converter import ToolConverter

log = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseProvider):
    """
    OpenAI 兼容端点 Provider

    支持所有兼容 OpenAI API 格式的服务
    """

    provider_type = "openai_compatible"
    supported_models = [
        "gpt-4",
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "claude-3-opus",
        "claude-3-sonnet",
    ]
    supports_vision = True
    supports_tools = True
    supports_thinking = False

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider_name: str = "openai_compatible",
        models: Optional[List[str]] = None,
        default_model: Optional[str] = None,
    ):
        """
        初始化 OpenAI 兼容 Provider

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            provider_name: Provider 名称标识
            models: 支持的模型列表
            default_model: 默认模型
        """
        self.provider_name = provider_name
        self.api_key = api_key or os.getenv("OPENAI_COMPATIBLE_API_KEY")
        self.base_url = base_url or os.getenv(
            "OPENAI_COMPATIBLE_URL", "https://api.openai.com/v1"
        )
        self.default_model = default_model or "gpt-4o"

        if models:
            self.supported_models = models

        self._client: Optional[httpx.AsyncClient] = None

        if not self.api_key:
            log.warning(f"OpenAICompatibleProvider '{provider_name}' 未配置 API 密钥")
        else:
            log.info(
                f"OpenAICompatibleProvider '{provider_name}' 初始化完成，base_url: {self.base_url}"
            )

    def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client

    def get_client(self) -> Any:
        """获取底层客户端对象"""
        return self._get_client()

    async def is_available(self) -> bool:
        """检查服务是否可用"""
        return bool(self.api_key) and bool(self.base_url)

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
        if not self.api_key:
            raise ProviderNotAvailableError("未配置 API 密钥")

        config = config or GenerationConfig()
        model_name = model or self.default_model

        try:
            client = self._get_client()

            # 构建请求体
            request_body = self._build_request_body(messages, config, tools, model_name)

            # 调用 API
            response = await client.post(
                "/chat/completions",
                json=request_body,
            )
            response.raise_for_status()

            result_data = response.json()

            # 处理响应
            return self._process_response(result_data, model_name)

        except httpx.HTTPStatusError as e:
            log.error(f"OpenAI Compatible API HTTP 错误: {e}")
            raise GenerationError(
                f"OpenAI Compatible API 错误: {e.response.text}",
                provider_type=self.provider_type,
                original_error=e,
            )
        except httpx.RequestError as e:
            log.error(f"OpenAI Compatible API 请求错误: {e}")
            raise GenerationError(
                f"OpenAI Compatible API 请求失败: {e}",
                provider_type=self.provider_type,
                original_error=e,
            )
        except Exception as e:
            log.error(f"OpenAI Compatible 生成错误: {e}", exc_info=True)
            raise GenerationError(
                f"OpenAI Compatible 生成错误: {e}",
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
        model_name = model or self.default_model

        if not tools or not tool_executor:
            return await self.generate(messages, config, tools, model_name)

        conversation_history = messages.copy()

        try:
            for iteration in range(max_iterations):
                log.info(
                    f"OpenAI Compatible 工具调用循环: 第 {iteration + 1}/{max_iterations} 次"
                )

                # 调用 API
                result = await self.generate(
                    messages=conversation_history,
                    config=config,
                    tools=tools,
                    model=model_name,
                )

                # 检查是否有工具调用
                if not result.has_tool_calls or not result.tool_calls:
                    return result

                # 执行工具调用
                tool_calls_list = result.tool_calls
                log.info(f"OpenAI Compatible 请求调用 {len(tool_calls_list)} 个工具")

                # 将模型响应添加到对话历史
                assistant_message = {
                    "role": "assistant",
                    "content": result.content or "",
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": json.dumps(
                                    call["arguments"], ensure_ascii=False
                                ),
                            },
                        }
                        for call in tool_calls_list
                    ],
                }
                conversation_history.append(assistant_message)

                # 执行工具并添加结果
                for call in tool_calls_list:
                    try:
                        tool_result = await tool_executor(call, **kwargs)
                        tool_message = ToolConverter.tool_result_to_openai_message(
                            tool_call_id=call["id"],
                            tool_name=call["name"],
                            result=tool_result,
                            is_error=isinstance(tool_result, dict)
                            and "error" in tool_result,
                        )
                        conversation_history.append(tool_message)
                    except Exception as e:
                        log.error(f"执行工具 {call['name']} 失败: {e}")
                        tool_message = ToolConverter.tool_result_to_openai_message(
                            tool_call_id=call["id"],
                            tool_name=call["name"],
                            result={"error": str(e)},
                            is_error=True,
                        )
                        conversation_history.append(tool_message)

            # 达到最大迭代次数
            log.warning(f"OpenAI Compatible 达到最大工具调用迭代次数 {max_iterations}")
            return GenerationResult(
                content="抱歉，我在处理这个请求时遇到了一些复杂的情况，请换个方式问我。",
                model_used=model_name,
                finish_reason=FinishReason.MAX_ITERATIONS,
            )

        except Exception as e:
            log.error(f"OpenAI Compatible 工具调用生成错误: {e}", exc_info=True)
            raise GenerationError(
                f"OpenAI Compatible 工具调用生成错误: {e}",
                provider_type=self.provider_type,
                original_error=e,
            )

    async def generate_embedding(
        self, text: str, model: str = "text-embedding-ada-002", **kwargs
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
        if not self.api_key:
            log.warning("未配置 API 密钥，无法生成嵌入")
            return None

        try:
            client = self._get_client()

            response = await client.post(
                "/embeddings",
                json={
                    "model": model,
                    "input": text,
                },
            )
            response.raise_for_status()

            result_data = response.json()
            embeddings = result_data.get("data", [])

            if embeddings:
                return embeddings[0].get("embedding")
            return None

        except Exception as e:
            log.error(f"生成嵌入失败: {e}")
            return None

    def _convert_messages_to_openai_format(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        将消息转换为 OpenAI 兼容格式

        支持两种输入格式：
        - OpenAI 格式: {"role": "user", "content": "text"}
        - Gemini 格式: {"role": "user", "parts": ["text"]} 或 {"role": "user", "parts": [{"text": "..."}]}

        Args:
            messages: 消息列表

        Returns:
            List[Dict]: OpenAI 兼容格式的消息列表
        """
        converted_messages = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content")
            parts = msg.get("parts")

            # 转换角色 (model -> assistant)
            openai_role = "assistant" if role == "model" else role

            # 如果已经有 content 字段且是字符串，直接使用
            if content is not None and isinstance(content, str):
                converted_messages.append(
                    {
                        "role": openai_role,
                        "content": content,
                    }
                )
                continue

            # 如果 content 是列表（OpenAI 多部分格式）
            if content is not None and isinstance(content, list):
                # 提取文本内容
                text_parts = []
                for item in content:
                    if isinstance(item, str):
                        text_parts.append(item)
                    elif isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))

                if text_parts:
                    converted_messages.append(
                        {
                            "role": openai_role,
                            "content": "\n".join(text_parts),
                        }
                    )
                continue

            # 处理 Gemini 格式 (parts 字段)
            if parts is not None:
                text_parts = []
                if isinstance(parts, list):
                    for item in parts:
                        if isinstance(item, str):
                            if item:  # 跳过空字符串
                                text_parts.append(item)
                        elif isinstance(item, dict) and "text" in item:
                            text = item["text"]
                            if text:
                                text_parts.append(text)
                elif isinstance(parts, str):
                    if parts:
                        text_parts.append(parts)

                if text_parts:
                    converted_messages.append(
                        {
                            "role": openai_role,
                            "content": "\n".join(text_parts),
                        }
                    )
                else:
                    # 如果 parts 为空，添加一个空内容消息以避免 API 错误
                    log.warning(f"消息 parts 为空，将使用占位符内容: {msg}")
                    converted_messages.append(
                        {
                            "role": openai_role,
                            "content": " ",  # 使用空格作为占位符
                        }
                    )
                continue

            # 如果既没有 content 也没有 parts，记录警告并添加占位符
            log.warning(f"消息缺少 content 和 parts 字段: {msg}")
            converted_messages.append(
                {
                    "role": openai_role,
                    "content": " ",  # 使用空格作为占位符
                }
            )

        return converted_messages

    def _build_request_body(
        self,
        messages: List[Dict[str, Any]],
        config: GenerationConfig,
        tools: Optional[List[Any]],
        model: str,
    ) -> Dict[str, Any]:
        """
        构建 API 请求体

        Args:
            messages: 对话消息列表
            config: 生成配置
            tools: 工具列表
            model: 模型名称

        Returns:
            Dict: API 请求体
        """
        # 转换消息格式为 OpenAI 兼容格式
        converted_messages = self._convert_messages_to_openai_format(messages)

        body: Dict[str, Any] = {
            "model": model,
            "messages": converted_messages,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_output_tokens,
        }

        # 添加频率和存在惩罚
        if config.frequency_penalty is not None:
            body["frequency_penalty"] = config.frequency_penalty
        if config.presence_penalty is not None:
            body["presence_penalty"] = config.presence_penalty

        # 添加停止序列
        if config.stop_sequences:
            body["stop"] = config.stop_sequences

        # 添加响应格式
        if config.response_format:
            body["response_format"] = config.response_format

        # 添加工具
        if tools:
            body["tools"] = ToolConverter.to_openai_tools(tools)

        return body

    def _process_response(
        self, response_data: Dict[str, Any], model_name: str
    ) -> GenerationResult:
        """
        处理 API 响应

        Args:
            response_data: API 响应数据
            model_name: 模型名称

        Returns:
            GenerationResult: 生成结果
        """
        choices = response_data.get("choices", [])
        if not choices:
            return GenerationResult(
                content="",
                model_used=model_name,
                finish_reason=FinishReason.ERROR,
            )

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        # 确定结束原因
        finish_reason_str = choice.get("finish_reason", "stop")
        reason_map = {
            "stop": FinishReason.STOP,
            "length": FinishReason.MAX_TOKENS,
            "content_filter": FinishReason.SAFETY,
            "tool_calls": FinishReason.TOOL_CALL,
        }
        finish_reason = reason_map.get(finish_reason_str.lower(), FinishReason.UNKNOWN)

        # 提取工具调用
        tool_calls = None
        if "tool_calls" in message:
            tool_calls = ToolConverter.parse_openai_function_calls(response_data)
            if tool_calls:
                finish_reason = FinishReason.TOOL_CALL

        # 提取 token 使用量
        usage = response_data.get("usage", {})
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        tokens_used = (input_tokens or 0) + (output_tokens or 0)

        return GenerationResult(
            content=content,
            model_used=model_name,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            raw_response=response_data,
        )

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
