# -*- coding: utf-8 -*-
"""
频道总结工具 - 获取频道消息历史供模型生成文本总结
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

import discord
from pydantic import BaseModel, Field

from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)


MAX_MESSAGE_LENGTH = 500
MAX_TOTAL_CHARS = 20000
URL_ONLY_PATTERN = re.compile(r"^https?://\S+$")
CUSTOM_EMOJI_PATTERN = re.compile(r"<a?:.+?:\d+>")
WHITESPACE_PATTERN = re.compile(r"\s+")
REPEATED_CHAR_PATTERN = re.compile(r"(.)\1{8,}")


class SummarizeChannelParams(BaseModel):
    """频道总结参数"""

    limit: int = Field(
        default=200,
        description="要获取的消息数量，默认200条。",
    )
    start_date: Optional[str] = Field(
        None,
        description="开始日期 (格式: YYYY-MM-DD)",
    )
    end_date: Optional[str] = Field(
        None,
        description="结束日期 (格式: YYYY-MM-DD)",
    )


@tool_metadata(
    name="总结",
    description="提取频道消息历史供模型生成文本总结，可指定消息数量和时间范围",
    emoji="📝",
    category="总结",
)
async def summarize_channel(
    params: SummarizeChannelParams,
    **kwargs,
) -> str:
    """
    被要求总结时必须使用, 获取当前频道的消息历史。
    仅在用户明确要求"总结"时使用。
    返回清洗后的消息文本，供模型生成结构化总结。
    """
    channel = kwargs.get("channel")
    if not channel or not isinstance(channel, discord.abc.Messageable):
        return "错误：无法在当前上下文中找到有效的频道。"

    limit = min(params.limit, 500)

    after = None
    if params.start_date:
        try:
            after = datetime.strptime(params.start_date, "%Y-%m-%d")
        except ValueError:
            return "错误: `start_date` 格式不正确，请使用 YYYY-MM-DD 格式。"

    before = None
    if params.end_date:
        try:
            before = datetime.strptime(params.end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            return "错误: `end_date` 格式不正确，请使用 YYYY-MM-DD 格式。"

    channel_id = getattr(channel, "id", "未知")
    log.info(
        f"工具 'summarize_channel' 被调用，在频道 {channel_id} 中获取 {limit} 条消息"
    )

    try:
        messages = []
        total_chars = 0

        async for message in channel.history(limit=limit, before=before, after=after):
            if message.author.bot:
                continue

            cleaned_content = _normalize_message_content(message.content)
            if not cleaned_content:
                continue

            local_time = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            formatted_message = (
                f"{message.author.display_name}({local_time}): {cleaned_content}"
            )

            if total_chars + len(formatted_message) > MAX_TOTAL_CHARS:
                log.info(
                    f"频道 {channel_id} 的总结消息已达到字符上限 {MAX_TOTAL_CHARS}，提前截断。"
                )
                break

            messages.append(formatted_message)
            total_chars += len(formatted_message)

        messages.reverse()

        if not messages:
            return "在指定范围内没有找到可用于总结的消息。"

        return "\n".join(messages)

    except discord.Forbidden:
        log.error(f"机器人缺少访问频道 {channel_id} 历史记录的权限。")
        return "错误：我没有权限查看这个频道的历史记录。"
    except Exception as e:
        log.error(f"处理频道 {channel_id} 的消息时发生未知错误: {e}")
        return f"错误：处理消息时发生未知错误: {e}"


def _normalize_message_content(content: str) -> Optional[str]:
    """对消息文本做轻量清洗，减少无意义噪音。"""
    if not content:
        return None

    cleaned = CUSTOM_EMOJI_PATTERN.sub("", content)
    cleaned = cleaned.replace("\r", "\n")
    cleaned = WHITESPACE_PATTERN.sub(" ", cleaned).strip()

    if not cleaned or URL_ONLY_PATTERN.fullmatch(cleaned):
        return None

    cleaned = REPEATED_CHAR_PATTERN.sub(lambda match: match.group(1) * 4, cleaned)

    if len(cleaned) > MAX_MESSAGE_LENGTH:
        cleaned = f"{cleaned[:MAX_MESSAGE_LENGTH]}..."

    return cleaned
