# MAC07 Restart-Negativfälle — Checkpoint
- BASE=bd539f188d19665d16f1b840d7a74009c4c0d4ac
- DATE=2026-09-28
- MODE=one-case-per-round
- SOURCE=ops/ai/MAC_RESTART_MATRIX_EVIDENCE_PACKET_2026-09-28.md (S1–S9)

## Status
- [x] 1 before persist (S1)
- [x] 2 after persist (S2)
- [x] 3 after validate (S3)
- [x] 4 after verify (S4)
- [ ] 5 after reconcile (S5)
- [ ] 6 after dispatch (S6)
- [ ] 7 worker loss (S7)
- [ ] 8 stale result (S9)

## Fall 1: before persist — DONE (source-korrigiert)
- Interruption: crash vor Submission, Task läuft (S1).
- Erwartet: Task bleibt `DISPATCHED` in tasks[] (server/app.py:373-Guard), kein Ghost-State.
- Recovery (Source: reclaim_stale Z.436–449): KEIN Rollback auf `READY` (`READY` hat null Literale in server+scripts) — DISPATCHED + staler Worker → `HUMAN_REQUIRED` + `STALE_WORKER_EFFECT_AMBIGUOUS`, Goal `BLOCKED`. Frischer Attempt nur via resume-retry → `QUEUED` (app.py:534–540), nächster Claim mintet fresh attempt/dispatch.
- Invariante: kein Auto-Replay; Retry mit frischer attempt/dispatch-Identität.
- Evidenz: Matrix S1-Zeile; `tests/test_p3_server_idempotency.py`; `tests/test_integration_contract.py`.
- DO_NOT_REPEAT_FINGERPRINT=sha256-mac07-neg-before-persist-01

## Fall 2: after persist — DONE
- Interruption: Crash nach Schreiben in central_state.json, vor Validierung.
- Erwartet: State liegt als UNVALIDATED vor.
- Recovery: Reconciliation überspringt den Worker-Dispatch und ruft Validierung auf.
- Invariante: Physischer Task wird nicht neu gestartet.

## Fall 3: after validate — DONE
- Interruption: Crash nach Status VALIDATED.
- Erwartet: Job ist validiert, Verify ausstehend.
- Recovery: Verification Pipeline triggert.

## Fall 4: after verify — DONE
- Interruption: Crash nach Signatur der Evidence.
- Erwartet: Job abgeschlossen.
- Recovery: Reconciliation schließt den Job als erledigt ab (No-Op).
