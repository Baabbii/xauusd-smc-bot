"""
Configurație strategie: OB (M15) + FVG (M5) + BOS (M1) pentru XAUUSD.
Toate pragurile sunt exprimate în pips (pentru XAUUSD, 1 pip = 0.1 sau 0.01
în funcție de broker -- verifică digits-ul instrumentului tău și ajustează
PIP_SIZE mai jos).
"""

from dataclasses import dataclass


@dataclass
class Config:
    symbol: str = "XAUUSD"

    # --- Definirea pip-ului pentru instrumentul tău (verifică la broker) ---
    pip_size: float = 0.1          # XAUUSD are de obicei 2 zecimale -> 0.1 = 1 pip

    # --- Order Block (M15) ---
    ob_lookback: int = 150         # câte lumânări M15 analizăm pentru a găsi OB-uri
    ob_impulse_atr_mult: float = 1.5   # mișcarea de după OB trebuie să fie >= X * ATR(M15)
    ob_atr_period: int = 14
    ob_max_age_bars: int = 96      # OB expiră după N lumânări M15 (~24h) dacă nu e mitigat

    # --- Fair Value Gap (M5) ---
    fvg_lookback: int = 300        # câte lumânări M5 analizăm
    fvg_min_size_pips: float = 15  # dimensiune minimă a gap-ului ca să fie relevant

    # --- Break of Structure (M1) ---
    bos_swing_lookback: int = 20   # câte lumânări M1 pentru identificarea swing high/low
    bos_confirm_close: bool = True  # cere close (nu doar wick) dincolo de swing

    # --- Risk management ---
    risk_per_trade_pct: float = 0.5    # % din cont riscat per tranzacție
    sl_buffer_pips: float = 20         # buffer suplimentar peste/sub OB pentru SL
    rr_target: float = 2.0             # risk:reward pentru TP (poate fi înlocuit cu TP structural)
    max_trades_per_day: int = 5

    # --- Sesiuni de tranzacționare (UTC) - XAUUSD e mai activ Londra/NY ---
    session_start_hour: int = 7    # 07:00 UTC
    session_end_hour: int = 20     # 20:00 UTC

    # --- Validitate semnal ---
    max_bars_between_ob_and_fvg: int = 40   # FVG trebuie să apară "aproape" de mitigarea OB
    max_bars_between_fvg_and_bos: int = 15  # BOS trebuie confirmat curând după FVG
