# Muse Workbench — Status (neu aufgebaut 2026-09-19; alter Baum extern verschwunden)

## Aktuelle Wahrheit (beobachtet, kein Lauf)
- HEAD=ec4efd70 (Branch release-candidate-integration); Tree/Dirty UNKNOWN (kein Git-Werkzeug).
- Paket-Candidate=0456722c (Drift zu HEAD offen); PR39/42/43 UNKNOWN.
- Lauf-Zähler (DUPLICATE_EFFECTS, LOST_RESULTS, HUMAN_CONTINUE, DONE-Zahlen): ALLE UNBEWIESEN — kein Lauf je ausgeführt (Runner/Shell defekt).
- Belegte Code-Funde: Claim-IDs + Result-Gates (409/400/ACK_DUPLICATE); Intake-Doppel-Risiko (5 Stellen, Owner GOOGLE); Claim ohne Scope-Lock (Lücke); VERIFY-400 = Korrekt-Reject; UI-Hard-HEADs; STOP-Endstatus → PAUSED (falsch, New-Target); Fetcher-Tight-Loop (alte Daemons).
- New-Target (Desktop): Controller/CLI/Web gelesen; Deltas D1–D6 + DAUERLAUF-Lücken spezifiziert; kein Write (Policy), kein Run.
- Fixtures (13, Inhalte aus Sitzungsverlauf rekonstruierbar): Sätze, Generatoren, Deps, Gates, Provider, Governor, Barrieren, Scopes, Call-Counter, VP-02–VP-06, Update, Night.

## Blocker + Owner
1. Final-Candidate-Entscheid — CODEX. 2. Lauffähiger Runner/Host — UMGEBUNG. 3. Target-Schreibzugang — POLICY/Owner. 4. Google-Fixes G1–G6 — GOOGLE. 5. Workbench-Löschung Ursache — UNBEKANNT.

## CONTINUE (M22/M27 geschlossen, Rest blockiert)
- M22 Worker-State-Tabelle geliefert (Register→Heartbeat→Claim→Execute→Outbox vs. Server-Stati; FALSCH: Prozess-ohne-Heartbeat als AVAILABLE, Idle-Fetcher als WAITING; MEHRDEUTIG: CONNECTED/OPEN_AVAILABLE ohne Registry-Beleg).
- M27 10k-Render: Voll-Listen-Render (innerHTML/forEach, dashboard + studio) belegt → Pagination/Virtualisierung nötig (GOOGLE); Messung BLOCKED.
- S4 Bypass-Sweep: pyproject hat KEINE pytest-Config/Test-Extras (nur Flask/requests/psutil/keyring); Python=PROJECT/.venv/Scripts/python.exe (server.py-Kommentar, Datei absent); smart_test.py referenziert aber UNLESBAR (os error 2, 2x); Search-Backend degradiert (gleiche Query 4 Treffer → 0 Treffer, Reads ok). Blocker: TEST_RUNNER=exec-blockiert, LIVE=UNPROVEN, FOREIGN/PERMISSION=umgangen, DEPENDENCY=Codex G1-G6/D1-D6 offen, REAL_DEFECT=keiner bestätigt.
- S5 Cannon-Recovery (read-only): evidence.json gelesen (BLOCKED_CONCURRENT_SOURCE_WRITER, loaded_build_current=false, Server 8768 preserved); acceptance.py:8-9 WEITER cwd-abhängig (MODULE_ERROR_FIXED=NO); adapters.py:88 aktuell sauber (SyntaxError weg — Datei erneut fremd geändert, ohne Hash nicht beweisbar); controller.py:154 plausibel. Target-Root nicht schreibbar + keine Shell → keine Preflight/Load/Tests A–G möglich. CANNON_EXCLUSIVE_WRITER beansprucht, nicht durchsetzbar. FIRST_REAL_BLOCKER=Capability (Target-Write + Shell).
