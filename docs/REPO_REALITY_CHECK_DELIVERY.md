# Repo Reality Check: manuelle Lieferung

Der Repo Reality Check beta kostet 5 EUR. Solange keine Zahlungsschnittstelle
angeschlossen ist, führt eine Person die Schritte unten von Hand aus.

Aufträge liegen im lokalen Courier-Zustand unter `reality-orders`, nicht im
Git-Repository. `--data-dir` oder die Umgebungsvariable `COURIER_ORDERS_DIR`
wählen ein anderes Verzeichnis. Ein Verzeichnis innerhalb einer
Git-Arbeitskopie wird abgelehnt.

Die Kontaktadresse der Bestellung wird nur als gesalzener Hash gespeichert.
Der Bericht selbst wird nicht in das Auftragsbuch geschrieben. Vorgemerkt
werden Prüfsumme und Größe der Berichtsdatei, der Commit und die
Tarball-Prüfsumme.

## Ablauf

1. Eine Bestellung kommt per E-Mail an die hinterlegte Bestelladresse. Die
   Nachricht nennt die öffentliche Repository-URL
   `https://github.com/owner/repo`. Andere Adressen und ZIP-Dateien werden
   nicht angenommen; `new` lehnt sie mit einer Meldung auf Deutsch und
   Englisch ab.

2. Auftrag anlegen. Die gedruckte Auftragsnummer für die nächsten Schritte
   notieren.

   ```
   python -m courier_core.reality_orders new --repo https://github.com/owner/repo --contact KONTAKTADRESSE
   ```

   `KONTAKTADRESSE` ist die Adresse aus der Bestellmail. Sie wird nicht im
   Klartext gespeichert.

3. In PayPal oder Stripe prüfen, ob die Zahlung über 5 EUR sichtbar ist.
   Ohne diese sichtbare Zahlung nicht weiterarbeiten. Die Zahlung wird nie
   aus einem späteren Schritt abgeleitet.

4. Zahlung mit der Transaktionsnummer eintragen, so wie sie beim Anbieter
   steht: ohne Leerzeichen, höchstens 100 Zeichen. Der Anbieter wird nicht
   abgefragt.

   ```
   python -m courier_core.reality_orders confirm-payment AUFTRAGSNUMMER --evidence TRANSAKTIONSNUMMER
   ```

5. Bericht in einem Schritt erzeugen. Das geht nur nach bestätigter Zahlung.
   Der Auftrag wird als in Arbeit markiert. Der Bericht liegt danach unter
   `AUSGABE/AUFTRAGSNUMMER-report.md`. Er gilt noch nicht als geliefert.

   ```
   python -m courier_core.reality_orders fulfill AUFTRAGSNUMMER --out-dir AUSGABE
   ```

   Dabei wird der Bericht für die GitHub-URL mit
   `python -m courier_core.repo_reality_report` erzeugt. Ein zweiter Aufruf
   für denselben begonnenen Auftrag benutzt die vorhandene Datei und holt
   das Repository nicht erneut.

   Fehlt das Repository oder ist es nicht öffentlich, wird der Auftrag als
   fehlgeschlagen markiert. Die Ausgabe nennt den Pfad dieser Datei. Die
   Erstattungsmail steht unten.

6. Den Bericht lesen, bevor er verschickt wird.

   - Keine Zugangsdaten, Token, Schlüssel oder Sitzungsdaten.
   - Keine personenbezogenen Daten, die für die Feststellung nicht nötig sind.
   - Nur Feststellungen aus dem Repository. Keine Vermutungen über Personen.

7. Den Bericht mit der Liefermail unten an die bestellende Person senden.
   Das Programm verschickt keine Mail.

8. Erst nach dem Versand die Lieferung bestätigen.

   ```
   python -m courier_core.reality_orders deliver AUFTRAGSNUMMER --confirm-sent
   ```

9. Stand der Einnahmen prüfen. Verifiziert ist nur gelieferte und nicht
   erstattete Arbeit. Bestätigte, noch nicht gelieferte Zahlungen stehen
   unter pending.

    ```
    python -m courier_core.reality_orders revenue
    ```

## Probebestellung

Eine Probe ohne echte Zahlung wird mit `--test` angelegt. Sie läuft durch
dieselben Schritte, zählt aber nie als Einnahme. `list` markiert sie mit
`TEST`, `revenue` nennt sie in einer eigenen Zeile.

```
python -m courier_core.reality_orders new --test --repo https://github.com/owner/repo --contact KONTAKTADRESSE
```

Offene Aufträge anzeigen:

```
python -m courier_core.reality_orders list
```

## Wenn die Arbeit nicht geliefert wird

Vor dem Start, nach bestätigter Zahlung:

```
python -m courier_core.reality_orders fail AUFTRAGSNUMMER --reason KURZER_GRUND
```

Erstattung, nachdem die Zahlung bestätigt ist:

```
python -m courier_core.reality_orders refund AUFTRAGSNUMMER --reason KURZER_GRUND
```

Danach die Erstattungsmail senden. Die 5 EUR laufen über denselben Weg
zurück, PayPal oder Stripe. Eine erstattete Bestellung zählt nicht als
Einnahme.

## Liefermail

Betreff: Repo Reality Check für [Repository]

```
Guten Tag,

anbei der Bericht zum Repository [https://github.com/owner/repo].
Geprüft wurde der Stand, den Sie genannt haben. Der Bericht enthält
Feststellungen aus diesem Repository.

Bei Rückfragen antworten Sie auf diese Nachricht.
```

## Erstattungsmail

Betreff: Erstattung Repo Reality Check [Auftragsnummer]

```
Guten Tag,

die Zahlung über 5 EUR für den Repo Reality Check erstatten wir.
Die Erstattung läuft über denselben Zahlungsweg, PayPal oder Stripe.

Auftragsnummer: [Auftragsnummer]
```
