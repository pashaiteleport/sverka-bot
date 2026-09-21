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
        return json.load(open(STATE, encoding="utf-8")).get("seen", [])
    except:
        return []

def save_seen(seen):
    STATE.parent.mkdir(exist_ok=True)
    json.dump({"seen": seen[-1000:]}, open(STATE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

def send(text):
    url = "https://api.telegram.org/bot" + TOKEN + "/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT, "text": text}).encode()
    urllib.request.urlopen(
        urllib.request.Request(url, data=data, method="POST"),
        timeout=30
    )

def get_news(query):
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query)
    url += "&hl=ru&gl=UA&ceid=UA:ru"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=30).read())

    result = []
    for item in root.findall(".//item")[:10]:
        title = item.find("title")
        if title is not None and title.text:
            result.append(title.text.strip())
    return result

def
