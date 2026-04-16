# -*- coding: utf-8 -*-
"""
网络搜索工具 - 基于 YouAPI 的日常广度搜索

使用 You.com Web Search API (GET /v1/search) 进行通用网络搜索。
返回 LLM-ready 的结构化搜索结果，包括网页和新闻。

API 文档: docs/api-docs/you-api/v1-search.md
"""

import logging
import os
from typing import List, Optional

import aiohttp
from pydantic import BaseModel, Field

from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)

# YouAPI 配置
YOU_API_BASE_URL = "https://ydc-index.io/v1/search"
YOU_API_KEY = os.getenv("YOU_API_KEY")

# 每条 snippet 最大字符数
MAX_SNIPPET_LENGTH = 500
# 默认返回结果数
DEFAULT_COUNT = 8


class WebSearchParams(BaseModel):
    """网络搜索参数"""

    query: str = Field(
        ...,
        description="搜索关键词。",
    )
    count: int = Field(
        default=DEFAULT_COUNT,
        description="返回结果数量，1-20。建议至少传入 5 以获取足够的信息。",
    )
    freshness: Optional[str] = Field(
        default=None,
        description="结果时效性过滤：day/week/month/year，或日期范围 YYYY-MM-DDtoYYYY-MM-DD。",
    )


def _truncate(text: str, max_length: int = MAX_SNIPPET_LENGTH) -> str:
    """截断文本到指定长度"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def _format_web_result(result: dict) -> str:
    """将单条 WebResult/NewsResult 格式化为可读字符串"""
    title = result.get("title", "无标题")
    url = result.get("url", "")

    # 拼接所有 snippets 以获取更丰富的信息
    snippets = result.get("snippets", [])
    description = result.get("description", "")
    if snippets:
        # 拼接所有 snippet，用空格分隔
        snippet_text = " ".join(snippets)
        # 如果 description 也存在且不重复，则合并
        if description and description not in snippet_text:
            description = f"{description} {snippet_text}"
        else:
            description = snippet_text
    
    description = _truncate(description)

    parts = [f"标题: {title}"]
    if description:
        parts.append(f"摘要: {description}")
    if url:
        parts.append(f"来源: {url}")

    return "\n".join(parts)


@tool_metadata(
    name="网络搜索",
    description="通过搜索引擎查询最新信息、新闻、产品资料等",
    emoji="🌐",
    category="查询",
)
async def web_search(
    params: WebSearchParams,
    **kwargs,
) -> List[str]:
    """
    日常网络搜索工具。适用于：
    - 查询最新新闻、时事动态
    - 搜索产品信息、价格对比
    - 常识问答、百科查询
    - 验证信息的准确性
    - 查找官方网站和文档

    当用户要求联网搜索、查询最新信息时使用此工具。

    返回格式：
    - 返回一个字符串列表，每个字符串包含标题、摘要和来源链接。
    - 你在最终回复时，必须原样输出搜索结果中的链接，**不要**对链接进行任何形式的再加工。
    """
    api_key = YOU_API_KEY or os.getenv("YOU_API_KEY")
    if not api_key:
        log.error("YOU_API_KEY 未配置，无法执行网络搜索。")
        return ["错误：网络搜索服务未配置 API Key，请联系管理员。"]

    query = params.query
    if not query or not query.strip():
        return ["错误：搜索关键词不能为空。"]

    count = min(max(params.count, 1), 20)

    log.info(f"工具 'web_search' 被调用，查询: '{query}', count: {count}")

    # 构建请求参数
    request_params = {
        "query": query,
        "count": count,
        "safesearch": "off",
        "country": "CN",
        "language": "ZH-HANS",
    }

    if params.freshness:
        request_params["freshness"] = params.freshness

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                YOU_API_BASE_URL,
                params=request_params,
                headers={"X-API-Key": api_key},
            ) as response:
                if response.status == 401:
                    log.error("YouAPI 认证失败：API Key 无效或已过期。")
                    return ["错误：搜索服务认证失败，请检查 API Key。"]
                elif response.status == 402:
                    log.error("YouAPI 额度不足。")
                    return ["错误：搜索服务额度已用完，请联系管理员。"]
                elif response.status == 429:
                    log.warning("YouAPI 请求频率超限。")
                    return ["搜索请求太频繁了，请稍后再试。"]
                elif response.status != 200:
                    error_text = await response.text()
                    log.error(
                        f"YouAPI 请求失败，状态码: {response.status}，响应: {error_text[:200]}"
                    )
                    return [f"搜索请求失败（状态码 {response.status}），请稍后再试。"]

                data = await response.json()

    except aiohttp.ClientError as e:
        log.error(f"YouAPI 网络请求异常: {e}", exc_info=True)
        return ["网络搜索请求失败，可能是网络连接问题，请稍后再试。"]
    except Exception as e:
        log.error(f"YouAPI 调用时发生未知错误: {e}", exc_info=True)
        return ["网络搜索时发生意外错误。"]

    # 解析结果
    results_data = data.get("results", {})
    web_results = results_data.get("web", [])
    news_results = results_data.get("news", [])

    output_list = []

    # 处理网页结果
    for result in web_results[:count]:
        formatted = _format_web_result(result)
        if formatted:
            output_list.append(formatted)

    # 处理新闻结果（追加，但不超过总 count）
    remaining = count - len(output_list)
    if remaining > 0:
        for result in news_results[:remaining]:
            formatted = _format_web_result(result)
            if formatted:
                output_list.append(formatted)

    if not output_list:
        log.info(f"YouAPI 搜索 '{query}' 无结果。")
        return []

    log.info(f"YouAPI 搜索 '{query}' 返回 {len(output_list)} 条结果。")
    return output_list
