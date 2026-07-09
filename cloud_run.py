"""
Script rulat de GitHub Actions (vezi .github/workflows/signal_check.yml).

Diferența față de daily_run.py: aici datele vin din cloud (Twelve Data),
nu din CSV local exportat din MT5. Token-urile vin din variabile de mediu
setate de workflow (din GitHub Secrets), NU dintr-un fișier .env local.
"""

import json
import os

from config import Config
from cloud_data import get_multi_timeframe_cloud
from strategy import generate_signals
from alerts import alert_new_signals

STATE_FILE = "state.json"


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_alerted_time": None}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def main():
    api_key = os.environ.get("TWELVEDATA_API_KEY")
    if not api_key:
        raise SystemExit(
            "Lipsește TWELVEDATA_API_KEY din variabilele de mediu / secrets."
        )

    cfg = Config()
    state = load_state()

    tf = get_multi_timeframe_cloud(api_key)
    m1, m5, m15 = tf["M1"], tf["M5"], tf["M15"]

    print(f"Bare primite -> M1: {len(m1)}, M5: {len(m5)}, M15: {len(m15)}")

    signals = generate_signals(m15, m5, m1, cfg)

    last_time = state.get("last_alerted_time")
    if last_time:
        new_signals = [s for s in signals if str(s.time) > last_time]
    else:
        # prima rulare -- nu alertam retroactiv, doar marcam punctul de start
        new_signals = []

    if new_signals:
        print(f"Semnale noi găsite: {len(new_signals)}")
        alert_new_signals(new_signals)
    else:
        print("Niciun semnal nou.")

    if signals:
        state["last_alerted_time"] = str(signals[-1].time)
        save_state(state)


if __name__ == "__main__":
    main()
