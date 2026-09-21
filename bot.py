import os
import json
import random
import html
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher
from urllib.parse import quote
import re

import requests
import feedparser


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = os.getenv("TELEGRAM_CHANNEL")

STATE_FILE = Path("data/seen.json")
KYIV_TZ = ZoneInfo("Europe/Kyiv")

MAX_NEWS_PER_RUN = 5
MAX_SEEN_NEWS = 1500

FEEDS = {
    "🇺🇦 Украина": "https://news.google.com/rss/search?q=Украина&hl=ru&gl=UA&ceid=UA:ru",
    "🌍 Мир": "https://news.google.com/rss/search?q=мир+новости&hl=ru&gl=UA&ceid=UA:ru",
    "💻 Технологии": "https://news.google.com/rss/search?q=технологии+AI&hl=ru&gl=UA&ceid=UA:ru",
    "🔬 Наука": "https://news.google.com/rss/search?q=наука+космос&hl=ru&gl=UA&ceid=UA:ru",
    "💰 Экономика": "https://news.google.com/rss/search?q=экономика+бизнес&hl=ru&gl=UA&ceid=UA:ru",
}

DAILY_TIPS = [
    "Проверяй важную информацию минимум по двум независимым источникам.",
    "Если заголовок звучит слишком сенсационно — проверь подробности.",
    "Смотри не только на заголовок, но и на дату публикации.",
    "Разделяй факт, мнение и предположение.",
    "Не спеши делиться новостью, пока информация не проверена.",
]


def load_state():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not STATE_FILE.exists():
        return {
            "seen": [],
            "weather_date": "",
            "tip
