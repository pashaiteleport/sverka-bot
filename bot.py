import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from difflib import SequenceMatcher

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHANNEL")
STATE = Path("data/seen.json")

FEEDS = {
    "🇺🇦 Украина": "Украина",
    "🌍 Мир": "мир новости",
    "💻 Технологии": "технологии AI",
    "🔬 Наука": "наука космос",
    "💰 Экономика": "экономика бизнес",
}


def load_seen():
    if not STATE.exists():
        return []

    try:
        with open(STATE, "r", encoding="utf-8") as f:
            data = json.load(f)

        seen = data.get("seen", [])

        if isinstance(seen, list):
            return [
                str(item).replace("\n", " ").strip()
                for item in seen
                if item
            ]

    except Exception as error:
        print("Ошибка памяти:", error)

    return []


def save_seen(seen):
    STATE.parent.mkdir(parents=True, exist_ok=True)

    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(
            {"seen": seen[-1000:]},
            f,
            ensure_ascii=False,
            indent=2
        )


def send(text):
    url = (
        "https://api.telegram.org/bot"
        + TOKEN
        + "/sendMessage"
    )

    data = urllib.parse.urlencode({
        "chat_id": CHAT,
        "text": text
    }).encode()

    request = urllib.request.Request(
        url,
        data=data,
        method="POST"
    )

    urllib.request.urlopen(
        request,
        timeout=30
    )


def get_news(query):
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(query)
        + "&hl=ru&gl=UA&ceid=UA:ru"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    data = urllib.request.urlopen(
        request,
        timeout=30
    ).read()

    root = ET.fromstring(data)

    news = []

    for item in root.findall(".//item")[:10]:
        title = item.find("title")

        if title is not None and title.text:
            news.append(title.text.strip())

    return news


def duplicate(title, seen):
    title = title.lower()

    for old in seen:
        old = old.lower()

        similarity = SequenceMatcher(
            None,
            title,
            old
        ).ratio()

        words1 = set(title.split())
        words2 = set(old.split())

        if not words1 or not words2:
            continue

        common = len(words1 & words2) / max(
            len(words1),
            len(words2)
        )

        if similarity >= 0.80:
            return True

        if common >= 0.55:
            return True

    return False


def main():
    print("СВЕРКА запущена")

    if not TOKEN:
        raise Exception("Нет TELEGRAM_BOT_TOKEN")

    if not CHAT:
        raise Exception("Нет TELEGRAM_CHANNEL")

    seen = load_seen()

    print("В памяти:", len(seen))

    published = 0

    for category, query in FEEDS.items():

        try:
            news = get_news(query)
        except Exception as error:
            print("Ошибка категории:", category)
            print(error)
            continue

        for title in news:

            if duplicate(title, seen):
                print("Дубликат:", title)
                continue

            send(
                category
                + "\n\n📰 "
                + title
            )

            seen.append(title)
            published += 1

            if published >= 5:
                break

        if published >= 5:
            break

    save_seen(seen)

    print("Новых новостей:", published)
    print("Память сохранена:", len(seen))


if __name__ == "__main__":
    main()
