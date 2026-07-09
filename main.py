"""
Backtester simplu (bar-by-bar pe M1) pentru semnalele generate de strategy.py.

Simplificări (importante de conștientizat):
- Nu modelează spread/comision/slippage decât printr-un parametru fix simplu.
- Presupune execuție instant la prețul de close al lumânării BOS (nu simulează
  order queue sau latență reală de broker).
- O singură poziție deschisă simultan (poți extinde pentru mai multe).
Folosește-l ca punct de plecare, nu ca validare finală înainte de live.
"""

from dataclasses import dataclass

import pandas as pd

from config import Config
from strategy import Signal


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: str
    entry: float
    exit: float
    stop_loss: float
    take_profit: float
    result: str      # "TP", "SL", "EOD" (end of data)
    pnl_pips: float


def run_backtest(signals: list[Signal], m1: pd.DataFrame, cfg: Config,
                  spread_pips: float = 3.0) -> list[Trade]:

    trades: list[Trade] = []
    m1_indexed = m1.set_index("time")
    spread = spread_pips * cfg.pip_size

    for sig in signals:
        future = m1_indexed[m1_indexed.index > sig.time]
        if future.empty:
            continue

        exit_time = None
        exit_price = None
        result = "EOD"

        for ts, bar in future.iterrows():
            if sig.direction == "bullish":
                hit_sl = bar["low"] <= sig.stop_loss
                hit_tp = bar["high"] >= sig.take_profit
            else:
                hit_sl = bar["high"] >= sig.stop_loss
                hit_tp = bar["low"] <= sig.take_profit

            # dacă ambele sunt atinse în aceeași lumânare, presupunem
            # conservator că SL-ul e lovit primul
            if hit_sl:
                exit_time, exit_price, result = ts, sig.stop_loss, "SL"
                break
            if hit_tp:
                exit_time, exit_price, result = ts, sig.take_profit, "TP"
                break

        if exit_time is None:
            exit_time = future.index[-1]
            exit_price = future["close"].iloc[-1]

        if sig.direction == "bullish":
            pnl = (exit_price - sig.entry - spread) / cfg.pip_size
        else:
            pnl = (sig.entry - exit_price - spread) / cfg.pip_size

        trades.append(Trade(
            entry_time=sig.time, exit_time=exit_time, direction=sig.direction,
            entry=sig.entry, exit=exit_price, stop_loss=sig.stop_loss,
            take_profit=sig.take_profit, result=result, pnl_pips=pnl,
        ))

    return trades


def summarize(trades: list[Trade]) -> dict:
    if not trades:
        return {"n_trades": 0}

    wins = [t for t in trades if t.pnl_pips > 0]
    losses = [t for t in trades if t.pnl_pips <= 0]
    total_pips = sum(t.pnl_pips for t in trades)
    win_rate = len(wins) / len(trades) * 100

    avg_win = sum(t.pnl_pips for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.pnl_pips for t in losses) / len(losses) if losses else 0

    days = len({t.entry_time.date() for t in trades})

    return {
        "n_trades": len(trades),
        "n_days": days,
        "avg_trades_per_day": round(len(trades) / days, 2) if days else 0,
        "win_rate_pct": round(win_rate, 1),
        "total_pips": round(total_pips, 1),
        "avg_win_pips": round(avg_win, 1),
        "avg_loss_pips": round(avg_loss, 1),
        "expectancy_pips": round(total_pips / len(trades), 2),
    }
