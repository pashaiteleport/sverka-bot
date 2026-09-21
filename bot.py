import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from pathlib import Path
from difflib import SequenceMatcher


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHANNEL")

STATE_FILE = Path("data/seen.json")

FEEDS = {
    "🇺🇦 Украина": "Украина",
    "🌍 Мир": "мир новости",
    "💻 Технологии": "технологии AI",
    "🔬 Наука": "наука космос",
    "💰 Экономика": "экономика бизнес",
}


def load_seen():
    if not STATE_FILE.exists():
        return []

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        return data.get("seen", [])

    except Exception:
        return []


def save_seen(seen):
    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            {"seen": seen[-1000:]},
            file,
            ensure_ascii=False,
            indent=2,
        )


def telegram(text):
    url = (
        "https://api.telegram.org/bot"
        + TOKEN
        + "/sendMessage"
    )

    data = urllib.parse.urlencode({
        "chat_id": CHAT,
        "text": text,
    }).encode()

    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
    )

    urllib.request.urlopen(
        request,
        timeout=30,
    )


def get_news(query):
    encoded = urllib.parse.quote(query)

    url = (
        "https://news.google.com/rss/search?q="
        + encoded
        + "&hl=ru&gl=UA&ceid=UA:ru"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
    )

    data = urllib.request.urlopen(
        request,
        timeout=30,
    ).read()

    root = ET.fromstring(data)

    news = []

    for item in root.findall(".//item")[:10]:

        title = item.find("title")

        if title is not None and title.text:

            news.append(
                title.text.strip()
            )

    return news


def duplicate(title, seen):

    for old_title in seen:

        similarity = SequenceMatcher(
            None,
            title.lower(),
            old_title.lower(),
        ).ratio()

        if similarity >= 0.85:
            return True

    return False


def main():

    print("СВЕРКА DUPLICATES запущена")

    seen = load_seen()

    print(
        "В памяти: "
        + str(len(seen))
        + " новостей"
    )

    published = 0

    for category, query in FEEDS.items():

        news = get_news(query)

        for title in news:

            if duplicate(
                title,
                seen,
            ):
                print(
                    "Дубликат: "
                    + title
                )
                continue

            message = (
                category
                + "\n\n📰 "
                + title
            )

            telegram(message)

            seen.append(title)

            published += 1

            if published >= 5:
                break

        if published >= 5:
            break

    save_seen(seen)

    print(
        "Опубликовано новых: "
        + str(published)
    )


if __name__ == "__main__":
    main()
