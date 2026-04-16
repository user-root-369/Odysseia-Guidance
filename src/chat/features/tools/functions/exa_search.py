# -*- coding: utf-8 -*-
"""
深度搜索工具 - 基于 Exa 的深度语义搜索

使用 Exa Search API (POST /search) 进行深度语义搜索。
支持多种搜索级别：auto / deep / deep-reasoning 等。
可返回页面内容摘要、高亮和 AI 总结。

API 文档: docs/api-docs/exa/search.md
SDK: exa-py (pip install exa-py)
"""

import asyncio
import logging
import os
from typing import List, Optional

from pydantic import BaseModel, Field

from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)

# Exa 配置
EXA_API_KEY = os.getenv("EXA_API_KEY")

# 高亮摘要的最大字符数
MAX_HIGHLIGHT_CHARS = 3000
# 每条结果摘要的最大字符数（用于输出截断）
MAX_RESULT_SNIPPET_LENGTH = 800
# 默认返回结果数
DEFAULT_NUM_RESULTS = 8


class ExaSearchParams(BaseModel):
    """深度搜索参数"""

    query: str = Field(
        ...,
        description="搜索查询，可以是关键词或自然语言描述。",
    )
    num_results: int = Field(
        default=DEFAULT_NUM_RESULTS,
        description="返回结果数量，1-15。建议至少传入 5 以获取足够的资源链接。",
    )
    search_type: str = Field(
        default="deep",
        description="搜索深度：auto（自动平衡速度和质量）/ deep（深度搜索，推荐）/ deep-reasoning（最强推理搜索，适合复杂问题）。",
    )
    category: Optional[str] = Field(
        default=None,
        description="搜索类别：research paper / news / company / personal site / people。不确定时留空。",
    )
    use_contents: bool = Field(
        default=True,
        description="是否获取页面内容摘要。查找资源链接、详细信息时建议开启。",
    )


def _truncate(text: str, max_length: int = MAX_RESULT_SNIPPET_LENGTH) -> str:
    """截断文本到指定长度"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def _format_exa_result(result) -> str:
    """
    将单条 Exa SearchResult 格式化为可读字符串。

    result 对象的属性（来自 exa-py SDK）：
    - title: str
    - url: str
    - published_date: Optional[str]
    - author: Optional[str]
    - score: Optional[float]
    - text: Optional[str]  (当请求 contents.text 时)
    - highlights: Optional[List[str]]  (当请求 contents.highlights 时)
    - summary: Optional[str]  (当请求 contents.summary 时)
    """
    title = getattr(result, "title", "无标题") or "无标题"
    url = getattr(result, "url", "")

    # 优先使用 highlights，其次 summary，最后 text
    snippet = ""
    highlights = getattr(result, "highlights", None)
    if highlights and isinstance(highlights, list) and len(highlights) > 0:
        snippet = " ".join(highlights)
    else:
        summary = getattr(result, "summary", None)
        if summary:
            snippet = summary
        else:
            text = getattr(result, "text", None)
            if text:
                snippet = text

    snippet = _truncate(snippet)

    published_date = getattr(result, "published_date", None)

    parts = [f"标题: {title}"]
    if snippet:
        parts.append(f"摘要: {snippet}")
    if url:
        parts.append(f"来源: {url}")
    if published_date:
        # 截取日期部分 (YYYY-MM-DD)
        date_str = str(published_date)[:10]
        parts.append(f"发布日期: {date_str}")

    return "\n".join(parts)


@tool_metadata(
    name="深度搜索",
    description="深度语义搜索，用于查找资源链接、工具推荐、GitHub 项目等",
    emoji="🔬",
    category="查询",
)
async def exa_search(
    params: ExaSearchParams,
    **kwargs,
) -> List[str]:
    """
    深度语义搜索工具。在以下场景中使用：
    - 用户要求查找具体的下载链接、资源合集
    - 用户需要 GitHub 项目、开源工具推荐
    - 用户寻找模型资源、插件、扩展
    - 用户需要学术论文或专业文献
    - 用户要求工具推荐列表或对比
    - 普通搜索（web_search）结果不够详细或未能找到时
    - 小众内容、专业技术内容查找

    此工具与 web_search 配合使用。通常先用 web_search 获取广度信息，
    当结果不满足需求时再调用此工具进行深度搜索。

    当用户明确说"找资源""找链接""找工具""深度搜索"时，直接调用此工具。

    search_type 选择指南：
    - 一般情况使用 deep（默认），平衡深度和速度
    - 复杂问题（如技术对比、方案调研）使用 deep-reasoning
    - 快速检索使用 auto

    重要：请传入足够的 num_results（建议 5-10），不要只传 1，
    用户通常需要多个资源链接来比较和选择。

    返回格式：
    - 返回一个字符串列表，每个字符串包含标题、摘要、来源链接和发布日期。
    - 你在最终回复时，必须原样输出搜索结果中的链接，**不要**对链接进行任何形式的再加工。
    """
    api_key = EXA_API_KEY or os.getenv("EXA_API_KEY")
    if not api_key:
        log.error("EXA_API_KEY 未配置，无法执行深度搜索。")
        return ["错误：深度搜索服务未配置 API Key，请联系管理员。"]

    query = params.query
    if not query or not query.strip():
        return ["错误：搜索查询不能为空。"]

    num_results = min(max(params.num_results, 1), 15)

    # 验证搜索类型
    valid_search_types = ["auto", "neural", "fast", "instant", "deep-lite", "deep", "deep-reasoning"]
    search_type = params.search_type if params.search_type in valid_search_types else "deep"

    log.info(
        f"工具 'exa_search' 被调用，查询: '{query}', "
        f"num_results: {num_results}, search_type: {search_type}, "
        f"category: {params.category}, use_contents: {params.use_contents}"
    )

    try:
        # 延迟导入 exa-py SDK，避免在未安装时阻塞其他工具加载
        from exa_py import Exa

        exa = Exa(api_key)

        # 构建搜索参数
        search_kwargs = {
            "num_results": num_results,
            "type": search_type,
        }

        # 添加可选的 category 过滤
        if params.category:
            valid_categories = [
                "company",
                "research paper",
                "news",
                "personal site",
                "financial report",
                "people",
            ]
            if params.category.lower() in [c.lower() for c in valid_categories]:
                search_kwargs["category"] = params.category
            else:
                log.warning(
                    f"无效的 Exa 搜索类别 '{params.category}'，将忽略此参数。"
                )

        # 根据 use_contents 决定调用方式
        if params.use_contents:
            # 使用 search_and_contents，获取页面高亮摘要和 summary 双保险
            search_kwargs["highlights"] = {"max_characters": MAX_HIGHLIGHT_CHARS}
            search_kwargs["summary"] = True

            # exa-py SDK 的 search_and_contents 是同步的，需要在线程池中执行
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: exa.search_and_contents(query, **search_kwargs),
            )
        else:
            # 仅搜索，不获取内容
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: exa.search(query, **search_kwargs),
            )

    except ImportError:
        log.error("exa-py 未安装，无法使用深度搜索功能。请执行 pip install exa-py")
        return ["错误：深度搜索依赖库未安装，请联系管理员。"]
    except Exception as e:
        error_msg = str(e)
        log.error(f"Exa 搜索时发生错误: {error_msg}", exc_info=True)

        # 尝试解析常见错误
        if "401" in error_msg or "unauthorized" in error_msg.lower():
            return ["错误：深度搜索服务认证失败，请检查 API Key。"]
        elif "402" in error_msg or "payment" in error_msg.lower():
            return ["错误：深度搜索服务额度已用完，请联系管理员。"]
        elif "429" in error_msg or "rate" in error_msg.lower():
            return ["深度搜索请求太频繁了，请稍后再试。"]

        return ["深度搜索时发生意外错误，请稍后再试。"]

    # 解析结果
    results = getattr(response, "results", [])
    if not results:
        log.info(f"Exa 搜索 '{query}' 无结果。")
        return []

    output_list = []
    for result in results[:num_results]:
        formatted = _format_exa_result(result)
        if formatted:
            output_list.append(formatted)

    log.info(f"Exa 搜索 '{query}' 返回 {len(output_list)} 条结果（搜索类型: {search_type}）。")
    return output_list
