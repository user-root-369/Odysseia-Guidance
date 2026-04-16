# -*- coding: utf-8 -*-
"""
综合研究工具 - 基于 YouAPI Research 的多步搜索与综合

使用 You.com Research API (POST /v1/research) 进行深度研究。
该端点会自动执行多次搜索、阅读来源，并综合成带引用的详细答案。

API 文档: docs/api-docs/you-api/v1-research.md
"""

import logging
import os
from typing import List, Optional

import aiohttp
from pydantic import BaseModel, Field

from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)

# YouAPI Research 配置
YOU_RESEARCH_API_URL = "https://api.you.com/v1/research"
YOU_API_KEY = os.getenv("YOU_API_KEY")

# 研究结果最大字符数（防止超长回复占满 context）
MAX_RESEARCH_CONTENT_LENGTH = 4000
# 每条来源摘要的最大字符数
MAX_SOURCE_SNIPPET_LENGTH = 300


class WebResearchParams(BaseModel):
    """综合研究参数"""

    input: str = Field(
        ...,
        description="研究问题或复杂查询。支持自然语言提问，最长 40000 字符。",
    )
    research_effort: str = Field(
        default="standard",
        description="研究深度：lite（快速简答）/ standard（默认平衡）/ deep（深度交叉验证）/ exhaustive（最彻底，适合复杂研究）。",
    )


def _truncate(text: str, max_length: int) -> str:
    """截断文本到指定长度"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def _format_research_source(source: dict, index: int) -> str:
    """格式化单个来源引用"""
    title = source.get("title", "")
    url = source.get("url", "")
    snippets = source.get("snippets", [])

    parts = [f"[{index}]"]
    if title:
        parts[0] += f" {title}"
    if url:
        parts.append(f"    链接: {url}")
    if snippets:
        snippet_text = " ".join(snippets)
        snippet_text = _truncate(snippet_text, MAX_SOURCE_SNIPPET_LENGTH)
        parts.append(f"    摘要: {snippet_text}")

    return "\n".join(parts)


@tool_metadata(
    name="综合研究",
    description="多步深度研究，适合复杂问题，自动多次搜索并综合答案",
    emoji="📚",
    category="查询",
)
async def web_research(
    params: WebResearchParams,
    **kwargs,
) -> List[str]:
    """
    综合研究工具。适用于需要多步搜索、综合多来源信息的复杂问题。
    该工具会自动执行多次搜索、阅读和交叉验证来源，生成带引用的详细答案。

    在以下场景中使用：
    - 用户需要比较多个平台的功能、价格、试用福利等
    - 用户提出复杂的调研型问题（如"2024年最好的XX工具有哪些"）
    - 用户需要全面了解某个话题（如"XX技术的优缺点"）
    - 需要交叉验证多个来源的信息时
    - web_search 返回的简单搜索结果不能满足用户需求时

    research_effort 选择指南：
    - lite: 简单问题快速回答（约 5s）
    - standard: 大多数问题的默认选择（约 10-15s）
    - deep: 需要准确性和深度时使用（约 20-30s）
    - exhaustive: 最彻底的研究，适合重要决策（约 30-60s）

    注意：此工具响应时间较长（10-60秒），请仅在确实需要深度研究时使用。
    简单的信息查询请使用 web_search。

    返回格式：
    - 返回一个包含研究答案和来源引用的字符串列表。
    - 你在最终回复时，必须原样输出搜索结果中的链接，**不要**对链接进行任何形式的再加工。
    """
    api_key = YOU_API_KEY or os.getenv("YOU_API_KEY")
    if not api_key:
        log.error("YOU_API_KEY 未配置，无法执行综合研究。")
        return ["错误：综合研究服务未配置 API Key，请联系管理员。"]

    question = params.input
    if not question or not question.strip():
        return ["错误：研究问题不能为空。"]

    # 验证研究深度
    valid_efforts = ["lite", "standard", "deep", "exhaustive"]
    effort = params.research_effort if params.research_effort in valid_efforts else "standard"

    log.info(
        f"工具 'web_research' 被调用，问题: '{question[:100]}...', "
        f"research_effort: {effort}"
    )

    # 构建请求
    request_body = {
        "input": question,
        "research_effort": effort,
    }

    # 根据研究深度调整超时时间
    timeout_map = {
        "lite": 15,
        "standard": 30,
        "deep": 60,
        "exhaustive": 90,
    }
    timeout_seconds = timeout_map.get(effort, 30)

    try:
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                YOU_RESEARCH_API_URL,
                json=request_body,
                headers={
                    "X-API-Key": api_key,
                    "Content-Type": "application/json",
                },
            ) as response:
                if response.status == 401:
                    log.error("YouAPI Research 认证失败：API Key 无效或已过期。")
                    return ["错误：研究服务认证失败，请检查 API Key。"]
                elif response.status == 402:
                    log.error("YouAPI Research 额度不足。")
                    return ["错误：研究服务额度已用完，请联系管理员。"]
                elif response.status == 403:
                    log.error("YouAPI Research 权限不足：API Key 缺少 research 范围。")
                    return ["错误：API Key 缺少研究功能的权限，请联系管理员。"]
                elif response.status == 429:
                    log.warning("YouAPI Research 请求频率超限。")
                    return ["研究请求太频繁了，请稍后再试。"]
                elif response.status == 422:
                    error_text = await response.text()
                    log.error(f"YouAPI Research 请求参数无效: {error_text[:200]}")
                    return ["研究请求参数无效，请换个方式描述你的问题。"]
                elif response.status != 200:
                    error_text = await response.text()
                    log.error(
                        f"YouAPI Research 请求失败，状态码: {response.status}，"
                        f"响应: {error_text[:200]}"
                    )
                    return [f"研究请求失败（状态码 {response.status}），请稍后再试。"]

                data = await response.json()

    except aiohttp.ClientError as e:
        log.error(f"YouAPI Research 网络请求异常: {e}", exc_info=True)
        return ["综合研究请求失败，可能是网络连接问题，请稍后再试。"]
    except asyncio.TimeoutError:
        log.warning(f"YouAPI Research 请求超时（{timeout_seconds}s），研究深度: {effort}")
        return ["综合研究请求超时，可能是问题太复杂了。请尝试简化问题或降低研究深度。"]
    except Exception as e:
        log.error(f"YouAPI Research 调用时发生未知错误: {e}", exc_info=True)
        return ["综合研究时发生意外错误。"]

    # 解析结果
    output = data.get("output", {})
    content = output.get("content", "")
    sources = output.get("sources", [])

    if not content:
        log.info(f"YouAPI Research 对 '{question[:50]}...' 无结果。")
        return ["未能找到相关研究结果，请尝试换个描述方式。"]

    # 构建输出
    output_list = []

    # 主要研究内容（截断防止 context 爆炸）
    content_truncated = _truncate(content, MAX_RESEARCH_CONTENT_LENGTH)
    output_list.append(f"研究结果:\n{content_truncated}")

    # 来源列表
    if sources:
        source_parts = ["参考来源:"]
        for idx, source in enumerate(sources, 1):
            formatted_source = _format_research_source(source, idx)
            source_parts.append(formatted_source)
        output_list.append("\n".join(source_parts))

    log.info(
        f"YouAPI Research 对 '{question[:50]}...' 返回结果，"
        f"内容长度: {len(content)} 字符，来源: {len(sources)} 个"
        f"（研究深度: {effort}）"
    )
    return output_list
