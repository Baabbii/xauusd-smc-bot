"""
Teste de fum (smoke tests) -- verifică doar că pipeline-ul rulează fără
erori și produce structuri de date corecte. NU validează calitatea
strategiei (asta se face cu backtesting pe date reale, separat).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from config import Config
from data_loader import resample_ohlc
from detectors import detect_order_blocks, mark_mitigation, detect_fvg, detect_bos
from strategy import generate_signals
from backtester import run_backtest, summarize
from scripts.generate_synthetic_data import generate_synthetic_m1


def _load_test_data():
    m1 = generate_synthetic_m1(n_bars=20000, seed=42)
    m5 = resample_ohlc(m1, "5min")
    m15 = resample_ohlc(m1, "15min")
    return m1, m5, m15


def test_data_loader_resample_shapes():
    m1, m5, m15 = _load_test_data()
    assert len(m1) == 20000
    assert len(m5) > 0
    assert len(m15) > 0
    assert len(m5) < len(m1)
    assert len(m15) < len(m5)


def test_order_block_detection_runs():
    m1, m5, m15 = _load_test_data()
    cfg = Config()
    obs = detect_order_blocks(m15, cfg.ob_lookback, cfg.ob_atr_period, cfg.ob_impulse_atr_mult)
    assert isinstance(obs, list)
    for ob in obs:
        assert ob.direction in ("bullish", "bearish")
        assert ob.high >= ob.low


def test_fvg_detection_runs():
    m1, m5, m15 = _load_test_data()
    cfg = Config()
    fvgs = detect_fvg(m5, cfg.fvg_lookback, cfg.fvg_min_size_pips, cfg.pip_size)
    assert isinstance(fvgs, list)
    for f in fvgs:
        assert f.top > f.bottom


def test_bos_detection_runs():
    m1, m5, m15 = _load_test_data()
    cfg = Config()
    bos = detect_bos(m1, cfg.bos_swing_lookback, cfg.bos_confirm_close)
    assert isinstance(bos, list)


def test_full_pipeline_runs_end_to_end():
    m1, m5, m15 = _load_test_data()
    cfg = Config()
    # praguri relaxate ca sa avem sanse sa vedem si semnale pe date sintetice
    cfg.fvg_min_size_pips = 2
    cfg.max_bars_between_ob_and_fvg = 200
    cfg.max_bars_between_fvg_and_bos = 60
    cfg.session_start_hour = 0
    cfg.session_end_hour = 24

    signals = generate_signals(m15, m5, m1, cfg)
    assert isinstance(signals, list)

    trades = run_backtest(signals, m1, cfg)
    stats = summarize(trades)
    assert "n_trades" in stats

    # daca a generat semnale, verificam consistenta SL/TP
    for s in signals:
        if s.direction == "bullish":
            assert s.stop_loss < s.entry < s.take_profit
        else:
            assert s.take_profit < s.entry < s.stop_loss


def test_max_trades_per_day_respected():
    m1, m5, m15 = _load_test_data()
    cfg = Config()
    cfg.fvg_min_size_pips = 1
    cfg.max_bars_between_ob_and_fvg = 500
    cfg.max_bars_between_fvg_and_bos = 200
    cfg.session_start_hour = 0
    cfg.session_end_hour = 24
    cfg.max_trades_per_day = 2

    signals = generate_signals(m15, m5, m1, cfg)
    by_day = {}
    for s in signals:
        day = s.time.date()
        by_day[day] = by_day.get(day, 0) + 1
    for day, count in by_day.items():
        assert count <= cfg.max_trades_per_day
