"""
Preluare date XAU/USD din cloud, via Twelve Data API -- necesar pentru ca
strategia sa poata rula pe GitHub Actions (care nu are acces la MT5).

Cont gratuit: https://twelvedata.com/ -- iti da un API key gratuit, cu
o limita zilnica de request-uri (verifica in dashboard-ul tau contul
exact, planurile se mai schimba). Cu schedule la 15 minute si 3 cereri
per rulare (M1+M5+M15), ramai confortabil in limita free tier.
"""

import json
import ssl
import urllib.request
import urllib.parse

import certifi
import pandas as pd

BASE_URL = "https://api.twelvedata.com/time_series"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def fetch_series(symbol: str, interval: str, outputsize: int, api_key: str) -> pd.DataFrame:
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": api_key,
        "order": "ASC",
        "timezone": "UTC",
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"

    with urllib.request.urlopen(url, timeout=20, context=SSL_CONTEXT) as resp:
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


def get_multi_timeframe_cloud(
    api_key: str,
    symbol: str = "XAU/USD",
    m1_outputsize: int | None = None,
    m5_outputsize: int = 400,
    m15_outputsize: int = 200,
) -> dict:
    """
    Aduce M1, M5, M15 direct din API (nu prin resample local).

    Important: pentru alinierea OB(M15)->FVG(M5)->BOS(M1), seria M1 trebuie
    să acopere cel puțin aceeași fereastră temporală ca M5/M15. Dacă
    m1_outputsize nu e dat explicit, îl calculăm automat din celelalte două.
    """
    if m1_outputsize is None:
        # Acoperire minimă în minute: M15(15m/bar) și M5(5m/bar).
        m1_outputsize = max(m15_outputsize * 15, m5_outputsize * 5)

    m1 = fetch_series(symbol, "1min", outputsize=m1_outputsize, api_key=api_key)
    m5 = fetch_series(symbol, "5min", outputsize=m5_outputsize, api_key=api_key)
    m15 = fetch_series(symbol, "15min", outputsize=m15_outputsize, api_key=api_key)
    return {"M1": m1, "M5": m5, "M15": m15}
