"""
Gold Price Service Module
Fetches real-time gold prices from Vietnamese sources.
Sends formatted price updates to Telegram.
"""

import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Giá Vàng API (free, no key required)
GOLD_API_URL = "https://api.wahool.com/api/gold-price"
GOLD_FALLBACK_URL = "https://giavang.org"


def _format_number(n: float) -> str:
    """Format number with dot separator: 12345678 → 12.345.678"""
    return f"{n:,.0f}".replace(",", ".")


def fetch_gold_prices() -> dict | None:
    """
    Fetch gold prices from API.
    Returns dict with gold types and prices, or None on failure.
    """
    try:
        # Try primary API
        prices = _fetch_from_giavang_org()
        if prices:
            return prices

        logger.warning("Primary gold source failed, no fallback available.")
        return None

    except Exception as e:
        logger.error("Error fetching gold prices: %s", e)
        return None


def _fetch_from_giavang_org() -> dict | None:
    """Scrape gold prices from giavang.org."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(GOLD_FALLBACK_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")

        prices = {}
        # Find the main price table
        table = soup.find("table", {"id": "gold-table"}) or soup.find("table")
        if not table:
            # Try to find price data in any structured format
            rows = soup.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    name = cells[0].get_text(strip=True)
                    buy = cells[1].get_text(strip=True).replace(",", "").replace(".", "")
                    sell = cells[2].get_text(strip=True).replace(",", "").replace(".", "")

                    # Filter for gold-related rows
                    if any(kw in name.lower() for kw in ["sjc", "pnj", "9999", "vàng", "gold"]):
                        try:
                            buy_price = float(buy) if buy.isdigit() else 0
                            sell_price = float(sell) if sell.isdigit() else 0
                            if buy_price > 0 or sell_price > 0:
                                prices[name] = {"buy": buy_price, "sell": sell_price}
                        except (ValueError, TypeError):
                            continue
        else:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    name = cells[0].get_text(strip=True)
                    buy = cells[1].get_text(strip=True).replace(",", "").replace(".", "")
                    sell = cells[2].get_text(strip=True).replace(",", "").replace(".", "")
                    try:
                        buy_price = float(buy) if buy.isdigit() else 0
                        sell_price = float(sell) if sell.isdigit() else 0
                        if buy_price > 0 or sell_price > 0:
                            prices[name] = {"buy": buy_price, "sell": sell_price}
                    except (ValueError, TypeError):
                        continue

        if prices:
            logger.info("Fetched %d gold price entries from giavang.org", len(prices))
            return prices

        logger.warning("No gold prices parsed from giavang.org")
        return None

    except Exception as e:
        logger.error("Error scraping giavang.org: %s", e)
        return None


def format_gold_message(prices: dict) -> str:
    """Format gold prices into a Telegram-friendly message."""
    now = datetime.now().strftime("%H:%M %d/%m/%Y")

    lines = [
        "🥇 <b>Giá Vàng Hôm Nay</b>",
        f"🕐 Cập nhật: <code>{now}</code>",
        "━" * 30,
        "",
        f"{'Loại':<20} {'Mua':>12} {'Bán':>12}",
        "─" * 46,
    ]

    for name, data in prices.items():
        buy_str = _format_number(data["buy"]) if data["buy"] > 0 else "—"
        sell_str = _format_number(data["sell"]) if data["sell"] > 0 else "—"
        # Truncate name if too long
        short_name = name[:18] if len(name) > 18 else name
        lines.append(f"<code>{short_name:<20} {buy_str:>12} {sell_str:>12}</code>")

    lines.append("")
    lines.append("💰 Đơn vị: <i>nghìn VNĐ / lượng</i>")
    lines.append("📊 Nguồn: giavang.org")

    return "\n".join(lines)


def check_price_alert(prices: dict, alert_config: dict) -> list[str]:
    """
    Check if any gold price crosses alert thresholds.
    alert_config: {"SJC": {"above": 90000, "below": 85000}, ...}
    Returns list of alert messages.
    """
    alerts = []

    for gold_type, thresholds in alert_config.items():
        for name, data in prices.items():
            if gold_type.lower() not in name.lower():
                continue

            sell_price = data.get("sell", 0)
            if sell_price <= 0:
                continue

            above = thresholds.get("above", 0)
            below = thresholds.get("below", 0)

            if above and sell_price >= above:
                alerts.append(
                    f"🔴 <b>{name}</b> vượt ngưỡng! "
                    f"Giá bán: <b>{_format_number(sell_price)}</b> "
                    f"(≥ {_format_number(above)})"
                )
            if below and sell_price <= below:
                alerts.append(
                    f"🟢 <b>{name}</b> dưới ngưỡng! "
                    f"Giá bán: <b>{_format_number(sell_price)}</b> "
                    f"(≤ {_format_number(below)})"
                )

    return alerts
