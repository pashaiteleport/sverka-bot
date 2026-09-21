import os
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import requests
import feedparser


# =========================
# НАСТРОЙКИ
# =========================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL")

STATE_FILE = Path("data/seen.json")
MAX_NEWS_PER_RUN = 5

RSS_FEEDS = [
    ("Мир", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Технологии", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("Наука", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
]


# =========================
# ПРОВЕРКА НАСТРОЕК
# =========================

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN")

if not TELEGRAM_CHANNEL:
    raise RuntimeError("Не задан TELEGRAM_CHANNEL")


# =========================
# СОСТОЯНИЕ
# =========================

def load_seen():
    if not STATE_FILE.exists():
        return set()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Храним только последние 1000 новостей
    data = list(seen)[-1000:]

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# TELEGRAM
# =========================

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHANNEL,
            "text": text,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    response.raise_for_status()


# =========================
# RSS
# =========================

def get_news():
    news = []

    for category, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)

            for item in feed.entries[:10]:
                title = item.get("title", "").strip()
                link = item.get("link", "").strip()
                summary = item.get("summary", "").strip()

                if not title or not link:
                    continue

                news_id = hashlib.sha256(
                    link.encode("utf-8")
                ).hexdigest()

                news.append({
                    "id": news_id,
                    "category": category,
                    "title": title,
                    "summary": summary,
                    "link": link,
                })

        except Exception as e:
            print(f"Ошибка RSS {feed_url}: {e}")

    return news


# =========================
# ФОРМИРОВАНИЕ ПОСТА
# =========================

def make_post(item):
    category = item["category"]
    title = item["title"]
    link = item["link"]

    return (
        f"📰 {title
