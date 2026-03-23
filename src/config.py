"""
Pro-Notify Configuration Module
Loads settings from .env file and provides config access.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Email (IMAP + App Password)
    EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")
    EMAIL_APP_PASSWORD: str = os.getenv("EMAIL_APP_PASSWORD", "")
    IMAP_SERVER: str = os.getenv("IMAP_SERVER", "imap.gmail.com")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))

    # Polling
    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "60"))

    # Keywords (comma-separated in .env)
    KEYWORDS: list[str] = [
        kw.strip().lower()
        for kw in os.getenv("KEYWORDS", "").split(",")
        if kw.strip()
    ]

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration. Returns list of errors."""
        errors = []
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is not set")
        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID is not set")
        if not cls.EMAIL_ADDRESS:
            errors.append("EMAIL_ADDRESS is not set")
        if not cls.EMAIL_APP_PASSWORD:
            errors.append("EMAIL_APP_PASSWORD is not set")
        if not cls.KEYWORDS:
            errors.append("KEYWORDS is not set or empty")
        return errors
