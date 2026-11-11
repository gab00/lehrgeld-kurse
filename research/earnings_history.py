#!/usr/bin/env python3
"""Lädt vergangene Quartalszahlen-Termine je Aktie (nur für Rückrechnungen).

Schreibt research/earnings/<SYMBOL>.csv mit einer Spalte date (JJJJ-MM-TT, aufsteigend).
Quelle: Yahoo Finance über yfinance. Lücken sind möglich und werden nicht geraten.
"""
import sys
import time
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetch import UNIVERSUM  # noqa: E402

OUT = Path(__file__).parent / "earnings"
OUT.mkdir(exist_ok=True)
ok = 0
for sym in UNIVERSUM:
    tage = set()
    for versuch in range(3):
        try:
            df = yf.Ticker(sym).get_earnings_dates(limit=100)
            if df is not None and len(df):
                tage = {ts.strftime("%Y-%m-%d") for ts in df.index}
                break
        except Exception as e:
            print(sym, "Fehler", e, file=sys.stderr)
        time.sleep(4 * (versuch + 1))
    if not tage:
        print(sym, "keine Termine", file=sys.stderr)
        continue
    (OUT / f"{sym}.csv").write_text("date\n" + "\n".join(sorted(tage)) + "\n")
    print(sym, len(tage), min(tage), max(tage))
    ok += 1
    time.sleep(1.5)
print("Aktien mit Terminen:", ok)
