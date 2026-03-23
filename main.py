"""
Pro-Notify — Email Keyword Monitor → Telegram Notification
Entry point: polls Gmail for unread emails, matches keywords, sends alerts to Telegram.
"""

import sys
import time
import signal
import logging

from src.config import Config
from src.gmail_service import GmailService
from src.telegram_service import TelegramService
from src.keyword_matcher import KeywordMatcher

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pro-notify")

# Graceful shutdown flag
_running = True


def _handle_signal(signum, _frame):
    global _running
    logger.info("Received signal %s — shutting down…", signal.Signals(signum).name)
    _running = False


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ── Core loop ────────────────────────────────────────────
def run_once(
    gmail: GmailService,
    telegram: TelegramService,
    matcher: KeywordMatcher,
) -> int:
    """Single poll cycle. Returns the number of notifications sent."""
    emails = gmail.fetch_unread_emails(max_results=20)
    if not emails:
        return 0

    matches = matcher.match_many(emails)
    sent = 0

    for match in matches:
        email = match.email
        ok = telegram.send_email_notification(
            subject=email.subject,
            sender=email.sender,
            date=email.date,
            body_preview=email.body,
            matched_keywords=match.matched_keywords,
        )
        if ok:
            gmail.mark_as_read(email.id)
            sent += 1
            logger.info(
                "✅ Notified → %s (keywords: %s)",
                email.subject,
                ", ".join(match.matched_keywords),
            )
        else:
            logger.warning("⚠️  Failed to notify for email: %s", email.subject)

    return sent


def main() -> None:
    """Start the polling loop."""
    # ── Validate config ──
    errors = Config.validate()
    if errors:
        for err in errors:
            logger.error("Config error: %s", err)
        sys.exit(1)

    logger.info("Keywords to monitor: %s", Config.KEYWORDS)
    logger.info("Poll interval: %ds", Config.POLL_INTERVAL)

    # ── Init services ──
    telegram = TelegramService()
    if not telegram.test_connection():
        logger.error("Cannot connect to Telegram bot. Check TELEGRAM_BOT_TOKEN.")
        sys.exit(1)

    gmail = GmailService()
    matcher = KeywordMatcher()

    # Send startup message
    telegram.send_message(
        f"🟢 <b>Pro-Notify started</b>\n"
        f"Monitoring keywords: <code>{', '.join(Config.KEYWORDS)}</code>\n"
        f"Poll interval: {Config.POLL_INTERVAL}s",
    )

    # ── Poll loop ──
    logger.info("🚀 Pro-Notify is running. Press Ctrl+C to stop.")
    while _running:
        try:
            count = run_once(gmail, telegram, matcher)
            if count:
                logger.info("Cycle complete — %d notification(s) sent.", count)
        except Exception as exc:
            logger.exception("Error during poll cycle: %s", exc)

        # Sleep in small increments so we can react to signals quickly
        for _ in range(Config.POLL_INTERVAL):
            if not _running:
                break
            time.sleep(1)

    # Shutdown
    telegram.send_message("🔴 <b>Pro-Notify stopped</b>")
    logger.info("Pro-Notify stopped.")


if __name__ == "__main__":
    main()
