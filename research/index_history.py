#!/usr/bin/env python3
"""Lädt lange Tageshistorien von US-Indizes über yfinance (für Auswertungen, nicht fürs Trading)."""
from pathlib import Path
import yfinance as yf

OUT = Path(__file__).parent
for sym, name in [("^GSPC", "sp500"), ("^IXIC", "nasdaq"), ("^DJI", "dow")]:
    df = yf.Ticker(sym).history(period="max", interval="1d", auto_adjust=False, actions=False)
    df = df.dropna(subset=["Close"])
    with open(OUT / f"{name}.csv", "w") as f:
        f.write("date,open,high,low,close\n")
        for ts, r in df.iterrows():
            f.write(f"{ts.strftime('%Y-%m-%d')},{r['Open']:.2f},{r['High']:.2f},{r['Low']:.2f},{r['Close']:.2f}\n")
    print(name, len(df), df.index.min().date(), df.index.max().date())
