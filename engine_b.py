#!/usr/bin/env python3
"""System B „Gegenläufer“: Entscheidungs-Engine (Papier-Trading, Tagesbasis).

Eigenständiges Gegenstück zu engine.py (System A). Kauft überdehnte Abwärtsbewegungen
ohne Bestätigung und ohne Trendfilter. Kennt die Trades und Signale von System A nicht.
Regeln eingefroren am 11.11.2026, siehe REGELWERK_B.md. Änderung = neue Version.

Aufruf:  python3 engine_b.py STATE.json DATA_DIR
STATE.json: {"heute": "YYYY-MM-DD", "settings": {...}, "trades": [...],
             "signale": [...], "earnings": {"SYM": "YYYY-MM-DD" | null}}
            trades und signale enthalten NUR die Einträge von System B.
DATA_DIR:   SYM.csv je Aktie (timestamp,open,high,low,close,volume; neueste zuerst)
Ausgabe:    JSON-Plan auf stdout. Die Engine schreibt nichts in den Speicher.
"""
import csv, json, os, sys
from datetime import date, timedelta

VERSION = 'B1'
MAX_OFFEN = 3
ZEITSTOPP = 10          # Handelstage
EARNINGS_TAGE = 7       # Kalendertage Sperre vor Quartalszahlen
SMA_N = 20              # Durchschnittslinie
ATR_N = 14              # durchschnittliche Tagesschwankung über so viele Tage
DEHNUNG = 2.5           # Schluss mindestens so viele ATR unter der 20-Tage-Linie
TIEFER_MIN = 3          # so viele tiefere Schlusskurse …
TIEFER_FENSTER = 4      # … in den letzten so vielen Tagen
STOP_ATR = 2.0          # Stop = Einstieg minus so viele ATR
PANIK_MIN = 8           # so viele Aktien gleichzeitig überdehnt = Panik-Tag
PANIK_FAKTOR = 2.0      # Risiko-Vielfaches für Signale eines Panik-Tags
MIN_FREI = 0.01         # weniger freies Kapital als dieser Anteil am Konto: kein Kauf
MIN_BARS = 30


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
    """Durchschnitt der Schlusskurse über n Tage, endend bei Index end (inklusive)."""
    if end + 1 < n:
        return None
    return sum(r['c'] for r in rows[end - n + 1:end + 1]) / n


def atr(rows, n, end):
    """Durchschnittliche Tagesschwankung (True Range, einfacher Mittelwert) über n Tage bis Index end."""
    if end < n:
        return None
    s = 0.0
    for j in range(end - n + 1, end + 1):
        pc = rows[j - 1]['c']
        s += max(rows[j]['h'] - rows[j]['l'], abs(rows[j]['h'] - pc), abs(rows[j]['l'] - pc))
    return s / n


def pnl(t):
    return (t['ausstieg'] - t['einstieg']) * t['stueck'] - (t.get('gebuehren') or 0)


def main(state_path, data_dir):
    st = json.load(open(state_path))
    heute = st['heute']
    s = st['settings']
    start, risk_pct = float(s.get('startkapital', 500)), float(s.get('risikoPct', 1))
    trades = [t for t in st.get('trades', []) if not t.get('beispiel')]
    signale = [x for x in st.get('signale', []) if x.get('status') == 'wartet']
    earnings = st.get('earnings', {})
    kurse = lade(data_dir)
    plan = {'system': 'B', 'version': VERSION, 'heute': heute, 'handelstag': False, 'fills': [], 'cancels': [],
            'exits': [], 'kandidaten': [], 'brauche_earnings': [], 'neue_signale': [], 'hinweise': [], 'fehlend': []}

    letzte = max((k[-1]['d'] for k in kurse.values()), default=None)
    plan['datenstand'] = letzte
    if letzte != heute:
        plan['hinweise'].append('Kein neuer Tagesschluss für %s (Datenstand %s). Kein Handelstag oder Daten noch nicht da.' % (heute, letzte))
        print(json.dumps(plan, ensure_ascii=False, indent=1)); return
    plan['handelstag'] = True

    def heute_idx(sym):
        rows = kurse.get(sym)
        if rows and rows[-1]['d'] == heute:
            return rows, len(rows) - 1
        return None, None

    # --- Konto zur Eröffnung: nur abgeschlossene Trades; gebunden = alles, was in den Tag hinein offen ist ---
    geschlossen = [t for t in trades if t.get('ausstieg') is not None]
    equity_auf = start + sum(pnl(t) for t in geschlossen)
    offen = [t for t in trades if t.get('ausstieg') is None]
    gebunden = sum(t['stueck'] * t['einstieg'] for t in offen)

    # --- 1. Bestehende Positionen prüfen ---
    for t in offen:
        if t.get('quelle') != 'claude':
            continue
        sym = t['ticker']; rows, i = heute_idx(sym)
        if rows is None:
            plan['fehlend'].append(sym); continue
        b = rows[i]; stop = t['stop']; linie = sma(rows, SMA_N, i)
        tage = sum(1 for r in rows if r['d'] > t['datum'])
        ex = None
        if b['o'] <= stop: ex = (b['o'], 'Stop (Eröffnung unter Stop)')
        elif b['l'] <= stop: ex = (stop, 'Stop')
        elif linie is not None and b['c'] >= linie: ex = (b['c'], 'Rückkehr zur 20-Tage-Linie')
        elif tage >= ZEITSTOPP: ex = (b['c'], 'Zeitstopp nach %d Handelstagen' % tage)
        if ex:
            t2 = dict(t, ausstieg=r4(ex[0]), datumAus=heute)
            plan['exits'].append({'id': t['id'], 'ticker': sym, 'ausstieg': r4(ex[0]), 'datumAus': heute,
                                  'grund': ex[1], 'pnl': r2(pnl(t2)),
                                  'r': r2(pnl(t2) / ((t['einstieg'] - t['stop']) * t['stueck']))})

    # --- 2. Wartende Signale zur Eröffnung ausführen (Kapital und Risiko nach Stand der Eröffnung) ---
    neu_offen = []
    for sg in signale:
        if (sg.get('datumSignal') or '') >= heute:
            continue  # Signal vom selben Tag: Kauf erst zur nächsten Eröffnung
        sym = sg['ticker']; rows, i = heute_idx(sym)
        if rows is None:
            plan['fehlend'].append(sym); continue
        b = rows[i]; e = b['o']; stop = e - STOP_ATR * float(sg['atr'])
        if stop <= 0:
            plan['cancels'].append({'id': sg['id'], 'ticker': sym, 'grund': 'Stop wäre nicht positiv'}); continue
        frei_geld = equity_auf - gebunden
        if frei_geld < MIN_FREI * equity_auf:
            plan['cancels'].append({'id': sg['id'], 'ticker': sym, 'grund': 'Kein freies Kapital (Summe der Positionen darf das Konto nicht übersteigen)'}); continue
        faktor = PANIK_FAKTOR if sg.get('panik') else 1.0
        risk_eur = equity_auf * risk_pct * faktor / 100
        qty = int(min(risk_eur / (e - stop), frei_geld / e) * 10000) / 10000   # abrunden, damit die Kapitalgrenze hält
        if qty <= 0:
            plan['cancels'].append({'id': sg['id'], 'ticker': sym, 'grund': 'Stückzahl null'}); continue
        gebunden += qty * e
        linie = sma(rows, SMA_N, i)
        tr = {'datum': heute, 'ticker': sym, 'setup': 'Gegenläufer: Überdehnung nach unten', 'system': 'B',
              'einstieg': r4(e), 'stop': r4(stop), 'stueck': qty, 'ziel': r4(linie) if linie else None,
              'ausstieg': None, 'datumAus': None, 'gebuehren': 0, 'regel': True, 'panik': bool(sg.get('panik')),
              'risikoPct': risk_pct * faktor, 'phase': s.get('phase', 'papier'), 'beispiel': False,
              'quelle': 'claude', 'notiz': sg.get('begruendung', '')}
        # Gleicher Tag: Stop erreicht? Sonst Schluss schon an der 20-Tage-Linie?
        if b['l'] <= stop: tr.update(ausstieg=r4(stop), datumAus=heute, notiz=tr['notiz'] + ' · Ausstieg: Stop am Einstiegstag')
        elif linie is not None and b['c'] >= linie: tr.update(ausstieg=r4(b['c']), datumAus=heute, notiz=tr['notiz'] + ' · Ausstieg: Rückkehr zur 20-Tage-Linie am Einstiegstag')
        else:
            tr.update(kursAktuell=r4(b['c']), kursDatum=heute)
            neu_offen.append(dict(tr, id='neu-' + sym))
        plan['fills'].append({'signal_id': sg['id'], 'trade_id': sg['id'].replace('sb-', 'tb-', 1), 'trade': tr})

    # --- 2b. Aktueller Stand offener Positionen (für die Ansicht im Depot) ---
    plan['positionen'] = []
    for t in offen:
        if any(x['id'] == t['id'] for x in plan['exits']):
            continue
        rows, i = heute_idx(t['ticker'])
        if rows is None:
            continue
        b = rows[i]; linie = sma(rows, SMA_N, i)
        risiko = (t['einstieg'] - t['stop']) * t['stueck']
        offen_pnl = (b['c'] - t['einstieg']) * t['stueck']
        plan['positionen'].append({'id': t['id'], 'ticker': t['ticker'], 'kursAktuell': r4(b['c']), 'kursDatum': heute,
                                   'ziel': r4(linie) if linie else None,
                                   'pnl_offen': r2(offen_pnl), 'r_offen': r2(offen_pnl / risiko) if risiko > 0 else None})

    # --- 3. Notbremsen (wie System A, auf dem eigenen Konto) ---
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
    wartend = [sg for sg in signale if not any(f['signal_id'] == sg['id'] for f in plan['fills'])
               and not any(c['id'] == sg['id'] for c in plan['cancels'])]
    bleibt_offen = [t for t in offen if not any(x['id'] == t['id'] for x in plan['exits'])] + neu_offen
    belegt = {t['ticker'] for t in bleibt_offen} | {sg['ticker'] for sg in wartend}
    frei = MAX_OFFEN - len(bleibt_offen) - len(wartend)
    kand, ueberdehnt = [], 0
    for sym, rows in kurse.items():
        i = len(rows) - 1
        if rows[i]['d'] != heute or i < MIN_BARS:
            continue
        c = rows[i]['c']; linie = sma(rows, SMA_N, i); a = atr(rows, ATR_N, i)
        if not a or a <= 0:
            continue
        dehn = (linie - c) / a
        if dehn < DEHNUNG:
            continue
        ueberdehnt += 1           # zählt für den Panik-Tag, auch wenn die Aktie schon belegt ist
        tiefer = sum(1 for k in range(TIEFER_FENSTER) if rows[i - k]['c'] < rows[i - k - 1]['c'])
        if tiefer < TIEFER_MIN or sym in belegt:
            continue
        kand.append({'ticker': sym, 'schluss': r4(c), 'sma20': r4(linie), 'atr': r4(a), 'dehnung_atr': r2(dehn),
                     'tiefer_von_4': tiefer, 'stop_vorlaeufig': r4(c - STOP_ATR * a),
                     'stop_abstand_pct': r2(100 * STOP_ATR * a / c)})
    panik = ueberdehnt >= PANIK_MIN
    kand.sort(key=lambda k: -k['dehnung_atr'])
    plan['kandidaten'] = kand
    plan['ueberdehnt'] = ueberdehnt
    plan['panik_tag'] = panik
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
        plan['neue_signale'].append({'id': 'sb-%s-%s' % (heute, sym), 'ticker': sym, 'system': 'B', 'atr': k['atr'],
            'stop': k['stop_vorlaeufig'], 'panik': panik, 'datumSignal': heute, 'status': 'wartet',
            'begruendung': 'Signal B %s: Schluss %.2f liegt %.1f ATR unter der 20-Tage-Linie (%.2f), %d der letzten 4 Tage tiefer.%s Stop = Einstieg − 2 ATR (ca. −%.1f %%).'
                           % (heute, k['schluss'], k['dehnung_atr'], k['sma20'], k['tiefer_von_4'],
                              ' Panik-Tag (%d Aktien überdehnt): doppeltes Risiko.' % ueberdehnt if panik else '',
                              k['stop_abstand_pct'])})
    print(json.dumps(plan, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
