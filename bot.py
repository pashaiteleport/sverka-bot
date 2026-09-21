import os
import json
import re
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

MAX_TOTAL = 10
MAX_PER_CATEGORY = 2

STOPWORDS = {
    "в", "во", "и", "или", "на", "по", "из", "за",
    "для", "с", "со", "о", "об", "от", "до", "как",
    "что", "это", "у", "к", "не", "но", "а", "же",
    "он", "она", "они", "уже", "был", "была", "были",
    "будет", "будут", "новый", "новая", "новые",
    "заявил", "заявила", "заявили",
    "сообщил", "сообщила", "сообщили",
}


def load_seen():
    if not STATE.exists():
        return []

    try:
        with open(STATE, "r", encoding="utf-8") as file:
            data = json.load(file)
        seen = data.get("seen", [])

        if isinstance(seen, list):
            return [str(x).strip() for x in seen if x]

    except Exception as error:
        print("Ошибка памяти:", error)

    return []


def save_seen(seen):
    STATE.parent.mkdir(parents=True, exist_ok=True)

    with open(STATE, "w", encoding="utf-8") as file:
        json.dump(
            {"seen": seen[-1000:]},
            file,
            ensure_ascii=False,
            indent=2
        )def send(text):
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

    for item in root.findall(".//item")[:15]:
        title = item.find("title")

        if title is not None and title.text:
            news.append(title.text.strip())

    return news


def clean_title(title):
    title = re.sub(
        r"\s*[-—|]\s*[^-—|]+$",
        "",
        title
    )

    title = title.lower()

    title = re.sub(
        r"[^а-яёa-z0-9\s]",
        " ",
        title
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    ).strip()

    words = [
        word
        for word in title.split()
        if word not in STOPWORDS
        and len(word) > 2
    ]

    return set(words)def is_bad_title(title):
    text = title.lower()

    bad_words = [
        "видео",
        "новости дня",
        "утренний выпуск",
        "вечерний выпуск",
        "дайджест",
        "главные новости",
        "итоги дня",
    ]

    return any(word in text for word in bad_words)


def duplicate(title, seen):
    current_words = clean_title(title)

    for old_title in seen:
        old_words = clean_title(old_title)

        if not old_words:
            continue

        similarity = SequenceMatcher(
            None,
            title.lower(),
            old_title.lower()
        ).ratio()

        common = len(
            current_words & old_words
        ) / max(
            len(current_words),
            len(old_words)
        )

        if similarity >= 0.82:
            return True

        if common >= 0.60:
            return True

    return False


def main():
    print("СВЕРКА запущена")

    if not TOKEN:
        raise Exception("Нет TELEGRAM_BOT_TOKEN")

    if not CHAT:
        raise Exception("Нет TELEGRAM_CHANNEL")

    seen = load_seen()
    published = 0

    for category, query in FEEDS.items():

        category_published = 0

        try:
            news = get_news(query)
        except Exception as error:
            print("Ошибка RSS:", error)
            continue

        for title in news:

            if published >= MAX_TOTAL:
                break

            if category_published >= MAX_PER_CATEGORY:
                break

            if is_bad_title(title):
                continue

            if duplicate(title, seen):
                continue

            send(
                category
                + "\n\n📰 "
                + title
            )

            seen.append(title)

            published += 1
            category_published += 1

        if published >= MAX_TOTAL:
            break

    save_seen(seen)

    print("Новых новостей:", published)
    print("Память сохранена:", len(seen))


if __name__ == "__main__":
    main()
