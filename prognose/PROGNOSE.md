# Prognose-Journal – Protokoll P1

Eingefroren am 11.11.2026, vor der ersten Prognose. Rechnung: `prognose/prognose.py`.
Jede Änderung an Frage, Maßstäben oder Schwelle ist ein neues Protokoll (P2, …) und zählt von null.

## Frage

Kann Claude besser als feste Maßstäbe vorhersagen, ob eine Aktie in fünf Handelstagen höher steht?
Regeln lassen sich an der Vergangenheit prüfen, Claudes Urteil nicht, weil das Sprachmodell die
Vergangenheit kennt. Deshalb zählt hier nur, was ab heute vorhergesagt und danach abgerechnet wird.

## Ablauf

- **Jeden Morgen nach einem US-Handelstag:** für jede der 30 Aktien des Universums eine
  Wahrscheinlichkeit in ganzen Prozent (5 bis 95), dass der Schlusskurs fünf Handelstage später
  höher liegt als der Schlusskurs dieses Tages. Dazu ein Satz Begründung.
- **Erlaubte Grundlage:** Kurse bis zum Schluss dieses Tages, Termine der Quartalszahlen,
  eine begrenzte Websuche nach Nachrichten, die eigene bisherige Abrechnung und die Lernnotizen.
- **Frist:** gespeichert nach Börsenschluss und vor 09:25 New Yorker Zeit am nächsten Werktag.
  Später gibt es für diesen Tag keine Prognose. Gespeicherte Prognosen werden nie geändert.
- **Abrechnung:** nach fünf Handelstagen automatisch aus den Schlusskursen. Gleichstand zählt als
  nicht gestiegen. Beide Kurse kommen aus derselben Kursdatei, damit ein Aktiensplit nichts verfälscht.

## Messung

Fehlerpunkte = Mittelwert von (Wahrscheinlichkeit − Ergebnis)², Ergebnis 1 für gestiegen, 0 für nicht.
Niedriger ist besser. 0 wäre Hellsehen, 0,25 ist Münzwurf.

Zwei Maßstäbe:
1. **Münzwurf:** immer 50 %.
2. **Feste Quote:** immer dieselbe Zahl, nämlich der tatsächliche Anteil gestiegener Fälle im
   Zeitraum. Das ist der beste Wert, den eine einzige feste Zahl erreichen kann, und damit strenger
   als „steigt immer“.

Zur Anschauung zusätzlich die Trefferquote der Richtung gegen „steigt immer“. Sie entscheidet nicht.

## Probezeit und Urteil

60 Prognosetage, das sind rund 1.800 Prognosen. Danach gibt es keine neuen Prognosen mehr.

Bestanden, wenn alles gilt:
- Fehlerpunkte niedriger als beim Münzwurf,
- Fehlerpunkte niedriger als bei der festen Quote,
- der Vorsprung gegenüber der festen Quote hält in Wochenblöcken: t-Wert mindestens 2,0 bei
  mindestens 10 Wochen. Wochenblöcke, weil sich die 30 Aktien oft gemeinsam bewegen und ein guter
  Markttag sonst wie 30 einzelne Treffer aussähe.

Nicht bestanden: Aus Claudes Prognosen wird keine Handelsregel gebaut.
Bestanden: Eine Handelsregel darauf wird als eigene Hypothese mit eigener Vorab-Festlegung geprüft,
auf Papier und nach Gebühren.

## Lernen

- Vor jeder Prognose liest Claude die eigene Abrechnung: wie oft es bei welcher genannten
  Wahrscheinlichkeit tatsächlich gestiegen ist, und die Zahlen je Aktie.
- Einmal pro Woche hält Claude eine kurze Lernnotiz fest. Notizen werden nicht gelöscht.
- Gelernt wird nur nach vorn. Vergangene Prognosen und dieses Protokoll bleiben unverändert.

## Grenzen

- Prognosen überlappen sich (jeden Tag fünf Tage voraus). Die Wochenblöcke fangen das nur zum Teil ab.
- Drei Monate sind ein Marktabschnitt. Ein Ergebnis gilt für diesen Abschnitt, nicht für immer.
- Kein Geld, keine Orders, kein Broker.

Nur für den privaten Gebrauch. Keine Anlageberatung.
