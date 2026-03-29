"""
Telegram Service Module
Handles sending messages to Telegram via Bot API.
Accepts per-account token & chat_id (no dependency on global Config).
"""

import logging

import requests

logger = logging.getLogger(__name__)

# Telegram message limit
MAX_MESSAGE_LENGTH = 4096


class TelegramService:
    """Service to send messages via Telegram Bot API."""

    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(self, bot_token: str, chat_id: str, account_name: str = "default"):
        self.token = bot_token
        self.chat_id = chat_id
        self.account_name = account_name
        self.base_url = self.BASE_URL.format(token=self.token)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a text message to the configured Telegram chat.
        Automatically splits long messages if needed.
        """
        if not text.strip():
            logger.warning("Attempted to send empty message, skipping.")
            return False

        # Split message if too long
        chunks = self._split_message(text, MAX_MESSAGE_LENGTH)

        success = True
        for i, chunk in enumerate(chunks):
            try:
                url = f"{self.base_url}/sendMessage"
                payload = {
                    "chat_id": self.chat_id,
                    "text": chunk,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                }

                response = requests.post(url, json=payload, timeout=30)
                response.raise_for_status()

                result = response.json()
                if not result.get("ok"):
                    logger.error(
                        "Telegram API error (chunk %d/%d): %s",
                        i + 1, len(chunks), result.get("description", "Unknown error")
                    )
                    success = False
                else:
                    logger.debug("Message chunk %d/%d sent successfully.", i + 1, len(chunks))

            except requests.RequestException as e:
                logger.error("Failed to send Telegram message (chunk %d/%d): %s", i + 1, len(chunks), e)
                success = False

        return success

    def send_email_notification(
        self,
        subject: str,
        sender: str,
        date: str,
        body_preview: str,
        matched_keywords: list[str],
        account_label: str = "",
    ) -> bool:
        """Send a formatted email notification to Telegram."""
        keyword_tags = " ".join(f"#{self._escape_html(kw)}" for kw in matched_keywords)
        account_line = f"<b>Account:</b> {self._escape_html(account_label)}\n" if account_label else ""

        message = (
            f"📧 <b>Email Alert</b>\n"
            f"{'━' * 30}\n"
            f"{account_line}"
            f"<b>From:</b> {self._escape_html(sender)}\n"
            f"<b>Subject:</b> {self._escape_html(subject)}\n"
            f"<b>Date:</b> {self._escape_html(date)}\n"
            f"<b>Keywords:</b> {keyword_tags}\n"
            f"{'━' * 30}\n"
            f"<b>Content:</b>\n"
            f"<pre>{self._escape_html(body_preview[:2000])}</pre>"
        )

        return self.send_message(message, parse_mode="HTML")

    def test_connection(self) -> bool:
        """Test if the bot token and chat_id are valid."""
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)
            result = response.json()

            if result.get("ok"):
                bot_name = result["result"].get("username", "Unknown")
                logger.info("Telegram bot connected: @%s", bot_name)
                return True
            else:
                logger.error("Telegram bot validation failed: %s", result.get("description"))
                return False

        except requests.RequestException as e:
            logger.error("Failed to connect to Telegram: %s", e)
            return False

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters for Telegram."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @staticmethod
    def _split_message(text: str, max_length: int) -> list[str]:
        """Split a long message into chunks."""
        if len(text) <= max_length:
            return [text]

        chunks = []
        while text:
            if len(text) <= max_length:
                chunks.append(text)
                break

            # Try to split at a newline
            split_pos = text.rfind("\n", 0, max_length)
            if split_pos == -1:
                split_pos = max_length

            chunks.append(text[:split_pos])
            text = text[split_pos:].lstrip("\n")

        return chunks
