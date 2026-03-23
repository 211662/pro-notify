"""
Pro-Notify Configuration Module
Loads settings from .env file or .env.encrypted (if available).
"""

import os
import logging

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _load_config() -> None:
    """Load config from .env.encrypted (priority) or .env fallback."""
    from src.encryption import has_encrypted_env, decrypt_env

    if has_encrypted_env():
        logger.info("🔐 Found .env.encrypted — decrypting...")
        try:
            env_vars = decrypt_env()
            for key, value in env_vars.items():
                os.environ[key] = value
            logger.info("🔓 Config loaded from encrypted file.")
            return
        except Exception as e:
            logger.error("Failed to decrypt: %s", e)
            logger.info("Falling back to .env file...")

    load_dotenv()
    logger.info("📄 Config loaded from .env file.")


_load_config()


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
