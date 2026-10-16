"""Settings, read from environment variables.

Every key is optional. With no keys at all Friday runs in demo mode: a template
script, generated backgrounds and (if the network allows) free edge-tts voice.
Add keys to unlock the real thing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # Any OpenAI-compatible chat endpoint works (Gemini, Groq, OpenRouter, ...).
    llm_api_key: str = ""
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_model: str = "gemini-2.5-flash"
    # Free keys for stock footage. Either one is enough; both can be set.
    pexels_api_key: str = ""
    pixabay_api_key: str = ""
    # edge-tts voice name. Free, no key.
    voice: str = "en-US-AndrewNeural"
    # Caption font family (must exist on the machine doing the render).
    caption_font: str = "DejaVu Sans"
    # 1.0 renders 1080p. Lower values render faster (used by tests).
    render_scale: float = 1.0
    data_dir: Path = Path("data")
    # If set, the HTTP API requires this value in the X-Friday-Key header.
    access_key: str = ""

    @property
    def live_script(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def live_footage(self) -> bool:
        return bool(self.pexels_api_key or self.pixabay_api_key)

    @property
    def mode(self) -> str:
        if self.live_script and self.live_footage:
            return "live"
        if self.live_script or self.live_footage:
            return "partial"
        return "demo"


def load() -> Settings:
    # CI systems pass unset secrets as empty strings, so empty must mean "use the default".
    def env(name: str, default: str = "") -> str:
        return (os.environ.get(name) or "").strip() or default

    defaults = Settings()
    return Settings(
        llm_api_key=env("FRIDAY_LLM_API_KEY"),
        llm_base_url=env("FRIDAY_LLM_BASE_URL", defaults.llm_base_url).rstrip("/"),
        llm_model=env("FRIDAY_LLM_MODEL", defaults.llm_model),
        pexels_api_key=env("PEXELS_API_KEY"),
        pixabay_api_key=env("PIXABAY_API_KEY"),
        voice=env("FRIDAY_VOICE", defaults.voice),
        caption_font=env("FRIDAY_CAPTION_FONT", defaults.caption_font),
        render_scale=float(env("FRIDAY_RENDER_SCALE", "1.0")),
        data_dir=Path(env("FRIDAY_DATA_DIR", "data")),
        access_key=env("FRIDAY_ACCESS_KEY"),
    )
