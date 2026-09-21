import os
import json
import hashlib
import random
import html
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher

import requests
import feedparser

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL")

STATE_FILE = Path("data/seen.json")
TIMEZONE = ZoneInfo("Europe/Kyiv")
MAX_NEWS_PER_RUN = 5
MAX_SEEN_NEWS = 1500

RSS_FEEDS = [
    ("Украина", "https://news.google.com/rss/search?q=Украина&hl=ru&gl=UA&ceid=UA:ru"),
    ("Мир", "https://news.google.com/rss/search?q=мир+новости&hl=ru&gl=UA&ceid=UA:ru"),
    ("Технологии", "https://news.google.com/rss/search?q=технологии+AI&hl=ru&gl=UA&ceid=UA:ru"),
    ("Наука", "https://news.google.com/rss/search?q=наука+космос&hl=ru&gl=UA&ceid=UA:ru"),
    ("Бизнес", "https://news.google.com/rss/search?q=экономика+бизнес&hl=ru&gl=UA&ceid=UA:ru"),
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
    state["seen_news"] = state["seen_news"][-MAX_SEEN_NEWS:]

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

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


def clean_text(text):
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def remove_source_from_title(title):
    title = clean_text(title)

    patterns = [
        r"\s+[—–-]\s+[^—–|]{2,60}$",
        r"\s+\|\s+[^|]{2,60}$",
    ]

    for pattern in patterns:
        cleaned = re.sub(
            pattern,
            "",
            title,
            flags=re.IGNORECASE,
        )

        if len(cleaned) >= 20:
            title = cleaned.strip()

    return title


def normalize_title(title):
    title = remove_source_from_title(title).lower()

    title = re.sub(
        r"[^а-яёa-z0-9\s]",
        " ",
        title,
        flags=re.IGNORECASE,
    )

    title = re.sub(r"\s+", " ", title)

    return title.strip()


def title_similarity(title_a, title_b):
    a = normalize_title(title_a)
    b = normalize_title(title_b)

    if not a or not b:
        return 0

    return SequenceMatcher(None, a, b).ratio()


def is_duplicate_news(item, selected_items):
    current_title = item["title"]

    for selected in selected_items:
        if title_similarity(
            current_title,
            selected["title"],
        ) >= 0.72:
            return True

    return False


def shorten_description(description):
    description = clean_text(description)

    if not description:
        return ""

    return description[:500].strip()


def get_news():
    news = []

    for category, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)

            for item in feed.entries[:15]:
                raw_title = clean_text(
                    item.get("title", "")
                )

                link = item.get(
                    "link",
                    "",
                ).strip()

                description = clean_text(
                    item.get("summary", "")
                    or item.get("description", "")
                )

                if not raw_title or not link:
                    continue

                title = remove_source_from_title(
                    raw_title
                )

                if len(title) < 15:
                    continue

                news_id = hashlib.sha256(
                    link.encode("utf-8")
                ).hexdigest()

                news.append({
                    "id": news_id,
                    "category": category,
                    "title": title,
                    "description": shorten_description(
                        description
                    ),
                    "link": link,
                })

        except Exception as error:
            print(
                f"Ошибка RSS {feed_url}: {error}"
            )

    return news


def make_news_post(item):
    category_icons = {
        "Украина": "🇺🇦",
        "Мир": "🌍",
        "Технологии": "🤖",
        "Наука": "🔬",
        "Бизнес": "💰",
    }

    icon = category_icons.get(
        item["category"],
        "📰",
    )

    title = item["title"]
    description = item.get(
        "description",
        "",
    )

    if description and title_similarity(
        title,
        description,
    ) >= 0.55:
        description = ""

    if description:
        if len(description) > 350:
            description = (
                description[:350]
                .rsplit(" ", 1)[0]
                + "…"
            )

        body = description

    else:
        body = (
            "Подробности доступны "
            "в исходной информационной ленте."
        )

    return (
        f"📰 {title}\n\n"
        f"{body}\n\n"
        f"{icon} {item['category']}\n\n"
        f"🟡 Информация требует проверки "
        f"по дополнительным независимым источникам."
    )


def get_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
    )

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

    current = response.json()["current"]

    return (
        "🌤 ПОГОДА В КИЕВЕ\n\n"
        f"🌡 Температура: "
        f"{current.get('temperature_2m')}°C\n"
        f"🥶 Ощущается как: "
        f"{current.get('apparent_temperature')}°C\n"
        f"🌧 Осадки: "
        f"{current.get('precipitation')} мм\n"
        f"💨 Ветер: "
        f"{current.get('wind_speed_10m')} км/ч"
    )


def get_daily_tip(date_text):
    seed = int(
        date_text.replace("-", "")
    )

    return random.Random(
        seed
    ).choice(TIPS)


def main():
    print(
        "🚀 СВЕРКА 4.0 запущена"
    )

    today = datetime.now(
        TIMEZONE
    ).strftime("%Y-%m-%d")

    state = load_state()

    news = get_news()

    print(
        f"Получено новостей: {len(news)}"
    )

    new_count = 0
    selected_items = []

    for item in news:

        if item["id"] in state["seen_news"]:
            continue

        if is_duplicate_news(
            item,
            selected_items,
        ):
            print(
                f"⏭ Дубликат: "
                f"{item['title']}"
            )
            continue

        try:
            send_telegram(
                make_news_post(item)
            )

            state["seen_news"].append(
                item["id"]
            )

            selected_items.append(item)

            new_count += 1

            print(
                f"✅ Опубликовано: "
                f"{item['title']}"
            )

        except Exception as error:
            print(
                f"❌ Ошибка публикации: "
                f"{error}"
            )

        if new_count >= MAX_NEWS_PER_RUN:
            break

    if state["last_weather_date"] != today:
        try:
            send_telegram(
                get_weather()
            )

            state[
                "last_weather_date"
            ] = today

            print(
                "🌤 Погода опубликована"
            )

        except Exception as error:
            print(
                f"❌ Ошибка погоды: "
                f"{error}"
            )

    if state["last_tip_date"] != today:
        try:
            send_telegram(
                get_daily_tip(today)
            )

            state[
                "last_tip_date"
            ] = today

            print(
                "💡 Совет опубликован"
            )

        except Exception as error:
            print(
                f"❌ Ошибка совета: "
                f"{error}"
            )

    save_state(state)

    print(
        f"🏁 Готово. "
        f"Новостей опубликовано: "
        f"{new_count}"
    )


if __name__ == "__main__":
    main()
