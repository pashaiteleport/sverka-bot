
import os
import json
import hashlib
import random
import html
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher
from urllib.parse import quote_plus
from urllib.parse import urlparse

import requests
import feedparser


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL")

STATE_FILE = Path("data/seen.json")

TIMEZONE = ZoneInfo("Europe/Kyiv")

MAX_NEWS_PER_RUN = 5
MAX_SEEN_NEWS = 1500

# Сколько разных источников нужно для подтверждения
MIN_CONFIRMING_SOURCES = 2

# Сколько результатов брать при проверке
VERIFICATION_RESULTS = 10


RSS_FEEDS = [
    (
        "Украина",
        "https://news.google.com/rss/search?q=Украина&hl=ru&gl=UA&ceid=UA:ru",
    ),
    (
        "Мир",
        "https://news.google.com/rss/search?q=мир+новости&hl=ru&gl=UA&ceid=UA:ru",
    ),
    (
        "Технологии",
        "https://news.google.com/rss/search?q=технологии+AI&hl=ru&gl=UA&ceid=UA:ru",
    ),
    (
        "Наука",
        "https://news.google.com/rss/search?q=наука+космос&hl=ru&gl=UA&ceid=UA:ru",
    ),
    (
        "Бизнес",
        "https://news.google.com/rss/search?q=экономика+бизнес&hl=ru&gl=UA&ceid=UA:ru",
    ),
]


TIPS = [
    "💡 Совет дня: Перед важным решением проверь факты из нескольких независимых источников.",
    "💡 Совет дня: Запиши три главные задачи на сегодня и начни с самой важной.",
    "💡 Совет дня: Не открывай подозрительные ссылки и не передавай коды подтверждения.",
    "💡 Совет дня: Сделай короткую прогулку и дай глазам отдохнуть от экрана.",
    "💡 Совет дня: Сравни цены и условия перед крупной покупкой.",
    "💡 Совет дня: Сложную задачу раздели на несколько небольших шагов.",
    "💡 Совет дня: Используй уникальные пароли и двухфакторную защиту.",
]


if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN")

if not TELEGRAM_CHANNEL:
    raise RuntimeError("Не задан TELEGRAM_CHANNEL")


def load_state():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not STATE_FILE.exists():
        return {
            "seen_news": [],
            "last_weather_date": "",
            "last_tip_date": "",
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)

        state.setdefault("seen_news", [])
        state.setdefault("last_weather_date", "")
        state.setdefault("last_tip_date", "")

        return state

    except Exception:
        return {
            "seen_news": [],
            "last_weather_date": "",
            "last_tip_date": "",
        }


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    state["seen_news"] = state["seen_news"][-MAX_SEEN_NEWS:]

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            state,
            file,
            ensure_ascii=False,
            indent=2,
        )


def send_telegram(text):
    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHANNEL,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )

    response.raise_for_status()


def clean_text(text):
    if not text:
        return ""

    text = html.unescape(text)

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def remove_source_from_title(title):
    title = clean_text(title)

    patterns = [
        r"\s+[—–-]\s+[^—–|]{2,60}$",
        r"\s+\|\s+[^|]{2,60}$",
    ]

    for pattern in patterns:
        cleaned = re.sub(
            pattern,
            "",
            title,
            flags=re.IGNORECASE,
        )

        if len(cleaned) >= 20:
            title = cleaned.strip()

    return title


def normalize_title(title):
    title = remove_source_from_title(
        title
    ).lower()

    title = re.sub(
        r"[^а-яёa-z0-9\s]",
        " ",
        title,
        flags=re.IGNORECASE,
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip()


def title_similarity(title_a, title_b):
    a = normalize_title(title_a)
    b = normalize_title(title_b)

    if not a or not b:
        return 0

    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


def is_duplicate_news(item, selected_items):
    current_title = item["title"]

    for selected in selected_items:
        if title_similarity(
            current_title,
            selected["title"],
        ) >= 0.72:
            return True

    return False


def shorten_description(description):
    description = clean_text(description)

    if not description:
        return ""

    return description[:500].strip()


def get_news():
    news = []

    for category, feed_url in RSS_FEEDS:

        try:
            feed = feedparser.parse(
                feed_url
            )

            for item in feed.entries[:15]:

                raw_title = clean_text(
                    item.get(
                        "title",
                        "",
                    )
                )

                link = item.get(
                    "link",
                    "",
                ).strip()

                description = clean_text(
                    item.get("summary", "")
                    or item.get(
                        "description",
                        "",
                    )
                )

                source_name = clean_text(
                    item.get(
                        "source",
                        {},
                    ).get(
                        "title",
                        "",
                    )
                    if hasattr(
                        item.get(
                            "source",
                            {},
                        ),
                        "get",
                    )
                    else ""
                )

                if (
                    not raw_title
                    or not link
                ):
                    continue

                title = remove_source_from_title(
                    raw_title
                )

                if len(title) < 15:
                    continue

                news_id = hashlib.sha256(
                    link.encode("utf-8")
                ).hexdigest()

                news.append(
                    {
                        "id": news_id,
                        "category": category,
                        "title": title,
                        "description": shorten_description(
                            description
                        ),
                        "link": link,
                        "source": source_name,
                    }
                )

        except Exception as error:

            print(
                f"Ошибка RSS "
                f"{feed_url}: {error}"
            )

    return news


def get_domain(url):
    try:
        hostname = urlparse(
            url
        ).hostname

        if not hostname:
            return ""

        hostname = hostname.lower()

        if hostname.startswith("www."):
            hostname = hostname[4:]

        return hostname

    except Exception:
        return ""


def get_verification_results(title):
    """
    Ищем ту же новость в Google News RSS.

    Возвращаем список уникальных источников.
    """

    query = quote_plus(
        f'"{title}"'
    )

    url = (
        "https://news.google.com/rss/search"
        f"?q={query}"
        "&hl=ru"
        "&gl=UA"
        "&ceid=UA:ru"
    )

    try:
        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "SVERKA/4.1"
            },
        )

        response.raise_for_status()

        feed = feedparser.parse(
            response.content
        )

        sources = []

        for item in feed.entries[
            :VERIFICATION_RESULTS
        ]:

            source_name = clean_text(
                item.get(
                    "source",
                    {},
                ).get(
                    "title",
                    "",
                )
                if hasattr(
                    item.get(
                        "source",
                        {},
                    ),
                    "get",
                )
                else ""
            )

            link = item.get(
                "link",
                "",
            ).strip()

            domain = get_domain(
                link
            )

            result_title = clean_text(
                item.get(
                    "title",
                    "",
                )
            )

            # Проверяем, что найденная
            # публикация действительно
            # относится к нашей новости.
            similarity = title_similarity(
                title,
                result_title,
            )

            if (
                similarity >= 0.55
                and (
                    source_name
                    or domain
                )
            ):
                source_key = (
                    domain
                    or source_name.lower()
                )

                if source_key not in [
                    item_source["key"]
                    for item_source in sources
                ]:
                    sources.append(
                        {
                            "key": source_key,
                            "name": (
                                source_name
                                or domain
                            ),
                        }
                    )

        return sources

    except Exception as error:

        print(
            f"⚠️ Ошибка проверки "
            f"«{title}»: {error}"
        )

        return []


def verify_news(title):
    """
    Определяем статус новости.

    🟢 >= 2 независимых источника
    🟡 1 источник
    🔴 0 найденных подтверждений
    """

    sources = get_verification_results(
        title
    )

    source_count = len(
        sources
    )

    if (
        source_count
        >= MIN_CONFIRMING_SOURCES
    ):
        return {
            "status": "confirmed",
            "label": (
                "🟢 ПОДТВЕРЖДЕНО"
            ),
            "sources": sources,
        }

    if source_count == 1:
        return {
            "status": "checking",
            "label": (
                "🟡 ТРЕБУЕТ ПРОВЕРКИ"
            ),
            "sources": sources,
        }

    return {
        "status": "not_confirmed",
        "label": (
            "🔴 НЕ ПОДТВЕРЖДЕНО"
        ),
        "sources": [],
    }


def make_news_post(item):
    category_icons = {
        "Украина": "🇺🇦",
        "Мир": "🌍",
        "Технологии": "🤖",
        "Наука": "🔬",
        "Бизнес": "💰",
    }

    icon = category_icons.get(
        item["category"],
        "📰",
    )

    title = item["title"]

    description = item.get(
        "description",
        "",
    )

    if description and title_similarity(
        title,
        description,
    ) >= 0.55:
        description = ""

    if description:

        if len(description) > 350:
            description = (
                description[:350]
                .rsplit(" ", 1)[0]
                + "…"
            )

        body = description

    else:

        body = (
            "Новость получена из "
            "информационной ленты. "
            "Статус проверки указан ниже."
        )

    verification = verify_news(
        title
    )

    status = verification[
        "label"
    ]

    source_count = len(
        verification["sources"]
    )

    if source_count == 1:

        verification_text = (
            f"{status}\n"
            f"Найден 1 независимый "
            f"источник подтверждения."
        )

    elif source_count >= 2:

        verification_text = (
            f"{status}\n"
            f"Найдено независимых "
            f"источников: "
            f"{source_count}."
        )

    else:

        verification_text = (
            f"{status}\n"
            f"Надёжное независимое "
            f"подтверждение пока не найдено."
        )

    return (
        f"📰 {title}\n\n"
        f"{body}\n\n"
        f"{icon} {item['category']}\n\n"
        f"{verification_text}"
    )


def get_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
    )

    params = {
        "latitude": 50.4501,
        "longitude": 30.5234,
        "current": (
            "temperature_2m,"
            "apparent_temperature,"
            "precipitation,"
            "wind_speed_10m"
        ),
        "timezone": "Europe/Kyiv",
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    current = response.json()[
        "current"
    ]

    return (
        "🌤 ПОГОДА В КИЕВЕ\n\n"
        f"🌡 Температура: "
        f"{current.get('temperature_2m')}°C\n"
        f"🥶 Ощущается как: "
        f"{current.get('apparent_temperature')}°C\n"
        f"🌧 Осадки: "
        f"{current.get('precipitation')} мм\n"
        f"💨 Ветер: "
        f"{current.get('wind_speed_10m')} км/ч"
    )


def get_daily_tip(date_text):
    seed = int(
        date_text.replace(
            "-",
            "",
        )
    )

    return random.Random(
        seed
    ).choice(TIPS)


def main():

    print(
        "🚀 СВЕРКА 4.1 запущена"
    )

    today = datetime.now(
        TIMEZONE
    ).strftime(
        "%Y-%m-%d"
    )

    state = load_state()

    news = get_news()

    print(
        f"Получено новостей: "
        f"{len(news)}"
    )

    new_count = 0

    selected_items = []

    for item in news:

        if item["id"] in state[
            "seen_news"
        ]:
            continue

        if is_duplicate_news(
            item,
            selected_items,
        ):

            print(
                f"⏭ Дубликат: "
                f"{item['title']}"
            )

            continue

        try:

            post = make_news_post(
                item
            )

            send_telegram(
                post
            )

            state[
                "seen_news"
            ].append(
                item["id"]
            )

            selected_items.append(
                item
            )

            new_count += 1

            print(
                f"✅ Опубликовано: "
                f"{item['title']}"
            )

        except Exception as error:

            print(
                f"❌ Ошибка публикации: "
                f"{error}"
            )

        if (
            new_count
            >= MAX_NEWS_PER_RUN
        ):
            break

    if (
        state[
            "last_weather_date"
        ]
        != today
    ):

        try:

            send_telegram(
                get_weather()
            )

            state[
                "last_weather_date"
            ] = today

            print(
                "🌤 Погода опубликована"
            )

        except Exception as error:

            print(
                f"❌ Ошибка погоды: "
                f"{error}"
            )

    if (
        state[
            "last_tip_date"
        ]
        != today
    ):

        try:

            send_telegram(
                get_daily_tip(
                    today
                )
            )

            state[
                "last_tip_date"
            ] = today

            print(
                "💡 Совет опубликован"
            )

        except Exception as error:

            print(
                f"❌ Ошибка совета: "
                f"{error}"
            )

    save_state(
        state
    )

    print(
        f"🏁 Готово. "
        f"Новостей опубликовано: "
        f"{new_count}"
    )


if __name__ == "__main__":
    main()
