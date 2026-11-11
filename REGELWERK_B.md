# Regelwerk B „Gegenläufer“ – Version B1

Eingefroren am 11.11.2026, vor dem ersten Test. Engine: `engine_b.py`.
Jede Änderung an Regeln oder Schwellen ist eine neue Version (B2, …) und zählt von null.

## Gegenthese

System A kauft Stärke nach Bestätigung im Aufwärtstrend. System B kauft Schwäche:
eine nach unten überdehnte Aktie, ohne Bestätigung, auch gegen den Trend.

## Regeln

**Universum:** dieselben 30 größten US-Aktien wie System A. Nur Kauf, kein Hebel, keine Optionen. Tageschart.

**Begriffe:** 20-Tage-Linie = Durchschnitt der letzten 20 Schlusskurse.
ATR = durchschnittliche Tagesschwankung der letzten 14 Tage (True Range, einfacher Mittelwert).

**Setup „Überdehnung nach unten“** (alle Bedingungen am Tagesschluss):
1. Schluss liegt mindestens 2,5 ATR unter der 20-Tage-Linie.
2. Mindestens 3 der letzten 4 Tage mit tieferem Schlusskurs als am Vortag.
3. Kein Trendfilter. Die Lage zur 200-Tage-Linie spielt keine Rolle.
4. Kauf zur Eröffnung des nächsten Handelstags, ohne Bestätigung.
5. Stop = Einstieg minus 2 ATR (ATR vom Signaltag). Der Stop wird nie verschoben.
6. Keine neuen Trades, wenn Quartalszahlen in den nächsten 7 Kalendertagen anstehen.
7. Mehr Signale als freie Plätze: die am stärksten überdehnte Aktie zuerst.

**Risiko:** 1 % des Kontostands pro Trade. Panik-Tag (mindestens 8 Aktien erfüllen
Bedingung 1 am selben Tag): 2 % für die Signale dieses Tages. Höchstens 3 offene
Positionen (wartende Orders zählen mit). Die Summe aller Positionen übersteigt nie
den Kontostand; bleibt weniger als 1 % des Kontos frei, verfällt das Signal.

**Ausstieg:** Verkauf zum Schlusskurs, sobald der Schluss an oder über der 20-Tage-Linie
liegt. Zeitstopp nach 10 Handelstagen zum Schlusskurs. Stop wie oben; eröffnet der Kurs
unter dem Stop, zählt der Eröffnungskurs. Trifft ein Tag Stop und Linie, zählt der Stop.

**Notbremsen:** wie System A, auf dem eigenen Konto. 3 Verluste in Folge → 5 Handelstage
Pause. −10 % vom Höchststand → keine neuen Trades bis zum Review. −20 % → Regelwerk überarbeiten.

## Unabhängigkeit

- Eigenes Papierkonto mit 500 €, eigene Kontokurve, eigene Notbremsen.
- Eigene Engine. Sie bekommt nur die Trades und Signale von System B zu sehen;
  System A sieht die von B nicht. Beide dürfen dieselbe Aktie gleichzeitig halten.
- Gleiche Kursdaten, gleiche Gebühr, Vergleich ab demselben Starttag.
- Kein Ermessen: entschieden wird nur nach `engine_b.py`.

## Hypothese und Test (vorab festgelegt)

**Hypothese:** Das Setup hat nach Gebühren einen positiven Erwartungswert.

**Schritt 1 – ein einziger Rückblick.**
`research/tools/backtest.py` mit `engine_b.py`, Zeitraum 2006-01-03 bis 2026-11-10,
Universum je Jahr aus `research/top30_history.json` (die damals größten 30, nicht die heutigen),
Quartalstermine aus `research/earnings`, Kapital 500 €, Risiko 1 %, Gebühr 1 € je Order
(Kontoeinstellung vom 11.11.2026).

Bestanden, wenn beides gilt:
- Erwartungswert je Trade über 0 R nach Gebühren,
- maximaler Drawdown höchstens 25 %.

Nicht bestanden: System B wird nicht gebaut. Kein Nachjustieren der Schwellen an diesem Test.

Zur Einordnung, ohne Einfluss auf das Urteil: derselbe Lauf ohne Gebühren, System A im
selben Zeitraum, S&P 500 mit Dividenden.

**Schritt 2 – Schattenlauf neben System A** (nur nach bestandenem Schritt 1).
Probezeit: 40 abgeschlossene Trades oder 9 Monate, je nachdem, was zuerst eintritt.
Wertung am Ende: dieselben sechs Freigabe-Kriterien wie bei System A, dazu der Vergleich
mit Kaufen und Halten eines S&P-500-ETF nach Kosten.

Nur für den privaten Gebrauch. Keine Anlageberatung.

## Ergebnis Schritt 1 (11.11.2026): nicht bestanden

Engine `engine_b.py`, SHA-256 `514c9089e0e721095d35d00739d655a300e928fe3c67987015ad8862aa5672a8`,
Commit `0332d1b` (vor dem Test). Ein Lauf, keine Wiederholung mit anderen Schwellen.

| Lauf | Trades | Trefferquote | Erwartungswert | Max. Drawdown | Rendite p. a. |
|---|---|---|---|---|---|
| **B1 mit 1 € je Order (Urteil)** | 233 | 18,5 % | −2,38 R | 100 % (Konto im Dez. 2013 aufgebraucht) | – |
| B1 ohne Gebühren (Einordnung) | 878 | 49,4 % | +0,024 R | 30,2 % | 0,9 % |
| System A ohne Gebühren (Einordnung) | 1150 | 45,3 % | +0,04 R | 28,1 % | 1,8 % |
| S&P 500 mit Dividenden halten | – | – | – | 55,3 % | 11,0 % |

- Beide Schwellen verfehlt (Erwartungswert über 0 R, Drawdown höchstens 25 %).
- Im Gebührenlauf: 466 € Gebühren gegenüber −35 € Kursergebnis. Bei 500 € Konto und 1 % Risiko
  kosten Kauf und Verkauf zusammen 0,4 R je Trade, mit schrumpfendem Konto immer mehr.
- Auch ohne Gebühren liegt der Drawdown über der Grenze und der Vorteil ist praktisch null.
- System A mit 1 € je Order wird im selben Zeitraum ebenfalls von den Gebühren aufgezehrt.
- Alle 878 Trades des gebührenfreien Laufs wurden unabhängig aus den Rohkursen nachgerechnet, ohne Abweichung.

Folge laut Vorab-Festlegung: System B Version B1 wird nicht gebaut. Kein Schattenlauf.

Beobachtung, kein Ergebnis: Die 39 Panik-Tag-Trades lagen ohne Gebühren bei +0,16 R, die übrigen 839 bei +0,02 R.
39 Trades sind zu wenig für einen Schluss. Das wäre eine neue Hypothese (B2) mit eigener Vorab-Festlegung.
