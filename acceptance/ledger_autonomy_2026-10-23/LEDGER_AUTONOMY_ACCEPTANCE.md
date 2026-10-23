# LEDGER_AUTONOMY_ACCEPTANCE · 23.10.2026 · Claude Opus (CLD-AUTO-001…025)

**HEAD geprüft:** `integration/v1` = `d5b19f1dffe5f5478476bf090c522b38bfc7164e` (unverändert seit 22.10.)
**Modus:** nur lesend + isolierte Proben. Kein Writer-Lease für Controller-/Ledger-/Kirby-Dateien (L2/L3), GrokBot Ultra aus dieser Sitzung nicht erreichbar → **keine Produktcode-Änderung, kein PR** (CLD-AUTO-023 BLOCKED).
**Status-Wörter:** PASS / FAIL / FINDING (Fehlverhalten reproduziert) / BLOCKED / UNKNOWN.

## Beweise
| Lauf | Befehl | Ergebnis |
|---|---|---|
| Abnahme-Proben | `PYTHONPATH=<checkout d5b19f1> python -m pytest -q acceptance/ledger_autonomy_2026-10-23/test_ledger_autonomy_acceptance.py` | **24 passed** (21 Verhaltensproben + 3 FINDING-Reproduktionen), Exit 0 |
| Golden-Harness | `python -m pytest -q tests/golden` (Linux) | 11 passed, 0 skipped (Pin `EXPECTED_TOTAL=11`, `EXPECTED_SKIPPED_DEFAULT=0`) |

Die Proben laufen gegen die echten Klassen `courier_core.controller.Controller` und `courier_runtime.continuity.Kirby`, mit steuerbarer Uhr und echten Neustarts (neue Instanz auf derselben `courier.db` / `kirby.json`).

## Zwei Schichten, zwei Wahrheiten
- **Task-Ledger (Controller + Journal):** QUEUE → CLAIM → RUN → VERIFY → FINAL ist streng: hash-verkettetes Journal, Zustandsmaschine im Append, Fencing über attempt/dispatch/worker, Verifier fail-closed.
- **Workkey-Schleife (Kirby):** NEXT/Wake/Checkpoint funktioniert, aber **ohne VERIFY** und **ohne Mehrprozess-Schutz**. Diese Schicht macht „autonom“ heute noch nicht nachweisbar.

## Workkeys
| ID | Thema | Status | Beleg |
|---|---|---|---|
| 001 | Claude-Branches inventarisieren | PASS | 8 Branches auf origin bestätigt: g1 `f999acb22`, f1 `0c538c45b`, mission-chip `a298fc384`, beams `a74b0647c`, flow `8f6c32e1f`, previews `6cf07e07a`, #776 `a127e3e97`, #777 `a4ffc33dc` |
| 002 | G1/F1/B1/B2 gegen Trunk | PASS (kein neuer Lauf nötig) | Trunk unverändert `d5b19f1`; Kombi-Lauf vom 22.10. gilt weiter (85/85 desktop, 193 py) |
| 003 | Ledger-Zustände & Invarianten | PASS | `state_machine.py`: QUEUED→CLAIMED→RUNNING→VERIFYING→ACCEPTED→COMPLETE; RETRY_PENDING/FAILED/BLOCKED/CANCELLED; manipuliertes Journal → `degraded_readonly`, Schreiben verweigert (Probe `cld003`) |
| 004 | FINAL nur mit Resolution + Evidenz | PASS | `cld004`: COMPLETE nur nach RESULT_ACCEPTED, `resolution=verified`, exakte Ereignisfolge. Hinweis: Mensch-Entscheid `EFFECT_CONFIRMED` führt zu COMPLETE mit `resolution=effect_confirmed` (gewollt; Konsumenten müssen `resolution` prüfen) |
| 005 | CHECKPOINT als Resume-Signal | PASS | `cld005`: Checkpoint und CLAIMED überleben Neustart, `reconcile_after_restart` → RESUMED |
| 006 | Queue-Recovery nach Abbruch | PASS | `cld006`: nach Neustart eine TTL Gnadenfrist, dann idempotent → QUEUED, nicht-idempotent → BLOCKED |
| 007 | Doppelte Claims | PASS (Controller) · **FINDING (Kirby)** | `cld007` Controller: zweiter Claim = None. **Kirby: zwei Prozesse auf derselben `kirby.json` beanspruchen denselben Workkey; letzter Save gewinnt, S1 glaubt weiter, Besitzer zu sein** |
| 008 | Lease-Fencing & Ablauf | PASS | `cld008`: nicht-idempotent + Lease verloren → BLOCKED, kein neuer Claim. Datei-Lease G1 separat (Branch `f999acb22`, wartet auf Codex) |
| 009 | Idempotente Übergänge | PASS | `cld009`: doppelter `idempotency_key` → 200 duplicate; doppeltes Ergebnis → ACK_DUPLICATE, nur ein RESULT_READY |
| 010 | Retry-Budget | PASS | `cld010`: max_attempts=3 → nach 3 Ablehnungen FAILED, kein weiterer Claim; Obergrenze `MAX_ATTEMPTS_LIMIT=100` |
| 011 | Dead-Letter | PASS (als Abbildung) | Kein eigenes DLQ; Endzustände FAILED (terminal, mit Grund) und BLOCKED (Mensch) übernehmen die Rolle. Eine DLQ-Ansicht wäre UI, nicht Ledger |
| 012 | Kein SUCCESS durch Heartbeat | PASS | `cld012`: 50 Heartbeats über 250 s → bleibt RUNNING |
| 013 | Kein FINAL ohne Verifier-Proof | PASS (Controller) · **FINDING (Kirby)** | Controller: falsche Bytes, fehlender Verifier, Worker-„failure“ → nie COMPLETE. **Kirby: `on_turn_end("DONE")` setzt Workkey DONE auf Zuruf, ohne Verifier und sogar mit leerem Checkpoint; Receipt-Zeile wird trotzdem geschrieben** |
| 014 | Unknown Cost vor jeder Aktion | **FINDING** | `cld014`: Controller nimmt Task mit `estimated_cost_eur: None, unknown_cost: true` an und gibt ihn zum Claim frei. Kostensperren existieren nur in Adaptern (provider_exec, Gemini, Google Builder, Windows-Daemon) → „vor jeder Aktion“ ist nicht zentral garantiert |
| 015 | Faire, reproduzierbare Auswahl | PASS | `cld015`: Controller FIFO nach `created_seq, task_id`; Kirby nach `(priority, key)` (`cld016`). Fairness über Workkeys gleicher Priorität = alphabetisch, nicht round-robin (Beobachtung) |
| 016 | Next-Workkey nach Checkpoint | PASS | `cld016`: DONE mit Checkpoint → nächster Workkey sofort geclaimt |
| 017 | Race Wakeup ↔ Claim | PASS (ein Prozess) · siehe 007 | `cld017`: doppelte/ manuelle Wakes werden zusammengefasst, ein Claim. Prozessübergreifend: FINDING 007 |
| 018 | Restart während VERIFYING | PASS | `cld018`: Stopp vor Verifier → Neustart verifiziert genau einmal (1× RESULT_ACCEPTED) |
| 019 | Restart nach FINAL | PASS | `cld019`: keine neue Ausführung, keine neuen Task-Ereignisse |
| 020 | Stale-Lease / Doppelwriter negativ | PASS | `cld020` ×3: falscher Worker, veralteter Dispatch, spätes Ergebnis → abgelehnt bzw. LATE_RESULT_DISCARDED; Kirby: alter Token → REJECTED_STALE_WRITER |
| 021 | Offline-Autonomie synthetisch | PASS | `cld021`: 5 Workkeys ohne Mensch nacheinander erledigt, 0 manuelle Continues. **Aber: ohne Verifikation (siehe 013)** |
| 022 | CI- und Windows-Skips | PASS (erfasst) | 55 Skip-Marker in 38 Testdateien; plattformbedingt v. a. `win32`/`nt`. Wichtig: `tests/controller/test_gate_g3_zero_human.py` überspringt den **kanonischen Windows-Core-A→B-Nachweis** absichtlich („A skip is not a pass“). Golden-Ratchet pinnt 11/0 |
| 023 | Eigene Controller-Fixes + PR | **BLOCKED** | kein Writer-Lease für `courier_core/controller.py` / `courier_runtime/continuity.py`; Fix-Vorschläge unten |
| 024 | Unabhängiger Review | BLOCKED (kein Kanal) | Review-Auftrag unten, an GrokBot/Google weiterzugeben |
| 025 | Dieses Dokument | PASS | Proben + Dokument auf Branch `claude/ledger-autonomy-acceptance-2026-10-23` |

## Befunde mit Fix-Vorschlag (nicht umgesetzt, Owner entscheidet)
| # | Schwere | Befund | Minimaler Fix | Owner |
|---|---|---|---|---|
| F-K1 | **P0 für „autonom“** | Kirby DONE ohne Verifier-Beweis | `on_turn_end("DONE")` nur mit Beweis-Referenz (z. B. `journal:<seq>:RESULT_ACCEPTED` des zugehörigen Controller-Tasks), sonst Zustand `REPORTED_DONE` statt DONE | L3 / Kirby-Owner |
| F-K2 | P1 | Kirby ohne Mehrprozess-Schutz | Exklusiver Dateilock (oder SQLite BEGIN IMMEDIATE wie LeaseStore) um load-modify-save; Token-Check beim Save | L3 / Kirby-Owner |
| F-C1 | P1 | Controller ohne zentrale Kostensperre | In `create_task`/`claim`: Tasks mit `unknown_cost` oder fehlender Kostenangabe für kostenpflichtige Adapter → BLOCKED/abgelehnt; Adapter-Sperren bleiben als zweite Linie | L2 |

## Weiterhin offen (nicht Teil dieser Queue)
- **P0 Mensch:** offene `owner_token` in `scripts/windows_muse_wall/runtime/slots/MUSE-*/state.json` im öffentlichen Repo → Rotation + Entfernung (Werte hier nicht wiedergegeben).
- **P0 Receipt (Codex-Bereich):** `artifact_receipt.py` VERIFIED ohne gelesene Bytes.
- Echter Provider-A→B: BLOCKED (GO, Worker-Host).

## Review-Auftrag (CLD-AUTO-024, zum Weitergeben)
> Prüft unabhängig `acceptance/ledger_autonomy_2026-10-23/` auf Branch `claude/ledger-autonomy-acceptance-2026-10-23` gegen `d5b19f1`. Fragen: (1) Messen die 21 PASS-Proben wirklich die genannte Eigenschaft oder nur einen Nebenpfad? (2) Sind F-K1, F-K2, F-C1 echt und richtig eingestuft? (3) Fehlt eine Probe, die einen PASS widerlegen würde? Keine Codeänderung, keine Provider, nur Befund.

## Restqueue
1. Owner-Entscheid + Fix F-K1 (Kirby-Verifikation) — blockiert die Aussage „autonom und verifiziert“.
2. F-K2 Kirby-Lock.
3. F-C1 zentrale Kostensperre im Controller.
4. Review (024) durch GrokBot/Google.
