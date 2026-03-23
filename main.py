"""
Pro-Notify — Email Keyword Monitor → Telegram Notification
Phase 3: Multi-account + Gold Price + Weather bots.
"""

import sys
import time
import signal
import logging
from dataclasses import dataclass

from src.account_manager import (
    AccountConfig,
    GlobalSettings,
    GoldConfig,
    WeatherConfig,
    load_accounts,
    validate_all_accounts,
)
from src.email_service import EmailService
from src.telegram_service import TelegramService
from src.keyword_matcher import KeywordMatcher
from src.scheduler import ScheduledTask
from src.gold_price_service import fetch_gold_prices, format_gold_message, check_price_alert
from src.weather_service import (
    fetch_current_weather, fetch_forecast,
    format_weather_message, check_severe_weather,
)

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


# ── Per-account worker ───────────────────────────────────
@dataclass
class AccountWorker:
    """Holds the services for a single account."""
    config: AccountConfig
    email_svc: EmailService
    telegram_svc: TelegramService
    matcher: KeywordMatcher


def build_workers(accounts: list[AccountConfig]) -> list[AccountWorker]:
    """Initialize services for each account."""
    workers = []
    for acct in accounts:
        email_svc = EmailService(
            email_address=acct.email,
            app_password=acct.app_password,
            imap_server=acct.imap_server,
            imap_port=acct.imap_port,
            account_name=acct.name,
        )
        telegram_svc = TelegramService(
            bot_token=acct.telegram.bot_token,
            chat_id=acct.telegram.chat_id,
            account_name=acct.name,
        )
        matcher = KeywordMatcher(keywords=acct.keywords)
        workers.append(AccountWorker(
            config=acct,
            email_svc=email_svc,
            telegram_svc=telegram_svc,
            matcher=matcher,
        ))
    return workers


# ── Core loop ────────────────────────────────────────────
def run_once_for_account(worker: AccountWorker, max_results: int = 20) -> int:
    """Single poll cycle for one account. Returns number of notifications sent."""
    emails = worker.email_svc.fetch_unread_emails(max_results=max_results)
    if not emails:
        return 0

    matches = worker.matcher.match_many(emails)
    sent = 0

    for match in matches:
        em = match.email
        ok = worker.telegram_svc.send_email_notification(
            subject=em.subject,
            sender=em.sender,
            date=em.date,
            body_preview=em.body,
            matched_keywords=match.matched_keywords,
            account_label=worker.config.name,
        )
        if ok:
            worker.email_svc.mark_as_read(em.id)
            sent += 1
            logger.info(
                "✅ [%s] Notified → %s (keywords: %s)",
                worker.config.name,
                em.subject,
                ", ".join(match.matched_keywords),
            )
        else:
            logger.warning("⚠️  [%s] Failed to notify for: %s", worker.config.name, em.subject)

    return sent


def run_once(workers: list[AccountWorker], max_results: int = 20) -> int:
    """Single poll cycle across ALL accounts. Returns total notifications sent."""
    total = 0
    for worker in workers:
        try:
            total += run_once_for_account(worker, max_results=max_results)
        except Exception as exc:
            logger.exception("[%s] Error during poll: %s", worker.config.name, exc)
    return total


def main() -> None:
    """Start the app. Use --once flag for single run (GitHub Actions / cron)."""
    single_run = "--once" in sys.argv

    # ── Load accounts ──
    try:
        accounts, settings, gold_cfg, weather_cfg = load_accounts()
    except Exception as exc:
        logger.error("Failed to load accounts: %s", exc)
        sys.exit(1)

    # ── Validate ──
    errors = validate_all_accounts(accounts)
    if errors:
        for err in errors:
            logger.error("Config error: %s", err)
        sys.exit(1)

    # ── Log summary ──
    logger.info("━" * 50)
    logger.info("Loaded %d account(s):", len(accounts))
    for acct in accounts:
        logger.info("  📧 %s (%s) → %d keywords → chat %s",
                     acct.name, acct.email, len(acct.keywords), acct.telegram.chat_id)
    if gold_cfg.enabled:
        logger.info("  🥇 Gold price bot: ON")
    if weather_cfg.enabled:
        logger.info("  🌤 Weather bot: ON (%s)", weather_cfg.city)
    logger.info("━" * 50)

    # ── Build workers ──
    workers = build_workers(accounts)

    # ── Validate Telegram connections ──
    for worker in workers:
        if not worker.telegram_svc.test_connection():
            logger.error("[%s] Cannot connect to Telegram bot.", worker.config.name)
            sys.exit(1)

    # ── Build gold & weather schedulers ──
    gold_task = None
    gold_tg = None
    if gold_cfg.enabled and gold_cfg.telegram:
        gold_task = ScheduledTask(
            name="gold_price",
            interval_minutes=gold_cfg.schedule_interval,
            daily_times=gold_cfg.schedule_times,
        )
        gold_tg = TelegramService(
            bot_token=gold_cfg.telegram.bot_token,
            chat_id=gold_cfg.telegram.chat_id,
            account_name="GoldBot",
        )
        logger.info("🥇 Gold schedule: %s", gold_task.next_run_info())

    weather_task = None
    weather_severe_task = None
    weather_tg = None
    if weather_cfg.enabled and weather_cfg.telegram and weather_cfg.api_key:
        weather_task = ScheduledTask(
            name="weather",
            interval_minutes=weather_cfg.schedule_interval,
            daily_times=weather_cfg.schedule_times,
        )
        weather_tg = TelegramService(
            bot_token=weather_cfg.telegram.bot_token,
            chat_id=weather_cfg.telegram.chat_id,
            account_name="WeatherBot",
        )
        logger.info("🌤 Weather schedule: %s", weather_task.next_run_info())

        if weather_cfg.severe_alert:
            weather_severe_task = ScheduledTask(
                name="weather_severe",
                interval_minutes=60,  # Check severe weather every hour
            )

    # ── Single run mode ──
    if single_run:
        logger.info("🔄 Running single check...")
        try:
            count = run_once(workers, max_results=settings.max_results)
            # Also run gold & weather once
            if gold_task and gold_tg:
                _run_gold_task(gold_cfg, gold_tg)
            if weather_task and weather_tg:
                _run_weather_task(weather_cfg, weather_tg)
            logger.info("Done — %d email notification(s) sent.", count)
        except Exception as exc:
            logger.exception("Error: %s", exc)
            sys.exit(1)
        return

    # ── Poll loop mode ──
    logger.info("Poll interval: %ds", settings.poll_interval)

    # Send start message to all unique Telegram destinations
    seen_chats: set[str] = set()
    for worker in workers:
        chat_key = f"{worker.telegram_svc.token}:{worker.telegram_svc.chat_id}"
        if chat_key not in seen_chats:
            account_names = [
                w.config.name for w in workers
                if f"{w.telegram_svc.token}:{w.telegram_svc.chat_id}" == chat_key
            ]
            features = []
            if gold_cfg.enabled:
                features.append("🥇 Giá vàng")
            if weather_cfg.enabled:
                features.append(f"🌤 Thời tiết ({weather_cfg.city})")
            feature_line = f"\nBots: {', '.join(features)}" if features else ""
            worker.telegram_svc.send_message(
                f"🟢 <b>Pro-Notify started</b>\n"
                f"Monitoring {len(account_names)} account(s): "
                f"<code>{', '.join(account_names)}</code>\n"
                f"Poll interval: {settings.poll_interval}s"
                f"{feature_line}",
            )
            seen_chats.add(chat_key)

    logger.info("🚀 Pro-Notify is running. Press Ctrl+C to stop.")

    while _running:
        try:
            # Email check
            count = run_once(workers, max_results=settings.max_results)
            if count:
                logger.info("Cycle complete — %d notification(s) sent.", count)

            # Gold price check
            if gold_task and gold_tg and gold_task.should_run():
                try:
                    _run_gold_task(gold_cfg, gold_tg)
                    gold_task.mark_done()
                except Exception as exc:
                    logger.exception("Gold price error: %s", exc)

            # Weather check
            if weather_task and weather_tg and weather_task.should_run():
                try:
                    _run_weather_task(weather_cfg, weather_tg)
                    weather_task.mark_done()
                except Exception as exc:
                    logger.exception("Weather error: %s", exc)

            # Severe weather check (every hour)
            if weather_severe_task and weather_tg and weather_severe_task.should_run():
                try:
                    _run_severe_weather_check(weather_cfg, weather_tg)
                    weather_severe_task.mark_done()
                except Exception as exc:
                    logger.exception("Severe weather check error: %s", exc)

        except Exception as exc:
            logger.exception("Error during poll cycle: %s", exc)

        for _ in range(settings.poll_interval):
            if not _running:
                break
            time.sleep(1)

    # Graceful shutdown
    for worker in workers:
        worker.email_svc.disconnect()

    seen_chats.clear()
    for worker in workers:
        chat_key = f"{worker.telegram_svc.token}:{worker.telegram_svc.chat_id}"
        if chat_key not in seen_chats:
            worker.telegram_svc.send_message("🔴 <b>Pro-Notify stopped</b>")
            seen_chats.add(chat_key)

    logger.info("Pro-Notify stopped.")


# ── Gold & Weather runners ───────────────────────────────
def _run_gold_task(gold_cfg: GoldConfig, tg: TelegramService) -> None:
    """Fetch gold prices and send to Telegram."""
    prices = fetch_gold_prices()
    if not prices:
        logger.warning("🥇 No gold prices fetched.")
        return

    # Send price update
    msg = format_gold_message(prices)
    tg.send_message(msg, parse_mode="HTML")
    logger.info("🥇 Gold prices sent to Telegram.")

    # Check alerts
    if gold_cfg.alerts:
        alerts = check_price_alert(prices, gold_cfg.alerts)
        for alert in alerts:
            tg.send_message(alert, parse_mode="HTML")
            logger.info("🥇 Gold alert: %s", alert[:80])


def _run_weather_task(weather_cfg: WeatherConfig, tg: TelegramService) -> None:
    """Fetch weather and send forecast to Telegram."""
    current = fetch_current_weather(weather_cfg.city, weather_cfg.api_key)
    if not current:
        logger.warning("🌤 No weather data fetched.")
        return

    forecasts = fetch_forecast(weather_cfg.city, weather_cfg.api_key)
    msg = format_weather_message(current, forecasts)
    tg.send_message(msg, parse_mode="HTML")
    logger.info("🌤 Weather sent to Telegram: %s %.1f°C", current["weather_desc"], current["temp"])


def _run_severe_weather_check(weather_cfg: WeatherConfig, tg: TelegramService) -> None:
    """Check for severe weather conditions and alert."""
    current = fetch_current_weather(weather_cfg.city, weather_cfg.api_key)
    if not current:
        return

    alert = check_severe_weather(current)
    if alert:
        tg.send_message(alert, parse_mode="HTML")
        logger.warning("⚠️ Severe weather alert sent!")


if __name__ == "__main__":
    main()
