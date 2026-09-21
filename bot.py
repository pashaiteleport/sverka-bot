
import os
import json
import hashlib
import random
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import feedparser


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL")

STATE_FILE = Path("data/seen.json")
TIMEZONE = ZoneInfo("Europe/Kyiv")

MAX_NEWS_PER_RUN = 5

RSS_FEEDS = [
    ("Мир", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Технологии", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("Наука", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    ("Мир", "https://rss.dw.com/xml/rss-en-all"),
]


TIPS = [
    "💡 Совет дня: Перед важным решением проверь факты из нескольких независимых источников.",
    "💡 Совет дня: Запиши три главные задачи на сегодня и начни с самой важной.",
    "💡 Совет дня: Не открывай подозрительные ссылки и не передавай коды подтверждения.",
    "💡 Совет дня: Сделай короткую прогулку и дай глазам отдохнуть от экрана.",
    "💡 Совет дня: Сравни цены и условия перед крупной покупкой.",
    "💡 Совет дня: Сложную задачу раздели на несколько небольших шагов.",
    "💡 Совет дня: Используй уникальные пароли и двухфакторную защиту.",
]


if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN")

if not TELEGRAM_CHANNEL:
    raise RuntimeError("Не задан TELEGRAM_CHANNEL")


def load_state():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not STATE_FILE.exists():
        return {
            "seen_news": [],
            "last_weather_date": "",
            "last_tip_date": "",
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)

        state.setdefault("seen_news", [])
        state.setdefault("last_weather_date", "")
        state.setdefault("last_tip_date", "")

        return state

    except Exception:
        return {
            "seen_news": [],
            "last_weather_date": "",
            "last_tip_date": "",
        }


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    state["seen_news"] = state["seen_news"][-1000:]

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            state,
            file,
            ensure_ascii=False,
            indent=2,
        )


def send_telegram(text):
    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHANNEL,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )

    response.raise_for_status()


def get_news():
    news = []

    for category, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)

            for item in feed.entries[:10]:
                title = item.get("title", "").strip()
                link = item.get("link", "").strip()

                if not title or not link:
                    continue

                news_id = hashlib.sha256(
                    link.encode("utf-8")
                ).hexdigest()

                news.append({
                    "id": news_id,
                    "category": category,
                    "title": title,
                    "link": link,
                })

        except Exception as error:
            print(f"Ошибка RSS {feed_url}: {error}")

    return news


def make_news_post(item):
    category_icons = {
        "Мир": "🌍",
        "Технологии": "🤖",
        "Наука": "🔬",
    }

    icon = category_icons.get(item["category"], "📰")

    return (
        f"📰 {item['title']}\n\n"
        f"{icon} {item['category']}\n\n"
        f"🔎 СВЕРКА:\n"
        f"Новость поступила из информационной ленты. "
        f"Дополнительная проверка может потребоваться."
    )


def get_weather():
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": 50.4501,
        "longitude": 30.5234,
        "current": (
            "temperature_2m,"
            "apparent_temperature,"
            "precipitation,"
            "wind_speed_10m"
        ),
        "timezone": "Europe/Kyiv",
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()
    current = data["current"]

    temperature = current.get("temperature_2m")
    apparent = current.get("apparent_temperature")
    precipitation = current.get("precipitation")
    wind = current.get("wind_speed_10m")

    return (
        "🌤 ПОГОДА В КИЕВЕ\n\n"
        f"🌡 Температура: {temperature}°C\n"
        f"🥶 Ощущается как: {apparent}°C\n"
        f"🌧 Осадки: {precipitation} мм\n"
        f"💨 Ветер: {wind} км/ч"
    )


def get_daily_tip(date_text):
    seed = int(date_text.replace("-", ""))

    random_generator = random.Random(seed)

    return random_generator.choice(TIPS)


def main():
    print("🚀 СВЕРКА 2.0 запущена")

    now = datetime.now(TIMEZONE)
    today = now.strftime("%Y-%m-%d")

    state = load_state()

    news = get_news()

    print(f"Получено новостей: {len(news)}")

    new_count = 0

    for item in news:
        if item["id"] in state["seen_news"]:
            continue

        try:
            post = make_news_post(item)

            send_telegram(post)

            state["seen_news"].append(item["id"])
            new_count += 1

            print(f"✅ Опубликовано: {item['title']}")

        except Exception as error:
            print(f"❌ Ошибка публикации: {error}")

        if new_count >= MAX_NEWS_PER_RUN:
            break

    if state["last_weather_date"] != today:
        try:
            weather_post = get_weather()

            send_telegram(weather_post)

            state["last_weather_date"] = today

            print("🌤 Погода опубликована")

        except Exception as error:
            print(f"❌ Ошибка погоды: {error}")

    if state["last_tip_date"] != today:
        try:
            tip = get_daily_tip(today)

            send_telegram(tip)

            state["last_tip_date"] = today

            print("💡 Совет опубликован")

        except Exception as error:
            print(f"❌ Ошибка совета: {error}")

    save_state(state)

    print(f"🏁 Готово. Новостей опубликовано: {new_count}")


if __name__ == "__main__":
    main()
