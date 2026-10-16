#!/usr/bin/env python3
"""Lehrgeld-Labor Entscheidungs-Engine (Papier-Trading, Tagesbasis).

Aufruf:  python3 engine.py STATE.json DATA_DIR
STATE.json: {"heute": "YYYY-MM-DD", "settings": {...}, "trades": [...],
             "signale": [...], "earnings": {"SYM": "YYYY-MM-DD" | null}}
DATA_DIR:   SYM.csv je Aktie (timestamp,open,high,low,close,volume; neueste zuerst)
Ausgabe:    JSON-Plan auf stdout. Die Engine schreibt nichts in den Speicher.
"""
import csv, json, os, sys
from datetime import date, timedelta

MAX_OFFEN = 3
ZEITSTOPP = 15          # Handelstage
EARNINGS_TAGE = 7       # Kalendertage Sperre vor Quartalszahlen
STOP_MIN, STOP_MAX = 0.01, 0.08


def r4(x): return round(x + 0.0, 4)
def r2(x): return round(x + 0.0, 2)


def lade(data_dir):
    kurse = {}
    for fn in os.listdir(data_dir):
        if not fn.endswith('.csv'):
            continue
        sym = fn[:-4].upper()
        rows = []
        with open(os.path.join(data_dir, fn), newline='') as f:
            for r in csv.DictReader(f):
                try:
                    rows.append({'d': r['timestamp'].strip(), 'o': float(r['open']), 'h': float(r['high']),
                                 'l': float(r['low']), 'c': float(r['close'])})
                except (KeyError, ValueError):
                    continue
        rows.sort(key=lambda x: x['d'])
        if rows:
            kurse[sym] = rows
    return kurse


def sma(rows, n, end):
    """SMA der Schlusskurse über n Bars, endend bei Index end (inklusive)."""
    if end + 1 < n:
        return None
    return sum(r['c'] for r in rows[end - n + 1:end + 1]) / n


def pnl(t):
    return (t['ausstieg'] - t['einstieg']) * t['stueck'] - (t.get('gebuehren') or 0)


def main(state_path, data_dir):
    st = json.load(open(state_path))
    heute = st['heute']
    s = st['settings']
    start, risk_pct = float(s.get('startkapital', 50)), float(s.get('risikoPct', 1))
    trades = [t for t in st.get('trades', []) if not t.get('beispiel')]
    signale = [x for x in st.get('signale', []) if x.get('status') == 'wartet']
    earnings = st.get('earnings', {})
    kurse = lade(data_dir)
    plan = {'heute': heute, 'handelstag': False, 'fills': [], 'cancels': [], 'exits': [],
            'kandidaten': [], 'brauche_earnings': [], 'neue_signale': [], 'hinweise': [], 'fehlend': []}

    letzte = max((k[-1]['d'] for k in kurse.values()), default=None)
    plan['datenstand'] = letzte
    if letzte != heute:
        plan['hinweise'].append('Kein neuer Tagesschluss für %s (Datenstand %s). Kein Handelstag oder Daten noch nicht da.' % (heute, letzte))
        print(json.dumps(plan, ensure_ascii=False, indent=1)); return
    plan['handelstag'] = True

    def bar(sym, d=heute):
        for r in reversed(kurse.get(sym, [])):
            if r['d'] == d:
                return r
        return None

    # --- Konto vor heute ---
    geschlossen = [t for t in trades if t.get('ausstieg') is not None]
    equity = start + sum(pnl(t) for t in geschlossen)

    # --- 1. Bestehende Claude-Positionen prüfen ---
    offen = [t for t in trades if t.get('ausstieg') is None]
    for t in offen:
        if t.get('quelle') != 'claude':
            continue
        sym = t['ticker']; b = bar(sym)
        if not b:
            plan['fehlend'].append(sym); continue
        stop, ziel = t['stop'], t.get('ziel') or t['einstieg'] + 2 * (t['einstieg'] - t['stop'])
        tage = sum(1 for r in kurse[sym] if r['d'] > t['datum'])
        ex = None
        if b['o'] <= stop: ex = (b['o'], 'Stop (Eröffnung unter Stop)')
        elif b['l'] <= stop: ex = (stop, 'Stop')
        elif b['o'] >= ziel: ex = (b['o'], 'Ziel 2R (Eröffnung über Ziel)')
        elif b['h'] >= ziel: ex = (ziel, 'Ziel 2R')
        elif tage >= ZEITSTOPP: ex = (b['c'], 'Zeitstopp nach %d Handelstagen' % tage)
        if ex:
            t2 = dict(t, ausstieg=r2(ex[0]), datumAus=heute)
            equity += pnl(t2)
            plan['exits'].append({'id': t['id'], 'ticker': sym, 'ausstieg': r2(ex[0]), 'datumAus': heute,
                                  'grund': ex[1], 'pnl': r2(pnl(t2)),
                                  'r': r2(pnl(t2) / ((t['einstieg'] - t['stop']) * t['stueck']))})

    # --- 2. Wartende Signale zur Eröffnung ausführen ---
    for sg in signale:
        sym = sg['ticker']; b = bar(sym)
        if not b:
            plan['fehlend'].append(sym); continue
        stop = sg['stop']
        if b['o'] <= stop:
            plan['cancels'].append({'id': sg['id'], 'ticker': sym, 'grund': 'Eröffnung %.2f unter Stop %.2f' % (b['o'], stop)})
            continue
        e = b['o']; risk_eur = equity * risk_pct / 100
        qty = min(risk_eur / (e - stop), equity / e)
        qty = r4(qty)
        ziel = r2(e + 2 * (e - stop))
        tr = {'datum': heute, 'ticker': sym, 'setup': 'Rücksetzer im Aufwärtstrend', 'einstieg': r2(e), 'stop': r2(stop),
              'stueck': qty, 'ziel': ziel, 'ausstieg': None, 'datumAus': None, 'gebuehren': 0, 'regel': True,
              'phase': s.get('phase', 'papier'), 'beispiel': False, 'quelle': 'claude',
              'notiz': sg.get('begruendung', '')}
        # Gleicher Tag: Stop oder Ziel schon erreicht? Bei beidem zählt der Stop.
        if b['l'] <= stop: tr.update(ausstieg=r2(stop), datumAus=heute, notiz=tr['notiz'] + ' · Ausstieg: Stop am Einstiegstag')
        elif b['h'] >= ziel: tr.update(ausstieg=ziel, datumAus=heute, notiz=tr['notiz'] + ' · Ausstieg: Ziel 2R am Einstiegstag')
        else: offen.append(dict(tr, id='neu-' + sym))
        if tr['ausstieg'] is not None: equity += pnl(tr)
        plan['fills'].append({'signal_id': sg['id'], 'trade_id': sg['id'].replace('s-', 't-', 1), 'trade': tr})

    # --- 3. Notbremsen ---
    alle = geschlossen + [dict(t, ausstieg=x['ausstieg'], datumAus=x['datumAus']) for x in plan['exits'] for t in trades if t['id'] == x['id']] \
        + [f['trade'] for f in plan['fills'] if f['trade']['ausstieg'] is not None]
    alle.sort(key=lambda t: (t['datumAus'], t['datum']))
    eq, peak, streak, streak_end = start, start, 0, None
    for t in alle:
        eq += pnl(t); peak = max(peak, eq)
        if pnl(t) <= 0: streak += 1; streak_end = t['datumAus']
        else: streak = 0
    dd = (peak - eq) / peak if peak > 0 else 0
    sperre = None
    alle_bars = sorted({r['d'] for k in kurse.values() for r in k})
    if dd >= 0.20: sperre = 'Notbremse −20 %: keine neuen Trades. Regelwerk überarbeiten.'
    elif dd >= 0.10: sperre = 'Notbremse −10 %: keine neuen Trades bis zum Review.'
    elif streak >= 3 and streak_end:
        seit = sum(1 for d in alle_bars if d > streak_end)
        if seit < 5: sperre = '3 Verluste in Folge: Pause noch %d Handelstag(e).' % (5 - seit)
    plan['konto'] = {'equity': r2(eq), 'hoechststand': r2(peak), 'drawdown_pct': r2(dd * 100), 'verlustserie': streak}
    if sperre: plan['hinweise'].append(sperre)

    # --- 4. Neue Signale ---
    belegt = {t['ticker'] for t in offen if not any(x['id'] == t['id'] for x in plan['exits'])}
    noch_offen = len([t for t in offen if not any(x['id'] == t['id'] for x in plan['exits'])])
    frei = MAX_OFFEN - noch_offen
    kand = []
    for sym, rows in kurse.items():
        i = len(rows) - 1
        if rows[i]['d'] != heute or i < 99 or sym in belegt:
            continue
        c, prev = rows[i], rows[i - 1]
        lang = 200 if i >= 199 else 100   # 200er mit Yahoo-Daten, 100er als Notlösung
        s20, s50, slang = sma(rows, 20, i), sma(rows, 50, i), sma(rows, lang, i)
        trend = c['c'] > slang and s50 > slang
        ruecksetzer = any(rows[j]['l'] <= sma(rows, 20, j) for j in range(i - 5, i))
        trigger = c['c'] > prev['h']
        if not (trend and ruecksetzer and trigger):
            continue
        stop = min(r['l'] for r in rows[i - 5:i + 1])
        abst = (c['c'] - stop) / c['c']
        if not (STOP_MIN <= abst <= STOP_MAX):
            continue
        staerke = c['c'] / rows[i - 60]['c'] - 1
        kand.append({'ticker': sym, 'schluss': r2(c['c']), 'stop': r2(stop), 'stop_abstand_pct': r2(abst * 100),
                     'sma20': r2(s20), 'sma50': r2(s50), 'lang': lang, 'smalang': r2(slang), 'staerke60_pct': r2(staerke * 100)})
    kand.sort(key=lambda k: -k['staerke60_pct'])
    plan['kandidaten'] = kand
    plan['freie_plaetze'] = max(frei, 0)
    if sperre or frei <= 0:
        if frei <= 0 and kand: plan['hinweise'].append('3 Positionen belegt: keine neuen Signale.')
        print(json.dumps(plan, ensure_ascii=False, indent=1)); return

    d_heute = date.fromisoformat(heute)
    for k in kand:
        if len(plan['neue_signale']) >= frei:
            break
        sym = k['ticker']
        if sym not in earnings:
            plan['brauche_earnings'].append(sym); continue
        ed = earnings[sym]
        if ed and d_heute <= date.fromisoformat(ed) <= d_heute + timedelta(days=EARNINGS_TAGE):
            plan['hinweise'].append('%s ausgelassen: Quartalszahlen am %s.' % (sym, ed)); continue
        plan['neue_signale'].append({'id': 's-%s-%s' % (heute, sym), 'ticker': sym, 'stop': k['stop'], 'datumSignal': heute,
            'status': 'wartet',
            'begruendung': 'Signal %s: Schluss %.2f über Vortageshoch, Rücksetzer an 20-Tage-Linie, Kurs über %d-Tage-Linie (%.2f), 50er über %der. Stop %.2f (−%.1f %%).'
                           % (heute, k['schluss'], k['lang'], k['smalang'], k['lang'], k['stop'], k['stop_abstand_pct'])})
    print(json.dumps(plan, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
