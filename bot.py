import os
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import requests
import feedparser


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL")

STATE_FILE = Path("data/seen.json")
MAX_NEWS_PER_RUN = 5

    RSS_FEEDS = [
    # 🌍 Мир
    ("Мир", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Мир", "https://rss.dw.com/xml/rss-en-all"),

    # 🤖 Технологии
    ("Технологии", "https://feeds.bbci.co.uk/news/technology/rss.xml"),

    # 🔬 Наука
    ("Наука", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),

    # 🌍 Euronews
    ("Мир", "https://feeds.euronews.com/rss/en/world"),
    ("Спорт", "https://feeds.euronews.com/rss/en/sport"),
    ("Культура", "https://feeds.euronews.com/rss/en/culture"),
]
]


if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN")

if not TELEGRAM_CHANNEL:
    raise RuntimeError("Не задан TELEGRAM_CHANNEL")


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

    data = list(seen)[-1000:]

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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

        except Exception as e:
            print(f"Ошибка RSS {feed_url}: {e}")

    return news


def make_post(item):
    title = item["title"]
    category = item["category"]
    link = item["link"]

    current_time = datetime.now(timezone.utc).strftime(
        "%d.%m.%Y %H:%M UTC"
    )

    post = (
        f"📰 {title}\n\n"
        f"📂 Рубрика: {category}\n\n"
        f"🔎 СВЕРКА:\n"
        f"Информация поступила из указанного источника. "
        f"На этом этапе мы не называем неподтверждённую "
        f"информацию фейком.\n\n"
        f"🔗 Источник: {link}\n\n"
        f"🕐 {current_time}"
    )

    return post


def main():
    print("🚀 СВЕРКА запущена")

    seen = load_seen()
    news = get_news()

    print(f"Получено новостей: {len(news)}")

    new_count = 0

    for item in news:
        if item["id"] in seen:
            continue

        try:
            post = make_post(item)
            send_telegram(post)

            seen.add(item["id"])
            new_count += 1

            print(f"✅ Опубликовано: {item['title']}")

        except Exception as e:
            print(f"❌ Ошибка публикации: {e}")

        if new_count >= MAX_NEWS_PER_RUN:
            break

    save_seen(seen)

    print(f"🏁 Готово. Опубликовано: {new_count}")


if __name__ == "__main__":
    main()
