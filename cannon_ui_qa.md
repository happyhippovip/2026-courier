CANNON_UI_QA

1. Ist klar, was NORMAL bedeutet?
CURRENT: Bezeichnung "NORMAL".
RISK: Unklar, ob es sich auf Ausführungsgeschwindigkeit, Worker-Anzahl, Mock-Status oder Kosten bezieht.
MINIMAL_CHANGE: Umbenennen in "Standard (1 Worker seriell)" oder Tooltip mit exakter Definition ergänzen.

2. Ist "Aufgaben" verständlich?
CURRENT: Bezeichnung "Aufgaben".
RISK: Verwechslungsgefahr mit den übergeordneten "Zielen" (Goals) oder Projekten. Im System sind es spezifische Tasks.
MINIMAL_CHANGE: Umbenennen in "Arbeitsschritte (Tasks)" zur klaren Hierarchie-Abgrenzung.

3. Ist eindeutig, was "Lokalen Test starten" bedeutet?
CURRENT: Bezeichnung "Lokalen Test starten".
RISK: Nutzer könnten annehmen, dass Unittests laufen oder dass echte API-Calls vom lokalen Rechner durchgeführt werden (was Kosten/Effekte verursacht).
MINIMAL_CHANGE: Ändern in "Simulation starten (Offline/Mock-Worker)".

4. Kann ein Nutzer lokalen Test mit echter Provider-Ausführung verwechseln?
CURRENT: Status ist primär durch den Button-Text erkennbar.
RISK: Angst vor ungewollten Live-Side-Effects oder echten Provider-Kosten blockiert den Nutzer.
MINIMAL_CHANGE: Ein permanentes visuelles Badge "MOCK-MODUS: Keine echten Provider-Aufrufe" während des Tests einblenden.

5. Sind Pause, Fortsetzen und "Nach aktueller Aufgabe stoppen" semantisch eindeutig?
CURRENT: "Pause", "Fortsetzen" und "Nach aktueller Aufgabe stoppen" als separate Aktionen.
RISK: "Pause" suggeriert ein sofortiges Einfrieren des Prozesses (harter Interrupt), während Courier Tasks atomar beendet. Wenn beide "Soft Stops" sind, ist die Trennung verwirrend.
MINIMAL_CHANGE: "Pause" entfernen und durch einen eindeutigen "Pausieren (nach aktuellem Task)" Button ersetzen.

6. Sind Queue / Läuft / Wartet / Blockiert / Erledigt verständlich?
CURRENT: Die Status "Wartet" und "Blockiert".
RISK: Es ist unklar, worauf gewartet wird (Abhängigkeit, Human Gate, Provider) und warum blockiert ist (Fehler, Limit).
MINIMAL_CHANGE: Status dynamisch präzisieren: "Wartet (Abhängigkeit)" bzw. "Blockiert (Fehler/Gate)".

7. Wird sichtbar gesagt, dass lokaler Test != Live-Muse-/Ledger-Abnahme?
CURRENT: Keine explizite Warnung über den Ledger-Status der Simulation.
RISK: Ein Nutzer hält einen komplett grünen lokalen Test fälschlicherweise für eine offizielle Abnahme und committet unfertigen Code.
MINIMAL_CHANGE: Banner hinzufügen: "Lokale Simulation: Erzeugt keine autoritativen Ledger-Resultate."

8. Ist "Letztes Ergebnis" für Anfänger verständlich?
CURRENT: Bezeichnung "Letztes Ergebnis".
RISK: Anfänger wissen nicht, ob das Ziel-Ergebnis, der letzte Output eines Tasks oder ein Fehlercode gemeint ist.
MINIMAL_CHANGE: Umbenennen in "Details des letzten Schritts" oder "Output (Letzter Task)".

9. Gibt es technische Rohdaten, die standardmäßig besser eingeklappt wären?
CURRENT: UUIDs (goal_id, task_id), Hashes und rohe JSON-Payloads sind direkt sichtbar.
RISK: Information Overload und optische Unübersichtlichkeit für neue Nutzer.
MINIMAL_CHANGE: Technische IDs und Roh-JSON standardmäßig in einem `<details>`-Block ("Expertenansicht") verbergen und nur sprechende Namen anzeigen.

10. Welche maximal 5 UI-Änderungen verbessern Klarheit am stärksten?
CURRENT: Generische Bezeichnungen, hohe Informationsdichte und fehlende Warnbanner.
RISK: Kognitive Überlastung und mangelndes Vertrauen in die Sicherheit der lokalen Ausführung.
MINIMAL_CHANGE:
- 1. "Lokalen Test" eindeutig als "Simulation (Kostenlos/Mock)" labeln.
- 2. Banner: "Ersetzt keine Live-Ledger-Abnahme" permanent anzeigen.
- 3. "Aufgaben" zu "Arbeitsschritte (Tasks)" präzisieren.
- 4. "Pause" semantisch zu "Stopp nach aktuellem Task" zusammenlegen.
- 5. Rohdaten (JSON/UUIDs) standardmäßig hinter "Erweiterte Details" einklappen.
