"""
Account Manager Module
Loads and validates multi-account configuration from accounts.yml.
Falls back to single-account from .env for backward compatibility.
"""

import os
import logging
from dataclasses import dataclass, field

import yaml

logger = logging.getLogger(__name__)

ACCOUNTS_FILE = "accounts.yml"


@dataclass
class TelegramConfig:
    """Telegram configuration for one account."""
    bot_token: str
    chat_id: str


@dataclass
class AccountConfig:
    """Configuration for a single email account."""
    name: str
    email: str
    app_password: str
    imap_server: str
    imap_port: int
    keywords: list[str]
    telegram: TelegramConfig

    def validate(self) -> list[str]:
        """Validate this account config. Returns list of errors."""
        errors = []
        if not self.email:
            errors.append(f"[{self.name}] email is required")
        if not self.app_password:
            errors.append(f"[{self.name}] app_password is required")
        if not self.keywords:
            errors.append(f"[{self.name}] keywords list is empty")
        if not self.telegram.bot_token:
            errors.append(f"[{self.name}] telegram.bot_token is required")
        if not self.telegram.chat_id:
            errors.append(f"[{self.name}] telegram.chat_id is required")
        return errors


@dataclass
class GlobalSettings:
    """Global settings (from accounts.yml or .env)."""
    poll_interval: int = 60
    max_results: int = 20


def _get_project_root() -> str:
    """Get the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _parse_account(raw: dict, index: int) -> AccountConfig:
    """Parse a single account entry from YAML."""
    name = raw.get("name", f"Account-{index + 1}")
    telegram_raw = raw.get("telegram", {})

    keywords = [
        kw.strip().lower()
        for kw in raw.get("keywords", [])
        if isinstance(kw, str) and kw.strip()
    ]

    return AccountConfig(
        name=name,
        email=raw.get("email", ""),
        app_password=raw.get("app_password", ""),
        imap_server=raw.get("imap_server", "imap.gmail.com"),
        imap_port=int(raw.get("imap_port", 993)),
        keywords=keywords,
        telegram=TelegramConfig(
            bot_token=telegram_raw.get("bot_token", ""),
            chat_id=str(telegram_raw.get("chat_id", "")),
        ),
    )


def load_accounts_from_yaml(path: str | None = None) -> tuple[list[AccountConfig], GlobalSettings]:
    """
    Load accounts from accounts.yml.
    Returns (accounts, global_settings).
    """
    if path is None:
        path = os.path.join(_get_project_root(), ACCOUNTS_FILE)

    if not os.path.exists(path):
        raise FileNotFoundError(f"{ACCOUNTS_FILE} not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "accounts" not in data:
        raise ValueError(f"Invalid {ACCOUNTS_FILE}: missing 'accounts' key")

    raw_accounts = data["accounts"]
    if not isinstance(raw_accounts, list) or len(raw_accounts) == 0:
        raise ValueError(f"Invalid {ACCOUNTS_FILE}: 'accounts' must be a non-empty list")

    accounts = [_parse_account(raw, i) for i, raw in enumerate(raw_accounts)]

    # Global settings
    raw_settings = data.get("settings", {})
    settings = GlobalSettings(
        poll_interval=int(raw_settings.get("poll_interval", 60)),
        max_results=int(raw_settings.get("max_results", 20)),
    )

    logger.info("Loaded %d account(s) from %s", len(accounts), ACCOUNTS_FILE)
    return accounts, settings


def load_accounts_from_env() -> tuple[list[AccountConfig], GlobalSettings]:
    """
    Fallback: build a single AccountConfig from .env / environment variables.
    Backward compatible with Phase 1 single-account setup.
    """
    from src.config import Config

    keywords = Config.KEYWORDS if Config.KEYWORDS else []

    account = AccountConfig(
        name="Default",
        email=Config.EMAIL_ADDRESS,
        app_password=Config.EMAIL_APP_PASSWORD,
        imap_server=Config.IMAP_SERVER,
        imap_port=Config.IMAP_PORT,
        keywords=keywords,
        telegram=TelegramConfig(
            bot_token=Config.TELEGRAM_BOT_TOKEN,
            chat_id=Config.TELEGRAM_CHAT_ID,
        ),
    )

    settings = GlobalSettings(
        poll_interval=Config.POLL_INTERVAL,
        max_results=20,
    )

    logger.info("Loaded single account from .env (backward-compat mode)")
    return [account], settings


def load_accounts() -> tuple[list[AccountConfig], GlobalSettings]:
    """
    Load accounts with priority:
    1. accounts.yml (multi-account)
    2. .env / environment variables (single account, backward compat)

    Returns (accounts, global_settings).
    """
    root = _get_project_root()
    yml_path = os.path.join(root, ACCOUNTS_FILE)

    if os.path.exists(yml_path):
        try:
            return load_accounts_from_yaml(yml_path)
        except Exception as e:
            logger.error("Failed to load %s: %s", ACCOUNTS_FILE, e)
            raise
    else:
        logger.info("No %s found, falling back to .env config.", ACCOUNTS_FILE)
        return load_accounts_from_env()


def validate_all_accounts(accounts: list[AccountConfig]) -> list[str]:
    """Validate all accounts, return combined list of errors."""
    errors = []
    for account in accounts:
        errors.extend(account.validate())
    return errors
