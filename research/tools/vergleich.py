#!/usr/bin/env python3
"""Vergleichsmaßstäbe für den Monatsrückblick: einfach halten statt handeln.

Aufruf: python3 -I vergleich.py STOCKS_DIR TOP30.json SP500.csv SP500TR.csv START END
Ausgabe: JSON-Liste [{name, rendite_pa_pct, max_drawdown_pct}] auf stdout.
Aktienkörbe: gleich gewichtet, zu jedem Jahresbeginn neu verteilt, nur Kurse (ohne Dividenden).
"""
import csv, json, os, sys

HEUTE30 = ("NVDA AAPL GOOGL MSFT AMZN AVGO META TSLA LLY MU JPM WMT AMD V XOM JNJ MA INTC ABBV CSCO "
           "BAC AMAT COST CAT CVX UNH LRCX GE KO PG").split()


def kennzahlen(kurve):
    hoch, rueck = 0.0, 0.0
    for v in kurve:
        hoch = max(hoch, v); rueck = max(rueck, (hoch - v) / hoch)
    return round(((kurve[-1] / kurve[0]) ** (252 / len(kurve)) - 1) * 100, 2), round(rueck * 100, 1)


def main():
    stocks, top30, sp, sptr, start, end = sys.argv[1:7]
    listen = json.load(open(top30))['lists']
    px = {}
    for f in os.listdir(stocks):
        if f.endswith('.csv'):
            px[f[:-4]] = {r['timestamp']: float(r['close']) for r in csv.DictReader(open(os.path.join(stocks, f)))}
    tage = sorted({d for s in HEUTE30 if s in px for d in px[s] if start <= d <= end})

    def korb(wahl):
        wert, kurve, halte, jahr, letzter = 1.0, [], {}, None, {}
        for d in tage:
            if halte:
                v = 0.0
                for s, (w, p0) in halte.items():
                    p = px[s].get(d, letzter.get(s, p0)); letzter[s] = p; v += w * p / p0
                jetzt = wert * v
            else:
                jetzt = wert
            kurve.append(jetzt)
            if d[:4] != jahr:
                jahr = d[:4]; wert = jetzt
                da = [s for s in wahl(jahr) if d in px.get(s, {})]
                halte = {s: (1 / len(da), px[s][d]) for s in da}; letzter = {}
        return kennzahlen(kurve)

    def index(pfad):
        return kennzahlen([float(r['close']) for r in csv.DictReader(open(pfad)) if start <= r['date'] <= end])

    def damals(jahr):
        l = listen.get(str(int(jahr) - 1)) or listen[max(listen)]
        return [e['yahoo_today'] for e in l if e.get('yahoo_today')]

    out = []
    for name, (pa, dd) in (
        ('Die damaligen 30 Aktien einfach halten', korb(damals)),
        ('Die heutigen 30 Aktien einfach halten (geschönt)', korb(lambda j: HEUTE30)),
        ('S&P 500 halten', index(sp)),
        ('S&P 500 halten, mit Dividenden', index(sptr)),
    ):
        out.append({'name': name, 'rendite_pa_pct': pa, 'max_drawdown_pct': dd})
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
