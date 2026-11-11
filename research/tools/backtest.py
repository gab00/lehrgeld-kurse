#!/usr/bin/env python3
"""Backtest für das Aktiendepot: lässt engine.py Tag für Tag über die Historie laufen.

Aufruf:
  python3 -I backtest.py ENGINE.py STOCKS_DIR START END [NAME=WERT ...]

  ENGINE.py   die unveränderte Engine (aus dem Skill lehrgeld-engine)
  STOCKS_DIR  Ordner mit <SYMBOL>.csv (timestamp,open,high,low,close,volume; neueste zuerst)
  START, END  Zeitraum JJJJ-MM-TT
  NAME=WERT   optionale Variante:
    MAX_OFFEN, ZEITSTOPP, STOP_MIN, STOP_MAX   Konstanten der Engine
    RISIKO (Prozent je Trade, Standard 1), KAPITAL (Standard 500)
    GEBUEHR      Euro je Order; Kauf und Verkauf werden beim Kauf gebucht (Standard 0)
    REVIEW_TAGE  (Standard 20) so viele Handelstage nach einer −10/−20-%-Notbremse gilt
                 das Review als erledigt; der Höchststand beginnt beim aktuellen Konto neu
    SP500=<csv> MARKTFILTER=<n>  neue Signale nur, wenn der S&P 500 (date,…,close) über
                 seinem n-Tage-Durchschnitt schließt
    EARNINGS=<ordner>  <SYMBOL>.csv mit Spalte date: Quartalstermine für die 7-Tage-Sperre
    UNIVERSUM=<json>   {"lists": {"2005": [{"yahoo_today": "XOM"}, …], …}}: im Jahr J sind nur
                 die Aktien der Liste vom Jahresende J−1 handelbar (statt aller Dateien)

Ausgabe: JSON mit Kennzahlen auf stdout.

Grenzen: Ohne UNIVERSUM gelten die heutigen 30 größten Aktien rückwirkend
(Überlebens-Verzerrung, Ergebnis zu optimistisch). Ohne EARNINGS entfällt die Sperre.
"""
import bisect, contextlib, csv, importlib.util, io, json, os, sys, tempfile

FENSTER = 260   # so viele Handelstage sieht die Engine je Aktie (reicht für 200er + 60-Tage-Stärke)


def main():
    eng_path, stocks, start, end = sys.argv[1:5]
    opts = dict(a.split('=', 1) for a in sys.argv[5:])
    spec = importlib.util.spec_from_file_location('engine', eng_path)
    eng = importlib.util.module_from_spec(spec); spec.loader.exec_module(eng)
    for k in ('MAX_OFFEN', 'ZEITSTOPP'):
        if k in opts: setattr(eng, k, int(opts[k]))
    for k in ('STOP_MIN', 'STOP_MAX'):
        if k in opts: setattr(eng, k, float(opts[k]))
    kapital = float(opts.get('KAPITAL', 500)); risiko = float(opts.get('RISIKO', 1))
    gebuehr = float(opts.get('GEBUEHR', 0))
    review_tage = int(opts.get('REVIEW_TAGE', 20))
    start_k = kapital; archiv = []; gesperrt = 0; reviews = 0

    alle = eng.lade(stocks)
    daten = {s: [r['d'] for r in rows] for s, rows in alle.items()}

    # Marktfilter: Datum -> True, wenn der S&P 500 über seinem n-Tage-Durchschnitt schließt
    markt_ok = None
    if 'MARKTFILTER' in opts:
        n = int(opts['MARKTFILTER'])
        sp = sorted((r['date'], float(r['close'])) for r in csv.DictReader(open(opts['SP500'])))
        markt_ok, summe = {}, 0.0
        for i, (d, c) in enumerate(sp):
            summe += c
            if i >= n: summe -= sp[i - n][1]
            if i >= n - 1: markt_ok[d] = c > summe / n

    # Quartalstermine je Aktie (aufsteigend)
    termine = None
    if 'EARNINGS' in opts:
        termine = {}
        for fn in os.listdir(opts['EARNINGS']):
            if fn.endswith('.csv'):
                termine[fn[:-4].upper()] = sorted(r['date'] for r in csv.DictReader(open(os.path.join(opts['EARNINGS'], fn))))

    # Universum je Jahr; fehlt die Liste eines Jahres, gilt die jüngste vorhandene
    uni = None
    if 'UNIVERSUM' in opts:
        lists = json.load(open(opts['UNIVERSUM']))['lists']
        uni = {int(j) + 1: {e['yahoo_today'] for e in l if e.get('yahoo_today')} for j, l in lists.items()}
        alle = {s: r for s, r in alle.items() if any(s in u for u in uni.values())}
        daten = {s: daten[s] for s in alle}

    tage = sorted({d for ds in daten.values() for d in ds if start <= d <= end})
    sicht = {}
    eng.lade = lambda _d: sicht          # Engine sieht nur das Fenster bis zum jeweiligen Tag

    trades, signale, n_sig, gefiltert = [], [], 0, 0
    konto_verlauf, investiert = [], []
    tmp = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False); tmp.close()
    for heute in tage:
        erlaubt = None
        if uni is not None:
            j = int(heute[:4])
            erlaubt = uni.get(j) or uni[max(k for k in uni if k <= j)] if any(k <= j for k in uni) else set()
        gebunden = {t['ticker'] for t in trades if t.get('ausstieg') is None} | {s['ticker'] for s in signale}
        # Aktie ohne weitere Kurse (übernommen, eingestellt): Position zum letzten Schluss beenden
        for t in trades:
            if t.get('ausstieg') is None and daten[t['ticker']][-1] < heute:
                t.update(ausstieg=alle[t['ticker']][-1]['c'], datumAus=daten[t['ticker']][-1], grund='Daten enden')
        signale = [s for s in signale if daten[s['ticker']][-1] >= heute]
        sicht.clear()
        for s, rows in alle.items():
            if erlaubt is not None and s not in erlaubt and s not in gebunden:
                continue
            j = bisect.bisect_right(daten[s], heute)
            if j and daten[s][j - 1] == heute:
                sicht[s] = rows[max(0, j - FENSTER):j]
        if not sicht:
            continue
        earn = {s: None for s in sicht}
        if termine is not None:
            for s in sicht:
                tl = termine.get(s, [])
                k = bisect.bisect_left(tl, heute)
                earn[s] = tl[k] if k < len(tl) else None
        state = {'heute': heute, 'settings': {'startkapital': start_k, 'risikoPct': risiko, 'phase': 'papier'},
                 'trades': trades, 'signale': signale, 'earnings': earn}
        with open(tmp.name, 'w') as f: json.dump(state, f)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): eng.main(tmp.name, '-')
        plan = json.loads(buf.getvalue())
        if not plan.get('handelstag'):
            continue
        for x in plan['exits']:
            for t in trades:
                if t['id'] == x['id']: t.update(ausstieg=x['ausstieg'], datumAus=x['datumAus'], grund=x['grund'])
        weg = {f['signal_id'] for f in plan['fills']} | {c['id'] for c in plan['cancels']}
        for f in plan['fills']:
            trades.append(dict(f['trade'], id=f['trade_id'], gebuehren=2 * gebuehr))
        signale = [s for s in signale if s['id'] not in weg]
        for s in plan['neue_signale']:
            if (markt_ok is not None and not markt_ok.get(heute, False)) or (erlaubt is not None and s['ticker'] not in erlaubt):
                gefiltert += 1; continue
            signale.append(dict(s)); n_sig += 1
        zu_heute = sum(eng.pnl(t) for t in trades if t.get('ausstieg') is not None)
        eq = start_k + zu_heute
        konto_verlauf.append((heute, eq))
        investiert.append(sum(t['stueck'] * t['einstieg'] for t in trades if t.get('ausstieg') is None) / eq if eq > 0 else 0)
        # Review nach Notbremse simulieren: abgeschlossene Trades archivieren, neuer Startpunkt
        if any('Notbremse' in h for h in plan['hinweise']):
            gesperrt += 1
            if gesperrt >= review_tage:
                archiv += [t for t in trades if t.get('ausstieg') is not None]
                trades = [t for t in trades if t.get('ausstieg') is None]
                start_k = eq; gesperrt = 0; reviews += 1
        else:
            gesperrt = 0
    os.unlink(tmp.name)

    zu = archiv + [t for t in trades if t.get('ausstieg') is not None]
    pnl = [eng.pnl(t) for t in zu]
    rs = [p / ((t['einstieg'] - t['stop']) * t['stueck']) for p, t in zip(pnl, zu)]
    gew = sum(p for p in pnl if p > 0); verl = -sum(p for p in pnl if p <= 0)
    peak, mdd = kapital, 0.0
    for _, e in konto_verlauf:
        peak = max(peak, e); mdd = max(mdd, (peak - e) / peak)
    jahre = {}
    for d, e in konto_verlauf: jahre[d[:4]] = e
    vorjahr, jahr_rendite = kapital, {}
    for j in sorted(jahre):
        jahr_rendite[j] = round((jahre[j] / vorjahr - 1) * 100, 1); vorjahr = jahre[j]
    ende = konto_verlauf[-1][1] if konto_verlauf else kapital
    n_jahre = max(len(tage) / 252, 1e-9)
    grunde = {}
    for t in zu:
        g = t.get('grund', 'Am Einstiegstag').split(' (')[0].split(' nach')[0]
        grunde[g] = grunde.get(g, 0) + 1
    print(json.dumps({
        'zeitraum': [tage[0] if tage else None, tage[-1] if tage else None], 'variante': opts,
        'trades': len(zu), 'signale': n_sig, 'signale_gefiltert': gefiltert,
        'trefferquote_pct': round(100 * sum(r > 0 for r in rs) / len(rs), 1) if rs else None,
        'erwartungswert_r': round(sum(rs) / len(rs), 3) if rs else None,
        'profitfaktor': round(gew / verl, 2) if verl else None,
        'max_drawdown_pct': round(mdd * 100, 1), 'endkapital': round(ende, 2), 'reviews_nach_notbremse': reviews,
        'rendite_pa_pct': round(((ende / kapital) ** (1 / n_jahre) - 1) * 100, 2) if ende > 0 else None,
        'investiert_pct_mittel': round(100 * sum(investiert) / len(investiert), 1) if investiert else None,
        'ausstiege': grunde, 'rendite_je_jahr_pct': jahr_rendite,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
