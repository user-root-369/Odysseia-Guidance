# -*- coding: utf-8 -*-
"""
Adobe Firefly Web Provider 配置。

所有端点和固定值均来自抓包分析，Token 在运行时由开发者通过命令注入。
"""

FIREFLY_CONFIG = {
    # --- 功能开关 ---
    # 总开关，False 时所有 Firefly 功能均不可用（不影响原有 prodia/gemini 图片生成）
    "ENABLED": True,
    # --- API 固定值（来自抓包，无需修改）---
    # 网页版内嵌的固定 client_id，所有请求均使用此值
    "WEB_API_KEY": "clio-playground-web",
    # 图片生成提交端点
    "IMAGE_SUBMIT_URL": "https://firefly-3p.ff.adobe.io/v2/3p-images/generate-async",
    # 视频生成提交端点
    "VIDEO_SUBMIT_URL": "https://firefly-3p.ff.adobe.io/v2/3p-videos/generate-async",
    # 图片上传端点（图生视频时先上传图片取得 blob ID，再引用到 referenceBlobs）
    "IMAGE_UPLOAD_URL": "https://firefly-3p.ff.adobe.io/v2/storage/image",
    # 轮询端点从响应体 links.result.href 动态获取，此处为前缀（用于日志）
    "POLL_HOST": "firefly-epo852232.adobe.io",
    # --- 图片生成默认参数 ---
    "IMAGE_DEFAULT_MODEL_ID": "gpt-image",
    "IMAGE_DEFAULT_MODEL_VERSION": "1.5",
    "IMAGE_DEFAULT_WIDTH": 1024,
    "IMAGE_DEFAULT_HEIGHT": 1024,
    # --- 视频生成默认参数（来自抓包）---
    "VIDEO_DEFAULT_MODEL_ID": "veo",
    "VIDEO_DEFAULT_MODEL_VERSION": "3.1-fast-generate",
    "VIDEO_DEFAULT_WIDTH": 1920,
    "VIDEO_DEFAULT_HEIGHT": 1080,
    "VIDEO_DEFAULT_DURATION": 8,
    "VIDEO_DEFAULT_NEGATIVE_PROMPT": "cartoon, vector art, & bad aesthetics & poor aesthetic",
    # generationMetadata.module 值：文生视频 / 图生视频
    # 图生视频的 module 名称待抓包确认，目前使用最可能的值 "image2video"
    "VIDEO_TEXT2VIDEO_MODULE": "text2video",
    "VIDEO_IMAGE2VIDEO_MODULE": "image2video",
    # --- 超时与轮询配置 ---
    # 提交请求超时（秒）
    "SUBMIT_TIMEOUT": 30,
    # 单次轮询请求超时（秒）
    "POLL_TIMEOUT": 15,
    # 视频生成最大总等待时间（秒），超过则放弃
    # Veo 3.1-fast-generate 生成 8s 视频预计需要数分钟，设置 900 秒（15 分钟）
    "VIDEO_MAX_WAIT": 900,
    # 图片生成最大总等待时间（秒）
    "IMAGE_MAX_WAIT": 120,
    # 初始轮询间隔（秒），来自响应头 retry-after 建议值
    "POLL_INTERVAL": 5,
    # --- 下载配置 ---
    # 结果文件下载超时（秒）
    "DOWNLOAD_TIMEOUT": 60,
}
