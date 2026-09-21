import os
import urllib.parse
import urllib.request

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHANNEL")


def send(text):
    if not TOKEN:
        raise Exception("Нет TELEGRAM_BOT_TOKEN")
    if not CHAT:
        raise Exception("Нет TELEGRAM_CHANNEL")

    url = "https://api.telegram.org/bot" + TOKEN + "/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": CHAT,
        "text": text,
    }).encode()

    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = response.read().decode()

    if '"ok":true' not in result:
        raise Exception(result)


def main():
    print("СВЕРКА TEST запущена")
    send("🟢 СВЕРКА работает!")
    print("Сообщение отправлено в Telegram")


if __name__ == "__main__":
    main()
