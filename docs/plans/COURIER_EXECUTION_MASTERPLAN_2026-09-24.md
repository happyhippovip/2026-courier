# Courier Execution Masterplan (2026-09-24)

## 1. Geprüfter Ausgangsstand
- **Zugänge (OBSERVED):** Voller Lese-/Schreibzugriff auf den lokalen Mac-Workspace (`/Users/user/Downloads/2026-courier`). Kein direkter Schreibzugriff (Push) auf GitHub (origin) ohne Human-in-the-Loop Freigabe.
- **SHA-Status (OBSERVED):** 
  - `CANONICAL_HEAD_SHA`: `2fe697ef2b0fbf71a5ce679bc5874e1bc4afa1a5`
  - `ACTUAL_SERVING_RUNTIME_SHA`: `2fe697ef2b0fbf71a5ce679bc5874e1bc4afa1a5`
  - `REMOTE_HEAD_SHA`: `3e2fe24d6dc59d7613aec9d1099695f5520c4733`
- **Aktive Writer (OBSERVED):** `Google-Antigravity` (Mac). Windows-Agent arbeitet parallel (INFERRED aus User-Prompt).
- **Laufende Arbeit (OBSERVED):** P0, P1 und P2 wurden im Mac-Scope (Antigravity) lokal abgeschlossen (Bug in `approve_merge` behoben, Ledger erfolgreich validiert).
- **Widersprüchliche Angaben (OBSERVED):** Dieses Masterplan-Dokument wurde als "vorhanden" referenziert, existierte aber initial nicht unter dem angegebenen Pfad und wurde nun aus dem OPUS-Handoff-Dokument generiert.

## 2. Bewahrter bisheriger Plan und konkret ergänzte Anforderungen
Der grundlegende Plan aus `docs/OPUS_MASTERPLAN_HANDOFF_2026-09-24.md` bleibt erhalten.
**Ergänzte Anforderungen:** 
- Strikte Autonomie: Kein Standby bei fehlendem GitHub-Zugang. 
- Ergebnisse werden via `PERSISTENCE_PENDING` an den Nutzer zur externen Speicherung (Push) übergeben.
- Keine Beschäftigungs- oder Doppelarbeit. Der bestätigte Scope (Mac/Anti-Gravity vs. Windows/Opus) wird streng respektiert.

## 3. Arbeitspakete P0–P6

| Paket | Ergebnis | Abhängigkeiten | Zuständiger Scope | Kleinste Umsetzung | Abnahmetest | Ressourcen-/Kostenrahmen | Offene Freigabe |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **P0** (Bestand/Zuständigkeit) | Geklärter Startpunkt | Keine | Mac / Windows | Abgleich lokaler State vs. Cloud | `runtime_truth.py` zeigt korrekte Zuordnung | Minimal (Lokal) | Keine |
| **P1** (Übergabe/Ledger) | Validierter Ledger | P0 | Mac | Wiederaufnahme prüfen | `courier_continue.py` startet sauber | Minimal | Keine |
| **P2** (Abschluss/Fortsetzung) | Reparierte Kausal-Fehler | P1 | Mac | Fix `approve_merge` Bug | `courier_continue.py` löst `TIMEOUT_HUNG_TASK` | Minimal | Keine (lokal DONE) |
| **P3** (Betriebsnachweis) | Stabiler End-to-End Loop | P2, Reboot-Test (Phase 3) | Mac + Windows | Echter Goal-Lauf mit >= 2 Workern | >=10 Abschlüsse ohne geleakte Prozesse | Normaler Token/Provider-Verbrauch | Erlaubnis für echte Pilot-API (falls nötig) |
| **P4** (Pilot-Ablauf) | Solo-Pilot abgeschlossen | P3 | Opus / Courier | Pilot ohne Sandbox-Fakes | Erfolgreiche Abrechnung (Sandbox) | Pilot-Budget | Veröffentlichung öffentlicher PRs |
| **P5** (Erweiterungen) | Communities/Chats | P4 | Courier | Priorisierte Pakete nacheinander bauen | Isolierte Feature-Abnahme | TBD nach P4 | Feature-Budgets |
| **P6** (Wirtschaftlichkeit) | Valide Kostenstruktur | P4, P5 | Opus | Kalkulation basierend auf P3/P4 | Einnahmen/Ausgaben-Report | Management-Ressourcen | Preisgestaltung |

## 4. Ledger-/Wiederaufnahmeplan
- **Runtime-Autorität:** Die absolute Wahrheit liegt im Systemzustand (`ACTUAL_SERVING_RUNTIME_SHA`), nicht im Chat-Speicher.
- **Ledger-Fortsetzung:** `agent_handoff_ledger.json` (lokal) dient als asynchrone Aufgabenliste. Wenn der SHA durch eine Reparatur (wie in P2) inkonsistent wird, pausiert Courier sicher (`FAIL CLOSED`), bis der Ledger auf den neuen `RUNTIME_IDENTITY` SHA aktualisiert wird.
- Wiederaufnahme erfolgt rein durch `python3 scripts/courier_continue.py --run`.

## 5. Erster tatsächlich ausführbarer Schritt
- **Sofort:** Durchführung des Terminal-Wall-System (Phase 3) Physischen Reboots durch den User, um die Stabilität der Dienste (`Mac Worker`, `Server`, `Terminal-Wall`) über Neustarts hinweg zu garantieren.
- **Nach Reboot:** Start von **P3** (Echter Betriebsnachweis) mit einem echten, nicht gemockten Goal unter Einbezug beider aktiver Worker (Mac + Windows).

## 6. Zeitrahmen und Annahmen
- **Kernnachweis (P3):** 1-2 Stunden Ausführungszeit nach erfolgreichem Reboot (Annahme: Provider-Ratelimits halten).
- **Kleiner Pilot (P4):** 1-3 Tage (Annahme: Externe APIs und Sandbox-Zahlungen funktionieren auf Anhieb).
- **Erweiterungen (P5, P6):** 1-2 Wochen inkrementeller Ausbau.
- **Unschätzbar:** Externe Freigaben durch den User (GitHub Pushes, Zahlungsfreigaben, Public Deployment).

## 7. Persistenznachweis und offene Entscheidungen
- Dieses Plan-Dokument wurde lokal unter `docs/plans/COURIER_EXECUTION_MASTERPLAN_2026-09-24.md` abgelegt.
- **Offene Entscheidung:** Werden Windows und Mac für P3 strikt auf denselben Branch/Commit-SHA synchronisiert, oder arbeiten sie auf getrennten SHAs asynchron?
- Ein `PERSISTENCE_PENDING`-Block für dieses Dokument wird der Chat-Antwort angehängt, damit der User den Push nach GitHub übernehmen kann.

## 8. Testlauf P3 (Isolierter Abbruchtest)
- **Status (OBSERVED):** Das isolierte Test-Goal `P3-ISOLATED-TEST` wurde gestartet. Der lokale Mac-Worker übernahm `WF-CHIEF-fa8de4-STEP-1-DISCOVER`.
- **Kausaler Fehler:** Der Task schlug nach exakt 5 Minuten fehl. Ursache ist das hartkodierte 300-Sekunden-Timeout im `subprocess.communicate(timeout=300)` in `scripts/mac_worker/daemon.py` (Zeilen 261 und 348), das für rechenintensive `agy`-Agents zu kurz ist. 
- **Blocker:** Da in der aktuellen Planungsrunde **keine Codeänderungen** erlaubt sind (`OPUS_MASTERPLAN_HANDOFF`), kann das Timeout jetzt noch nicht behoben werden.
