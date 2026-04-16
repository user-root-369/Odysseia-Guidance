# -*- coding: utf-8 -*-
"""图像生成配置。"""

import os

IMAGE_GENERATION_CONFIG = {
    "ENABLED": os.getenv("IMAGE_GENERATION_ENABLED", "False").lower() == "true",
    "DEFAULT_PROVIDER": os.getenv("IMAGE_GENERATION_DEFAULT_PROVIDER", "prodia"),
    "TIMEOUT_SECONDS": int(os.getenv("IMAGE_GENERATION_TIMEOUT_SECONDS", "45")),
    "MAX_PROMPT_LENGTH": int(os.getenv("IMAGE_GENERATION_MAX_PROMPT_LENGTH", "1000")),
    "MAX_NEGATIVE_PROMPT_LENGTH": int(
        os.getenv("IMAGE_GENERATION_MAX_NEGATIVE_PROMPT_LENGTH", "500")
    ),
    "DEFAULT_ASPECT_RATIO": os.getenv("IMAGE_GENERATION_DEFAULT_ASPECT_RATIO", "1:1"),
    "ALLOWED_ASPECT_RATIOS": ["1:1", "3:4", "4:3", "9:16", "16:9"],
    "PRODIA": {
        "API_KEY": os.getenv("PRODIA_API_KEY"),
        "BASE_URL": os.getenv("PRODIA_BASE_URL", "https://api.prodia.com/v1"),
        "MODEL": os.getenv("PRODIA_MODEL", "flux-fast-schnell"),
        "POLL_INTERVAL_SECONDS": float(
            os.getenv("PRODIA_POLL_INTERVAL_SECONDS", "1.5")
        ),
        "MAX_POLLS": int(os.getenv("PRODIA_MAX_POLLS", "30")),
        "OUTPUT_FORMAT": os.getenv("PRODIA_OUTPUT_FORMAT", "png"),
    },
    "GEMINI_MULTIMODAL": {
        "API_KEY": os.getenv("GEMINI_MULTIMODAL_API_KEY", os.getenv("PRODIA_API_KEY")),
        "BASE_URL": os.getenv(
            "GEMINI_MULTIMODAL_BASE_URL",
            os.getenv("PRODIA_BASE_URL", "https://ai-gateway.vercel.sh/v1"),
        ),
        "MODEL": os.getenv(
            "GEMINI_MULTIMODAL_MODEL",
            "google/gemini-3.1-flash-image-preview",
        ),
        "OUTPUT_FORMAT": os.getenv("GEMINI_MULTIMODAL_OUTPUT_FORMAT", "png"),
    },
}
