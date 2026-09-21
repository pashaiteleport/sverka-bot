import os
import json
import random
import html
import re
import requests
import xml.etree.ElementTree as ET

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher
from urllib.parse import quote


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
            "tip_date": "",
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)

        if "seen" not in state:
            state["seen"] = []

        if "weather_date" not in state:
            state["weather_date"] = ""

        if "tip_date" not in state:
            state["tip_date"] = ""

        return state

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


def send_telegram(text):
    if not BOT_TOKEN:
        raise RuntimeError("Не найден TELEGRAM_BOT_TOKEN")

    if not CHANNEL:
        raise RuntimeError("Не найден TELEGRAM_CHANNEL")

    url = (
        "https://api.telegram.org/bot"
        + BOT_TOKEN
        + "/sendMessage"
    )

    payload = {
        "chat_id": CHANNEL,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30
    )

    if not response.ok:
        raise RuntimeError(
            "Telegram ошибка "
            + str(response.status_code)
            + ": "
            + response.text
        )

    print("Telegram: сообщение отправлено")


def parse_rss(url):
    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    root = ET.fromstring(response.content)

    result = []

    for item in root.findall(".//item"):
        title_node = item.find("title")
        link_node = item.find("link")

        title = ""

        if title_node is not None and title_node.text:
            title = title_node.text.strip()

        link = ""

        if link_node is not None and link_node.text:
            link = link_node.text.strip()

        if title:
            result.append(
                {
                    "title": title,
                    "link": link,
                }
            )

    return result


def get_news():
    news = []

    for category, url in FEEDS.items():
        try:
            entries = parse_rss(url)

            print(
                category
                + ": найдено "
                + str(len(entries))
                + " материалов"
            )

            for entry in entries[:10]:
                news.append(
                    {
                        "title": entry["title"],
                        "link": entry["link"],
                        "category": category,
                    }
                )

        except Exception as error:
            print(
                "Ошибка RSS "
                + category
                + ": "
                + str(error)
            )

    return news


def is_duplicate(title, seen_titles):
    for old_title in seen_titles:
        similarity = SequenceMatcher(
            None,
            title.lower(),
            old_title.lower(),
        ).ratio()

        if similarity >= 0.85:
            return True

    return False


def get_verification_count(title):
    try:
        query = quote(title)

        url = (
            "https://news.google.com/rss/search?q="
            + query
            + "&hl=ru&gl=UA&ceid=UA:ru"
        )

        entries = parse_rss(url)

        domains = set()

        for entry in entries[:10]:
            other_title = entry["title"]
            link = entry["link"]

            similarity = SequenceMatcher(
                None,
                title.lower(),
                other_title.lower(),
            ).ratio()

            if similarity < 0.55:
                continue

            match = re.search(
                r"https?://(?:www\.)?([^/]+)",
                link
            )

            if match:
                domains.add(
                    match.group(1).lower()
                )

        return len(domains)

    except Exception as error:
        print(
            "Ошибка проверки: "
            + str(error)
        )

        return 0


def verification_text(title):
    count = get_verification_count(title)

    if count >= 2:
        return (
            "🟢 <b>ПОДТВЕРЖДЕНО</b>\n"
            "Найдено совпадение минимум в "
            + str(count)
            + " независимых источниках."
        )

    if count == 1:
        return (
            "🟡 <b>ТРЕБУЕТ ПРОВЕРКИ</b>\n"
            "Найден один источник с похожей информацией."
        )

    return (
        "🔴 <b>НЕ ПОДТВЕРЖДЕНО</b>\n"
        "Независимых подтверждений не найдено."
    )


def make_news_post(title, category):
    safe_title = html.escape(title)

    return (
        "📰 <b>"
        +
