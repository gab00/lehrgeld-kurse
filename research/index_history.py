#!/usr/bin/env python3
"""Lädt lange Tageshistorien für Auswertungen und Backtests (nicht fürs Trading).

- research/sp500.csv, nasdaq.csv, dow.csv: Indizes, so weit Yahoo zurückreicht
- research/sp500tr.csv: S&P 500 mit Dividenden (Total Return), für den ehrlichen Vergleich
- research/stocks/<SYMBOL>.csv: die 30 Aktien des Universums ab 2005, dazu alle
  Aktien aus research/top30_history.json (die größten 30 je Jahresende, falls vorhanden), im selben
  Format wie data/ (timestamp,open,high,low,close,volume; neueste Zeile zuerst),
  split-bereinigt, nicht dividendenbereinigt
"""
import sys
import time
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetch import UNIVERSUM  # noqa: E402

OUT = Path(__file__).parent

for sym, name in [("^GSPC", "sp500"), ("^SP500TR", "sp500tr"), ("^IXIC", "nasdaq"), ("^DJI", "dow")]:
    try:
        df = yf.Ticker(sym).history(period="max", interval="1d", auto_adjust=False, actions=False)
        df = df.dropna(subset=["Close"])
    except Exception as e:
        print(name, "Fehler", e, file=sys.stderr)
        continue
    if not len(df):
        print(name, "leer", file=sys.stderr)
        continue
    with open(OUT / f"{name}.csv", "w") as f:
        f.write("date,open,high,low,close\n")
        for ts, r in df.iterrows():
            f.write(f"{ts.strftime('%Y-%m-%d')},{r['Open']:.2f},{r['High']:.2f},{r['Low']:.2f},{r['Close']:.2f}\n")
    print(name, len(df), df.index.min().date(), df.index.max().date())

(OUT / "stocks").mkdir(exist_ok=True)
alle = list(UNIVERSUM)
import json
for hist in (OUT / "top30_history.json", OUT / "top100_history.json"):
    if hist.exists():
        for liste in json.loads(hist.read_text()).get("lists", {}).values():
            for e in liste:
                t = e.get("yahoo_today")
                if t and t not in alle:
                    alle.append(t)
for sym in alle:
    for versuch in range(3):
        try:
            df = yf.Ticker(sym).history(start="2005-01-01", interval="1d", auto_adjust=False, actions=False)
            df = df.dropna(subset=["Open", "High", "Low", "Close"])
            if len(df):
                break
        except Exception as e:
            print(sym, "Fehler", e, file=sys.stderr)
        time.sleep(3 * (versuch + 1))
    else:
        print(sym, "fehlt", file=sys.stderr)
        continue
    if not len(df):
        print(sym, "leer", file=sys.stderr)
        continue
    zeilen = ["timestamp,open,high,low,close,volume"]
    for ts, r in df.sort_index(ascending=False).iterrows():
        zeilen.append(f"{ts.strftime('%Y-%m-%d')},{r['Open']:.4f},{r['High']:.4f},{r['Low']:.4f},{r['Close']:.4f},{int(r['Volume'] or 0)}")
    (OUT / "stocks" / f"{sym}.csv").write_text("\n".join(zeilen) + "\n")
    print(sym, len(df), df.index.min().date())
    time.sleep(1)
