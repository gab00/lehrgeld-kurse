# lehrgeld-kurse

Tageskurse für das Papier-Trading-System „Lehrgeld-Labor“.

Ein GitHub-Actions-Ablauf holt Montag bis Freitag nach US-Börsenschluss die Tageskurse der 30 größten US-Aktien von Yahoo Finance (über die inoffizielle Bibliothek yfinance) und legt sie hier ab:

- `data/<SYMBOL>.csv`: rund 15 Monate Tageskurse, `timestamp,open,high,low,close,volume`, neueste Zeile zuerst. Split-bereinigt, nicht dividendenbereinigt.
- `data/_status.json`: Zeitpunkt des Abrufs, letzter Handelstag, fehlende Aktien.

Die tägliche Auswertung liest diese Dateien. Fällt Yahoo aus, nutzt sie Alpha Vantage als Absicherung.

Von Hand starten: Reiter **Actions** → **Tageskurse holen** → **Run workflow**.

Nur für den privaten Gebrauch. Keine Anlageberatung.
