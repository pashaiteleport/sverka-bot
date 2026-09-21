import os
import json
import random
import html
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher
from urllib.parse import quote

import requests
import feedparser


# =========================
# НАСТРОЙКИ
# =========================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = os.getenv("TELEGRAM_CHANNEL")

STATE_FILE = Path("data/seen.json")

KYIV_TZ = ZoneInfo("Europe/Kyiv")

MAX_NEWS_PER_RUN = 5
MAX_SEEN_NEWS = 1500

MIN_CONFIRMING_SOURCES = 2
VERIFICATION_RESULTS = 10


# =========================
# RSS ЛЕНТЫ
# =========================

FEEDS = {
    "🇺🇦 Украина": (
        "https://news.google.com/rss/search?"
        "q=Украина&hl=ru&gl=UA&ceid=UA:ru"
    ),
    "🌍 Мир": (
        "https://news.google.com/rss/search?"
        "q=мир+новости&hl=ru&gl=UA&ceid=UA:ru"
    ),
    "💻 Технологии": (
        "https://news.google.com/rss/search?"
        "q=технологии+AI&hl=ru&gl=UA&ceid=UA:ru"
    ),
    "🔬 Наука": (
        "https://news.google.com/rss/search?"
        "q=наука+космос&hl=ru&gl=UA&ceid=UA:ru"
    ),
    "💰 Экономика": (
        "https://news.google.com/rss/search?"
        "q=экономика+бизнес&hl=ru&gl=UA&ceid=UA:ru"
    ),
}


# =========================
# СОВЕТЫ
# =========================

DAILY_TIPS = [
    "Проверяй важную информацию минимум по двум независимым источникам.",
    "Если заголовок звучит слишком сенсационно — проверь подробности.",
    "Смотри не только на заголовок, но и на дату публикации.",
    "Не делись новостью сразу после появления — дай ей время на подтверждение.",
    "Разделяй факт, мнение и предположение.",
]


# =========================
# СОСТОЯНИЕ
# =========================

def load_state():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not STATE_FILE.exists():
        return {
            "seen": [],
            "weather_date": "",
            "tip_date": "",
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {
            "seen": [],
            "weather_date": "",
            "tip_date": "",
        }


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            state,
            file,
            ensure_ascii=False,
            indent=2
        )


# =========================
# ТЕКСТ
# =========================

def normalize_text(text):
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def similarity(text_a, text_b):
    return SequenceMatcher(
        None,
        normalize_text(text_a),
        normalize_text(text_b)
    ).ratio()


def get_domain(url):
    match = re.search(
        r"https?://([^/]+)",
        url or ""
    )

    if not match:
        return ""

    domain = match.group(1).lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


# =========================
# ПРОВЕРКА НОВОСТИ
# =========================

def get_verification_results(title):

    encoded_title = quote(title)

    url = (
        "https://news.google.com/rss/search?"
        f"q={encoded_title}"
        "&hl=ru"
        "&gl=UA"
        "&ceid=UA:ru"
    )

    try:
        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        feed = feedparser.parse(
            response.content
        )

    except Exception as error:
        print(
            f"Ошибка проверки новости: {error}"
        )
        return []

    sources = []
    domains = set()

    for item in feed.entries[:VERIFICATION_RESULTS]:

        item_title = item.get(
            "title",
            ""
        )

        if not item_title:
            continue

       
