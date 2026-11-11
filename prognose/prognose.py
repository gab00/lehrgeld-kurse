#!/usr/bin/env python3
"""Prognose-Journal, Protokoll P1: Kursblatt, Prüfung und Abrechnung. Rechnet nur, urteilt nicht frei.

  python3 -I prognose.py blatt   DATA_DIR HEUTE [EARNINGS.json]
  python3 -I prognose.py pruefen ENTWURF.json DATA_DIR HEUTE STATE.json
  python3 -I prognose.py werten  STATE.json DATA_DIR

DATA_DIR  <SYMBOL>.csv (timestamp,open,high,low,close,volume; neueste Zeile zuerst)
HEUTE     der ausgewertete US-Handelstag JJJJ-MM-TT (Schlusskurs liegt vor)
STATE     {"heute": HEUTE, "prognosen": [<Dokumente aus prognosen>], "wertungen": [<vorhandene Datumswerte>]}
ENTWURF   {"datum": HEUTE, "markt": "…", "werte": {"AAPL": {"p": 57, "grund": "…"}, …}}

Prognose je Aktie: Wahrscheinlichkeit p (ganze Prozent, 5–95), dass der Schlusskurs 5 Handelstage
nach HEUTE HÖHER liegt als der Schlusskurs von HEUTE. Gleichstand zählt als nicht gestiegen.
Fehlerpunkte = Mittel von (p − Ergebnis)², Ergebnis 1 = gestiegen, 0 = nicht. Niedriger ist besser.
Maßstäbe: Münzwurf (immer 50 %, also 0,25) und feste Quote (immer der tatsächliche Anteil gestiegener
Fälle im selben Zeitraum, der beste Wert, den eine einzige feste Zahl erreichen kann).
"""
import csv, json, math, os, sys
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

VERSION = 'P1'
UNIVERSUM = ("NVDA AAPL GOOGL MSFT AMZN AVGO META TSLA LLY MU JPM WMT AMD V XOM JNJ MA INTC ABBV CSCO "
             "BAC AMAT COST CAT CVX UNH LRCX GE KO PG").split()
HORIZONT = 5            # Handelstage
P_MIN, P_MAX = 5, 95    # erlaubte Wahrscheinlichkeiten in Prozent
PROBEZEIT = 60          # Prognosetage
MIN_JE_TAG = 20         # so viele Ergebnisse braucht ein Tag, um zu zählen
T_SCHWELLE = 2.0        # Vorsprung gegen die feste Quote, in Wochenblöcken
MIN_WOCHEN = 10
GRUND_MAX, MARKT_MAX = 160, 400
NY = ZoneInfo('America/New_York')
BEREICHE = [(5, 39, 'unter 40 %'), (40, 49, '40–49 %'), (50, 50, 'genau 50 %'), (51, 60, '51–60 %'),
            (61, 70, '61–70 %'), (71, 95, 'über 70 %')]


def lade(data_dir):
    kurse = {}
    for sym in UNIVERSUM:
        pfad = os.path.join(data_dir, sym + '.csv')
        if not os.path.exists(pfad):
            continue
        rows = []
        with open(pfad, newline='') as f:
            for r in csv.DictReader(f):
                try:
                    rows.append({'d': r['timestamp'].strip(), 'o': float(r['open']), 'h': float(r['high']),
                                 'l': float(r['low']), 'c': float(r['close']), 'v': float(r.get('volume') or 0)})
                except (KeyError, ValueError):
                    continue
        rows.sort(key=lambda x: x['d'])
        if rows:
            kurse[sym] = rows
    return kurse


def pct(a, b):
    return round((a / b - 1) * 100, 2) if b else None


def blatt(data_dir, heute, earnings_pfad=None):
    kurse = lade(data_dir)
    termine = {}
    if earnings_pfad and os.path.exists(earnings_pfad):
        try:
            termine = json.load(open(earnings_pfad)).get('termine', {})
        except (ValueError, AttributeError):
            termine = {}
    d0 = date.fromisoformat(heute)
    aktien, fehlend = {}, []
    for sym in UNIVERSUM:
        rows = kurse.get(sym)
        if not rows or rows[-1]['d'] != heute or len(rows) < 61:
            fehlend.append(sym); continue
        i = len(rows) - 1; c = rows[i]['c']
        def schnitt(n):
            return sum(r['c'] for r in rows[i - n + 1:i + 1]) / n if i + 1 >= n else None
        tr = [max(rows[j]['h'] - rows[j]['l'], abs(rows[j]['h'] - rows[j - 1]['c']), abs(rows[j]['l'] - rows[j - 1]['c']))
              for j in range(i - 13, i + 1)]
        jahr = rows[max(0, i - 251):i + 1]
        hoch, tief = max(r['h'] for r in jahr), min(r['l'] for r in jahr)
        vol20 = sum(r['v'] for r in rows[i - 20:i]) / 20
        steigt5 = [rows[j + 5]['c'] > rows[j]['c'] for j in range(max(0, i - 124), i - 4)]
        e = termine.get(sym)
        zeile = {'schluss': round(c, 2), 'tag_pct': pct(c, rows[i - 1]['c']), 'woche_pct': pct(c, rows[i - 5]['c']),
                 'monat_pct': pct(c, rows[i - 20]['c']), 'quartal_pct': pct(c, rows[i - 60]['c']),
                 'zu_20_tage_linie_pct': pct(c, schnitt(20)), 'zu_50_tage_linie_pct': pct(c, schnitt(50)),
                 'zu_200_tage_linie_pct': pct(c, schnitt(200)) if schnitt(200) else None,
                 'tagesschwankung_pct': round(100 * sum(tr) / 14 / c, 2),
                 'lage_im_jahresband_pct': round(100 * (c - tief) / (hoch - tief), 0) if hoch > tief else None,
                 'umsatz_zu_schnitt': round(rows[i]['v'] / vol20, 2) if vol20 else None,
                 'stieg_in_5_tagen_letzte_120_pct': round(100 * sum(steigt5) / len(steigt5), 0) if steigt5 else None,
                 'quartalszahlen': e,
                 'quartalszahlen_in_tagen': (date.fromisoformat(e) - d0).days if e else None}
        aktien[sym] = zeile
    w = [a['tag_pct'] for a in aktien.values() if a['tag_pct'] is not None]
    return {'heute': heute, 'horizont_handelstage': HORIZONT, 'aktien': aktien, 'fehlend': fehlend,
            'markt': {'aktien_im_plus_heute': sum(x > 0 for x in w), 'von': len(w),
                      'mittel_tag_pct': round(sum(w) / len(w), 2) if w else None,
                      'mittel_woche_pct': round(sum(a['woche_pct'] for a in aktien.values()) / len(aktien), 2) if aktien else None,
                      'ueber_50_tage_linie': sum((a['zu_50_tage_linie_pct'] or 0) > 0 for a in aktien.values())}}


def frist(heute):
    """Spätester Zeitpunkt für die Prognose: 09:25 New Yorker Zeit am nächsten Werktag nach HEUTE."""
    d = date.fromisoformat(heute) + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return datetime.combine(d, time(9, 25), NY)


def jetzt():
    t = os.environ.get('PROGNOSE_JETZT')        # nur für Tests
    return datetime.fromisoformat(t) if t else datetime.now(timezone.utc)


def pruefen(entwurf_pfad, data_dir, heute, state_pfad):
    ent = json.load(open(entwurf_pfad)); st = json.load(open(state_pfad))
    kurse = lade(data_dir); fehler = []
    da = [s for s in UNIVERSUM if s in kurse and kurse[s][-1]['d'] == heute]
    now = jetzt()
    schluss = datetime.combine(date.fromisoformat(heute), time(16, 5), NY)
    if ent.get('datum') != heute: fehler.append('datum ist nicht HEUTE')
    if now <= schluss: fehler.append('zu früh: der Handelstag ist noch nicht abgeschlossen')
    if now >= frist(heute): fehler.append('zu spät: nach 09:25 New Yorker Zeit am nächsten Werktag gibt es keine Prognose mehr')
    tage = {p.get('datum') for p in st.get('prognosen', [])}
    if heute in tage: fehler.append('für HEUTE gibt es schon Prognosen; sie werden nie überschrieben')
    if len(tage - {heute}) >= PROBEZEIT: fehler.append('Probezeit: alle %d Prognosetage sind abgegeben' % PROBEZEIT)
    if len(da) < MIN_JE_TAG: fehler.append('zu wenige Aktien mit Schlusskurs von HEUTE (%d)' % len(da))
    werte = ent.get('werte') or {}
    for s in da:
        if s not in werte: fehler.append('%s fehlt' % s)
    aus = {}
    for s, w in werte.items():
        if s not in da:
            fehler.append('%s: kein Schlusskurs von HEUTE oder nicht im Universum' % s); continue
        p = w.get('p') if isinstance(w, dict) else None
        if isinstance(p, bool) or not isinstance(p, int) or not (P_MIN <= p <= P_MAX):
            fehler.append('%s: p muss eine ganze Zahl von %d bis %d sein' % (s, P_MIN, P_MAX)); continue
        g = (w.get('grund') or '').strip()
        if not g or len(g) > GRUND_MAX:
            fehler.append('%s: grund fehlt oder ist länger als %d Zeichen' % (s, GRUND_MAX)); continue
        aus[s] = {'p': p, 'schluss': round(kurse[s][-1]['c'], 4), 'grund': g}
    markt = (ent.get('markt') or '').strip()
    if not markt or len(markt) > MARKT_MAX: fehler.append('markt fehlt oder ist länger als %d Zeichen' % MARKT_MAX)
    if fehler:
        print(json.dumps({'ok': False, 'fehler': fehler}, ensure_ascii=False, indent=1)); sys.exit(1)
    print(json.dumps({'ok': True, 'dokument': {
        'datum': heute, 'version': VERSION, 'erstellt': now.astimezone(timezone.utc).isoformat(timespec='seconds'),
        'frist': frist(heute).astimezone(timezone.utc).isoformat(timespec='seconds'), 'horizont': HORIZONT,
        'markt': markt, 'werte': aus, 'fehlend': [s for s in UNIVERSUM if s not in da]}}, ensure_ascii=False, indent=1))


def r4(x): return round(x, 4)


def kennzahlen(faelle):
    """faelle: Liste (datum, sym, p in 0..1, y in 0/1). Liefert die Zahlen eines Zeitraums."""
    n = len(faelle)
    if not n:
        return None
    q = sum(y for *_, y in faelle) / n
    brier = sum((p - y) ** 2 for _, _, p, y in faelle) / n
    ri = [(p, y) for _, _, p, y in faelle if p != 0.5]
    wochen = {}
    for d, _, p, y in faelle:
        iso = date.fromisoformat(d).isocalendar()
        wochen.setdefault('%d-W%02d' % (iso[0], iso[1]), []).append((p, y))
    wl, roh = [], {'vorsprung_feste_quote': [], 'vorsprung_muenzwurf': []}
    for k in sorted(wochen):
        f = wochen[k]
        mein = sum((p - y) ** 2 for p, y in f) / len(f)
        vq, vm = sum((q - y) ** 2 for _, y in f) / len(f) - mein, 0.25 - mein
        roh['vorsprung_feste_quote'].append(vq); roh['vorsprung_muenzwurf'].append(vm)
        wl.append({'woche': k, 'n': len(f), 'fehlerpunkte': r4(mein),
                   'vorsprung_feste_quote': r4(vq), 'vorsprung_muenzwurf': r4(vm)})
    def t_wert(key):
        x = roh[key]            # ungerundete Wochenwerte
        if len(x) < 2: return None
        m = sum(x) / len(x); sd = math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))
        return round(m / (sd / math.sqrt(len(x))), 2) if sd > 0 else None
    kal = []
    for lo, hi, name in BEREICHE:
        f = [(p, y) for _, _, p, y in faelle if lo <= round(p * 100) <= hi]
        if f:
            kal.append({'bereich': name, 'n': len(f), 'gesagt_pct': round(100 * sum(p for p, _ in f) / len(f), 1),
                        'gestiegen_pct': round(100 * sum(y for _, y in f) / len(f), 1)})
    return {'n': n, 'fehlerpunkte': r4(brier), 'muenzwurf': 0.25, 'feste_quote': r4(q * (1 - q)),
            'anteil_gestiegen_pct': round(100 * q, 1),
            'vorsprung_muenzwurf': r4(0.25 - brier), 'vorsprung_feste_quote': r4(q * (1 - q) - brier),
            'treffer_pct': round(100 * sum((p > 0.5) == (y == 1) for p, y in ri) / len(ri), 1) if ri else None,
            'n_mit_richtung': len(ri), 'immer_steigt_treffer_pct': round(100 * q, 1),
            'wochen': wl, 't_feste_quote': t_wert('vorsprung_feste_quote'), 't_muenzwurf': t_wert('vorsprung_muenzwurf'),
            'kalibrierung': kal}


def werten(state_pfad, data_dir):
    st = json.load(open(state_pfad)); heute = st['heute']
    kurse = lade(data_dir)
    idx = {s: {r['d']: k for k, r in enumerate(rows)} for s, rows in kurse.items()}
    vorhanden = set(st.get('wertungen', []))
    prognosen = sorted((p for p in st.get('prognosen', []) if p.get('datum')), key=lambda p: p['datum'])[:PROBEZEIT]
    faelle, tage, neue, offen = [], [], {}, []
    for pr in prognosen:
        d = pr['datum']; erg = {}; faellig = None
        for s, w in (pr.get('werte') or {}).items():
            rows = kurse.get(s); i = idx.get(s, {}).get(d)
            if rows is None or i is None or i + HORIZONT >= len(rows) or rows[i + HORIZONT]['d'] > heute:
                continue
            c0, c5 = rows[i]['c'], rows[i + HORIZONT]['c']
            faellig = max(faellig or '', rows[i + HORIZONT]['d'])
            erg[s] = {'p': w['p'], 'schluss0': round(c0, 4), 'schluss5': round(c5, 4), 'gestiegen': c5 > c0}
        if len(erg) < MIN_JE_TAG:
            offen.append(d); continue
        f = [(d, s, e['p'] / 100, 1 if e['gestiegen'] else 0) for s, e in erg.items()]
        faelle += f
        up = sum(y for *_, y in f); q = up / len(f)
        mein = sum((p - y) ** 2 for _, _, p, y in f) / len(f)
        tag = {'datum': d, 'faellig': faellig, 'n': len(f), 'gestiegen': up, 'fehlerpunkte': r4(mein),
               'mittel_p': round(100 * sum(p for _, _, p, _ in f) / len(f), 1),
               'treffer': sum((p > 0.5) == (y == 1) for _, _, p, y in f if p != 0.5),
               'n_mit_richtung': sum(1 for _, _, p, _ in f if p != 0.5)}
        tage.append(tag)
        if d not in vorhanden:
            neue[d] = dict(tag, version=VERSION, ergebnisse=erg)
    k = kennzahlen(faelle)
    je = {}
    for d, s, p, y in faelle:
        a = je.setdefault(s, {'n': 0, 'gestiegen': 0, 'sp': 0.0, 'fp': 0.0})
        a['n'] += 1; a['gestiegen'] += y; a['sp'] += p; a['fp'] += (p - y) ** 2
    je_aktie = {s: {'n': a['n'], 'gestiegen': a['gestiegen'], 'mittel_p': round(100 * a['sp'] / a['n'], 1),
                    'fehlerpunkte': r4(a['fp'] / a['n'])} for s, a in sorted(je.items())}
    urteil, gruende = None, []
    if len(tage) >= PROBEZEIT and k:
        gruende = [
            ('besser als Münzwurf' if k['fehlerpunkte'] < 0.25 else 'nicht besser als Münzwurf')
            + ' (%.4f gegen 0,2500)' % k['fehlerpunkte'],
            ('besser als feste Quote' if k['fehlerpunkte'] < k['feste_quote'] else 'nicht besser als feste Quote')
            + ' (%.4f gegen %.4f)' % (k['fehlerpunkte'], k['feste_quote']),
            'Vorsprung in Wochenblöcken: t = %s bei %d Wochen (nötig: mindestens %.1f bei mindestens %d Wochen)'
            % (k['t_feste_quote'], len(k['wochen']), T_SCHWELLE, MIN_WOCHEN)]
        ok = (k['fehlerpunkte'] < 0.25 and k['fehlerpunkte'] < k['feste_quote'] and len(k['wochen']) >= MIN_WOCHEN
              and k['t_feste_quote'] is not None and k['t_feste_quote'] >= T_SCHWELLE)
        urteil = 'bestanden' if ok else 'nicht bestanden'
    stand = {'version': VERSION, 'bis': heute, 'tage': tage, 'je_aktie': je_aktie,
             'probezeit': {'noetig': PROBEZEIT, 'tage_abgegeben': len(prognosen), 'tage_gewertet': len(tage),
                           'noch_offen': offen, 'urteil': urteil, 'gruende': gruende,
                           'prognosen_beendet': len(prognosen) >= PROBEZEIT}}
    stand.update(k or {'n': 0})
    print(json.dumps({'neue_wertungen': neue, 'stand': stand}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    befehl = sys.argv[1] if len(sys.argv) > 1 else ''
    if befehl == 'blatt':
        print(json.dumps(blatt(*sys.argv[2:5]), ensure_ascii=False, indent=1))
    elif befehl == 'pruefen':
        pruefen(*sys.argv[2:6])
    elif befehl == 'werten':
        werten(*sys.argv[2:4])
    else:
        print(__doc__); sys.exit(2)
