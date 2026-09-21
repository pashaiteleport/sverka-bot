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
    (
        "Украина",
        "https://news.google.com/rss/search?q=Украина&hl=ru&gl=UA&ceid=UA:ru",
    ),
    (
        "Мир",
        "https://news.google.com/rss/search?q=мир+новости&hl=ru&gl=UA&ceid=UA:ru",
    ),
    (
        "Технологии",
        "https://news.google.com/rss/search?q=технологии+AI&hl=ru&gl=UA&ceid=UA:ru",
    ),
    (
        "Наука",
        "https://news.google.com/rss/search?q=наука+космос&hl=ru&gl=UA&ceid=UA:ru",
    ),
    (
        "Бизнес",
        "https://news.google.com/rss/search?q=экономика+бизнес&hl=ru&gl=UA&ceid=UA:ru",
    ),
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


def clean_text(text):
    if not text:
        return ""

    text = html.unescape(text)

    text = re.sub(r"<[^>]+>", " ", text)

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def remove_source_from_title(title):
    """
    Убирает типичные хвосты вида:
    - УНИАН
    - - BBC
    - — Reuters
    - | РБК
    """

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
    title = remove_source_from_title(title)

    title = title.lower()

    title = re.sub(
        r"[^а-яёa-z0-9\s]",
        " ",
        title,
        flags=re.IGNORECASE,
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip()


def title_similarity(title_a, title_b):
    a = normalize_title(title_a)
    b = normalize_title(title_b)

    if not a or not b:
        return 0

    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


def is_duplicate_news(item, selected_items
