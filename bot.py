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
    "🇺🇦 Украина": "Украина новости",
    "🌍 Мир": "мир новости",
    "💻 Технологии": "технологии AI",
    "🔬 Наука": "наука космос",
    "💰 Экономика": "экономика бизнес",
}

BAD_WORDS = [
    "видео. новости дня",
    "утренний выпуск",
    "вечерний выпуск",
    "дайджест",
    "обзор дня",
]

def load_seen():
    if not STATE_FILE.exists():
        return []
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("seen", [])
    except Exception:
        return []

def save_seen(seen):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"seen": seen[-1000:]}, f, ensure_ascii=False, indent=2)

def send(text):
    url = "https://api.telegram.org/bot" + TOKEN + "/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT,
        "text": text
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    urllib.request.urlopen(req, timeout=30)

def get_news(query):
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(query)
        + "&hl=ru&gl=UA&ceid=UA:ru"
    )

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    data = urllib.request.urlopen(req, timeout=30).read()
    root = ET.fromstring(data)

    result = []

    for item in root.findall(".//item")[:15]:
        title = item.find("title")

        if title is not None and title.text:
            result.append(title.text.strip())

    return result

def bad_title(title):
    text = title.lower()

    for word in BAD_WORDS:
        if word in text:
            return True

    return False

def duplicate(title, seen):
    for old in seen:
        if SequenceMatcher(
            None,
            title.lower(),
            old.lower()
        ).ratio() >= 0.88:
            return True

    return False

def main():
    print("СВЕРКА запущена")

    seen = load_seen()
    published = 0

    for category, query in FEEDS.items():

        category_count = 0

        for title in get_news(query):

            if bad_title(title):
                continue

            if duplicate(title, seen):
                continue

            message = category + "\n\n📰 " + title

            try:
                send(message)
            except Exception as e:
                print("Ошибка Telegram:", e)
                continue

            seen.append(title)
            published += 1
            category_count += 1

            if category_count >= 2:
                break

        if published >= 10:
            break

    save_seen(seen)

    print("Опубликовано:", published)

if __name__ == "__main__":
    main()
