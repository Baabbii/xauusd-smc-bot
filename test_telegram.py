"""
Test SIMPLU pentru alerta Telegram -- pune token-ul si chat_id-ul direct
aici, jos, intre ghilimele. Fara .env, fara export, fara nimic altceva.

Cum rulezi:
    python test_telegram.py
"""

import urllib.request
import urllib.parse
import json

# ==========================================================================
# PUNE AICI DATELE TALE (intre ghilimele, nu sterge ghilimelele):
BOT_TOKEN = "8705232005:AAFBJHknxEPppdtoDzdrv_9-S-OjOSsqNnU"
CHAT_ID = "xauusd-smc-bot"
# ==========================================================================


def send_test_message():
    if "PUNE_AICI" in BOT_TOKEN or "PUNE_AICI" in CHAT_ID:
        print("!!! Nu ai completat BOT_TOKEN sau CHAT_ID in fisierul asta.")
        print("Deschide test_telegram.py cu Notepad si inlocuieste valorile.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": "Test — functioneaza! 🎯",
    }).encode()

    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            if body.get("ok"):
                print("REUSIT! Verifica canalul de Telegram.")
            else:
                print("Telegram a raspuns cu eroare:")
                print(json.dumps(body, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"EROARE la conectare: {e}")


if __name__ == "__main__":
    send_test_message()
