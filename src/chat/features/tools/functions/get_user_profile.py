# -*- coding: utf-8 -*-
"""
用户资料查询工具 - 查询用户的类脑币余额、头像、角色等信息
"""

import base64
import logging
from typing import Dict, Any, List, Literal, Optional

import httpx
from pydantic import BaseModel, Field

import discord

from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)


# 支持的查询字段类型
QueryField = Literal["balance", "avatar", "roles"]


class UserProfileQuery(BaseModel):
    """用户资料查询参数"""

    user_id: Optional[str] = Field(
        None,
        description="目标用户的标识。可以是: 1) Discord数字ID; 2) 'user'表示当前对话用户;系统会自动识别并替换为正确的ID。",
    )
    queries: List[QueryField] = Field(
        ...,
        description="需要查询的字段列表。可选值: 'balance', 'avatar', 'roles'。",
    )


@tool_metadata(
    name="查询资料",
    description="查询用户的类脑币余额、头像、角色等信息",
    emoji="👤",
    category="用户信息",
)
async def get_user_profile(
    params: UserProfileQuery,
    **kwargs,
) -> Dict[str, Any]:
    """
    查询用户的个人资料，可选择性地包括多个字段。
    [调用指南]
    - **自主决策**: 只要认为有必要就可以调用
    - **按需查询**: 根据上下文，在 `queries` 列表中指定一个或多个需要查询的字段，以获取必要的信息。
    - **查询当前对话用户**: 如果你要查询当前对话用户信息,系统会自动提供用户的数字ID，无需填写 `user_id`,调用工具即可。

    Args:
        user_id (str): 目标用户的 Discord 数字ID。**注意**: 如果是查询当前对话用户, 此参数将由系统自动填充, 模型无需处理。
        queries (List[str]): 需要查询的字段列表。有效值: "balance", "avatar", "roles"。

    Returns:
        一个包含查询结果和状态的字典。返回值中的 `user_id` 字段即为本次查询的目标用户 Discord ID，
        若未主动指定 `user_id`，则该值为当前对话用户的 ID。
    """
    # 从 kwargs 安全地获取由系统注入的 bot 和 guild 实例
    bot = kwargs.get("bot")
    guild = kwargs.get("guild")

    if not bot:
        return {"error": "Bot instance is not available."}

    # 从 Pydantic 模型中提取参数
    user_id = params.user_id
    queries = params.queries

    # 处理特殊值 'user' -> 使用当前用户ID
    if user_id == "user":
        user_id = kwargs.get("user_id")
        if not user_id:
            return {"error": "无法获取当前用户ID"}
        log.info(f"将 'user' 替换为当前用户ID: {user_id}")

    log.info(
        f"--- [工具执行]: get_user_profile, user_id={user_id}, queries={queries} ---"
    )

    if not user_id or not user_id.isdigit():
        return {"error": f"Invalid or missing user_id provided: {user_id}"}

    target_id = int(user_id)
    query_set = set(queries)

    result = {
        "user_id": str(target_id),
        "queries_requested": queries,
        "queries_successful": [],
        "profile": {},
        "errors": [],
    }

    # 首先获取用户基本信息（用户名），让 AI 知道查询的是哪个用户
    try:
        user = await bot.fetch_user(target_id)
        if user:
            result["username"] = user.name
            result["display_name"] = user.display_name
            log.info(f"成功获取用户 {target_id} 的基本信息: {user.name}")
    except discord.NotFound:
        result["errors"].append("User not found on Discord.")
        log.warning(f"无法找到 ID 为 {target_id} 的用户。")
        return result
    except Exception as e:
        error_msg = f"获取用户基本信息时发生错误: {str(e)}"
        result["errors"].append(error_msg)
        log.error(error_msg, exc_info=True)
        return result

    # --- 查询分支 ---

    # 1. 查询头像 (Avatar)
    if "avatar" in query_set:
        try:
            if user.display_avatar:
                avatar_url = str(user.display_avatar.url)
                result["profile"]["avatar_url"] = avatar_url

                async with httpx.AsyncClient() as client:
                    response = await client.get(avatar_url)
                    response.raise_for_status()
                    image_bytes = response.content
                    result["profile"]["avatar_image_base64"] = base64.b64encode(
                        image_bytes
                    ).decode("utf-8")

                result["queries_successful"].append("avatar")
                log.info(f"成功获取用户 {target_id} 的头像 URL 并下载了图片。")
            else:
                result["errors"].append("User has no avatar.")
        except httpx.HTTPStatusError as e:
            error_msg = f"下载头像时发生HTTP错误: {e}"
            result["errors"].append(error_msg)
            log.error(error_msg, exc_info=True)
        except Exception as e:
            error_msg = f"获取头像时发生未知错误: {str(e)}"
            result["errors"].append(error_msg)
            log.error(error_msg, exc_info=True)

    # 2. 查询角色 (Roles)
    if "roles" in query_set:
        if not guild:
            result["errors"].append(
                "Guild information is not available for roles query."
            )
        else:
            try:
                member = guild.get_member(target_id)
                if member:
                    role_names = [
                        role.name for role in member.roles if role.name != "@everyone"
                    ]
                    result["profile"]["roles"] = role_names
                    result["queries_successful"].append("roles")
                    log.info(f"成功获取用户 {target_id} 在服务器 {guild.name} 的角色。")
                else:
                    result["errors"].append("User is not a member of this server.")
            except Exception as e:
                error_msg = f"获取角色时发生未知错误: {str(e)}"
                result["errors"].append(error_msg)
                log.error(error_msg, exc_info=True)

    # 3. 查询余额 (Balance)
    if "balance" in query_set:
        try:
            balance = await coin_service.get_balance(target_id)
            result["profile"]["balance"] = {"amount": balance, "name": "类脑币"}
            result["queries_successful"].append("balance")
            log.info(f"成功获取用户 {target_id} 的余额: {balance}")
        except Exception as e:
            error_msg = f"获取余额时发生未知错误: {str(e)}"
            result["errors"].append(error_msg)
            log.error(error_msg, exc_info=True)

    log.info(
        f"用户 {target_id} 的个人资料查询完成。成功: {result['queries_successful']}, 失败: {len(result['errors'])} 项。"
    )
    return result
