#!/usr/bin/env python3
"""Ganz anderer Ansatz zum Vergleich: monatliche Rotation in die stärksten Aktien.

Aufruf: python3 -I rotation.py STOCKS_DIR TOP30.json SP500.csv START END [TOP=5] [N=126] [MARKT=200]

Regel: Am letzten Handelstag eines Monats werden die Aktien der damaligen Top-30-Liste nach ihrem
Anstieg über N Handelstage gereiht. Am ersten Handelstag des neuen Monats wird zur Eröffnung
umgeschichtet: Was nicht mehr unter den TOP stärksten ist, wird verkauft, der Erlös gleichmäßig auf
die Neuen verteilt. Schließt der S&P 500 unter seinem MARKT-Tage-Durchschnitt, wird alles verkauft.
Ohne Gebühren, nur Kurse (ohne Dividenden). Ausgabe: JSON auf stdout.
"""
import csv, json, os, sys


def main():
    stocks, top30, spf, start, end = sys.argv[1:6]
    o = dict(a.split('=', 1) for a in sys.argv[6:])
    TOP, N, MARKT = int(o.get('TOP', 5)), int(o.get('N', 126)), int(o.get('MARKT', 200))
    listen = json.load(open(top30))['lists']
    px = {}
    for f in os.listdir(stocks):
        if f.endswith('.csv'):
            px[f[:-4]] = {r['timestamp']: (float(r['open']), float(r['close'])) for r in csv.DictReader(open(os.path.join(stocks, f)))}
    sp = sorted((r['date'], float(r['close'])) for r in csv.DictReader(open(spf)))
    sp_d = [d for d, _ in sp]; sp_c = [c for _, c in sp]
    alle = [d for d in sp_d if d <= end and d in px['XOM']]      # alle Handelstage, auch vor START (für den Rückblick)
    i0 = next(i for i, d in enumerate(alle) if d >= start)

    def universum(jahr):
        l = listen.get(str(int(jahr) - 1)) or listen[max(listen)]
        return [e['yahoo_today'] for e in l if e.get('yahoo_today')]

    def markt_ok(d):
        k = sp_d.index(d)
        return k >= MARKT - 1 and sp_c[k] > sum(sp_c[k - MARKT + 1:k + 1]) / MARKT

    bar, halte, letzter = 1.0, {}, {}
    kurve, orders, investiert = [], 0, 0
    for i in range(i0, len(alle)):
        d, vortag = alle[i], alle[i - 1]
        if d[:7] != vortag[:7]:                                   # erster Handelstag des Monats
            ziel = []
            if markt_ok(vortag):
                rang = []
                for s in universum(d[:4]):
                    a, b = px.get(s, {}).get(alle[i - 1 - N]), px.get(s, {}).get(vortag)
                    if a and b and d in px[s]:
                        rang.append((b[1] / a[1], s))
                ziel = [s for _, s in sorted(rang, reverse=True)[:TOP]]
            for s in [s for s in halte if s not in ziel]:         # Verkauf zur Eröffnung
                kurs = px[s][d][0] if d in px[s] else letzter[s]
                bar += halte.pop(s) * kurs; orders += 1
            neu = [s for s in ziel if s not in halte]
            if neu:
                je = bar / (TOP - len(halte)) if len(halte) < TOP else 0
                for s in neu:
                    halte[s] = je / px[s][d][0]; bar -= je; orders += 1
        wert = bar
        for s, stk in halte.items():
            if d in px[s]: letzter[s] = px[s][d][1]
            wert += stk * letzter[s]
        kurve.append(wert); investiert += 1 if halte else 0
    hoch, rueck = 0.0, 0.0
    for v in kurve:
        hoch = max(hoch, v); rueck = max(rueck, (hoch - v) / hoch)
    jahre = len(kurve) / 252
    print(json.dumps({'zeitraum': [alle[i0], alle[-1]], 'rendite_pa_pct': round(((kurve[-1] / kurve[0]) ** (1 / jahre) - 1) * 100, 2),
                      'max_drawdown_pct': round(rueck * 100, 1), 'orders_pro_jahr': round(orders / jahre, 1),
                      'zeit_investiert_pct': round(100 * investiert / len(kurve), 1), 'optionen': o}, ensure_ascii=False))


if __name__ == '__main__':
    main()
