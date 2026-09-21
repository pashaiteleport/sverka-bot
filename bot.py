import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHANNEL")

FEEDS = {
    "🇺🇦 Украина": "Украина",
    "🌍 Мир": "мир новости",
    "💻 Технологии": "технологии AI",
    "🔬 Наука": "наука космос",
    "💰 Экономика": "экономика бизнес",
}


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

    for item in root.findall(".//item")[:3]:
        title = item.find("title")

        if title is not None and title.text:
            news.append(title.text.strip())

    return news


def main():
    print("СВЕРКА NEWS запущена")

    for category, query in FEEDS.items():

        news = get_news(query)

        for title in news:

            message = (
                category
                + "\n\n📰 "
                + title
            )

            telegram(message)

    print("Новости отправлены")


if __name__ == "__main__":
    main()
