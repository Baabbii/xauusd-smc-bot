"""
Alertare prin Telegram atunci când apare un semnal nou.

Setup rapid:
1. Deschide Telegram, caută @BotFather, scrie /newbot și urmează pașii ->
   primești un TELEGRAM_BOT_TOKEN.
2. Trimite orice mesaj botului tău nou creat (altfel nu-ți poate răspunde).
3. Vizitează https://api.telegram.org/bot<TOKEN>/getUpdates ca să-ți
   găsești CHAT_ID (apare în JSON, câmpul "chat":{"id": ...}).
4. Setează variabilele de mediu (sau pune-le într-un fișier .env local,
   NU le urca niciodată pe GitHub):
       export TELEGRAM_BOT_TOKEN="123456:ABC-your-token"
       export TELEGRAM_CHAT_ID="123456789"
"""

import os
import urllib.request
import urllib.parse
import json

from strategy import Signal


def send_telegram_message(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[alerts] TELEGRAM_BOT_TOKEN sau TELEGRAM_CHAT_ID nesetate -- "
              "afișez doar în consolă:\n" + text)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode()

    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            return body.get("ok", False)
    except Exception as e:
        print(f"[alerts] Eroare la trimiterea pe Telegram: {e}")
        return False


def format_signal_message(signal: Signal) -> str:
    emoji = "🟢" if signal.direction == "bullish" else "🔴"
    return (
        f"{emoji} <b>Semnal nou XAUUSD -- {signal.direction.upper()}</b>\n"
        f"Ora: {signal.time}\n"
        f"Entry: {signal.entry:.2f}\n"
        f"SL: {signal.stop_loss:.2f}\n"
        f"TP: {signal.take_profit:.2f}\n"
        f"OB M15: {signal.ob.time} | FVG M5: {signal.fvg.time} | BOS M1: {signal.bos.time}"
    )


def alert_new_signals(signals: list[Signal]) -> None:
    for s in signals:
        msg = format_signal_message(s)
        send_telegram_message(msg)
