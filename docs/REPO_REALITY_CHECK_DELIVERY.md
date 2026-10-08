# Repo Reality Check: manuelle Lieferung

Der Repo Reality Check beta kostet 5 EUR. Solange keine Zahlungsschnittstelle
angeschlossen ist, führt eine Person die Schritte unten von Hand aus.

Aufträge liegen im lokalen Courier-Zustand unter `reality-orders`, nicht im
Git-Repository. `--data-dir` oder die Umgebungsvariable `COURIER_ORDERS_DIR`
wählen ein anderes Verzeichnis. Ein Verzeichnis innerhalb einer
Git-Arbeitskopie wird abgelehnt.

Die Kontaktadresse der Bestellung wird nur als gesalzener Hash gespeichert.
Der Bericht selbst wird nicht in das Auftragsbuch geschrieben, sondern nur
Prüfsumme und Dateigröße.

## Ablauf

1. Eine Bestellung kommt per E-Mail an die hinterlegte Bestelladresse. Die
   Nachricht nennt die öffentliche Repository-URL
   `https://github.com/owner/repo`. Andere Adressen werden nicht angenommen.

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
   steht.

   ```
   python -m courier_core.reality_orders confirm-payment AUFTRAGSNUMMER --evidence TRANSAKTIONSNUMMER
   ```

5. Auftrag als in Arbeit markieren.

   ```
   python -m courier_core.reality_orders start AUFTRAGSNUMMER
   ```

6. Das Repository lokal auschecken und den Bericht erzeugen. Der Befehl
   schreibt eine Markdown-Datei und gehört zum Berichtsgenerator:

   ```
   python -m courier_core.repo_reality_report PFAD_ZUM_CHECKOUT --out report.md
   ```

7. Den Bericht lesen, bevor er verschickt wird.

   - Keine Zugangsdaten, Token, Schlüssel oder Sitzungsdaten.
   - Keine personenbezogenen Daten, die für die Feststellung nicht nötig sind.
   - Nur Feststellungen aus dem Repository. Keine Vermutungen über Personen.

8. Den Bericht mit der Liefermail unten an die bestellende Person senden.

9. Lieferung eintragen. Gespeichert werden Prüfsumme und Größe der Datei,
   nicht der Dateiinhalt.

   ```
   python -m courier_core.reality_orders deliver AUFTRAGSNUMMER --report report.md
   ```

10. Stand der Einnahmen prüfen. Verifiziert ist nur gelieferte und nicht
    erstattete Arbeit. Bestätigte, noch nicht gelieferte Zahlungen stehen
    unter pending.

    ```
    python -m courier_core.reality_orders revenue
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
