# Courier: Kundenauftrag bis zum nachgewiesenen Ergebnis

Datum: 2026-09-24
Typ: unabhängiger Review- und Übergabebeleg, keine Laufzeitautorität
Geprüfter Git-Stand: `14f1dbfe2171b64f2a017eae493ee1229b716f13`
Geprüfte Datei: `server/app.py`
SHA256: `0fcf1a827969688160f2054f6aceabab48e83ed9199e10f41f0607dcdf293cd4`

## Kundenauftrag und Produktbotschaft

Der aktuelle Nutzerauftrag konkretisiert den bestehenden Goal-only-Ansatz:
Ein Kunde beschreibt ein Ergebnis; Courier koordiniert die nötigen Schritte,
prüft Ergebnisse, setzt nach Unterbrechungen fort und betreut das Ergebnis
im vereinbarten Umfang weiter. Ein beendeter Chat ist kein Abnahmenachweis.

Vorgeschlagene Botschaft, ausdrücklich als Produktziel:
**„Beschreibe dein Ziel. Courier arbeitet weiter — bis das Ergebnis geprüft ist.“**

Die Pizza-Anwendung ist das vom Nutzer genannte Beispiel, keine erteilte
Erlaubnis für eine Veröffentlichung, Zahlungsabwicklung oder echte Bestellung.
Ein aussagekräftiger späterer Pilot umfasst einen nachvollziehbaren Weg von
Bestellung über bestätigte Zahlung bis zur Übergabe an Küche/Lieferdienst.
Die tatsächliche Auslieferung benötigt einen ausführenden Betrieb oder
Lieferpartner. PayPal-Zugang und Händlerkonto gehören dem berechtigten Kunden.
Zahlungstests beginnen in einer Testumgebung. Beträge, Erstattungen und
Veröffentlichungen bleiben an die jeweils erteilte Berechtigung gebunden.
Fortlaufende Betreuung benötigt vereinbarte Aufgaben, Budget und Prüfungen;
sie bedeutet keine unbegrenzten, kostenfreien Änderungen.

## OBSERVED: reproduzierbare Abschlussfehler

Die vorhandene Funktion `approve_merge` wurde direkt aus dem aktuellen
Python-Syntaxbaum geladen und ohne Dekoratoren mit ausschließlich flüchtigen
Testdaten ausgeführt. Keine Serverimporte, kein Netzwerk, keine Provider,
keine echten Freigaben und keine Schreibzugriffe auf Laufzeitdaten.
Dies ist ein isolierter Funktionsnachweis, kein vollständiger Live-API-Test.

1. Ein Goal mit `terminal=False` und einem letzten freigegebenen Schritt wird
   zu `DONE`. Erwartet ist fortgesetzte nichtterminale Bearbeitung bzw. ein
   ausdrücklich ausgewiesener Warte-/Blockerzustand, nicht `DONE`.
2. Ein terminales Goal mit einem bereits regulär abgeglichenen Schritt und
   einem letzten zur Freigabe stehenden Schritt bleibt `ACTIVE`, obwohl danach
   alle Schritte `RECONCILED` sind. Der Zähler `current_step_index` bildet den
   tatsächlichen Abschluss des gemischten Ablaufs nicht ab.

Ergebnis: zwei fehlgeschlagene Abschlussinvarianten gegen die angegebenen
Quellbytes. Nicht behauptet wird, dass einer dieser Fälle den gerade laufenden
Auftrag verursacht hat.

## OBSERVED: aktuelle Integrationsgrenze

Der gelesene Handoff-Eintrag passt zum Git-Stand und nennt
`ACTIVE_WRITERS=[Google-Antigravity]`,
`COLLISION_SCOPE=[Ledger, motor-eligibility-v1]` sowie
`FIRST_CAUSAL_BLOCKER=TIMEOUT_HUNG_TASK`.
Die Ownership-Datei weist Google außerdem den Integrations-/Laufzeitbereich zu.
Der Checkout enthält fremde Änderungen und aktive Laufzeitdaten.
Die lokale Zustandsaufnahme zeigte ein aktives Goal mit je einer Aufgabe in
`WAITING_PROVIDER`, `DISPATCHED` und `RECONCILED`.
Diese Daten sind eine Momentaufnahme und kein Beleg für einen sicheren Stopp.

## Reparaturauftrag für den zuständigen Integrationswriter

Nach bestätigter Übergabe oder durch den bestehenden Writer:

- Die Abschlussentscheidung nach regulärer Verifikation und nach expliziter
  Merge-Freigabe auf dieselbe bestehende Goal-Semantik bringen.
- Erst den freigegebenen Schritt synchronisieren, dann sämtliche tatsächlichen
  Schrittzustände prüfen. Nicht allein den Schrittzähler verwenden.
- `terminal=False` auch nach einer Merge-Freigabe respektieren und über den
  bestehenden Fortsetzungspfad weiterführen; keine zweite Laufzeitautorität.
- Offene, ausgeführte oder wartende Schritte dürfen keinen falschen Abschluss
  und keine doppelte Ausführung auslösen.
- Genau diese beiden Fälle sowie die bestehenden Freigabe-/Fortsetzungstests
  isoliert prüfen. Tests dürfen keine produktive Zustandsdatei löschen.
- Danach den im Release-Checkpoint geforderten echten Betriebsnachweis
  durchführen. Dieser Review ersetzt ihn nicht.

Eine zusätzliche beobachtete Testgefahr: Der bestehende Test
`tests/test_auto_replenishment.py` löscht in seiner Vorbereitung eine feste
Zustandsdatei unter `~/.courier_runtime`. Er wurde deshalb nicht ausgeführt.

## Stand dieser Übergabe

Produktionscode geändert: nein.
Live-API-Aufträge/Freigaben: keine.
Provider-Aufrufe, neue Worker, Zahlungen, Veröffentlichungen: keine.
Vollständige Produktabnahme: offen.
Integration der Reparatur: offen, Writer-Zuordnung zuerst bestätigen.
Neue Spezifikation oder alternative Architektur: keine.
