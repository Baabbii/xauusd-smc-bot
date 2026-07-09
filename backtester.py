"""
Generează date OHLC sintetice (random-walk) M1, doar pentru CI/testing.
NU folosi datele astea pentru backtesting real -- sunt zgomot aleator,
nu reflectă comportamentul real al XAUUSD.
"""

import numpy as np
import pandas as pd


def generate_synthetic_m1(n_bars: int = 20000, seed: int = 42,
                           start_price: float = 2050.0,
                           start_time: str = "2024-01-01 00:00:00") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    times = pd.date_range(pd.Timestamp(start_time), periods=n_bars, freq="1min")

    price = start_price
    opens, highs, lows, closes = [], [], [], []
    trend = 0.0

    for i in range(n_bars):
        if i % 300 == 0:
            trend = rng.choice([-1, 1]) * rng.uniform(0.5, 2.0)
        drift = trend * 0.01
        noise = rng.normal(0, 0.15)
        o = price
        c = price + drift + noise
        h = max(o, c) + abs(rng.normal(0, 0.08))
        l = min(o, c) - abs(rng.normal(0, 0.08))
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        price = c

    return pd.DataFrame({
        "time": times, "open": opens, "high": highs,
        "low": lows, "close": closes, "volume": 100,
    })


if __name__ == "__main__":
    df = generate_synthetic_m1()
    df.to_csv("data/XAUUSD_M1_synthetic.csv", index=False)
    print(f"Generat {len(df)} bare sintetice -> data/XAUUSD_M1_synthetic.csv")
