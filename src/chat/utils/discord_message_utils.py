import logging
import re
from collections.abc import Awaitable, Callable
from typing import Optional

import discord

from src.chat.config.chat_config import MESSAGE_SETTINGS

log = logging.getLogger(__name__)

CUSTOM_EMOJI_PATTERN = re.compile(r"<a?:.+?:\d+>")


def get_text_length_without_emojis(text: str) -> int:
    text_without_emojis = CUSTOM_EMOJI_PATTERN.sub("", text)
    return len(text_without_emojis)


def split_discord_message(text: str, limit: int | None = None) -> list[str]:
    max_length = limit or MESSAGE_SETTINGS["SINGLE_MESSAGE_LIMIT"]
    if get_text_length_without_emojis(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text.strip()
    separators = ("\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", "，", ", ", " ")

    while remaining:
        if get_text_length_without_emojis(remaining) <= max_length:
            chunks.append(remaining)
            break

        split_at = -1
        window = remaining[: max_length + 1]
        for separator in separators:
            candidate = window.rfind(separator)
            if candidate > split_at:
                split_at = candidate + len(separator)

        if split_at <= 0:
            split_at = max_length

        chunk = remaining[:split_at].strip()
        if not chunk:
            chunk = remaining[:max_length]
            split_at = len(chunk)

        chunks.append(chunk)
        remaining = remaining[split_at:].strip()

    return chunks


async def send_split_message(
    send_first_chunk: Callable[..., Awaitable[discord.Message]],
    send_followup_chunk: Callable[..., Awaitable[discord.Message]],
    content: str,
    *,
    files: Optional[list[discord.File]] = None,
    mention_author: bool = False,
) -> None:
    chunks = split_discord_message(content)
    for index, chunk in enumerate(chunks):
        kwargs = {}
        if index == 0:
            if files:
                kwargs["files"] = files
            if mention_author:
                kwargs["mention_author"] = True
            await send_first_chunk(chunk, **kwargs)
            continue

        await send_followup_chunk(chunk)


async def send_via_dm_in_chunks(
    user: discord.abc.Messageable,
    content: str,
    *,
    files: Optional[list[discord.File]] = None,
    prefix: str | None = None,
) -> None:
    first_chunk = content
    if prefix:
        first_chunk = f"{prefix}\n\n{content}"

    chunks = split_discord_message(first_chunk)
    for index, chunk in enumerate(chunks):
        kwargs = {"files": files} if index == 0 and files else {}
        await user.send(chunk, **kwargs)


def should_send_via_dm(content: str, dm_threshold: int | None = None) -> bool:
    threshold = dm_threshold or MESSAGE_SETTINGS["CHANNEL_DM_THRESHOLD"]
    return get_text_length_without_emojis(content) > threshold
