# -*- coding: utf-8 -*-
"""
工具格式转换器

在不同的 AI Provider 之间转换工具声明格式。
支持 Gemini、OpenAI、Claude 等格式。
"""

import logging
from typing import Any, Dict, List, Union

# 导入 Google Gemini types（用于 Gemini 格式转换）
from google.genai import types as genai_types

# 导入通用工具声明
from src.chat.features.tools.tool_declaration import ToolDeclaration

log = logging.getLogger(__name__)


class ToolConverter:
    """
    工具格式转换器

    在不同的 AI Provider 之间转换工具声明格式。
    支持以下格式：
    - Gemini: google.genai.types.Tool
    - OpenAI: OpenAI Function Calling 格式
    - Claude: Claude Tools 格式
    - 通用: ToolDeclaration
    """

    # ==================== Gemini 格式转换 ====================

    @staticmethod
    def to_gemini_tool(declaration: ToolDeclaration) -> genai_types.Tool:
        """
        将 ToolDeclaration 转换为 Gemini Tool 格式

        Args:
            declaration: 通用工具声明

        Returns:
            genai_types.Tool: Gemini 格式的工具
        """
        # 构建 FunctionDeclaration
        function_declaration = genai_types.FunctionDeclaration(
            name=declaration.name,
            description=declaration.description,
            parameters=ToolConverter._convert_schema_to_gemini(declaration.parameters),  # type: ignore
        )

        return genai_types.Tool(function_declarations=[function_declaration])

    @staticmethod
    def to_gemini_tools(declarations: List[ToolDeclaration]) -> List[genai_types.Tool]:
        """
        批量转换为 Gemini Tool 格式

        Args:
            declarations: 通用工具声明列表

        Returns:
            List[genai_types.Tool]: Gemini 格式的工具列表
        """
        return [ToolConverter.to_gemini_tool(d) for d in declarations]

    @staticmethod
    def _convert_schema_to_gemini(schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 JSON Schema 转换为 Gemini 兼容格式

        Gemini 对 schema 有一些特殊要求：
        1. 不支持某些 JSON Schema 关键字
        2. 需要特定的格式

        Args:
            schema: 标准 JSON Schema

        Returns:
            Dict: Gemini 兼容的 schema
        """
        # Gemini 基本兼容标准 JSON Schema，但需要清理一些不支持的属性
        result = {}

        if "type" in schema:
            result["type"] = schema["type"]

        if "description" in schema:
            result["description"] = schema["description"]

        if "properties" in schema:
            result["properties"] = {}
            for key, value in schema["properties"].items():
                result["properties"][key] = ToolConverter._convert_schema_to_gemini(
                    value
                )

        if "required" in schema:
            result["required"] = schema["required"]

        if "enum" in schema:
            result["enum"] = schema["enum"]

        if "items" in schema:
            result["items"] = ToolConverter._convert_schema_to_gemini(schema["items"])

        # 处理嵌套的 additionalProperties（用于 dict 类型）
        if "additionalProperties" in schema:
            additional = schema["additionalProperties"]
            if isinstance(additional, dict):
                result["additionalProperties"] = (
                    ToolConverter._convert_schema_to_gemini(additional)
                )

        return result

    # ==================== OpenAI 格式转换 ====================

    @staticmethod
    def to_openai_tool(declaration: ToolDeclaration) -> Dict[str, Any]:
        """
        将 ToolDeclaration 转换为 OpenAI Tool 格式

        Args:
            declaration: 通用工具声明

        Returns:
            Dict: OpenAI 格式的工具
        """
        return declaration.to_openai_format()

    @staticmethod
    def to_openai_tools(declarations: List[ToolDeclaration]) -> List[Dict[str, Any]]:
        """
        批量转换为 OpenAI Tool 格式

        Args:
            declarations: 通用工具声明列表

        Returns:
            List[Dict]: OpenAI 格式的工具列表
        """
        return [ToolConverter.to_openai_tool(d) for d in declarations]

    # ==================== Claude 格式转换 ====================

    @staticmethod
    def to_claude_tool(declaration: ToolDeclaration) -> Dict[str, Any]:
        """
        将 ToolDeclaration 转换为 Claude Tool 格式

        Args:
            declaration: 通用工具声明

        Returns:
            Dict: Claude 格式的工具
        """
        return declaration.to_claude_format()

    @staticmethod
    def to_claude_tools(declarations: List[ToolDeclaration]) -> List[Dict[str, Any]]:
        """
        批量转换为 Claude Tool 格式

        Args:
            declarations: 通用工具声明列表

        Returns:
            List[Dict]: Claude 格式的工具列表
        """
        return [ToolConverter.to_claude_tool(d) for d in declarations]

    # ==================== 工具调用结果转换 ====================

    @staticmethod
    def tool_result_to_gemini_part(
        tool_name: str, result: Dict[str, Any], is_error: bool = False
    ) -> genai_types.Part:
        """
        将工具执行结果转换为 Gemini Part 格式

        Args:
            tool_name: 工具名称
            result: 工具执行结果
            is_error: 是否是错误结果

        Returns:
            genai_types.Part: Gemini 格式的 Part
        """
        if is_error:
            response = {"error": result.get("error", "Unknown error")}
        else:
            response = {"result": result}

        return genai_types.Part.from_function_response(
            name=tool_name,
            response=response,
        )

    @staticmethod
    def tool_result_to_openai_message(
        tool_call_id: str,
        tool_name: str,
        result: Dict[str, Any],
        is_error: bool = False,
    ) -> Dict[str, Any]:
        """
        将工具执行结果转换为 OpenAI 消息格式

        Args:
            tool_call_id: 工具调用 ID
            tool_name: 工具名称
            result: 工具执行结果
            is_error: 是否是错误结果

        Returns:
            Dict: OpenAI 格式的工具结果消息
        """
        import json

        if is_error:
            content = json.dumps({"error": result.get("error", "Unknown error")})
        else:
            content = json.dumps(result, ensure_ascii=False)

        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content,
        }

    # ==================== 工具调用解析 ====================

    @staticmethod
    def parse_gemini_function_calls(
        response: genai_types.GenerateContentResponse,
    ) -> List[Dict[str, Any]]:
        """
        从 Gemini 响应中解析函数调用

        Args:
            response: Gemini 响应对象

        Returns:
            List[Dict]: 函数调用列表，每个包含 name 和 args
        """
        function_calls = []

        if hasattr(response, "function_calls") and response.function_calls:
            for call in response.function_calls:
                function_calls.append(
                    {
                        "id": getattr(call, "id", None),
                        "name": call.name,
                        "arguments": dict(call.args) if call.args else {},
                    }
                )

        return function_calls

    @staticmethod
    def parse_openai_function_calls(response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从 OpenAI 响应中解析函数调用

        Args:
            response: OpenAI 响应对象

        Returns:
            List[Dict]: 函数调用列表，每个包含 id、name 和 arguments
        """
        import json

        function_calls = []

        message = response.get("choices", [{}])[0].get("message", {})
        tool_calls = message.get("tool_calls", [])

        for call in tool_calls:
            if call.get("type") == "function":
                function_info = call.get("function", {})
                arguments_str = function_info.get("arguments", "{}")

                try:
                    arguments = json.loads(arguments_str)
                except json.JSONDecodeError:
                    arguments = {}

                function_calls.append(
                    {
                        "id": call.get("id"),
                        "name": function_info.get("name"),
                        "arguments": arguments,
                    }
                )

        return function_calls

    # ==================== 通用转换方法 ====================

    @staticmethod
    def convert_for_provider(
        declarations: List[ToolDeclaration], provider_type: str
    ) -> Union[List[genai_types.Tool], List[Dict[str, Any]]]:
        """
        根据 Provider 类型自动转换工具声明

        Args:
            declarations: 通用工具声明列表
            provider_type: Provider 类型 (gemini, openai, deepseek, claude 等)

        Returns:
            转换后的工具列表
        """
        provider_type = provider_type.lower()

        if provider_type in ["gemini", "gemini_official", "gemini_custom"]:
            return ToolConverter.to_gemini_tools(declarations)
        elif provider_type in ["openai", "openai_compatible", "deepseek"]:
            return ToolConverter.to_openai_tools(declarations)
        elif provider_type in ["claude"]:
            return ToolConverter.to_claude_tools(declarations)
        else:
            # 默认使用 OpenAI 格式
            log.warning(f"未知的 Provider 类型 '{provider_type}'，使用 OpenAI 格式")
            return ToolConverter.to_openai_tools(declarations)
