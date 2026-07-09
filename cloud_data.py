"""
Preluare date XAU/USD din cloud, via Twelve Data API -- necesar pentru ca
strategia sa poata rula pe GitHub Actions (care nu are acces la MT5).

Cont gratuit: https://twelvedata.com/ -- iti da un API key gratuit, cu
o limita zilnica de request-uri (verifica in dashboard-ul tau contul
exact, planurile se mai schimba). Cu schedule la 15 minute si 3 cereri
per rulare (M1+M5+M15), ramai confortabil in limita free tier.
"""

import json
import urllib.request
import urllib.parse

import pandas as pd

BASE_URL = "https://api.twelvedata.com/time_series"


def fetch_series(symbol: str, interval: str, outputsize: int, api_key: str) -> pd.DataFrame:
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": api_key,
        "order": "ASC",
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"

    with urllib.request.urlopen(url, timeout=20) as resp:
        body = json.loads(resp.read().decode())

    if body.get("status") == "error":
        raise RuntimeError(f"Twelve Data a returnat eroare pentru {symbol}/{interval}: "
                            f"{body.get('message')}")

    values = body.get("values", [])
    if not values:
        raise RuntimeError(f"Niciun rezultat de la Twelve Data pentru {symbol}/{interval}")

    df = pd.DataFrame(values)
    df["time"] = pd.to_datetime(df["datetime"])
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df["volume"] = df["volume"].astype(float) if "volume" in df.columns else 0

    df = df[["time", "open", "high", "low", "close", "volume"]]
    df = df.sort_values("time").reset_index(drop=True)
    return df


def get_multi_timeframe_cloud(api_key: str, symbol: str = "XAU/USD") -> dict:
    """
    Aduce M1, M5, M15 direct din API (nu prin resample local), fiecare cu
    outputsize suficient pentru lookback-urile din config.py.
    """
    m1 = fetch_series(symbol, "1min", outputsize=500, api_key=api_key)
    m5 = fetch_series(symbol, "5min", outputsize=400, api_key=api_key)
    m15 = fetch_series(symbol, "15min", outputsize=200, api_key=api_key)
    return {"M1": m1, "M5": m5, "M15": m15}
