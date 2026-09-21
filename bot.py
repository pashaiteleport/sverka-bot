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


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = os.getenv("TELEGRAM_CHANNEL")

STATE_FILE = Path("data/seen.json")

KYIV_TZ = ZoneInfo("Europe/Kyiv")

MAX_NEWS_PER_RUN = 5
MAX_SEEN_NEWS = 1500

MIN_CONFIRMING_SOURCES = 2
VERIFICATION_RESULTS = 10


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
        "q=наука+космос&hl=ru&gl=UA&ceid=UA
