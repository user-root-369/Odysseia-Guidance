# -*- coding: utf-8 -*-
"""
AI 服务兼容层

提供与旧 GeminiService 兼容的接口，内部使用新的 AIService 实现。
这样可以平滑迁移，无需修改所有调用方。

使用方法：
    # 旧代码
    from src.chat.services.gemini_service import gemini_service

    # 新代码（兼容层）
    from src.chat.services.ai.compat_service import gemini_service

    # 或者使用新的 AIService
    from src.chat.services.ai.service import ai_service
"""

import logging
from typing import Optional, Dict, List, Any

from .service import ai_service as _ai_service
from .providers.base import GenerationConfig

log = logging.getLogger(__name__)


class GeminiServiceCompat:
    """
    GeminiService 兼容层

    提供与旧 GeminiService 相同的公共方法签名，内部使用新的 AIService。
    """

    def __init__(self):
        """初始化兼容层"""
        self._ai_service = _ai_service
        self._bot = None
        self._tool_service = None
        self._available_tools = []
        self._tool_map = {}
        self.last_called_tools: List[str] = []

    # === 属性（与旧 gemini_service 兼容）===

    @property
    def bot(self):
        """获取 Bot 实例"""
        return self._bot

    @bot.setter
    def bot(self, value):
        """设置 Bot 实例"""
        self._bot = value
        self._ai_service.set_bot(value)

    @property
    def tool_service(self):
        """获取工具服务"""
        return self._tool_service

    @tool_service.setter
    def tool_service(self, value):
        """设置工具服务"""
        self._tool_service = value
        self._ai_service.set_tools(self._available_tools, self._tool_map, value)

    @property
    def available_tools(self):
        """获取可用工具列表"""
        return self._available_tools

    @available_tools.setter
    def available_tools(self, value):
        """设置可用工具列表"""
        self._available_tools = value
        self._ai_service.set_tools(value, self._tool_map, self._tool_service)

    @property
    def tool_map(self):
        """获取工具映射"""
        return self._tool_map

    @tool_map.setter
    def tool_map(self, value):
        """设置工具映射"""
        self._tool_map = value
        self._ai_service.set_tools(self._available_tools, value, self._tool_service)

    @property
    def key_rotation_service(self):
        """获取密钥轮换服务（兼容属性）"""
        # 返回一个兼容对象
        return self._ai_service.get_provider("gemini_official")

    # === 方法（与旧 gemini_service 兼容）===

    def set_bot(self, bot):
        """设置 Discord Bot 实例"""
        self._bot = bot
        self._ai_service.set_bot(bot)
        log.info("Discord Bot 实例已注入 GeminiServiceCompat")

    async def generate_response(
        self,
        user_id: int,
        guild_id: int,
        message: str,
        channel: Optional[Any] = None,
        replied_message: Optional[str] = None,
        images: Optional[List[Dict]] = None,
        user_name: str = "用户",
        channel_context: Optional[List[Dict]] = None,
        world_book_entries: Optional[List[Dict]] = None,
        personal_summary: Optional[str] = None,
        affection_status: Optional[Dict[str, Any]] = None,
        user_profile_data: Optional[Dict[str, Any]] = None,
        guild_name: str = "未知服务器",
        location_name: str = "未知位置",
        model_name: Optional[str] = None,
        user_id_for_settings: Optional[str] = None,
        conversation_memory: Optional[str] = None,
        latest_block: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        AI 回复生成（兼容方法）

        这是一个兼容层方法，内部调用新的 AIService。
        注意：此方法需要与 prompt_service 配合使用来构建完整的对话上下文。
        """
        # 由于旧方法非常复杂，这里提供一个简化的实现
        # 实际迁移时，应该重构调用方使用新的接口

        log.warning(
            "generate_response 是兼容层方法，建议迁移到新的 AIService.generate_with_tools"
        )

        # 构建基本消息
        messages = [{"role": "user", "content": message}]

        try:
            config = GenerationConfig()

            result = await self._ai_service.generate(
                messages=messages,
                config=config,
                model=model_name,
                fallback=True,
            )

            return result.content

        except Exception as e:
            log.error(f"generate_response 失败: {e}", exc_info=True)
            return "呜哇，有点晕嘞，等我休息一会儿 <伤心>"

    async def generate_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
        title: Optional[str] = None,
        **kwargs,
    ) -> Optional[List[float]]:
        """
        生成文本嵌入向量（兼容方法）
        """
        return await self._ai_service.generate_embedding(text, **kwargs)

    async def generate_text(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        model_name: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        简单文本生成（兼容方法）
        """
        config = GenerationConfig()
        if temperature is not None:
            config.temperature = temperature

        messages = [{"role": "user", "content": prompt}]

        try:
            result = await self._ai_service.generate(
                messages=messages,
                config=config,
                model=model_name,
                fallback=True,
            )
            return result.content
        except Exception as e:
            log.error(f"generate_text 失败: {e}", exc_info=True)
            return None

    async def generate_simple_response(
        self,
        prompt: str,
        generation_config: Dict,
        model_name: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        单次文本生成（兼容方法）
        """
        config = GenerationConfig(
            temperature=generation_config.get("temperature", 1.0),
            top_p=generation_config.get("top_p", 0.95),
            max_output_tokens=generation_config.get("max_output_tokens", 6000),
        )

        messages = [{"role": "user", "content": prompt}]

        try:
            result = await self._ai_service.generate(
                messages=messages,
                config=config,
                model=model_name,
                fallback=False,  # 简单生成不需要故障转移
            )
            return result.content
        except Exception as e:
            log.error(f"generate_simple_response 失败: {e}", exc_info=True)
            return None

    async def generate_thread_praise(
        self, conversation_history: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        暖贴功能（兼容方法）
        """
        # 使用特定的暖贴模型
        from src.chat.config import chat_config as app_config

        model_name = getattr(app_config, "THREAD_PRAISE_MODEL", "gemini-2.5-flash")

        try:
            result = await self._ai_service.generate(
                messages=conversation_history,
                config=GenerationConfig(temperature=1.2),
                model=model_name,
                fallback=True,
            )
            return result.content
        except Exception as e:
            log.error(f"generate_thread_praise 失败: {e}", exc_info=True)
            return None

    async def generate_text_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str,
        model_name: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        图文生成（兼容方法）
        """
        import base64

        # 构建 Base64 图片 URL
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:{mime_type};base64,{base64_image}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]

        try:
            result = await self._ai_service.generate(
                messages=messages,
                config=GenerationConfig(),
                model=model_name,
                fallback=True,
            )
            return result.content
        except Exception as e:
            log.error(f"generate_text_with_image 失败: {e}", exc_info=True)
            return None

    async def generate_confession_response(
        self, prompt: str, model_name: Optional[str] = None, **kwargs
    ) -> Optional[str]:
        """
        忏悔功能（兼容方法）
        """
        messages = [{"role": "user", "content": prompt}]

        try:
            result = await self._ai_service.generate(
                messages=messages,
                config=GenerationConfig(temperature=1.5),
                model=model_name,
                fallback=True,
            )
            return result.content
        except Exception as e:
            log.error(f"generate_confession_response 失败: {e}", exc_info=True)
            return None

    def is_available(self) -> bool:
        """检查服务是否可用"""
        return self._ai_service.is_available()

    async def clear_user_context(self, user_id: int, guild_id: int):
        """清除用户上下文（兼容方法）"""
        # 此功能由 chat_db_manager 处理，这里只是兼容层
        log.info(f"clear_user_context 被调用 (user_id={user_id}, guild_id={guild_id})")


# 全局兼容实例
gemini_service = GeminiServiceCompat()


# 导出
__all__ = ["gemini_service", "GeminiServiceCompat"]
