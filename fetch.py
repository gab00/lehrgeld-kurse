#!/usr/bin/env python3
"""Holt Tageskurse für das Lehrgeld-Labor von Yahoo Finance (über yfinance).

Schreibt je Aktie data/<SYMBOL>.csv im Format
    timestamp,open,high,low,close,volume   (neueste Zeile zuerst)
und data/_status.json mit Zeitpunkt, letztem Handelstag und fehlenden Aktien.
Dazu data/earnings.json: der nächste Quartalszahlen-Termin je Aktie (für die
7-Tage-Sperre vor Quartalszahlen).

Kurse sind split-bereinigt, aber nicht dividendenbereinigt, damit der letzte
Tag den echten Börsenkursen entspricht.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

UNIVERSUM = [
    "NVDA", "AAPL", "GOOGL", "MSFT", "AMZN", "AVGO", "META", "TSLA", "LLY", "MU",
    "JPM", "WMT", "AMD", "V", "XOM", "JNJ", "MA", "INTC", "ABBV", "CSCO",
    "BAC", "AMAT", "COST", "CAT", "CVX", "UNH", "LRCX", "GE", "KO", "PG",
]
# Zusatzreihen für den Vergleich mit dem echten Depot (nicht für Handelsentscheidungen)
EXTRAS = {"SP500": "^GSPC", "EURUSD": "EURUSD=X"}
ZEITRAUM = "15mo"      # reicht für die 200-Tage-Linie plus Rückblick
MIN_ZEILEN = 220

DATA = Path(__file__).parent / "data"


def hole(symbol):
    """Lädt eine Aktie, bis zu drei Versuche."""
    for versuch in range(3):
        try:
            df = yf.Ticker(symbol).history(period=ZEITRAUM, interval="1d", auto_adjust=False, actions=False)
            df = df.dropna(subset=["Open", "High", "Low", "Close"])
            if len(df) >= MIN_ZEILEN:
                return df
            print(f"{symbol}: nur {len(df)} Zeilen", file=sys.stderr)
        except Exception as e:  # yfinance wirft je nach Fehler verschiedene Typen
            print(f"{symbol}: Versuch {versuch + 1} fehlgeschlagen: {e}", file=sys.stderr)
        time.sleep(3 * (versuch + 1))
    return None


def schreibe(symbol, df, ordner=None):
    zeilen = ["timestamp,open,high,low,close,volume"]
    for ts, r in df.sort_index(ascending=False).iterrows():
        zeilen.append(
            f"{ts.strftime('%Y-%m-%d')},{r['Open']:.4f},{r['High']:.4f},{r['Low']:.4f},{r['Close']:.4f},{int(r['Volume'] or 0)}"
        )
    ziel = ordner or DATA
    ziel.mkdir(exist_ok=True)
    (ziel / f"{symbol}.csv").write_text("\n".join(zeilen) + "\n")
    return df.index.max().strftime("%Y-%m-%d")


def hole_termine():
    """Nächster Quartalszahlen-Termin je Aktie laut Yahoo.

    termine[SYM] = "JJJJ-MM-TT" oder None (Yahoo kennt noch keinen Termin).
    Aktien, bei denen der Abruf scheitert, fehlen in termine und stehen in fehler.
    """
    heute = datetime.now(timezone.utc).date()
    termine, fehler = {}, []
    for sym in UNIVERSUM:
        try:
            cal = yf.Ticker(sym).calendar or {}
            tage = cal.get("Earnings Date") or []
            if not isinstance(tage, (list, tuple)):
                tage = [tage]
            tage = [t.date() if isinstance(t, datetime) else t for t in tage]
            kommend = sorted(t for t in tage if hasattr(t, "isoformat") and t >= heute)
            termine[sym] = kommend[0].isoformat() if kommend else None
        except Exception as e:
            print(f"{sym}: Quartalstermin nicht abrufbar: {e}", file=sys.stderr)
            fehler.append(sym)
        time.sleep(0.5)
    return termine, fehler


def schreibe_termine():
    """Schreibt data/earnings.json. Scheitert der Abruf weitgehend, bleibt die alte Datei stehen."""
    try:
        termine, fehler = hole_termine()
    except Exception as e:
        print(f"Quartalstermine: {e}", file=sys.stderr)
        return None
    if len(termine) < len(UNIVERSUM) // 2:
        return None
    (DATA / "earnings.json").write_text(json.dumps({
        "aktualisiert": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quelle": "Yahoo Finance (Kalender) über yfinance " + yf.__version__,
        "termine": termine,
        "fehler": fehler,
    }, indent=1, ensure_ascii=False) + "\n")
    return {"mit_termin": sum(1 for v in termine.values() if v), "ohne_termin": sum(1 for v in termine.values() if not v), "fehler": fehler}


def main():
    DATA.mkdir(exist_ok=True)
    ok, fehlend, letzte = [], [], {}
    for sym in UNIVERSUM:
        df = hole(sym)
        if df is None:
            fehlend.append(sym)
            continue
        letzte[sym] = schreibe(sym, df)
        ok.append(sym)
        time.sleep(1)
    extras = {}
    for name, sym in EXTRAS.items():
        df = hole(sym)
        if df is not None:
            extras[name] = schreibe(name, df, DATA / "extra")
        time.sleep(1)
    status = {
        "aktualisiert": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "letzter_handelstag": max(letzte.values()) if letzte else None,
        "ok": ok,
        "fehlend": fehlend,
        "letzter_tag_je_aktie": letzte,
        "extras": extras,
        "quartalstermine": schreibe_termine(),
        "quelle": "Yahoo Finance über yfinance " + yf.__version__,
    }
    (DATA / "_status.json").write_text(json.dumps(status, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: status[k] for k in ("letzter_handelstag", "fehlend")}))
    # Nur scheitern, wenn fast nichts kam – einzelne Ausfälle fängt die Auswertung ab.
    if len(ok) < len(UNIVERSUM) // 2:
        sys.exit(1)


if __name__ == "__main__":
    main()
