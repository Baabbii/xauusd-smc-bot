"""
Detectoare SMC: Order Block (OB), Fair Value Gap (FVG), Break of Structure (BOS).

IMPORTANT: aceste concepte nu au o definiție universal acceptată -- fiecare
trader ICT le definește puțin diferit. Regulile de mai jos sunt niște
definiții algoritmice explicite și testabile, alese pentru claritate și
reproductibilitate. Ajustează pragurile din config.py după cum vezi în
backtesting că se comportă pe XAUUSD.
"""

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
import pandas as pd

Direction = Literal["bullish", "bearish"]


@dataclass
class OrderBlock:
    index: int              # indexul lumânării OB în df M15
    direction: Direction
    high: float
    low: float
    time: pd.Timestamp
    mitigated: bool = False
    mitigated_at: Optional[pd.Timestamp] = None


@dataclass
class FVG:
    index: int
    direction: Direction
    top: float
    bottom: float
    time: pd.Timestamp


@dataclass
class BOSEvent:
    index: int
    direction: Direction
    level: float
    time: pd.Timestamp


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def detect_order_blocks(df: pd.DataFrame, lookback: int, atr_period: int,
                         impulse_atr_mult: float) -> list[OrderBlock]:
    """
    Regulă OB (simplificată, standard ICT):
    - OB bullish = ultima lumânare BEARISH (close < open) înainte de o
      mișcare impulsivă în SUS a cărei amplitudine >= impulse_atr_mult * ATR.
    - OB bearish = ultima lumânare BULLISH înainte de o mișcare impulsivă
      în JOS.
    Căutăm doar în ultimele `lookback` lumânări.
    """
    df = df.copy()
    df["atr"] = _atr(df, atr_period)
    start = max(atr_period + 2, len(df) - lookback)

    obs: list[OrderBlock] = []

    for i in range(start, len(df) - 1):
        atr = df["atr"].iloc[i]
        if pd.isna(atr) or atr == 0:
            continue

        candle = df.iloc[i]
        next_candle = df.iloc[i + 1]

        is_bearish_candle = candle["close"] < candle["open"]
        is_bullish_candle = candle["close"] > candle["open"]

        # mișcare impulsivă în sus care pleacă din candela curentă
        up_move = next_candle["close"] - candle["low"]
        down_move = candle["high"] - next_candle["close"]

        if is_bearish_candle and up_move >= impulse_atr_mult * atr:
            obs.append(OrderBlock(
                index=i, direction="bullish",
                high=candle["high"], low=candle["low"], time=candle["time"],
            ))

        if is_bullish_candle and down_move >= impulse_atr_mult * atr:
            obs.append(OrderBlock(
                index=i, direction="bearish",
                high=candle["high"], low=candle["low"], time=candle["time"],
            ))

    return obs


def mark_mitigation(ob: OrderBlock, df: pd.DataFrame, max_age_bars: int) -> OrderBlock:
    """
    Marchează un OB ca "mitigat" în momentul în care prețul revine în
    interiorul zonei OB (high-low) pentru prima dată după formare.
    """
    end = min(ob.index + 1 + max_age_bars, len(df))
    for j in range(ob.index + 1, end):
        bar = df.iloc[j]
        if ob.direction == "bullish":
            touched = bar["low"] <= ob.high and bar["low"] >= ob.low
        else:
            touched = bar["high"] >= ob.low and bar["high"] <= ob.high
        if touched:
            ob.mitigated = True
            ob.mitigated_at = bar["time"]
            ob.index = j  # reținem indexul mitigării, util pentru pasul următor
            return ob
    return ob


def detect_fvg(df: pd.DataFrame, lookback: int, min_size_pips: float,
                pip_size: float) -> list[FVG]:
    """
    Regulă FVG (3 lumânări consecutive: A, B, C):
    - Bullish FVG: low(C) > high(A)  -> gap-ul este [high(A), low(C)]
    - Bearish FVG: high(C) < low(A)  -> gap-ul este [high(C), low(A)]
    Filtrăm după dimensiune minimă (în pips) ca să evităm gap-uri nesemnificative.
    """
    start = max(2, len(df) - lookback)
    min_size = min_size_pips * pip_size
    fvgs: list[FVG] = []

    for i in range(start, len(df)):
        a = df.iloc[i - 2]
        c = df.iloc[i]

        if c["low"] > a["high"] and (c["low"] - a["high"]) >= min_size:
            fvgs.append(FVG(
                index=i, direction="bullish",
                top=c["low"], bottom=a["high"], time=c["time"],
            ))

        if c["high"] < a["low"] and (a["low"] - c["high"]) >= min_size:
            fvgs.append(FVG(
                index=i, direction="bearish",
                top=a["low"], bottom=c["high"], time=c["time"],
            ))

    return fvgs


def detect_bos(df: pd.DataFrame, swing_lookback: int, confirm_close: bool) -> list[BOSEvent]:
    """
    Regulă BOS:
    - Identificăm swing high/low locale (fractal simplu: high mai mare
      decât cele 2 lumânări anterioare și 2 următoare, respectiv low mai mic).
    - BOS bullish: close (sau high, dacă confirm_close=False) depășește
      cel mai recent swing high nedepășit.
    - BOS bearish: analog pentru swing low.
    """
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    swing_highs = []  # (index, price)
    swing_lows = []

    for i in range(2, n - 2):
        if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and \
           highs[i] > highs[i + 1] and highs[i] > highs[i + 2]:
            swing_highs.append((i, highs[i]))
        if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and \
           lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
            swing_lows.append((i, lows[i]))

    events: list[BOSEvent] = []
    start = max(0, n - swing_lookback * 4)

    last_swing_high = None
    last_swing_low = None
    sh_idx = lh_idx = 0

    for i in range(start, n):
        while sh_idx < len(swing_highs) and swing_highs[sh_idx][0] < i:
            last_swing_high = swing_highs[sh_idx][1]
            sh_idx += 1
        while lh_idx < len(swing_lows) and swing_lows[lh_idx][0] < i:
            last_swing_low = swing_lows[lh_idx][1]
            lh_idx += 1

        price_up = df["close"].iloc[i] if confirm_close else df["high"].iloc[i]
        price_down = df["close"].iloc[i] if confirm_close else df["low"].iloc[i]

        if last_swing_high is not None and price_up > last_swing_high:
            events.append(BOSEvent(index=i, direction="bullish",
                                    level=last_swing_high, time=df["time"].iloc[i]))
            last_swing_high = None  # evită semnale duplicate pe același nivel

        if last_swing_low is not None and price_down < last_swing_low:
            events.append(BOSEvent(index=i, direction="bearish",
                                    level=last_swing_low, time=df["time"].iloc[i]))
            last_swing_low = None

    return events
