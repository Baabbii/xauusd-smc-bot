"""
Script rulat de GitHub Actions (vezi .github/workflows/signal_check.yml).

Diferența față de daily_run.py: aici datele vin din cloud (Twelve Data),
nu din CSV local exportat din MT5. Token-urile vin din variabile de mediu
setate de workflow (din GitHub Secrets), NU dintr-un fișier .env local.
"""

import json
import os
from datetime import datetime, timedelta

import pandas as pd

from config import Config
from cloud_data import get_multi_timeframe_cloud
from strategy import generate_signals
from alerts import alert_new_signals

STATE_FILE = "state.json"


def load_state() -> dict:
    now = datetime.now()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)

        last_time = state.get("last_alerted_time")
        if last_time:
            parsed = pd.to_datetime(last_time, errors="coerce")
            if pd.notna(parsed):
                last_dt = parsed.to_pydatetime().replace(tzinfo=None)
                # Dacă timestamp-ul din state e în viitor, îl aducem la "acum".
                if last_dt > now + timedelta(minutes=5):
                    state["last_alerted_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
        return state
    return {"last_alerted_time": now.strftime("%Y-%m-%d %H:%M:%S")}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def _generate_with_fallback(
    m15: pd.DataFrame, m5: pd.DataFrame, m1: pd.DataFrame, cfg: Config
) -> tuple[list, str]:
    signals = generate_signals(m15, m5, m1, cfg)
    if signals:
        return signals, "strict"

    relaxed_cfg = Config(**vars(cfg))
    relaxed_cfg.fvg_min_size_pips = min(cfg.fvg_min_size_pips, 3)
    relaxed_cfg.bos_confirm_close = False
    relaxed_cfg.bos_swing_lookback = min(cfg.bos_swing_lookback, 10)
    relaxed_cfg.max_bars_between_ob_and_fvg = max(cfg.max_bars_between_ob_and_fvg, 200)
    relaxed_cfg.max_bars_between_fvg_and_bos = max(cfg.max_bars_between_fvg_and_bos, 360)
    relaxed_cfg.session_start_hour = 0
    relaxed_cfg.session_end_hour = 24

    return generate_signals(m15, m5, m1, relaxed_cfg), "fallback"


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

    signals, mode = _generate_with_fallback(m15, m5, m1, cfg)
    print(f"Mod semnale: {mode}; total găsite: {len(signals)}")

    last_time = state.get("last_alerted_time")
    if last_time:
        parsed = pd.to_datetime(last_time, errors="coerce")
        if pd.notna(parsed):
            last_time_dt = parsed.to_pydatetime().replace(tzinfo=None)
            new_signals = [
                s for s in signals
                if pd.Timestamp(s.time).to_pydatetime().replace(tzinfo=None) > last_time_dt
            ]
        else:
            new_signals = []
    else:
        # prima rulare -- nu alertam retroactiv, doar marcam punctul de start
        new_signals = []

    if new_signals:
        print(f"Semnale noi găsite: {len(new_signals)}")
        alert_new_signals(new_signals)
        state["last_alerted_time"] = str(new_signals[-1].time)
    else:
        if signals:
            print(
                "Semnale există, dar niciunul nu e nou față de state "
                f"(ultimul semnal: {signals[-1].time}, state: {state.get('last_alerted_time')})."
            )
        else:
            print("Niciun semnal nou.")

    save_state(state)


if __name__ == "__main__":
    main()
