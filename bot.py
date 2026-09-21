
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
# СОВЕТ ДНЯ
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
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "seen": [],
            "weather_date": "",
            "tip_date": "",
        }


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================

def normalize_text(text):
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def make_id(title):
    normalized = normalize_text(title)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def similarity(a, b):
    return SequenceMatcher(
        None,
        normalize_text(a),
        normalize_text(b)
    ).ratio()


def get_domain(url):
    match = re.search(r"https?://([^/]+)", url or "")
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
    """
    Ищем публикации с максимально похожим заголовком
    в Google News RSS.

    Возвращаем уникальные домены источников.
    """

    query = requests.utils.quote(title)

    url = (
        "https://news.google.com/rss/search?"
        f"q={query}&hl=ru&gl
