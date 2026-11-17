"""Configuration from environment only. No secrets in code."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _ids(raw: str) -> list[int]:
    out: list[int] = []
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


@dataclass
class Config:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    admin_ids: list[int] = field(
        default_factory=lambda: _ids(os.getenv("ADMIN_IDS", ""))
    )
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./stickerbot.db"
        )
    )
    fa_font_path: str = field(default_factory=lambda: os.getenv("FA_FONT_PATH", ""))
    use_rembg: bool = field(
        default_factory=lambda: os.getenv("USE_REMBG", "0") == "1"
    )
    tenor_api_key: str = field(default_factory=lambda: os.getenv("TENOR_API_KEY", ""))
    giphy_api_key: str = field(default_factory=lambda: os.getenv("GIPHY_API_KEY", ""))

    def require_token(self) -> str:
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN is not set (see .env.example)")
        return self.bot_token


config = Config()
