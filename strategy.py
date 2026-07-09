"""
Strategia principală: combină Order Block (M15) + Fair Value Gap (M5) +
Break of Structure (M1) într-un singur semnal de intrare.

Logica de aliniere temporală:
1. Găsim un OB pe M15 care a fost mitigat (prețul a revenit în zonă).
2. Căutăm un FVG pe M5, în aceeași direcție, format DUPĂ mitigarea OB,
   într-o fereastră de `max_bars_between_ob_and_fvg` lumânări M5.
3. Căutăm un BOS pe M1, în aceeași direcție, format DUPĂ FVG, într-o
   fereastră de `max_bars_between_fvg_and_bos` lumânări M1.
4. Dacă toate 3 se aliniază -> semnal de intrare, cu SL sub/peste OB și
   TP calculat din risk:reward (sau poți înlocui cu TP structural).
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from config import Config
from detectors import (
    OrderBlock, FVG, BOSEvent,
    detect_order_blocks, mark_mitigation, detect_fvg, detect_bos,
)


@dataclass
class Signal:
    time: pd.Timestamp
    direction: str          # "bullish" / "bearish"
    entry: float
    stop_loss: float
    take_profit: float
    ob: OrderBlock
    fvg: FVG
    bos: BOSEvent


def _in_session(ts: pd.Timestamp, cfg: Config) -> bool:
    return cfg.session_start_hour <= ts.hour < cfg.session_end_hour


def generate_signals(m15: pd.DataFrame, m5: pd.DataFrame, m1: pd.DataFrame,
                      cfg: Config) -> list[Signal]:

    obs = detect_order_blocks(
        m15, cfg.ob_lookback, cfg.ob_atr_period, cfg.ob_impulse_atr_mult
    )
    obs = [mark_mitigation(ob, m15, cfg.ob_max_age_bars) for ob in obs]
    mitigated_obs = [ob for ob in obs if ob.mitigated]

    fvgs = detect_fvg(m5, cfg.fvg_lookback, cfg.fvg_min_size_pips, cfg.pip_size)
    bos_events = detect_bos(m1, cfg.bos_swing_lookback, cfg.bos_confirm_close)

    signals: list[Signal] = []

    for ob in mitigated_obs:
        if ob.mitigated_at is None:
            continue

        # 1) căutăm FVG-uri M5 în aceeași direcție, formate după mitigare
        candidate_fvgs = [
            f for f in fvgs
            if f.direction == ob.direction and f.time > ob.mitigated_at
        ]
        if not candidate_fvgs:
            continue

        # limităm la fereastra de timp permisă (aprox. în bare M5)
        window_end = ob.mitigated_at + pd.Timedelta(
            minutes=5 * cfg.max_bars_between_ob_and_fvg
        )
        candidate_fvgs = [f for f in candidate_fvgs if f.time <= window_end]
        if not candidate_fvgs:
            continue

        fvg = min(candidate_fvgs, key=lambda f: f.time)  # primul FVG relevant

        # 2) căutăm BOS pe M1, aceeași direcție, după FVG
        bos_window_end = fvg.time + pd.Timedelta(
            minutes=1 * cfg.max_bars_between_fvg_and_bos
        )
        candidate_bos = [
            b for b in bos_events
            if b.direction == ob.direction and fvg.time < b.time <= bos_window_end
        ]
        if not candidate_bos:
            continue

        bos = min(candidate_bos, key=lambda b: b.time)

        if not _in_session(bos.time, cfg):
            continue

        # --- construim semnalul ---
        entry_row = m1[m1["time"] == bos.time]
        if entry_row.empty:
            continue
        entry_price = float(entry_row["close"].iloc[0])

        sl_buffer = cfg.sl_buffer_pips * cfg.pip_size
        if ob.direction == "bullish":
            stop_loss = ob.low - sl_buffer
            risk = entry_price - stop_loss
            take_profit = entry_price + risk * cfg.rr_target
        else:
            stop_loss = ob.high + sl_buffer
            risk = stop_loss - entry_price
            take_profit = entry_price - risk * cfg.rr_target

        if risk <= 0:
            continue

        signals.append(Signal(
            time=bos.time, direction=ob.direction, entry=entry_price,
            stop_loss=stop_loss, take_profit=take_profit,
            ob=ob, fvg=fvg, bos=bos,
        ))

    signals.sort(key=lambda s: s.time)

    # limităm nr. de semnale/zi conform config
    if cfg.max_trades_per_day:
        by_day: dict = {}
        filtered = []
        for s in signals:
            day = s.time.date()
            by_day.setdefault(day, 0)
            if by_day[day] < cfg.max_trades_per_day:
                filtered.append(s)
                by_day[day] += 1
        signals = filtered

    return signals
