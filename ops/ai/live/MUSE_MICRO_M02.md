# M02 Q1_RESULT_BINDING_FALSIFIER — take-latest binding falsified (5 Subcases)
- DATE=2026-09-28, HEAD=bd539f18, FILE=scripts/intake_dispatcher.py:7-68 (voll gelesen)
- GATE=DURABLE/YES (nicht revalidiert); 0 Edits, 0 Runs; M01 via TURBO_01 wiederverwendet, nicht wiederholt

## Falsifikation (Source-Truth)
1. Take-latest statt Dispatch-Antwort: `sleep(3)` (:35) + `gh run list --limit 1` (:36) → neuester Run gewinnt; bei nebenläufigen Dispatches falsche Run-ID am Task (Cross-Contamination). FALSIFIED.
2. Sentinel statt ID: leere Ausgabe → `execution_ref="DISPATCHED"` (:58) — String-Sentinel im ID-Feld; Adapter-Run-Bindung (`result-{dispatch_id}`, run_id-Match) kann nie treffen. Irreführend, fail-closed per Accident.
3. Paralleles State-Universum: Task-Shape (`DISPATCHED_TO_EXTERNAL`, `last_transition`, `real_wall`, :52-63) passt weder zu TASK_STATES noch zum Contract — und schreibt ins SELBE `central_state.json` (COURIER_STATE_FILE-Default :40), das der Server liest. Erfundener State + Kontaminationspfad. CONFIRMED_SHAPE.
4. Crash-Fenster: plain `open/write` ohne tmp/fsync/Lock (:65-66); `except Exception → state={"tasks":{}}` (:49-50) verwirft bestehenden State bei korruptem Read (Datenverlust statt Quarantäne). CONFIRMED.
5. KeyError-Pfad: `intake[...]`-Direktzugriffe (:17-22) → Traceback-Exit ohne fail-closed Record. Minor.

## Paket
- MIN_FIX (nicht editiert): run-ID aus Dispatch-Antwort statt take-latest (oder fail-closed ohne Bindung); Server-Shape validieren (prepare_task/validate reuse); atomic write (tmp/fsync/replace + Lock); Sentinel entfernen.
- MIN_TEST: Doppel-Dispatch → beide Tasks tragen eigene Run-ID; korruptes State-File → Quarantäne statt Reset; fehlendes Intake-Feld → 400-artiger Record statt Traceback.
- OWNER=Intake/Revenue-Lane (Writer-owned; außerhalb 5-File-Candidate-Scope).
- BEFORE_RUN1=NO (Core-RUN_1 nutzt diesen Pfad nicht) → DEFER (Revenue-Lane), kein Codex-Blocker.

DO_NOT_REPEAT=sha256-muse-micro-m02-20260928
STATUS=M02_COMPLETE
