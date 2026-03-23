"""
Weather Service Module
Fetches weather data from OpenWeatherMap API (free tier).
Sends formatted weather updates to Telegram.
"""

import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# OpenWeatherMap free API
OWM_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
OWM_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# Weather emoji mapping
WEATHER_EMOJI = {
    "Clear": "☀️",
    "Clouds": "☁️",
    "Rain": "🌧",
    "Drizzle": "🌦",
    "Thunderstorm": "⛈",
    "Snow": "❄️",
    "Mist": "🌫",
    "Fog": "🌫",
    "Haze": "🌫",
    "Smoke": "💨",
    "Dust": "💨",
    "Tornado": "🌪",
}

# Severe weather conditions to alert
SEVERE_CONDITIONS = {"Thunderstorm", "Tornado", "Snow"}


def fetch_current_weather(city: str, api_key: str, units: str = "metric", lang: str = "vi") -> dict | None:
    """
    Fetch current weather for a city.
    Returns parsed weather dict or None on failure.
    """
    try:
        params = {
            "q": city,
            "appid": api_key,
            "units": units,
            "lang": lang,
        }
        resp = requests.get(OWM_CURRENT_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("cod") != 200:
            logger.error("OWM API error: %s", data.get("message", "Unknown"))
            return None

        weather_main = data["weather"][0]["main"]
        weather_desc = data["weather"][0]["description"]

        result = {
            "city": data.get("name", city),
            "country": data.get("sys", {}).get("country", ""),
            "temp": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "humidity": data["main"]["humidity"],
            "pressure": data["main"]["pressure"],
            "wind_speed": data["wind"]["speed"],
            "weather_main": weather_main,
            "weather_desc": weather_desc,
            "emoji": WEATHER_EMOJI.get(weather_main, "🌡"),
            "visibility": data.get("visibility", 0) / 1000,  # km
            "clouds": data.get("clouds", {}).get("all", 0),
            "temp_min": data["main"].get("temp_min", 0),
            "temp_max": data["main"].get("temp_max", 0),
        }

        logger.info("Fetched weather for %s: %s %.1f°C", city, weather_desc, result["temp"])
        return result

    except Exception as e:
        logger.error("Error fetching weather for %s: %s", city, e)
        return None


def fetch_forecast(city: str, api_key: str, units: str = "metric", lang: str = "vi") -> list[dict] | None:
    """
    Fetch 5-day / 3-hour forecast for a city.
    Returns list of forecast entries (next 24h) or None.
    """
    try:
        params = {
            "q": city,
            "appid": api_key,
            "units": units,
            "lang": lang,
            "cnt": 8,  # 8 x 3h = 24h
        }
        resp = requests.get(OWM_FORECAST_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        forecasts = []
        for item in data.get("list", []):
            dt = datetime.fromtimestamp(item["dt"])
            weather_main = item["weather"][0]["main"]
            forecasts.append({
                "time": dt.strftime("%H:%M"),
                "date": dt.strftime("%d/%m"),
                "temp": item["main"]["temp"],
                "weather_main": weather_main,
                "weather_desc": item["weather"][0]["description"],
                "emoji": WEATHER_EMOJI.get(weather_main, "🌡"),
                "rain_chance": item.get("pop", 0) * 100,  # probability of precipitation
            })

        logger.info("Fetched %d forecast entries for %s", len(forecasts), city)
        return forecasts

    except Exception as e:
        logger.error("Error fetching forecast for %s: %s", city, e)
        return None


def format_weather_message(current: dict, forecasts: list[dict] | None = None) -> str:
    """Format weather data into a Telegram-friendly message."""
    now = datetime.now().strftime("%H:%M %d/%m/%Y")

    lines = [
        f"{current['emoji']} <b>Thời Tiết {current['city']}</b>",
        f"🕐 Cập nhật: <code>{now}</code>",
        "━" * 30,
        "",
        f"🌡 Nhiệt độ: <b>{current['temp']:.1f}°C</b> (cảm giác {current['feels_like']:.1f}°C)",
        f"📊 Min/Max: {current['temp_min']:.1f}°C / {current['temp_max']:.1f}°C",
        f"💧 Độ ẩm: {current['humidity']}%",
        f"💨 Gió: {current['wind_speed']} m/s",
        f"👁 Tầm nhìn: {current['visibility']:.1f} km",
        f"☁️ Mây: {current['clouds']}%",
        f"📝 Mô tả: <i>{current['weather_desc']}</i>",
    ]

    if forecasts:
        lines.append("")
        lines.append("━" * 30)
        lines.append("📅 <b>Dự báo 24h tới:</b>")
        lines.append("")

        for fc in forecasts:
            rain_info = f" 🌧{fc['rain_chance']:.0f}%" if fc['rain_chance'] > 20 else ""
            lines.append(
                f"  {fc['emoji']} <code>{fc['time']}</code> "
                f"{fc['temp']:.0f}°C — {fc['weather_desc']}{rain_info}"
            )

    lines.append("")
    lines.append("📊 Nguồn: OpenWeatherMap")

    return "\n".join(lines)


def check_severe_weather(current: dict) -> str | None:
    """
    Check if current weather is severe → return alert message.
    Returns alert string or None.
    """
    if current["weather_main"] in SEVERE_CONDITIONS:
        return (
            f"⚠️ <b>CẢNH BÁO THỜI TIẾT</b>\n"
            f"{'━' * 30}\n"
            f"📍 {current['city']}: <b>{current['weather_desc']}</b>\n"
            f"🌡 {current['temp']:.1f}°C | 💨 Gió {current['wind_speed']} m/s\n"
            f"Hãy cẩn thận khi ra ngoài!"
        )

    # Heat alert
    if current["temp"] >= 40:
        return (
            f"🔥 <b>CẢNH BÁO NẮNG NÓNG</b>\n"
            f"📍 {current['city']}: <b>{current['temp']:.1f}°C</b>\n"
            f"Hạn chế ra ngoài từ 11h-15h!"
        )

    return None
