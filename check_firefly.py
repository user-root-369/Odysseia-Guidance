import sys

sys.stdout.reconfigure(encoding="utf-8")

try:
    from src.chat.features.firefly.providers.firefly_web_provider import (
        firefly_web_provider as fwp,
    )

    print(f"OK imported, id={id(fwp)}, enabled={fwp._enabled}")
except Exception as e:
    print(f"IMPORT ERROR: {e}")

try:
    from src.chat.features.tools.functions.generate_video import generate_video

    print("generate_video imported OK")
except Exception as e:
    print(f"generate_video IMPORT ERROR: {e}")

try:
    from src.chat.features.firefly.cogs.firefly_cog import FireflyCog

    print("FireflyCog imported OK")
except Exception as e:
    print(f"FireflyCog IMPORT ERROR: {e}")
